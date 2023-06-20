"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

import jinja2
import prefect
from box import Box

from .app import app
from .artifacts import Artifacts
from .serializable import Serializable


class ModuleFile(Serializable):
    """Module file writer."""

    settings = Box(app.settings.dict())

    @dataclass
    class BuildInfo:
        """Build info model."""

        id: UUID
        image: str
        created: Optional[datetime]
        updated: Optional[datetime]

    def __init__(
        self,
        id: UUID,
        name: str,
        path: Path,
        model: dict[str, Any],
        artifacts: Artifacts,
        version: str,
    ) -> None:
        """Constructor.

        Args:
            id: Environment ID.
            name: Environment name.
            path: Environment staging directory.
            model: Environment model.
            version: Artifact version number.
            artifacts: Artifacts class.
        """
        super().__init__()
        self.id = id
        self.name = name
        self.path = path
        self.model = Box(model)
        self.version = version
        self.artifacts = artifacts
        self.filename = self.path / self.settings.modules.name

    def buildinfo(self, id: UUID) -> "BuildInfo":
        """Get build info.

        Args:
            id: Build ID.

        Returns:
            BuildInfo: A newly created BuildInfo.
        """
        created: Optional[datetime] = None
        updated: Optional[datetime] = None
        flow = prefect.context.FlowRunContext.get()
        if flow:
            created = flow.flow_run.created.isoformat()
            updated = flow.flow_run.updated.isoformat()

        registry = self.artifacts.default_registry(self.name)
        return self.BuildInfo(
            id=id,
            image=f"{registry.image_url}:{self.version}",
            created=created,
            updated=updated,
        )

    @property
    def template(self) -> str:
        """Return the template to use for the module file.

        Returns:
            str: Template name.
        """
        for template in self.settings.modules.templates.patterns:
            regex = re.compile(template.pattern)
            if list(filter(regex.match, self.model.packages)):
                return template.name
        return self.settings.modules.templates.default

    def create(self) -> None:
        """Create module file.

        Returns:
            None.
        """
        templates = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                self.settings.modules.templates.path
            )
        )

        template = templates.get_template(self.template)
        content = template.render(
            description=self.model.description,
            build=self.buildinfo(self.id),
            packages=self.model.packages,
            cache_dir=self.settings.container.cache,
        )
        with open(self.filename, "w") as file:
            file.write(content)
        self.artifacts.add(self.filename, Path(self.name, self.filename.name))


ModuleFile.register_serializer()
