"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import dataclasses
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml
from fastapi import APIRouter
from prefect import flow, get_run_logger, task
from prefect_dask.task_runners import DaskTaskRunner
from prefect_shell import ShellOperation
from typer import Typer

from .app import app
from .deployments import Deployments


def delay_task(timeout: int = 30) -> None:
    """Test delay loop."""
    logger = get_run_logger()
    for i in range(timeout):
        time.sleep(1)
        logger.info(f"delay_task: {i}")


class Environment:
    """Service module."""

    name = "environment"
    router = APIRouter(prefix=f"/{name}")
    commands = Typer(help="Commands for managing environments.")
    deployments: Deployments

    @dataclass
    class Model:
        """Data model for a SoftPack environment."""

        name: str
        description: str
        packages: list[str]

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

        def asdict(self) -> dict:
            """Return the model as a dictionary.

            Returns:
                dict: Model as a dictionary

            """
            return dataclasses.asdict(self)

    def __init__(self, model: Model):
        """Constructor.

        Args:
            model: An Environment.Model
        """
        self.model = model
        self.logger = get_run_logger()

    def stage(self) -> None:
        """Stage the environment in a temporary directory.

        Returns:
            None
        """
        self.path = Path(tempfile.mkdtemp(prefix=f"spack_{self.model.name}_"))
        self.logger.info(
            f"staging environment: name={self.model.name}, path={self.path}"
        )
        self.spack_command(f"env create -d {self.path}")

    def create_manifest(self) -> None:
        """Create Spack manifest.

        Returns:
            None.
        """
        self.logger.info(f"creating manifest: name={self.model.name}")
        packages = " ".join(self.model.packages)
        self.logger.info(f"adding packages: {packages}")
        self.spack_env_command(f"add {packages}")

    def build(self) -> None:
        """Build a Spack environment.

        Returns:
            None.
        """
        self.logger.info(f"building environment: name={self.model.name}")
        self.spack_env_command("install --fail-fast")

    def shell_commands(self, *args: str) -> None:
        """Execute shell commands with Prefect.

        Args:
            *args: List of commands to execute

        Returns:
            None.
        """
        commands = list(args)
        self.logger.info(f"running shell commands: {commands}")
        with ShellOperation(commands=commands) as shell_commands:
            process = shell_commands.trigger()
            process.wait_for_completion()

    def spack_command(self, command: str) -> None:
        """Run a Spack command.

        Args:
            command: Spack command to run

        Returns:
            None.
        """
        self.shell_commands(f"{app.settings.spack.command} {command}")

    def spack_env_command(self, command: str) -> None:
        """Run a Spack environment command.

        Args:
            command: Spack environment command to run

        Returns:
            None,
        """
        self.spack_command(f"-e {self.path} {command}")

    @classmethod
    def register_deployments(cls, *flows: Any) -> None:
        """Register flow deployments with the API.

        Args:
            *flows: List of flows

        Returns:
            None
        """
        cls.deployments = Deployments.register(*flows)

    @staticmethod
    def url(path: str) -> str:
        """Get absolute URL path.

        Args:
            path: Relative URL path under module prefix

        Returns:
            str: URL path
        """
        return str(Path(Environment.router.prefix) / path)

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
            app.url(Environment.url("create")),
            json=model.asdict(),
        )
        result = response.json()
        result = {
            "name": result["name"],
            "created": result["created"],
            "state": {"type": result["state"]["type"]},
        }
        app.echo(yaml.dump(result, sort_keys=False))

    @staticmethod
    @router.post("/create")
    def create_environment_route(model: Model) -> dict:
        """HTTP POST handler for /create route.

        Args:
            model: An Environment.Model object.

        Returns:
            dict: Status from deployment run.
        """
        return Environment.deployments.run(
            create_environment, parameters={"model": model.asdict()}
        )

        # return Environment.deployments.run(
        #     test_flow, parameters={"name": model.name}
        # )


@task()
def stage_environment(env: Environment) -> None:
    """Prefect task for staging an environment.

    Args:
        env: An Environment object

    Returns:
        None.
    """
    delay_task()
    env.stage()


@task()
def create_manifest(env: Environment) -> None:
    """Prefect task for creating environment manifest.

    Args:
        env: An Environment object

    Returns:
        None.
    """
    delay_task()
    env.create_manifest()


@task()
def build_image(env: Environment) -> None:
    """Prefect task for building an environment.

    Args:
        env: An Environment object

    Returns:
        None.
    """
    delay_task()
    env.build()


@flow(name="Create environment", task_runner=DaskTaskRunner())
def create_environment(model: Environment.Model) -> None:
    """Create an environment.

    Args:
        model: An Environment.Model instance.

    Returns:
        None.
    """
    env = Environment(model)
    stage_environment(env)
    create_manifest(env)
    build_image(env)


Environment.register_deployments(create_environment)
