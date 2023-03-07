"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import typer

from .spack_api import SpackAPI

app = typer.Typer()


@app.command()
def status():
    """Show SoftPack-Builder status."""
    spack = SpackAPI()
    spack.status()


@app.command()
def build():
    """Run SoftPack build."""
    spack = SpackAPI()
    spack.build()


def main():
    """Main entrypoint."""
    app()


if __name__ == "__main__":
    main()  # pragma: no cover
