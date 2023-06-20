"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import httpx
from box import Box

from softpack_builder import __version__
from softpack_builder.app import app


def test_service_run(service_thread) -> None:
    response = httpx.get(app.url())
    status = Box(response.json())
    assert status.softpack.builder.version == __version__
