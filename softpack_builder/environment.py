"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
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
from .utils import async_exec


class Environment:
    @dataclass
    class Model:
        name: str
        description: str
        packages: list[str]

    def __init__(self, model: Model):
        self.model = model
        self.logger = get_run_logger()
        self.path = Path(tempfile.mkdtemp(prefix=f"spack_{self.model.name}_"))
        self.logger.info(
            f"creating environment: name={self.model.name}, path={self.path}"
        )
        self.spack_command(f"env create -d {self.path}")

    @staticmethod
    def from_yaml(filename: Path):
        with open(filename) as file:
            return yaml.safe_load(file)

    def shell_commands(self, *args):
        commands = list(args)
        self.logger.info(f"running shell commands: {commands}")
        with ShellOperation(commands=commands) as shell_commands:
            process = shell_commands.trigger()
            process.wait_for_completion()

    def spack_command(self, command: str):
        self.shell_commands(f"spack {command}")

    def spack_env_command(self, command: str):
        self.spack_command(f"-e {self.path} {command}")

    def create_manifest(self):
        self.logger.info(
            f"creating spack.yaml manifest, name={self.model.name}"
        )
        packages = " ".join(self.model.packages)
        self.logger.info(f"adding packages: {packages}")
        self.spack_env_command(f"add {packages}")

    def build(self):
        self.logger.info(f"building environment: name={self.model.name}")
        self.spack_env_command("install --fail-fast")
        return "OK"

    def epilogue(self):
        response = requests.get("https://catfact.ninja/fact")
        parsed_response = Box(response.json())
        self.logger.info(f"random cat fact: {parsed_response.fact}")

    def print_build_status(self, status):
        self.logger.info(f"build status: {status}")
        self.epilogue()


@task
def environment_initialize(model):
    return Environment(model)


@task
def environment_build(env):
    env.build()


@task
def environment_create_manifest(env):
    env.create_manifest()


@task
def epilogue(env):
    env.epilogue()


@flow(task_runner=DaskTaskRunner())
def environment_create_flow(model):
    env = environment_initialize(model)
    environment_create_manifest(env)
    environment_build(env)
    epilogue(env)


router = APIRouter(prefix="/environments")


@router.post("/create")
def environment_create(
    model: Environment.Model, background_tasks: BackgroundTasks
):
    background_tasks.add_task(async_exec, environment_create_flow, model)
    return {"status": "OK", "message": "environment creation in progress"}


commands = typer.Typer()


@commands.command()
def create(filename: Path):
    """Create an environment.

    Args:
        filename:

    Returns:

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
