"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from pathlib import Path
from typing import Any

from box import Box

from .artifacts import Artifacts
from .logger import LogMixin
from .serializable import Serializable


class Container(Serializable):
    """Container image interface."""

    class Builder(LogMixin):
        """Builder interface."""

        def __init__(
            self,
            name: str,
            path: Path,
            model: dict[str, Any],
            artifacts: Artifacts,
        ) -> None:
            """Constructor.

            Args:
                name: Environment name.
                path: Environment path.
                model: Environment model.
                artifacts: Artifact object.
            """
            super().__init__()
            self.name = name
            self.path = path
            self.model = Box(model)
            self.artifacts = artifacts

        def build_image(self) -> None:
            """Builds a container image.

            Returns:
                None.
            """

        def push_image(
            self, registry: Artifacts.Registry, version: str
        ) -> None:
            """Push the image to container registry.

            Args:
                registry: Artifacts registry.
                version: Version to tag the image with.

            Returns:
                None.
            """

    def builder(self, **kwargs: Any) -> Builder:
        """Instantiate a Builder.

        Args:
            kwargs: Keyword arguments

        Returns:
            Builder: A new Builder object
        """
        return self.Builder(**kwargs)


Container.register_serializer()
