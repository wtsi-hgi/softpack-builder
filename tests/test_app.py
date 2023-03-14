"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""


import time
from multiprocessing import Process
from typing import Generator

import pytest
import requests

from softpack_builder.app import ServiceStatus
from softpack_builder.cli import service
from softpack_builder.config import settings


@pytest.fixture(scope="module")
def api_server() -> Generator:
    """Fixture for starting API server.

    Returns:
        None
    """
    startup_timeout = 5
    proc = Process(target=service, daemon=True)
    proc.start()
    time.sleep(startup_timeout)
    yield proc
    proc.kill()


def test_service_get_root(api_server: Generator) -> None:
    """Test HTTP GET for / route.

    Args:
        api_server: API server fixture.

    Returns:
        None.
    """
    response = requests.get(
        f"http://{settings.server.host}:{settings.server.port}"
    )
    assert response.status_code == 200
    assert response.json() == ServiceStatus()
