"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import dataclasses
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast
from uuid import UUID

import httpx
import prefect
import typer
import yaml
from box import Box
from fastapi import APIRouter, Request
from prefect import Task, flow
from prefect.context import FlowRunContext
from prefect_dask.task_runners import DaskTaskRunner
from pydantic import BaseModel
from typer import Typer
from typing_extensions import Annotated

from .api import API
from .app import app
from .artifacts import Artifacts
from .deployments import DeploymentRegistry
from .logger import LogMixin
from .modulefile import ModuleFile
from .spack import Spack


class Environment(LogMixin):
    """Encapsulation for a SoftPack environment."""

    settings = Box(app.settings.dict())

    @dataclass
    class Model:
        """SoftPack environment data model."""

        description: str
        packages: list[str]

        def dict(self) -> dict[str, Any]:
            """Get model as a dictionary.

            Returns:
                dict: A dictionary representation of the model.
            """
            return dataclasses.asdict(self)

        @classmethod
        def from_yaml(cls, filename: Path) -> "Environment.Model":
            """Load Model from a YAML file.

            Args:
                filename: A YAML file with a Model spec.

            Returns:
                Model: A Model object created from YAML file.
            """
            with open(filename) as file:
                return Environment.Model(**yaml.safe_load(file))

    @classmethod
    def create(cls, name: str, model: dict[str, Any]) -> "Environment":
        """Create Environment from a model.

        Args:
            name: Environment name.
            model: Model parameters.

        Returns:
            Environment: A newly created Environment instance.

        """
        return cls(name, cls.Model(**model))

    def __init__(self, name: str, model: Model) -> None:
        """Constructor.

        Args:
            name: Environment name.
            model: Environment parameters.
        """
        self.name = name
        self.model = Box(model.dict())
        context: FlowRunContext = cast(
            FlowRunContext, prefect.context.FlowRunContext.get()
        )
        self.id = context.flow_run.id if context else None
        self.path = self.settings.environments.path / f"{self.id}"
        self.path.mkdir(parents=True, exist_ok=True)
        self.spack = Spack(self.name, self.path)
        self.artifacts = Artifacts(self.name)
        module, _, cls = self.settings.container.module.rpartition('.')
        module = ".".join([str(Path(__file__).parent.name), module])
        container = getattr(importlib.import_module(module), cls)()
        self.builder = container.Builder(
            name=self.name,
            path=self.path,
            model=self.model,
            artifacts=self.artifacts,
        )
        registry = self.artifacts.default_registry(self.name)
        self.image_version = registry.next_version()
        self.modulefile = ModuleFile(
            id=self.id,
            name=self.name,
            path=self.path,
            model=self.model,
            artifacts=self.artifacts,
            version=self.image_version,
        )
        super().__init__()

    @staticmethod
    def task(fn: Callable, **kwargs: Any) -> Task:
        """Prefect task partial.

        Args:
            fn: Task function.
            **kwargs: Keyword arguments.

        Returns:
            Task: Function wrapped in a Prefect task.
        """
        return prefect.task(  # type: ignore
            fn, task_run_name=f"{fn.__name__} [{{env.name}}]", **kwargs
        )

    def stage(self) -> "Environment":
        """Stage environment in a new directory.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(
            f"staging environment: name={self.name}, path={self.path}"
        )
        self.spack.env_create()()
        return self

    def create_manifest(self) -> "Environment":
        """Create Spack manifest.

        Returns:
             Environment: A reference to self.
        """
        self.logger.info(f"creating manifest: name={self.name}")
        self.spack.env_add(self.model.packages)()
        self.artifacts.add(
            self.spack.manifest.filename,
            Path(self.name, self.spack.manifest.filename.name),
        )
        return self

    def concretize(self) -> "Environment":
        """Concretize an environment.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"concretizing environment: name={self.name}")
        self.spack.env_concretize()()
        return self

    def build_image(self) -> "Environment":
        """Build a Spack environment.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"building image: name={self.name}")
        self.builder.build_image()
        return self

    def push_image(self) -> "Environment":
        """Push the image to container registries.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"pushing image: name={self.name}")
        for registry in self.artifacts.registries():
            self.builder.push_image(registry, self.image_version)
        return self

    def create_modulefile(self) -> "Environment":
        """Create module file.

        Returns:
            Environment: A reference to self.
        """
        self.logger.info(f"creating modulefile: name={self.name}")
        self.modulefile.create()
        return self


class EnvironmentAPI(API):
    """Environment API module."""

    prefix = "/environments"
    router = APIRouter(prefix=prefix)
    commands = Typer(help="Commands for managing environments.")
    deployments = DeploymentRegistry()

    class Status(BaseModel):
        """Status class for returning the results from API."""

        class State(BaseModel):
            """State returned from the API."""

            type: Any

        id: UUID
        name: str
        created: Any
        state: State

    @staticmethod
    @commands.command("build", help="Build an environment.")
    def build_environment_command(
        name: Annotated[Path, typer.Option()], filename: Path
    ) -> None:
        """Build an environment.

        Args:
            name: Environment name.
            filename: A YAML file of environment spec.

        Returns:
            None.
        """
        model = Environment.Model.from_yaml(filename)
        response = httpx.post(
            EnvironmentAPI.url("build"),
            json={"name": str(name), "model": model.dict()},
        )
        app.echo(yaml.dump(response.json(), sort_keys=False))

    @staticmethod
    @router.post("/build")
    def build_environment_route(
        params: dict[str, Any], reqyuest: Request
    ) -> dict[str, Any]:
        """HTTP POST handler for /build route.

        Args:
            params: Environment parameters.

        Returns:
            dict: Status from deployment run.
        """
        response = EnvironmentAPI.deployments.run(
            build_environment, parameters=params
        )
        return EnvironmentAPI.Status(**response.dict()).dict()


@Environment.task
def stage_environment(env: Environment) -> Environment:
    """Stage an environment.

    Args:
        env: Environment to stage.

    Returns:
        Environment: An environment being staged.
    """
    return env.stage()


@Environment.task
def create_manifest(env: Environment) -> Environment:
    """Create an environment manifest.

    Args:
        env: Environment for creating the manifest.

    Returns:
        Environment: The environment being built.
    """
    return env.create_manifest()


@Environment.task
def concretize_environment(env: Environment) -> Environment:
    """Concretize an environment.

    Args:
        env: Environment to concretize.

    Returns:
        Environment: An environment being concretized.
    """
    return env.concretize()


@Environment.task
def build_image(env: Environment) -> Environment:
    """Build the environment.

    Args:
        env: Environment to build.

    Returns:
        Environment: The environment being built.
    """
    return env.build_image()


@Environment.task
def push_image(env: Environment) -> Environment:
    """Push the image to container registries.

    Args:
        env: Environment to push.

    Returns:
        Environment: The environment being built.
    """
    return env.push_image()


@Environment.task
def create_modulefile(env: Environment) -> None:
    """Create module file for the environment.

    Args:
        env: Environment for creating the modulefile

    Returns:
        None.
    """
    env.create_modulefile()


@flow(
    name="build_environment",
    task_runner=DaskTaskRunner(),
    flow_run_name="{name}",
)
def build_environment(name: str, model: dict[str, Any]) -> dict[str, Any]:
    """Create an environment.

    Args:
        name: Environment name.
        model: Model parameters.

    Returns:
        dict: Flow run context.
    """
    env = Environment.create(name, model)
    env = cast(Environment, stage_environment.submit(env))
    env = cast(Environment, create_manifest.submit(env))
    # env = cast(Environment, concretize_environment.submit(env))

    env = cast(Environment, build_image.submit(env))
    env = cast(Environment, push_image.submit(env))

    create_modulefile.submit(env)

    context = cast(FlowRunContext, prefect.context.get_run_context())
    return context.flow_run


EnvironmentAPI.deployments.register([build_environment])
