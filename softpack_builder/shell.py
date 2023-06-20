"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import shutil

from prefect_shell import ShellOperation

from .logger import LogMixin


class ShellCommand(LogMixin):
    """Base class for shell commands."""

    def __init__(self, command: str, *args: str, **kwargs: str) -> None:
        """Constructor.

        Args:
            command: Shell command to execute.
            *args: Positional arguments.
            kwargs: Keyword arguments.

        Returns:
            None.
        """
        super().__init__()
        self.command = " ".join([self.which(command)] + list(map(str, args)))
        self.env: dict[str, str] = {}
        self.kwargs = kwargs

    def which(self, command: str) -> str:
        """Locate a command in the current PATH.

        Args:
            command: Command to locate.

        Returns:
            str: Command path.

        """
        return shutil.which(command) or command

    def __repr__(self) -> str:
        """String representation of the command.

        Returns:
            str: Command as a printable string.
        """
        return self.command

    def __call__(self) -> None:
        """Runs the command.

        Returns:
            None.
        """
        self.logger.info(f"running shell command: {self.command}")
        # env = {"PYTHONUTF8": "1"}

        with ShellOperation(
            commands=[self.command],
            env=self.env,
            stream_output=True,
            **self.kwargs,
        ) as shell:
            process = shell.trigger()
            process.wait_for_completion()


ShellCommand.register_serializer()
