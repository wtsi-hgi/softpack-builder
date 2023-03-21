"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""


from pathlib import Path

import httpx
import yaml
from box import Box

from softpack_builder.environment import Environment


def pytest_generate_tests(metafunc):
    path = Path(__file__).parent / "data/specs"
    params = {"spec": [str(file) for file in path.glob("*.yml")]}
    for fixture, param in params.items():
        metafunc.parametrize(fixture, param)


def test_environment_create_api(client, spec) -> None:
    model = Environment.Model.from_yaml(spec)
    response = client.post(Environment.url("create"), json=model.asdict())
    assert response.status_code == httpx.codes.OK


def test_environment_create_command(service, cli, spec) -> None:
    response = cli.invoke([Environment.name, "create", spec])
    result = Box(yaml.safe_load(response.stdout))
    assert result.state.type == "SCHEDULED"
