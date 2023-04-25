"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""


import logging
import shutil
from pathlib import Path

import httpx
import prefect
import pytest
import yaml
from box import Box

from softpack_builder.app import app
from softpack_builder.environment import (
    Environment,
    EnvironmentAPI,
    create_environment,
)

PREFECT_AGENT_TIMEOUT = 300  # max amount of time to run (in seconds)


def pytest_generate_tests(metafunc):
    if "spec" not in metafunc.fixturenames:
        return
    path = Path(__file__).parent / "data/specs"
    params = {"spec": [str(file) for file in path.glob("*.yml")]}
    for fixture, param in params.items():
        metafunc.parametrize(fixture, param)


def test_environment_create_api(client, spec) -> None:
    model = Environment.Model.from_yaml(spec)
    response = client.post(
        app.url(EnvironmentAPI.url("create")), json=model.dict()
    )
    assert response.status_code == httpx.codes.OK
    # prefect_agent.join(PREFECT_AGENT_TIMEOUT)


def test_environment_create_command(service_thread, cli, spec) -> None:
    response = cli.invoke([EnvironmentAPI.name, "create", spec])
    result = Box(yaml.safe_load(response.stdout))
    assert result.state.type == "SCHEDULED"


def test_environment_create_flow(spec) -> None:
    model = Environment.Model.from_yaml(spec)
    result = Box(create_environment(model.dict()))
    assert result.state.type == "RUNNING"


def test_environment_logger(monkeypatch, spec) -> None:
    def init_logger(env: Environment):
        return logging.getLogger()

    original_init_logger = Environment.init_logger
    monkeypatch.setattr(Environment, "init_logger", init_logger)
    model = Environment.Model.from_yaml(spec)
    env = Environment.from_model(**model.dict())
    with pytest.raises(TypeError):
        env.logger.info("This code is never executed")

    def get_run_logger():
        return logging.getLogger()

    monkeypatch.setattr(Environment, "init_logger", original_init_logger)
    monkeypatch.setattr(prefect, "get_run_logger", get_run_logger)
    with pytest.raises(TypeError):
        env.init_logger()

    shutil.rmtree(env.path)
