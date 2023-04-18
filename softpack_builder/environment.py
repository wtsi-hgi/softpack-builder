"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import dataclasses
import importlib
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, cast

import httpx
import prefect
import yaml
from box import Box
from fastapi import APIRouter
from prefect import Task, flow, get_run_logger
from prefect.context import FlowRunContext
from prefect_dask.task_runners import DaskTaskRunner
from prefect_shell import ShellOperation
from pydantic import BaseModel
from typer import Typer

from .app import app
from .deployments import DeploymentRegistry


class Environment:
    """Encapsulation for a SoftPack environment."""

    settings = Box(app.settings.dict())

    @dataclass
    class Model:
        """SoftPack environment data model."""

        name: str
        owner: str
        description: str
        packages: list[str]

        def dict(self) -> dict:
            """Get model as a dictionary.

            Returns:
                dict: A dictionary representation of the model.
            """
            return dataclasses.asdict(self)

        @classmethod
        def from_yaml(cls, filename: Path) -> "Environment.Model":
            """Load Model from a YAML file.

            Args:
                filename: A YAML file with a Model spec

            Returns:
                Model: A Model object created from YAML file
            """
            with open(filename) as file:
                return Environment.Model(**yaml.safe_load(file))

    class Manifest:
        """Spack manifest abstraction class."""

        def __init__(self, filename: Path) -> None:
            """Constructor."""
            self.filename = filename

        def patch(self) -> None:
            """Patch a manifest.

            Returns:
                None
            """
            manifest = Box.from_yaml(filename=self.filename)
            manifest.spack |= Environment.settings.spack.manifest.config
            with open(self.filename, "w") as file:
                yaml.dump(manifest.to_dict(), file, sort_keys=False)

    @classmethod
    def from_model(cls, **kwargs: Any) -> "Environment":
        """Create an Environment model.

        Args:
            **kwargs: Keyword arguments for the Environment to instantiate.

        Returns:
            Environment: A newly created Environment instance.

        """
        return cls(cls.Model(**kwargs))

    def __init__(self, model: Model) -> None:
        """Constructor.

        Args:
            model: An Environment.Model
        """
        self.model = model
        context: FlowRunContext = cast(
            FlowRunContext, prefect.context.FlowRunContext.get()
        )
        self.flow_run_id = context.flow_run.id
        self.flow_logger = self.init_logger()
        self.task_logger: Optional[logging.Logger] = None
        self.spack = shutil.which("spack")

        self.name = f"{self.model.owner}_{self.model.name}"
        self.path = Path(tempfile.mkdtemp(prefix=f"spack_{self.name}_"))
        self.filenames = Box(
            {
                "manifest": self.path / self.settings.spack.manifest.name,
                "singularity": {
                    "spec": self.path / self.settings.singularity.spec,
                    "image": self.path / self.settings.singularity.image,
                },
            }
        )

    @property
    def logger(self) -> logging.Logger:
        """Get context-specific logger.

        Returns:
            Logger: A python Logger object.
        """
        if prefect.context.TaskRunContext.get():
            if not self.task_logger:
                self.task_logger = self.init_logger()
            return self.task_logger
        elif prefect.context.FlowRunContext.get():
            return self.flow_logger
        else:
            raise TypeError(
                "Called from unexpected context."
                "Logging is only available in flow and task contexts."
            )

    def init_logger(self) -> logging.Logger:
        """Initialize a logger.

        Returns:
            Logger: A python Logger object.
        """
        path = self.settings.logging.path.parent
        path.mkdir(parents=True, exist_ok=True)
        filename = path / self.settings.logging.filename.template.format(
            id=self.flow_run_id
        )
        handler = logging.FileHandler(filename=str(filename))
        args = self.settings.logging.formatters.prefect.to_dict()
        formatter_class = args.pop("class")
        module, _, cls = formatter_class.rpartition('.')
        formatter = getattr(importlib.import_module(module), cls)(**args)
        handler.setFormatter(formatter)
        logger = get_run_logger()
        if isinstance(logger, logging.LoggerAdapter):
            logger = logger.logger
        logger = cast(logging.Logger, logger)
        logger.addHandler(handler)
        return logger

    @staticmethod
    def task(fn: Callable, *args: Any, **kwargs: Any) -> Task:
        """Prefect task partial.

        Args:
            fn: Task function
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function wrapped in a Prefect task.
        """
        return prefect.task(  # type: ignore
            fn, task_run_name=f"{fn.__name__} [{{env.name}}]", *args, **kwargs
        )

    def shell_command(self, command: str, **kwargs: str) -> None:
        """Execute shell command with Prefect.

        Args:
            command: Shell command to execute
            kwargs: Keyword arguments

        Returns:
            None.
        """
        self.logger.info(f"running shell command: {command}")
        with ShellOperation(commands=[command], **kwargs) as shell_commands:
            process = shell_commands.trigger()
            process.wait_for_completion()

    def spack_command(self, command: str, **kwargs: str) -> None:
        """Run a Spack command.

        Args:
            command: Spack command to run
            kwargs: Keyword arguments

        Returns:
            None.
        """
        self.shell_command(f"{self.spack} {command}", **kwargs)

    def spack_env_command(self, command: str) -> None:
        """Run a Spack environment command.

        Args:
            command: Spack environment command to run

        Returns:
            None,
        """
        self.spack_command(f"-e {self.path} {command}")

    def singularity_command(self, command: str, **kwargs: str) -> None:
        """Run a singularity command.

        Args:
            command: Singularity command to run
            kwargs: Keyword arguments

        Returns:
            None.
        """
        self.shell_command(
            f"{self.settings.singularity.command} {command}", **kwargs
        )

    def stage(self) -> "Environment":
        """Stage environment in a new directory.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(
            f"staging environment: name={self.name}, path={self.path}"
        )
        self.spack_command(f"env create -d {self.path}")
        return self

    def create_manifest(self) -> "Environment":
        """Create Spack manifest.

        Returns:
             Environment: A reference to self.
        """
        self.logger.info(f"creating manifest: name={self.name}")
        packages = " ".join(self.model.packages)
        self.logger.info(f"adding packages: {packages}")
        self.spack_env_command(f"add {packages}")
        self.logger.info(f"patching manifest: name={self.model.name}")
        manifest = Environment.Manifest(self.filenames.manifest)
        manifest.patch()
        return self

    def concretize(self) -> "Environment":
        """Concretize the environment.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"concretizing environment: name={self.name}")
        self.spack_env_command("concretize")
        return self

    def containerize(self) -> "Environment":
        """Containerize the environment.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"containerizing environment: name={self.name}")
        self.spack_command(
            f"containerize > {self.filenames.singularity.spec}",
            working_dir=str(self.path),
        )
        return self

    def build(self) -> "Environment":
        """Build a Spack environment.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"building environment: name={self.name}")
        self.singularity_command(
            " ".join(
                [
                    "build",
                    "--force",
                    "--fakeroot",
                    str(self.filenames.singularity.image),
                    str(self.filenames.singularity.spec),
                ]
            ),
            working_dir=str(self.path),
        )
        return self


class EnvironmentAPI:
    """Service module."""

    name = "environment"
    router = APIRouter(prefix=f"/{name}")
    commands = Typer(help="Commands for managing environments.")
    deployments = DeploymentRegistry()

    class Status(BaseModel):
        """Status class for returning the results from API."""

        class State(BaseModel):
            """State returned from the API."""

            type: Any

        id: str
        name: str
        created: Any
        state: State

    @classmethod
    def url(cls, path: str) -> str:
        """Get absolute URL path.

        Args:
            path: Relative URL path under module prefix

        Returns:
            str: URL path
        """
        return str(Path(cls.router.prefix) / path)

    @staticmethod
    @commands.command("create")
    def create_environment_command(filename: Path) -> None:
        """Create an environment.

        Args:
            filename: A YAML file of environment spec.

        Returns:
            None.
        """
        model = Environment.Model.from_yaml(filename)
        response = httpx.post(
            app.url(EnvironmentAPI.url("create")),
            json=model.dict(),
        )
        status = EnvironmentAPI.Status(**response.json())
        app.echo(yaml.dump(status.dict(), sort_keys=False))

    @staticmethod
    @router.post("/create")
    def create_environment_route(model: dict) -> dict:
        """HTTP POST handler for /create route.

        Args:
            model: An Environment.Model object.

        Returns:
            dict: Status from deployment run.
        """
        return EnvironmentAPI.deployments.run(
            create_environment, parameters={"model": model}
        )


@Environment.task
def stage_environment(env: Environment) -> Environment:
    """Stage an environment.

    Args:
        env: Environment to stage

    Returns:
        Environment: The environment.
    """
    return env.stage()


@Environment.task
def create_manifest(env: Environment) -> Environment:
    """Create an environment manifest.

    Args:
        env: Environment for creating the manifest.

    Returns:
        Environment: The environment.
    """
    return env.create_manifest()


@Environment.task
def concretize_environment(env: Environment) -> Environment:
    """Concretize_an environment.

    Args:
        env: Environment to concretize.

    Returns:
        Environment: The environment.
    """
    return env.concretize()


@Environment.task
def containerize_environment(env: Environment) -> Environment:
    """Containerize the environment.

    Args:
        env: Environment to containerize.

    Returns:
        Environment: The environment.
    """
    return env.containerize()


@Environment.task
def build_environment(env: Environment) -> Environment:
    """Build the environment.

    Args:
        env: Environment to build.

    Returns:
        Environment: The newly built environment.
    """
    return env.build()


@flow(name="Create environment", task_runner=DaskTaskRunner())
def create_environment(model: dict) -> dict:
    """Create an environment.

    Args:
        parameters: Model parameters.

    Returns:
        dict: Flow run context
    """
    env = Environment.from_model(**model)
    logger = env.logger
    tasks = [
        stage_environment,
        create_manifest,
        # concretize_environment,
        containerize_environment,
        build_environment,
    ]
    for task in tasks:
        env = cast(Environment, task.submit(env))

    logger.info("create_environment flow completed")
    context = cast(FlowRunContext, prefect.context.get_run_context())
    return context.flow_run.dict()


EnvironmentAPI.deployments.register([create_environment])
