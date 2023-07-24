"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import importlib
import itertools
import re
import shutil
import socket
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

import jinja2
import mergedeep
import yaml
from box import Box

from .app import app
from .serializable import Serializable
from .shell import ShellCommand
from .url import URL


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

    @classmethod
    def command(cls, command: str, *args: str, **kwargs: str) -> Command:
        """Spack command wrapper.

        Args:
            command: Spack subcommand to run.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Command: A new Command object.

        """
        return cls.Command(command, *args, **kwargs)

    @dataclass
    class Modules:
        """Spack modules."""

        cmd_create: ModuleType
        config: ModuleType
        repo: ModuleType

    def __init__(self) -> None:
        """Constructor."""
        self.modules = self.load_modules()
        self.repos = self.load_repo_list()

    def load_modules(self) -> Modules:
        """Loads all required packages."""
        spack = shutil.which("spack")
        if spack:
            spack_root = Path(spack).resolve().parent.parent
        else:
            spack_root = Path.cwd() / "spack"

        lib_path = spack_root / "lib/spack"

        for path in [lib_path, lib_path / "external"]:
            if path not in sys.path:
                sys.path.append(str(path))

        return self.Modules(
            cmd_create=importlib.import_module('spack.cmd.create'),
            config=importlib.import_module('spack.config'),
            repo=importlib.import_module('spack.repo'),
        )

    def load_repo_list(self) -> dict[str, Any]:
        """Load a list of all repos."""
        return {
            repo.namespace: repo
            for repo in list(
                map(self.modules.repo.Repo, self.modules.config.get("repos"))
            )
        }

    class Package(ABC):
        """Spack package."""

        class Repo(ABC):
            """Package repo."""

            @property
            @abstractmethod
            def url(self) -> URL:
                """Get repo URL.

                Return:
                    URL: Repo URL.
                """

            @property
            @abstractmethod
            def source(self) -> dict[str, str]:
                """Get repo source as a URL or as a package identifier.

                Return:
                    dict: A dictionary of repo source key/value pairs.
                """

            @property
            @abstractmethod
            def version(self) -> dict[str, str]:
                """Get repo version.

                Return:
                    dict: A dictionary of repo version spec as key/value pair.
                """

            @abstractmethod
            def read(self, path: Path, serializer: type) -> Any:
                """Read the contents of a file from the repo.

                Args:
                    path (Path): Filename.
                    serializer (type): Serializer for reading file contents.

                Returns:
                    Any: File contents in package-specific format.
                """

        def __init__(self, name: str, template: str, repo: Repo) -> None:
            """Construct a Package object.

            Args:
                name (str): Package name.
                template (str): Package template.
                repo (Repo): Package repo.
            """
            self.spack = Spack()
            self.settings = self.spack.settings
            self.repo = repo
            self.name = name.lower()
            self.template = template
            metadata = self.load_metadata()
            if metadata:
                self.metadata = Box(metadata)

        @abstractmethod
        def load_metadata(self) -> dict[str, Any]:
            """Load package metadata.

            Returns:
                dict[str, Any]: Package metadata as dictionary of key/value
                pairs.
            """

        @property
        @abstractmethod
        def title(self) -> str:
            """Get package title.

            Returns:
                str: Package title.
            """

        @property
        @abstractmethod
        def description(self) -> str:
            """Get package description.

            Returns:
                str: Package description.
            """

        @property
        @abstractmethod
        def versions(self) -> dict[str, dict[str, str]]:
            """Get package versions.

            Returns:
                dict[str, dict[str, str]]: Package versions as a dictionary.
            """

        @property
        @abstractmethod
        def dependencies(self) -> list[dict[str, str]]:
            """Get package dependencies.

            Returns:
                list[dict[str, str]]: List of package dependencies.
            """

        def create(self, force: bool) -> None:
            """Create a package.

            Args:
                force (bool): Force package creation.

            Raises:
                FileExistsError: If package already exists and force=False.
            """
            dependencies = dict(
                itertools.chain.from_iterable(
                    filter(
                        None,
                        map(
                            partial(
                                self.format_dependency, url=str(self.repo.url)
                            ),
                            self.dependencies,
                        ),
                    )
                )
            )

            repo = self.spack.repos[self.settings.packages.repo.namespace]
            templates = getattr(self.spack.modules.cmd_create, "templates")
            package = templates[self.template](
                name=self.name, url=str(self.repo.url), versions=self.versions
            )

            path = Path(repo.filename_for_package_name(package.name))
            if path.is_file() and not force:
                raise FileExistsError(str(path))

            path.parent.mkdir(parents=True, exist_ok=True)

            package_templates = jinja2.Environment(
                loader=jinja2.FileSystemLoader(
                    self.settings.packages.templates.path
                )
            )

            package_template = package_templates.get_template("spack")
            content = package_template.render(
                class_name=package.class_name,
                base_class_name=package.base_class_name,
                title=self.title,
                description=self.description,
                homepage=self.repo.url,
                url=self.repo.url,
                versions=self.versions,
                dependencies=dependencies,
                **self.repo.source,
            )
            print(f"  writing {path}")
            with open(path, "w") as file:
                file.write(content)

        def format_dependency(
            self, dependency: Box, url: URL
        ) -> Optional[list]:
            """Format a dependency.

            Args:
                dependency: Dictionary of dependency attributes.
                url: Package URL.

            Return:
                list: A list of dependency attributes.
            """
            templates = getattr(self.spack.modules.cmd_create, "templates")
            package = templates[dependency.template or "generic"](
                name=dependency.package, url=url, versions=None
            )
            if package.name in self.settings.packages.exclude:
                return None

            name = "@".join(
                filter(
                    None,
                    [
                        self.settings.packages.rename.get(
                            package.name, default=package.name
                        ),
                        dependency.version,
                    ],
                )
            )
            return [(name, {"type": dependency.type})]

    class Environment:
        """Spack environment."""

        def __init__(self, name: str, path: Path) -> None:
            """Constructor.

            Args:
                name: Environment name.
                path: Environment staging dir.
            """
            self.name = name
            self.path = path
            self.settings = Spack.settings
            self.manifest = self.Manifest(self)

        def command(self, command: str, *args: str) -> "Spack.Command":
            """Run spack env command.

            Args:
                command: Subcommand to run.
                *args: Positional arguments.

            Returns:
                Command: A new Command object.
            """
            return Spack.command(
                "--env",
                str(self.path),
                command,
                *args,
                working_dir=str(self.path),
            )

        def create(self) -> "Spack.Command":
            """Create an environment.

            Returns:
                Command: A new Command object
            """
            return Spack.command(
                "env",
                "create",
                "--without-view",
                "--dir",
                str(self.path),
            )

        def add(self, packages: list[str]) -> "Spack.Command":
            """Add packages to the environment.

            Args:
                packages: List of packages to add.

            Returns:
                Command: A new Command object.
            """
            return self.command("add", *packages)

        def containerize(self, filename: Path) -> "Spack.Command":
            """Containerize the environment.

            Args:
                filename: Output filename.

            Returns:
                Command: A new Command object.
            """
            return self.command("containerize", ">", str(filename))

        def concretize(self) -> "Spack.Command":
            """Concretize the environment.

            Returns:
                Command: A new Command object.
            """
            return self.command("concretize")

        def buildcache(self, package: str) -> "Spack.Command":
            """Push build cache for a package.

            Args:
                package: A package to cache.

            Returns:
                Command: A new Command object.
            """
            return self.command(
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
            def represent_str(
                dumper: yaml.Dumper, data: str
            ) -> yaml.ScalarNode:
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

            def __init__(self, spack: "Spack.Environment") -> None:
                """Constructor."""
                self.spack = spack
                self.settings = self.spack.settings
                self.filename = (
                    self.spack.path / self.settings.spack.manifest.name
                )

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
                for spec in self.settings.spack.manifest.specs:
                    regex = re.compile(spec.pattern)
                    if list(filter(regex.match, manifest.spack.specs)):
                        manifest.spack = mergedeep.merge(
                            manifest.spack, spec.spack
                        )
                        break

                with open(self.filename, "w") as file:
                    yaml.dump(manifest.to_dict(), file, sort_keys=False)


Spack.register_serializer()
