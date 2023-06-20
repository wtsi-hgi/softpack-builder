"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, cast

from box import Box

from .app import app
from .artifacts import Artifacts
from .container import Container
from .logger import LogMixin
from .shell import ShellCommand
from .spack import Spack


class Singularity(Container):
    """Singularity container image interface."""

    class RemoteContext(LogMixin):
        """Context manager for handling connection to remote registries."""

        def __init__(
            self,
            builder: "Singularity.Builder",
            registry: Artifacts.Registry,
        ) -> None:
            """Constructor.

            Args:
                builder: A Builder object reference.
                registry: Registry parameters.
            """
            super().__init__()
            self.builder = builder
            self.registry = registry

        def __enter__(self) -> "Singularity.RemoteContext":
            """Enter the context manager.

            Returns:
                RemoteContext: A reference to self.
            """
            self.builder.remote_login(self.registry)()
            return self

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            """Exit the context manager.

            Args:
                exc_type: Exception type.
                exc_val: Exception value.
                exc_tb: Exception traceback.

            Returns:
                None.
            """
            self.builder.remote_logout()()

        def push_image(self, url: str) -> None:
            """Push an image to the remote registry.

            Args:
                url: Destination URL.

            Returns:
                None.
            """
            self.builder.push(url)()

    class Builder(Container.Builder):
        """Container builder interface."""

        settings = Box(app.settings.dict())

        def __init__(self, **kwargs: Any) -> None:
            """Constructor.

            Args:
                kwargs: Keyword arguments.
            """
            super().__init__(**kwargs)
            self.image = self.path / self.settings.container.singularity.image

        def build_image(self) -> None:
            """Runs the Singularity build.

            Returns:
                Path: Image path.
            """
            for stage in [self.Build, self.Final]:
                stage(self).build()

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
            self.logger.info("pushing image to container registry ...")
            with Singularity.RemoteContext(self, registry) as remote:
                url = f"{registry.image_url}:{version}"
                remote.push_image(url)

        class Command(ShellCommand):
            """Singularity command line interface."""

            def __init__(
                self, command: str, *args: str, **kwargs: str
            ) -> None:
                """Constructor.

                Args:
                    command: Singularity subcommand to run.
                    *args: Positional arguments.
                    **kwargs: Keyword arguments.
                """
                super().__init__("singularity", command, *args, **kwargs)

        def command(self, command: str, *args: str, **kwargs: str) -> Command:
            """Singularity command wrapper.

            Args:
                command: Singularity subcommand to run.
                *args: Positional arguments.
                **kwargs: Keyword arguments.

            Returns:
                Command: A new Command object.
            """
            return self.Command(
                command, *args, working_dir=str(self.path), **kwargs
            )

        def build(self, *args: str) -> Command:
            """Runs Singularity build command.

            Args:
                *args: Additional arguments passed to build command.

            Returns:
                Command: A new Command object.
            """
            return self.command("build", "--force", "--fakeroot", *args)

        def push(self, url: str) -> Command:
            """Push image to a container registry.

            Args:
                url: Destination URL.

            Returns:
                Command: A new Command object.
            """
            return self.command("push", self.image, url)

        def remote_login(self, registry: Artifacts.Registry) -> Command:
            """Login to a remote registry.

            Args:
                registry: Registry parameters.

            Returns:
                Command: A new command object.
            """
            command = self.command(
                "remote",
                "login",
                "--username",
                "$USERNAME",
                "--password",
                "$PASSWORD",
                registry.url,
            )
            command.env = {
                "USERNAME": registry.username,
                "PASSWORD": registry.password,
            }
            return command

        def remote_logout(self) -> Command:
            """Logout from a remote registry.

            Returns:
                None.
            """
            return self.command("remote", "logout")

        class Stage(ABC):
            """Image build stage."""

            def __init__(self, builder: Container.Builder) -> None:
                """Constructor.

                Args:
                    builder: Singularity container image builder.
                """
                self.builder = cast(Singularity.Builder, builder)
                self.settings = self.builder.settings.container.singularity
                self.spack = Spack(self.builder.name, self.builder.path)
                self.stage_name = self.__class__.__name__.lower()
                self.filename = self.builder.path / self.settings.spec.format(
                    stage=self.stage_name
                )

            def containerize(self) -> None:
                """Containerize the environment.

                Args:
                    spec: Container image spec.

                Returns:
                    None.
                """
                self.patch_manifest()
                self.spack.env_containerize(self.filename)()
                self.patch()
                self.builder.artifacts.add(
                    self.filename, Path(self.builder.name, self.filename.name)
                )

            def build(self) -> None:
                """Builds the stage.

                Returns:
                    None.
                """
                self.containerize()
                self.builder.build(*self.args())()

            def patch_manifest(self) -> None:
                """Patch the manifest for this stage.

                Returns:
                    None
                """
                patch = {
                    "container": {
                        "template": str(self.settings.template).format(
                            stage=self.stage_name
                        )
                    }
                }
                self.spack.patch_manifest(patch)

            @abstractmethod
            def patch(self) -> None:
                """Patch the build definition.

                Returns:
                    None.
                """

            @abstractmethod
            def args(self) -> list[str]:
                """Return arguments to be passed to the builder.

                Returns:
                    list[str]: List of arguments
                """

        class Build(Stage):
            """Singularity build stage."""

            def patch(self) -> None:
                """Patch the build definition.

                Returns:
                    None.
                """
                with open(self.filename, "a") as file:
                    commands = ["# spack build cache"] + list(
                        map(
                            lambda package: str(
                                self.spack.env_buildcache(package)
                            ),
                            self.builder.model.packages,
                        )
                    )
                    commands = [f"  {command}\n" for command in commands]
                    file.writelines(commands)

            def args(self) -> list[str]:
                """Arguments passed to the build command.

                Returns:
                    list[str]: List of arguments.
                """
                return [
                    "--bind",
                    self.settings.build.bind,
                    "--sandbox",
                    "build/",
                    str(self.filename),
                ]

        class Final(Stage):
            """Singularity final stage."""

            def patch(self) -> None:
                """Patch the build definition.

                Returns:
                    None.
                """
                image = None
                for patch in self.settings.patch:
                    regex = re.compile(patch.pattern)
                    if list(filter(regex.match, self.builder.model.packages)):
                        image = patch[self.stage_name].image
                        break

                with open(self.filename) as file:
                    lines = file.readlines()

                manifest = Box.from_yaml(filename=self.spack.manifest.filename)
                lines = [
                    re.sub(
                        fr"^(.*?)\s({manifest.spack.container.images.os})$",
                        fr"\1 {image}",
                        line,
                    )
                    for line in lines
                ]

                with open(self.filename, "w") as file:
                    file.writelines(lines)

            def args(self) -> list[str]:
                """Arguments passed to the build command.

                Returns:
                    list[str]: List of arguments.
                """
                return [str(self.builder.image), str(self.filename)]


Singularity.Builder.register_serializer()
