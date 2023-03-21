"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from typing import Any

from .app import app
from .environment import Environment
from .service import Service

app.register_module(Service)
app.register_module(Environment)


def main() -> Any:
    """Main entrypoint."""
    return app.main()


if __name__ == "__main__":
    main()
