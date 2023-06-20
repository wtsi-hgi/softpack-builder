"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import re
from pathlib import Path
from typing import Iterator

import oras.client
import oras.oci
import semver
from box import Box

from .app import app
from .logger import LogMixin
from .serializable import Serializable
from .url import URL


class Artifacts(Serializable):
    """Artifacts repo access class."""

    settings = Box(app.settings.dict())

    def __init__(self, name: str) -> None:
        """Constructor."""
        self.name = name
        super().__init__()

    def registries(self) -> Iterator:
        """Iterate over artifact registries.

        Returns:
            Iterator: An iterator over artifact registries
        """
        return iter(
            [
                self.Registry(self.name, registry)
                for registry in self.settings.artifacts.registries.values()
            ]
        )

    class Registry(LogMixin):
        """Artifacts registry."""

        def __init__(self, name: str, registry: Box) -> None:
            """Constructor.

            Args:
                name: Image path
                registry: Container registry config
            """
            super().__init__()
            self.name = Path(name.lstrip())
            self.url = registry.url
            self.username = registry.username
            self.password = registry.password
            self.client = oras.client.OrasClient()
            self.client.login(
                username=registry.username, password=registry.password
            )

        @staticmethod
        def parse_version(version: str) -> semver.Version:
            """Parse a version.

            Args:
                version: A semantic version string.

            Returns:
                semver.Version: Parsed semantic version.
            """
            try:
                return semver.Version.parse(
                    version, optional_minor_and_patch=True
                )
            except ValueError:
                return semver.Version(0)

        @property
        def image_url(self) -> URL:
            """Return image URL in the container registry.

            Returns:
                URL: Image URL.
            """
            url = URL(self.url)
            path = "-".join(self.name.parent.parts)
            url = URL(self.url, path=str(Path(path, self.name.name)))
            return url

        def next_version(self) -> str:
            """Get the next available image version number.

            Returns:
                str: A semantic version number as a string
            """
            try:
                url = URL(str(self.image_url), scheme="")
                tags = self.client.get_tags(str(url))
                pattern = re.compile(r"^\d+\.\d+$")
                tags = filter(pattern.match, tags)
                latest = sorted(map(self.parse_version, tags))[-1]
                version = latest.bump_major()
                return f"{version.major}.{version.minor}"
            except ValueError:
                return "1.0"

    def default_registry(self, name: str) -> Registry:
        """Get the default artifacts registry.

        Args:
            name: Name of the container image.

        Returns:
            Registry: An Artifacts.Registry object.
        """
        default = "default"
        registry = self.settings.artifacts.registries[default]
        return self.Registry(name=name, registry=registry)

    def add(self, src: Path, dest: Path) -> None:
        """Add an artifact.

        Args:
            src: Source path
            dest: Destination path in the artifacts repo.

        Returns:
            None.
        """
        print(f"placeholder for adding artifact: src={src}, dest={dest}")


Artifacts.register_serializer()
