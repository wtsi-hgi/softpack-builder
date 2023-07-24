"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import httpx
from box import Box

from softpack_builder import __version__
from softpack_builder.service import ServicePlugin


def test_service_run(service_thread) -> None:
    http = httpx.Client(follow_redirects=True)
    response = http.get(ServicePlugin.url())
    status = Box(response.json())
    assert status.softpack.builder.version == __version__
