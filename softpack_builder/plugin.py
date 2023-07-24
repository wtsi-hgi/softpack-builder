"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from pathlib import Path
from typing import Optional

from .app import app


class Plugin:
    """Plugin base class."""

    name = "plugin"
    prefix = "/"

    @classmethod
    def register(cls) -> None:
        """Register the plugin with the application.

        Returns:
            None.
        """
        app.register_plugin(cls)

    @classmethod
    def command(cls, command: str, *args: str) -> list[str]:
        """Build a command with arguments.

        Args:
            command: Command to run.
            *args: Positional arguments.

        Returns:
            list[str]: A build command line to execute.

        """
        return [cls.name, command, *args]

    @classmethod
    def url(cls, path: Optional[str] = None) -> str:
        """Get absolute URL path.

        Args:
            path: Relative URL path under module prefix.

        Returns:
            str: URL path
        """
        path = path or ""
        return app.url(path=str(Path(cls.prefix) / path))
