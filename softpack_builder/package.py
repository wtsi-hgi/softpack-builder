"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import itertools
import re
import tempfile
import urllib
import urllib.request
from enum import Enum
from functools import partial
from pathlib import Path
from typing import Any, Optional

import httpx
import pyreadr
import typer
from box import Box
from debian.deb822 import Deb822
from singleton_decorator import singleton
from typer import Typer
from typing_extensions import Annotated

from .app import app
from .plugin import Plugin
from .spack import Spack
from .url import URL


class CRAN(Spack.Package.Repo):
    """CRAN repo."""

    base_url = "https://cran.r-project.org/web/packages"

    @singleton
    class PackageArchive:
        """Package archive from CRAN."""

        db = "packages.rds"
        path = Path(tempfile.mkdtemp(), db)

        def __init__(self) -> None:
            """Constructor."""
            self.download()
            packages = pyreadr.read_r(self.path)[None].set_index("Package")
            self.packages = packages[~packages.index.duplicated(keep='last')]

        def download(self) -> None:
            """Download package archive.

            Returns:
                None.
            """
            response = httpx.get(f"{CRAN.base_url}/{self.db}")
            with open(self.path, 'wb') as file:
                file.write(response.content)

        def get(self, name: str) -> dict[str, Any]:
            """Get package entry from package archive.

            Args:
                name (str): Package name.

            Returns:
                dict[str, Any]: Package entry for the requested package.
            """
            return self.packages.loc[name].fillna("").to_dict()

    def __init__(self, package: str) -> None:
        """Constructor.

        Args:
            package (str): Package name in CRAN.
        """
        self.package = package
        self.packages = self.PackageArchive()

    @property
    def url(self) -> URL:
        """Get repo URL.

        Return:
            URL: Repo URL.
        """
        return URL(f"{self.base_url}/{self.package}")

    @property
    def source(self) -> dict[str, str]:
        """Get repo source as a URL or as a package identifier.

        Return:
            dict: A dictionary of repo source key/value pairs.
        """
        return {"cran": self.package}

    @property
    def version(self) -> dict[str, str]:
        """Get repo version.

        Return:
            dict: A dictionary of repo version spec as key/value pair.
        """
        return self.version_spec

    def read(self, path: Path, serializer: type) -> Any:
        """Read the contents of a file from the repo.

        Args:
            path (Path): Filename.
            serializer (type): Serializer for reading file contents.

        Returns:
            Any: File contents in package-specific format.
        """
        http = httpx.Client(follow_redirects=True)
        response = http.get(str(self.url))
        if not response.is_success:
            app.echo(f"  package not found, url={self.url}")
            return
        metadata = Box(self.packages.get(self.package))
        if not metadata:
            return
        md5_sum = metadata.get("MD5sum")
        self.version_spec = {"md5": f'"{md5_sum}"'}
        metadata.Imports = "\n".join(metadata.Imports.split(","))
        return metadata


class PyPI(Spack.Package.Repo):
    """PyPI package repo."""

    base_url = "https://pypi.org"

    def __init__(self, package: str) -> None:
        """Constructor.

        Args:
            package (str): Package name.

        Raises:
            NotImplementedError: Not currently implemented.
        """
        raise NotImplementedError

    @property
    def source(self) -> dict[str, Any]:
        """Get package source.

        Returns:
            dict[str, Any]: Return the git URL as package source.
        """
        raise NotImplementedError

    @property
    def url(self) -> URL:
        """Get repo URL.

        Return:
            URL: Repo URL.
        """
        raise NotImplementedError

    @property
    def version(self) -> dict[str, str]:
        """Get repo version.

        Return:
            dict: A dictionary of repo version spec as key/value pair.
        """
        raise NotImplementedError

    def read(self, path: Path, serializer: type) -> Any:
        """Read the contents of a file from the repo.

        Args:
            path (Path): Filename.
            serializer (type): Serializer for reading file contents.

        Returns:
            Any: File contents in package-specific format.
        """
        raise NotImplementedError


class GitHub(Spack.Package.Repo):
    """GitHub package repo."""

    content = "raw.githubusercontent.com"

    def __init__(
        self,
        url: URL,
        branch: Optional[str],
        commit: Optional[str],
        tag: Optional[str],
    ) -> None:
        """Constructor.

        Args:
            url (URL): Repo url.
            branch (str): Name of branch.
            commit (str): Commit hash.
            tag (str): Repo tag.
        """
        self.git_url = url
        if commit:
            self.ref = commit
            self.version_spec = {"commit": f'"{commit}"'}
        elif tag:
            self.ref = tag
            self.version_spec = {"tag": f'"{tag}"'}
        elif branch:
            self.ref = branch
            self.version_spec = {"branch": f'"{branch}"'}

    @property
    def version(self) -> dict[str, str]:
        """Get repo version.

        Return:
            dict: A dictionary of repo version spec as key/value pair.
        """
        return self.version_spec

    @property
    def url(self) -> URL:
        """Get repo URL.

        Return:
            URL: Repo URL.
        """
        return self.git_url

    @property
    def source(self) -> dict[str, Any]:
        """Get package source.

        Returns:
            dict[str, Any]: Return the git URL as package source.
        """
        return {"git": str(self.url)}

    def read(self, path: Path, serializer: type) -> Any:
        """Read the contents of a file from the repo.

        Args:
            path (Path): Filename.
            serializer (type): Serializer for reading file contents.

        Returns:
            Any: File contents in package-specific format.
        """
        url = URL(
            scheme=self.url.parts.scheme,
            netloc=self.content,
            path=str(Path(self.url.parts.path, self.ref, path)),
        )
        with urllib.request.urlopen(str(url)) as file:
            return serializer(file.read())


class PythonPackage(Spack.Package):
    """Python Package."""

    def __init__(
        self, name: str, template: str, repo: Spack.Package.Repo
    ) -> None:
        """Constructor.

        Args:
            name (str): _description_
            template (str): _description_
            repo (Spack.Package.Repo): _description_

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError

    def load_metadata(self) -> dict[str, Any]:
        """Load package metadata.

        Returns:
            dict[str, Any]: Package metadata as dictionary of key/value pairs.
        """
        raise NotImplementedError

    @property
    def title(self) -> str:
        """Get package title.

        Returns:
            str: Package title.
        """
        raise NotImplementedError

    @property
    def description(self) -> str:
        """Get package description.

        Returns:
            str: Package description.
        """
        raise NotImplementedError

    @property
    def versions(self) -> dict[str, dict[str, str]]:
        """Get package versions.

        Returns:
            dict[str, dict[str, str]]: Package versions as a dictionary.
        """
        raise NotImplementedError

    @property
    def dependencies(self) -> list[dict[str, str]]:
        """Get package dependencies.

        Returns:
            list[dict[str, str]]: List of package dependencies.
        """
        raise NotImplementedError


class RPackage(Spack.Package):
    """R Package."""

    def load_metadata(self) -> dict[str, Any]:
        """Load package metadata.

        Returns:
            dict[str, Any]: Package metadata as dictionary of key/value pairs.
        """
        return self.repo.read(Path("DESCRIPTION"), serializer=Deb822)

    @property
    def title(self) -> str:
        """Get package title.

        Returns:
            str: Package title.
        """
        return self.metadata.Title

    @property
    def description(self) -> str:
        """Get package description.

        Returns:
            str: Package description.
        """
        return self.metadata.Description

    @property
    def versions(self) -> dict[str, dict[str, str]]:
        """Get package versions.

        Returns:
            dict[str, dict[str, str]]: Package versions as a dictionary.
        """
        return {self.metadata.Version: self.repo.version}

    class Dependency:
        """Package dependency parser."""

        name_pattern = re.compile(r'(?<!^)(?=[A-Z])')
        dependency_pattern = re.compile(
            r'^\s*(\w+)[\s]*(\(([>=]=)\s*([\d\.]*)\))?,?$'
        )
        dependency_type = ("build", "run")

        def __init__(self, spec: str) -> None:
            """Constructor.

            Args:
                spec (str): Dependency spec.
            """
            self.spec = spec

        def match(self, template: str) -> dict[str, str]:
            """Match a dependency.

            Args:
                template (str): Spack template.

            Returns:
                dict[str, str]: Dictionary of dependencies.
            """
            match = self.dependency_pattern.match(self.spec)

            if not match:
                return {}

            suffix = None
            if match.group(3) == ">=":
                suffix = ":"

            return Box(
                package=self.name_pattern.sub('-', match.group(1)).lower(),
                version="".join(filter(None, [match.group(4), suffix])),
                type=self.dependency_type,
                template=template,
            )

    def parse_dependencies(
        self, dependencies: str, template: Optional[str] = None
    ) -> Optional[list[dict[str, str]]]:
        """Parse package dependencies.

        Args:
            dependencies (str): Dependencies from package description file.
            template (Optional[str], optional): Spack template.
            Defaults to None.

        Returns:
            list[dict[str, str]]: List of package dependencies.
        """
        if not dependencies:
            return None

        return list(
            filter(
                None,
                (
                    map(
                        partial(self.Dependency.match, template=template),
                        map(self.Dependency, dependencies.splitlines()),
                    )
                ),
            )
        )

    @property
    def dependencies(self) -> list[dict[str, str]]:
        """Get package dependencies.

        Returns:
            list[dict[str, str]]: List of package dependencies.
        """
        return list(
            itertools.chain.from_iterable(
                filter(
                    None,
                    [
                        self.parse_dependencies(self.metadata.get("Depends")),
                        self.parse_dependencies(
                            self.metadata.get("Imports"), template="r"
                        ),
                    ],
                )
            )
        )


class PackagePlugin(Plugin):
    """Package plugin."""

    name = "package"
    commands = Typer(name=name, help="Commands for managing packages.")

    class TemplateType(str, Enum):
        """Template type."""

        python = "python"
        r = "r"

    @staticmethod
    def get_repo(
        name: str,
        cran: bool,
        pypi: bool,
        git: Optional[URL],
        branch: Optional[str],
        commit: Optional[str],
        tag: Optional[str],
    ) -> Spack.Package.Repo:
        """Instantiate a package repo based on arguments passed.

        Args:
            name (str): Package name.
            cran (bool): Get package from CRAN.
            pypi (bool): Get package from PyPI.
            git (Optional[URL]): URL of package repo in git.
            branch (Optional[str]): Git branch.
            commit (Optional[str]): Git commit hash.
            tag (Optional[str]): Git tag.

        Raises:
            TypeError: if invalid arguments are passed.

        Returns:
            Spack.Package.Repo: Instance of a package repo class.
        """
        if cran:
            return CRAN(name)
        if pypi:
            return PyPI(name)
        if git:
            return GitHub(git, branch=branch, commit=commit, tag=tag)
        raise TypeError

    @staticmethod
    @commands.command(help="Create a package.")
    def create(
        packages: list[str],
        template: Annotated[
            Optional[TemplateType], typer.Option(help="Package template.")
        ] = None,
        cran: Annotated[
            bool,
            typer.Option(
                "--cran",
                help="Get package from CRAN.",
            ),
        ] = False,
        pypi: Annotated[
            bool,
            typer.Option(
                "--pypi",
                help="Get package from PyPI.",
            ),
        ] = False,
        git: Annotated[
            Optional[URL],
            typer.Option(
                click_type=URL.Parser(), help="Get package from Git."
            ),
        ] = None,
        branch: Annotated[
            Optional[str], typer.Option(help="Git branch.")
        ] = None,
        commit: Annotated[
            Optional[str], typer.Option(help="Git commit hash.")
        ] = None,
        tag: Annotated[Optional[str], typer.Option(help="Git tag.")] = None,
        force: Annotated[
            bool,
            typer.Option(
                "--force",
                help="Overwrite if package already exists.",
            ),
        ] = False,
    ) -> None:
        """Create a package.

        Args:
            packages: Package names.
            template: Package template.
            cran: Get package from CRAN.
            git: Get package from Git.
            branch: Git branch.
            commit: Git commit hash.
            tag: Git tag.
            url: Package source.
            force: Overwrite existing package.

        Returns:
            None.
        """
        repo_group = ["--cran", "--pypi", "--git"]
        repo_option_count = sum(
            [cran is not False, pypi is not False, git is not None]
        )

        if not repo_option_count:
            app.echo(
                f"invalid options: one of {repo_group} "
                "required for package creation."
            )
            return

        if repo_option_count > 1:
            app.echo(
                f"invalid options: {repo_group} " "are mutually exclusive."
            )
            return

        if cran:
            template = PackagePlugin.TemplateType.r
        elif pypi:
            template = PackagePlugin.TemplateType.python

        if not template:
            app.echo(
                "invalid options: --template required for package creation."
            )
            return

        templates = {
            PackagePlugin.TemplateType.python: PythonPackage,
            PackagePlugin.TemplateType.r: RPackage,
        }

        for name in packages:
            app.echo(f"creating package, name={name}")

            try:
                repo = PackagePlugin.get_repo(
                    name=name,
                    git=git,
                    cran=cran,
                    pypi=pypi,
                    commit=commit,
                    branch=branch,
                    tag=tag,
                )
                package = templates[template](
                    name, template=template, repo=repo
                )
                package.create(force)
            except Exception as e:
                print(f"{e.__class__.__name__}: {e}")
