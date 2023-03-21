"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import httpx

from softpack_builder.app import Application


def test_root(client) -> None:
    response = client.get("/")
    assert response.status_code == httpx.codes.OK


def test_openapi_docs(client) -> None:
    response = client.get("/docs")
    assert response.status_code == httpx.codes.OK


def test_openapi_redoc(client) -> None:
    response = client.get("/redoc")
    assert response.status_code == httpx.codes.OK


def test_register_module(capsys) -> None:
    class Module:
        pass

    app = Application()
    app.register_module(Module)
    captured = capsys.readouterr()
    assert (
        captured.out
        == f"type object '{Module.__name__}' has no attribute 'router'\n"  # noqa: E501, W503
    )
