"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from fastapi import FastAPI
from singleton_decorator import singleton
from typer import Typer

from softpack_builder import __version__

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

    def register_api(self, api: Any) -> None:
        """Register an API with the application.

        Args:
            api: An API class to register.

        Returns:
            None.
        """

        def include_router() -> None:
            return self.router.include_router(api.router)

        def add_typer() -> None:
            name = Path(api.prefix).name
            return self.commands.add_typer(api.commands, name=name)

        for registry_func in [include_router, add_typer]:
            try:
                registry_func()
            except AttributeError as e:
                typer.echo(e)

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
        url = URL(
            scheme=scheme,
            netloc=f"{app.settings.server.host}:{app.settings.server.port}",
            path=path,
        )
        return str(url)


app = Application()


@app.router.get("/")
def root() -> dict[str, Any]:
    """HTTP GET handler for / route.

    Returns:
        dict: Application status to return.
    """
    return {
        "time": str(datetime.now()),
        "softpack": {"builder": {"version": __version__}},
    }
