"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import socket
from pathlib import Path
from typing import Any

import mergedeep
import yaml
from box import Box

from .app import app
from .serializable import Serializable
from .shell import ShellCommand


class Spack(Serializable):
    """Spack interface."""

    settings = Box(app.settings.dict())

    class Command(ShellCommand):
        """Spack command."""

        def __init__(self, command: str, *args: str, **kwargs: str):
            """Constructor.

            Args:
                command: Spack subcommand to run.
                *args: Positional arguments.
                **kwargs: Keyword arguments.
            """
            super().__init__("spack", command, *args, **kwargs)

    def __init__(self, name: str, path: Path) -> None:
        """Constructor.

        Args:
            name: Environment name.
            path: Environment staging dir.
        """
        self.name = name
        self.path = path
        self.manifest = self.Manifest(self)

    def command(self, command: str, *args: str, **kwargs: str) -> Command:
        """Spack command wrapper.

        Args:
            command: Spack subcommand to run.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Command: A new Command object.

        """
        return self.Command(
            command, *args, working_dir=str(self.path), **kwargs
        )

    def env_command(self, command: str, *args: str) -> Command:
        """Run spack env command.

        Args:
            command: Subcommand to run.
            *args: Positional arguments.

        Returns:
            Command: A new Command object.
        """
        return self.command("--env", str(self.path), command, *args)

    def env_create(self) -> Command:
        """Create an environment.

        Returns:
            Command: A new Command object
        """
        return self.command(
            "env", "create", "--without-view", "--dir", str(self.path)
        )

    def env_add(self, packages: list[str]) -> Command:
        """Add packages to the environment.

        Args:
            packages: List of packages to add.

        Returns:
            Command: A new Command object.
        """
        return self.env_command("add", *packages)

    def env_containerize(self, filename: Path) -> Command:
        """Containerize the environment.

        Args:
            filename: Output filename.

        Returns:
            Command: A new Command object.
        """
        return self.env_command("containerize", ">", str(filename))

    def env_concretize(self) -> Command:
        """Concretize the environment.

        Returns:
            Command: A new Command object.
        """
        return self.env_command("concretize")

    def env_buildcache(self, package: str) -> Command:
        """Push build cache for a package.

        Args:
            package: A package to cache.

        Returns:
            Command: A new Command object.
        """
        return self.command(
            "--env",
            ".",
            "buildcache",
            "push",
            "--allow-root",
            "--force",
            socket.gethostname(),
            package,
        )

    def patch_manifest(self, patch: dict[str, Any]) -> None:
        """Patch a environment manifest.

        Args:
            patch: Configuration to patch

        Returns:
            None.
        """
        return self.manifest.patch(patch)

    class Manifest:
        """Spack manifest abstraction class."""

        @staticmethod
        def represent_str(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
            """YAML multiline string formatter.

            implementation base on:
            https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data

            Args:
                data: Multiline string.

            Returns:
                str: A yaml ScalarNode object.
            """
            tag = "tag:yaml.org,2002:str"
            if len(data.splitlines()) > 1:
                return dumper.represent_scalar(tag, data, style='|')
            return dumper.represent_scalar(tag, data)

        def __init__(self, spack: "Spack") -> None:
            """Constructor."""
            self.spack = spack
            self.settings = self.spack.settings
            self.filename = self.spack.path / self.settings.spack.manifest.name

        def patch(self, patch: dict[str, Any]) -> None:
            """Patch a manifest.

            Args:
                patch: Patch to apply.

            Returns:
                None
            """
            yaml.add_representer(str, self.represent_str)

            manifest = Box.from_yaml(filename=self.filename)
            manifest.spack = mergedeep.merge(
                manifest.spack, self.settings.spack.manifest.spack
            )
            manifest.spack = mergedeep.merge(manifest.spack, patch)

            with open(self.filename, "w") as file:
                yaml.dump(manifest.to_dict(), file, sort_keys=False)


Spack.register_serializer()
