"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import dataclasses
import enum
import importlib
import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Union, cast

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


class ImageSpec(ABC):
    """Abstract class for defining container image specs."""

    settings = Box(app.settings.dict())

    class Stage(enum.Enum):
        """Image spec type."""

        build = enum.auto()
        final = enum.auto()

    def __init__(self, path: Path, packages: list[str], stage: Stage):
        """Constructor.

        Args:
            path: Environment path
            packages: List of packages in the environment for caching
            stage: Build stage
        """
        self.image = str(path / self.settings.singularity.image)
        self.filename = str(
            path / self.settings.singularity.spec.format(stage=stage.name)
        )
        self.packages = packages
        self.stage = stage

    def patch(self) -> None:
        """Patch the image spec.

        Returns:
            None
        """

    @abstractmethod
    def args(self) -> list[str]:
        """Additional arguments passed to image builder.

        Returns:
            list[str]: List of arguments
        """


class BuildSpec(ImageSpec):
    """Build spec."""

    def __init__(self, **kwargs: Any) -> None:
        """Constructor.

        Args:
            **kwargs: Keyword arguments
        """
        super().__init__(stage=self.Stage.build, **kwargs)

    def patch(self) -> None:
        """Patch the image spec.

        Returns:
            None
        """
        with open(self.filename, "a") as file:
            commands = map(
                lambda package: f"  spack -e . buildcache create"
                f" --directory {self.settings.spack.cache}"
                f" --allow-root --force {package}\n",
                self.packages,
            )
            file.writelines(commands)

    def args(self) -> list[str]:
        """Additional arguments passed to image builder.

        Returns:
            list[str]: List of arguments
        """
        return [
            f"--bind {self.settings.singularity.build.bind} --sandbox build/",
            self.filename,
        ]


class FinalSpec(ImageSpec):
    """Final spec."""

    def __init__(self, **kwargs: Any) -> None:
        """Constructor.

        Args:
            **kwargs: Keyword arguments
        """
        super().__init__(stage=self.Stage.final, **kwargs)

    def args(self) -> list[str]:
        """Additional arguments passed to image builder.

        Returns:
            list[str]: List of arguments
        """
        return [self.image, self.filename]


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

        def patch(self, spec: ImageSpec, settings: Box) -> None:
            """Patch a manifest.

            Args:
                spec: Image build spec.
                settings: Settings from the environment.

            Returns:
                None
            """
            manifest = Box.from_yaml(filename=self.filename)
            manifest.spack |= settings.spack.manifest.spack
            template = manifest.spack.container.template.format(
                stage=spec.stage.name
            )
            manifest.spack.container.template = template
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
        self.path = self.settings.spack.environments / f"{self.flow_run_id}"
        self.path.mkdir(parents=True)

        self.flow_logger: logging.LoggerAdapter = self.init_logger()
        self.task_logger: Union[logging.LoggerAdapter, None] = None
        self.spack = shutil.which("spack")
        self.name = f"{self.model.owner}_{self.model.name}"

    @property
    def logger(self) -> logging.LoggerAdapter:
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

    def init_logger(self) -> logging.LoggerAdapter:
        """Initialize a logger.

        Returns:
            Logger: A python Logger object.
        """
        filename = self.path / self.settings.logging.filename
        handler = logging.FileHandler(filename=str(filename))
        args = self.settings.logging.formatters.prefect.to_dict()
        formatter_class = args.pop("class")
        module, _, cls = formatter_class.rpartition('.')
        formatter = getattr(importlib.import_module(module), cls)(**args)
        handler.setFormatter(formatter)
        logger = get_run_logger()
        if isinstance(logger, logging.LoggerAdapter):
            logger.logger.addHandler(handler)
        return cast(logging.LoggerAdapter, logger)

    @staticmethod
    def task(fn: Callable, **kwargs: Any) -> Task:
        """Prefect task partial.

        Args:
            fn: Task function
            **kwargs: Keyword arguments

        Returns:
            Function wrapped in a Prefect task.
        """
        return prefect.task(  # type: ignore
            fn, task_run_name=f"{fn.__name__} [{{env.name}}]", **kwargs
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
        self.shell_command(
            f"{self.spack} {command}", working_dir=str(self.path), **kwargs
        )

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
            f"{self.settings.singularity.command} {command}",
            working_dir=str(self.path),
            **kwargs,
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
        return self

    def patch_manifest(self, spec: ImageSpec) -> None:
        """Patch environment manifest for a build stage.

        Args:
            stage: Container build stage.

        Returns:
            None
        """
        self.logger.info(
            f"patching manifest: name={self.model.name}, stage={spec.stage}"
        )
        manifest = Environment.Manifest(
            self.path / self.settings.spack.manifest.name
        )
        manifest.patch(spec, self.settings)

    def containerize(self, spec: ImageSpec) -> None:
        """Containerize the environment.

        Args:
            spec: Container image spec.

        Returns:
            None
        """
        self.patch_manifest(spec)
        self.logger.info(f"containerizing environment: name={self.name}")
        self.spack_command(f"containerize > {spec.filename}")
        spec.patch()

    def build(self, spec_type: type) -> "Environment":
        """Build a Spack environment.

        Args:
            spec: Container image spec.

        Returns:
            Environment: A reference to self.
        """
        spec = spec_type(path=self.path, packages=self.model.packages)
        self.containerize(spec)
        self.logger.info(f"building environment: name={self.name}")
        self.singularity_command(
            " ".join(["build", "--force", "--fakeroot"] + spec.args())
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
    def create_environment_route(model: Box) -> dict:
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
def build_environment(env: Environment, spec_type: type) -> Environment:
    """Build the environment.

    Args:
        env: Environment to build.
        spec: Container image spec.

    Returns:
        Environment: The newly built environment.
    """
    return env.build(spec_type)


@flow(name="create_environment", task_runner=DaskTaskRunner())
def create_environment(model: Box) -> dict:
    """Create an environment.

    Args:
        model: Model parameters.

    Returns:
        dict: Flow run context
    """
    env = Environment.from_model(**model)
    logger = env.logger
    env = cast(Environment, stage_environment.submit(env))
    env = cast(Environment, create_manifest.submit(env))
    env = cast(Environment, build_environment.submit(env, BuildSpec))
    build_environment.submit(env, FinalSpec)

    logger.info("create_environment flow completed")
    context = cast(FlowRunContext, prefect.context.get_run_context())
    return context.flow_run.dict()


EnvironmentAPI.deployments.register([create_environment])
