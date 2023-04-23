"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""


import tempfile
import time
from multiprocessing import Process
from pathlib import Path
from threading import Thread

import httpx
import pytest
import requests
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from softpack_builder.app import Application
from softpack_builder.environment import Environment, EnvironmentAPI
from softpack_builder.service import ServiceAPI

app = Application()
app.register_module(ServiceAPI)
app.register_module(EnvironmentAPI)


@pytest.fixture
def settings(monkeypatch):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        prev = Environment.settings.spack.environments.path
        Environment.settings.spack.environments.path = path
        monkeypatch.setitem(
            app.settings.spack.environments.__dict__, "path", str(path)
        )
        yield app.settings
        Environment.settings.spack.environments.path = prev


@pytest.fixture
def client() -> TestClient:
    return TestClient(app.router)


class CLI:
    def __init__(self):
        self.runner = CliRunner()

    def invoke(self, *args, **kwargs):
        return self.runner.invoke(app.commands, *args, **kwargs)


@pytest.fixture
def cli() -> CLI:
    return CLI()


def service_run():
    cli = CLI()
    cli.invoke(["service", "run", "--no-reload"])


@pytest.fixture
def service_factory():
    def create_service(module):
        service = module(target=service_run, daemon=True)
        service.start()
        while True:
            try:
                response = requests.get(app.url())
                if response.status_code == httpx.codes.OK:
                    break
            except requests.ConnectionError:
                time.sleep(0.1)
                continue
        return service

    return create_service


@pytest.fixture
def service(service_factory):
    return service_factory(Process)


@pytest.fixture
def service_thread(service_factory):
    return service_factory(Thread)


def prefect_agent_run():
    from prefect.cli import app as prefect_cli

    with pytest.raises(SystemExit):
        prefect_cli(
            [
                "agent",
                "start",
                "--hide-welcome",
                "--run-once",
                "--work-queue",
                "default",
            ]
        )


@pytest.fixture
def prefect_agent(settings):
    agent = Thread(target=prefect_agent_run, daemon=True)
    agent.start()
    yield agent
