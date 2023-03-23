"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import uvicorn
from fastapi import APIRouter
from typer import Typer

from .app import app


class ServiceAPI:
    """Service module."""

    name = "service"
    router = APIRouter(prefix="/service")
    commands = Typer(help="Commands for managing builder service.")

    @staticmethod
    @commands.command()
    def run(reload: bool = True) -> None:
        """Start the SoftPack Builder REST API service.

        Args:
            reload: Enable auto-reload

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
