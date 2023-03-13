"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import typer
import uvicorn

from . import environment
from .config import settings

cli = typer.Typer()

cli.add_typer(environment.commands, name="environment")


@cli.command()
def service():
    uvicorn.run(
        "softpack_builder.app:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=False,
        log_level="debug",
    )


def main():
    """Main entrypoint."""
    cli()


if __name__ == "__main__":
    main()  # pragma: no cover
