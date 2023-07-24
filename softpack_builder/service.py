"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from datetime import datetime
from typing import Any

import typer
import uvicorn
from fastapi import APIRouter
from typer import Typer
from typing_extensions import Annotated

from softpack_builder import __version__

from .app import app
from .plugin import Plugin


class ServicePlugin(Plugin):
    """Service plugin."""

    name = "service"
    prefix = f"/{name}"
    router = APIRouter(prefix=prefix)
    commands = Typer(name=name, help="Commands for managing builder service.")

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

    @staticmethod
    @router.get("/")
    def status() -> dict[str, Any]:
        """HTTP GET handler for / route.

        Returns:
            dict: Application status to return.
        """
        return {
            "time": str(datetime.now()),
            "softpack": {"builder": {"version": __version__}},
        }
