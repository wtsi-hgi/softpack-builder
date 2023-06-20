"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import typer
import uvicorn
from fastapi import APIRouter
from typer import Typer
from typing_extensions import Annotated

from .api import API
from .app import app


class ServiceAPI(API):
    """Service module."""

    prefix = "/service"
    router = APIRouter(prefix=prefix)
    commands = Typer(help="Commands for managing builder service.")

    @staticmethod
    @commands.command(help="Start the SoftPack Builder REST API service.")
    def run(
        reload: Annotated[
            bool,
            typer.Option(
                "--reload",
                help="Automatically reload when changes are detected.",
            ),
        ] = False
    ) -> None:
        """Start the SoftPack Builder REST API service.

        Args:
            reload: Enable auto-reload.

        Returns:
            None.
        """
        uvicorn.run(
            "softpack_builder.app:app.router",
            host=app.settings.server.host,
            port=app.settings.server.port,
            reload=reload,
            log_level="debug",
        )
