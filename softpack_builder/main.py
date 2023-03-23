"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from typing import Any

from .app import app
from .environment import EnvironmentAPI
from .service import ServiceAPI

app.register_module(ServiceAPI)
app.register_module(EnvironmentAPI)


def main() -> Any:
    """Main entrypoint."""
    return app.main()


if __name__ == "__main__":
    main()