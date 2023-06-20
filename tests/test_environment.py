"""Copyright (c) 2023 Genome Research Ltd.

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

from softpack_builder.environment import (
    Environment,
    EnvironmentAPI,
    build_environment,
)


def pytest_generate_tests(metafunc):
    if "spec" not in metafunc.fixturenames:
        return
    path = Path(__file__).parent / "data/specs"
    params = {"spec": [str(file) for file in path.glob("*.yml")]}
    for fixture, param in params.items():
        metafunc.parametrize(fixture, param)


def test_environment_build_api(client, spec) -> None:
    model = Environment.Model.from_yaml(spec)
    response = client.post(
        EnvironmentAPI.url("build"),
        json={"name": Path(spec).stem, "model": model.dict()},
    )
    assert response.status_code == httpx.codes.OK


def test_environment_build_command(service_thread, cli, spec) -> None:
    response = cli.invoke(
        EnvironmentAPI.command("build", spec, "--name", spec)
    )
    result = Box(yaml.safe_load(response.stdout))
    assert result.state.type == "SCHEDULED"


def test_environment_build_flow(spec) -> None:
    model = Environment.Model.from_yaml(spec)
    result = Box(build_environment(spec, model.dict()))
    assert result.state.type == "RUNNING"


#
def test_environment_logger(monkeypatch, spec) -> None:
    def init_logger(env: Environment):
        return logging.getLogger()

    original_init_logger = Environment.Logger.init_logger
    monkeypatch.setattr(Environment.Logger, "init_logger", init_logger)
    model = Environment.Model.from_yaml(spec)
    env = Environment.create(name=spec, model=model.dict())
    with pytest.raises(TypeError):
        env.logger.info("This call to logger triggers the exception")

    def get_run_logger():
        return logging.getLogger()

    monkeypatch.setattr(
        Environment.Logger, "init_logger", original_init_logger
    )
    monkeypatch.setattr(prefect, "get_run_logger", get_run_logger)
    with pytest.raises(TypeError):
        env.logger.init_logger()

    shutil.rmtree(env.path)
