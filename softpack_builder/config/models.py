"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from pathlib import Path
from typing import Any, Optional

from pydantic import AnyUrl, BaseModel, HttpUrl


class ServerConfig(BaseModel):
    """Server config model."""

    host: str
    port: int


class LoggingConfig(BaseModel):
    """Logging config model."""

    filename: Path
    formatters: dict[str, dict[str, str]]


class VaultConfig(BaseModel):
    """HashiCorp vault config."""

    url: Optional[HttpUrl]
    path: Optional[Path]
    token: Optional[str]


class EnvironmentsConfig(BaseModel):
    """Environments config model."""

    path: Path


class SpackConfig(BaseModel):
    """Spack config model."""

    class ManifestConfig(BaseModel):
        """Manifest config model."""

        name: str
        spack: dict

    cache: Path
    manifest: ManifestConfig


class ModulesConfig(BaseModel):
    """Modules config model."""

    class TemplatesConfig(BaseModel):
        """Templates config model."""

        class PatternConfig(BaseModel):
            """Pattern config model."""

            name: str
            pattern: str

        default: str
        path: Path
        patterns: list[PatternConfig]

    name: str
    templates: TemplatesConfig


class ContainerConfig(BaseModel):
    """Container config model."""

    class SingularityConfig(BaseModel):
        """Singularity config model."""

        class BuildConfig(BaseModel):
            """Build config model."""

            bind: str

        class PatchConfig(BaseModel):
            """Patch config model."""

            pattern: str
            build: Optional[dict[str, Any]]
            final: Optional[dict[str, Any]]

        command: str
        template: Path
        spec: str
        build: BuildConfig
        image: Path
        patch: list[PatchConfig]

    module: str
    cache: Path
    singularity: SingularityConfig


class Credentials(BaseModel):
    """Credentials model."""

    username: str
    password: str


class ArtifactsConfig(BaseModel):
    """Artifacts config model."""

    class Registry(Credentials):
        """ORAS model."""

        url: AnyUrl

    registries: dict[str, Registry]
