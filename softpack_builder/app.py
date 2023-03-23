"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from datetime import datetime
from typing import Any
from urllib.parse import urlunsplit

import typer
from fastapi import FastAPI
from singleton_decorator import singleton
from typer import Typer

from softpack_builder import __version__

from .config import Settings


@singleton
class Application:
    """Singleton Application class."""

    def __init__(self) -> None:
        """Constructor."""
        self.router = FastAPI()
        self.commands = Typer()
        self.settings = Settings.parse_obj({})

    def register_module(self, module: Any) -> None:
        """Register a module with the application.

        Args:
            module: A class with router and commands members.

        Returns:
            None.
        """
        try:
            self.router.include_router(module.router)
            self.commands.add_typer(module.commands, name=module.name)
        except AttributeError as e:
            self.echo(e)

    def echo(self, *args: Any, **kwargs: Any) -> Any:
        """Print a message using Typer/Click echo.

        Args:
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: The return value from Typer.echo.
        """
        return typer.echo(*args, **kwargs)

    def main(self) -> Any:
        """Main command line entrypoint.

        Returns:
            Any: The return value from running Typer commands.
        """
        return self.commands()

    @staticmethod
    def url(path: str = "/", scheme: str = "http") -> str:
        """Get absolute URL path.

        Args:
            path: Relative URL path
            scheme: URL scheme

        Returns:
            str: URL path
        """
        return urlunsplit(
            (
                scheme,
                f"{app.settings.server.host}:{app.settings.server.port}",
                path,
                "",
                "",
            )
        )


app = Application()


@app.router.get("/")
def root() -> dict:
    """HTTP GET handler for / route.

    Returns:
        dict: Application status
    """
    return {
        "time": datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f'),
        "softpack": {"builder": {"version": __version__}},
    }
