"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlunsplit

import requests
import typer
import yaml
from box import Box
from fastapi import APIRouter, BackgroundTasks
from prefect import flow, get_run_logger, task
from prefect_dask.task_runners import DaskTaskRunner
from prefect_shell import ShellOperation

from .config import settings


class Environment:
    """Encapsulation for a SoftPack environment."""

    @dataclass
    class Model:
        """Data model for a SoftPack environment."""

        name: str
        description: str
        packages: list[str]

    def __init__(self, model: Model):
        """Constructor.

        Args:
            model: An Environment.Model
        """
        self.model = model
        self.logger = get_run_logger()
        self.path = Path(tempfile.mkdtemp(prefix=f"spack_{self.model.name}_"))
        self.logger.info(
            f"creating environment: name={self.model.name}, path={self.path}"
        )
        self.spack_command(f"env create -d {self.path}")

    @staticmethod
    def from_yaml(path: Path) -> dict[str, Any]:
        """Load a YAML file.

        Args:
            path: YAML filename

        Returns:
            Dictionary loaded from the YAML file
        """
        with open(path) as file:
            return yaml.safe_load(file)

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
        self.shell_commands(f"{settings.spack.command} {command}")

    def spack_env_command(self, command: str) -> None:
        """Run a Spack environment command.

        Args:
            command: Spack environment command to run

        Returns:
            None,
        """
        self.spack_command(f"-e {self.path} {command}")

    def create_manifest(self) -> None:
        """Create Spack manifest.

        Returns:
            None.
        """
        self.logger.info(
            f"creating spack.yaml manifest, name={self.model.name}"
        )
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

    def epilogue(self) -> None:
        """Run an epilogue task.

        Returns:
            None.
        """
        response = requests.get("https://catfact.ninja/fact")
        parsed_response = Box(response.json())
        self.logger.info(f"random cat fact: {parsed_response.fact}")

    def print_status(self, status: Any) -> None:
        """Print status to log.

        Args:
            status: Status code to log

        Returns:
            None.
        """
        self.logger.info(f"build status: {status}")
        self.epilogue()


@task
def environment_instantiate(model: Environment.Model) -> Environment:
    """Prefect task for instantiating an Environment object.

    Args:
        model: An Environment.Model.

    Returns:
        Environment: A newly instantiated Environment object.

    """
    return Environment(model)


@task
def environment_build(env: Environment) -> None:
    """Prefect task for building an environment.

    Args:
        env: An Environment object.

    Returns:
        None.
    """
    env.build()


@task
def environment_create_manifest(env: Environment) -> None:
    """Prefect task for creating an environment manifest.

    Args:
        env: An Environment object.

    Returns:
        None.
    """
    env.create_manifest()


@task
def epilogue(env: Environment) -> None:
    """Run epilogue task.

    Args:
        env: An Environment object.

    Returns:
        None.
    """
    env.epilogue()


@flow(task_runner=DaskTaskRunner())
def environment_create_flow(model: Environment.Model) -> None:
    """Prefect flow for creating an environment.

    Args:
        model: An Environment.Model object.

    Returns:
        None.
    """
    env: Environment = environment_instantiate(model)  # type: ignore
    environment_create_manifest(env)
    environment_build(env)
    epilogue(env)


router = APIRouter(prefix="/environments")


@router.post("/create")
def environment_create(
    model: Environment.Model, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """HTTP POST handler for /create route.

    Args:
        model: An Environment.Model object.
        background_tasks: FastAPI background task scheduler.

    Returns:
        None.
    """

    async def flow_wrapper(model: Environment.Model) -> None:
        return environment_create_flow(model)  # type: ignore

    background_tasks.add_task(flow_wrapper, model)
    return {"status": "OK", "message": "environment creation in progress"}


commands = typer.Typer(help="Commands for managing SoftPack environments.")


@commands.command()
def create(filename: Path) -> None:
    """Create an environment.

    Args:
        filename: A YAML file of environment spec.

    Returns:
        None.
    """
    url = urlunsplit(
        (
            "http",
            f"{settings.server.host}:{settings.server.port}",
            "environments/create",
            "",
            "",
        )
    )
    response = requests.post(url, json=Environment.from_yaml(filename))
    typer.echo(response.text)
