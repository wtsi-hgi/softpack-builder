"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from prefect import flow, task
from prefect_dask.task_runners import DaskTaskRunner
from prefect_shell import ShellOperation


@task
def spack_build():
    """Run a spack build.

    Returns:
        None or an error
    """
    print("running build ...")
    try:
        command = "http --ignore-stdin GET https://catfact.ninja/fact"
        with ShellOperation(commands=[command]) as shell_command:
            process = shell_command.trigger()
            process.wait_for_completion()
            # output = process.fetch_result()
    except RuntimeError as error:
        return error


@flow(task_runner=DaskTaskRunner())
def distributed_build():
    """Run a distributed build.

    Returns:
        None
    """
    spack_build.submit()


class SpackAPI:
    """Spack API wrapper class."""

    def build(self):
        """Run SpackAPI build.

        Returns:
            None
        """
        distributed_build()
