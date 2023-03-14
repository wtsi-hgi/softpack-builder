"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from fastapi import FastAPI

from . import __version__, environment

app = FastAPI()


class ServiceStatus(dict):
    """Service status class."""

    def __init__(self) -> None:
        """Constructor."""
        super().__init__(softpack_builder=dict(version=__version__))


@app.get("/")
def root() -> ServiceStatus:
    """HTTP GET handler for / route.

    Returns:
        ServiceStatus: Service status object
    """
    return ServiceStatus()


app.include_router(environment.router)
