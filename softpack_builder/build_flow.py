"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import time

from prefect import flow, get_run_logger, task
from prefect_dask.task_runners import DaskTaskRunner
from prefect_shell import ShellOperation


@task
def simulated_build(timeout=30):
    """Run a simulated build.

    Args:
        timeout: number of seconds to wait for the task to finish

    Returns:
        None
    """
    logger = get_run_logger()
    for i in range(timeout):
        time.sleep(1)
        logger.info(f"{100*i/timeout:.2f} % complete")


@task
def spack_build(input):
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
def distributed_build(timeout):
    """Run a distributed build.

    Returns:
        None
    """
    result = simulated_build.submit(timeout)
    spack_build.submit(result)


class BuildFlow:
    """BuildFlow class for triggering a distributed build."""

    def run(self, timeout):
        """Run distributed build.

        Args:
            timeout: timeout for the build

        Returns:
            None
        """
        distributed_build(timeout)
