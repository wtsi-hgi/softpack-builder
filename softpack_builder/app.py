"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from typing import Any

import typer
from fastapi import FastAPI
from singleton_decorator import singleton
from typer import Typer

from .config.settings import Settings
from .url import URL


@singleton
class Application:
    """Singleton Application class."""

    def __init__(self) -> None:
        """Constructor."""
        self.router = FastAPI()
        self.commands = Typer()
        self.settings = Settings.parse_obj({})

    def register_plugin(self, plugin: Any) -> None:
        """Register a plugin with the application.

        Args:
            plugin: Plugin to register.

        Returns:
            None.
        """

        def include_router() -> None:
            return self.router.include_router(plugin.router)

        def add_typer() -> None:
            return self.commands.add_typer(plugin.commands)

        for registry_func in [include_router, add_typer]:
            try:
                registry_func()
            except AttributeError:
                pass

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
        """Get absolute URL path with current host and port settings.

        Args:
            path: Relative URL path
            scheme: URL scheme

        Returns:
            str: URL path
        """
        url = URL(
            scheme=scheme,
            netloc=f"{app.settings.server.host}:{app.settings.server.port}",
            path=path,
        )
        return str(url)


app = Application()
