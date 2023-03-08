"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import typer

from .build_flow import BuildFlow

app = typer.Typer()


@app.command()
def status():
    """Show service status."""
    typer.echo("OK")


@app.command()
def build(timeout: int = 30):
    """Start a build."""
    flow = BuildFlow()
    flow.run(timeout)


def main():
    """Main entrypoint."""
    app()


if __name__ == "__main__":
    main()  # pragma: no cover
