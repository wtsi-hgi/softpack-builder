"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import sys
from pathlib import Path
from typing import Any, Optional, Tuple

import hvac
import mergedeep
import yaml
from pydantic import BaseSettings
from pydantic.env_settings import SettingsSourceCallable

from softpack_builder.serializable import Serializable

from .models import (
    ArtifactsConfig,
    ContainerConfig,
    EnvironmentsConfig,
    LoggingConfig,
    ModulesConfig,
    PackagesConfig,
    ServerConfig,
    ServicesConfig,
    SpackConfig,
    VaultConfig,
)


class Settings(BaseSettings, Serializable):
    """Package settings."""

    debug: bool = False
    server: ServerConfig
    services: ServicesConfig
    logging: LoggingConfig
    spack: SpackConfig
    environments: EnvironmentsConfig
    modules: ModulesConfig
    container: ContainerConfig
    artifacts: ArtifactsConfig
    packages: Optional[PackagesConfig]
    vault: Optional[VaultConfig]

    class Config:
        """Configuration loader."""

        config_file = "config.yml"
        default_config_dir = "conf"
        user_config_dir = ".softpack/builder"

        @classmethod
        def file_settings(
            cls, path: Path, settings: BaseSettings
        ) -> dict[str, Any]:
            """Load settings from file.

            Args:
                path: Config file path.
                settings: Base settings object.

            Returns:
                dict[str, Any]: A dictionary of settings.
            """
            if not path.is_file():
                return {}
            with open(path) as f:
                return yaml.safe_load(f)

        @classmethod
        def defaults(cls, settings: BaseSettings) -> dict[str, Any]:
            """Load defaults from config file.

            Args:
                settings: BaseSettings model.

            Returns:
               dict[str, Any]: Settings loaded from default config file.
            """
            package_dir = Path(__file__).parent.absolute()
            path = package_dir / cls.default_config_dir / cls.config_file
            return cls.file_settings(path, settings)

        @classmethod
        def overrides(cls, settings: BaseSettings) -> dict[str, Any]:
            """Load overrides from config file in the home directory.

            Args:
                settings: BaseSettings model.

            Returns:
                dict[str, Any]: Settings loaded from deployment-specific
                config file.
            """
            path = Path.home() / cls.user_config_dir / cls.config_file
            overrides = cls.file_settings(path, settings)
            try:
                config = cls.vault(VaultConfig(**overrides["vault"]))
                overrides = mergedeep.merge(overrides, config)
            except KeyError as e:
                print(e, file=sys.stderr)
            return overrides

        @classmethod
        def vault(cls, vault: VaultConfig) -> dict[str, Any]:
            """Load secrets from HashiCorp Vault.

            Args:
                settings: BaseSettings model.

            Returns:
                dict[str, Any]: Settings loaded from HashiCorp Vault.
            """
            try:
                client = hvac.Client(
                    url=vault.address,
                    token=vault.token,
                )

                def get_secret(path: Path, key: str) -> dict[str, Any]:
                    secret = client.kv.v1.read_secret(
                        path=str(path / key), mount_point="/"
                    )
                    return secret["data"]

                secrets = client.secrets.kv.v1.list_secrets(
                    path=str(vault.path), mount_point="/"
                )

                return {
                    vault.path.name: {
                        key: get_secret(vault.path, key)
                        for key in secrets["data"]["keys"]
                    }
                }

            except Exception:
                return {}

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> Tuple[SettingsSourceCallable, ...]:
            """Override the default setting load behavior.

            Args:
                init_settings: initial settings
                env_settings: settings from environment
                file_secret_settings: settings from secrets file

            Returns:
                A tuple of settings sources
            """
            return cls.overrides, cls.defaults, init_settings


Settings.register_serializer()
