"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import pytest
from prefect import flow

from softpack_builder.deployments import DeploymentRegistry


@flow(name="test flow 1")
def test_flow_1() -> None:
    pass


@flow(name="test flow 2")
def test_flow_2() -> None:
    pass


@pytest.fixture
def flows():
    return [test_flow_1, test_flow_2]


@pytest.fixture
def deployments(flows):
    deployments = DeploymentRegistry()
    deployments.register(flows)
    return deployments


def test_deployments_build(flows, deployments) -> None:
    for f in flows:
        deployment = deployments.find(f)
        assert f.name == deployment.flow_name


def test_deployments_run(flows, deployments) -> None:
    for f in flows:
        status = deployments.run(f)
        assert status.state_name == "Scheduled"
