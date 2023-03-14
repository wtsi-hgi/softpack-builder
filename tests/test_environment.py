"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""


import pytest
from essential_generators import DocumentGenerator
from prefect import flow

from softpack_builder.environment import Environment, environment_instantiate


@pytest.fixture
def env_model() -> Environment.Model:
    """Create a random environment model.

    Returns:
        Environment.Model: A randomly generated environment model.
    """
    generator = DocumentGenerator()
    return Environment.Model(
        name=generator.word(),
        description=generator.sentence(),
        packages=["zlib"],
    )


@flow
def environment_flow(model: Environment.Model) -> None:
    """Runs an environment flow.

    Args:
        model: An environment model

    Returns:
        Environment: A newly instantiated environment object.
    """
    return environment_instantiate(model)


def test_environment_flow(env_model: Environment.Model) -> None:
    """Test an environment flow.

    Args:
        env_model: A randomly generated environment model.

    Returns:
        None.
    """
    env: Environment = environment_flow(env_model)  # type: ignore
    assert env.model == env_model
