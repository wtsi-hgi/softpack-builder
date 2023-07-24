"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from pathlib import Path
from typing import Any

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

    url: HttpUrl
    path: Path
    token: str

    def __bool__(self) -> bool:
        """Equality operator."""
        return all([self.url, self.path, self.token])


class EnvironmentsConfig(BaseModel):
    """Environments config model."""

    path: Path


class SpackConfig(BaseModel):
    """Spack config model."""

    class ManifestConfig(BaseModel):
        """Manifest config model."""

        class SpecConfig(BaseModel):
            """Spec config model."""

            pattern: str
            spack: dict[str, Any]

        name: str
        spack: dict
        specs: list[SpecConfig]

    cache: Path
    manifest: ManifestConfig


class ModulesConfig(BaseModel):
    """Modules config model."""

    class TemplatesConfig(BaseModel):
        """Templates config model."""

        class SpecConfig(BaseModel):
            """Spec config model."""

            name: str
            pattern: str

        default: str
        path: Path
        specs: list[SpecConfig]

    name: str
    templates: TemplatesConfig


class ContainerConfig(BaseModel):
    """Container config model."""

    class SingularityConfig(BaseModel):
        """Singularity config model."""

        class BuildConfig(BaseModel):
            """Build config model."""

            bind: str

        command: str
        template: Path
        spec: str
        build: BuildConfig
        image: Path

    module: str
    cache: Path
    singularity: SingularityConfig


class PackagesConfig(BaseModel):
    """Packages config model."""

    class RepoConfig(BaseModel):
        """Repo config model."""

        namespace: str

    class TemplatesConfig(BaseModel):
        """Templates config model."""

        path: Path

    repo: RepoConfig
    templates: TemplatesConfig
    exclude: list[str]
    rename: dict[str, str]


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
