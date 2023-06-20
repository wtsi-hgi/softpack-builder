"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from typing import Any, Optional

from prefect import Flow
from prefect.deployments import Deployment, run_deployment


class DeploymentRegistry:
    """Wrapper for building and running deployments."""

    def register(self, flows: list[Any]) -> None:
        """Build and register deployments from flows.

        Args:
            *flows: A list of flows to register.

        Returns:
            dict: A dictionary of flows and their corresponding deployments.
        """
        self.deployments = {
            flow: Deployment.build_from_flow(
                flow=flow,
                name=f"{flow.__name__} [default-deployment]",
                apply=True,
            )
            for flow in flows
        }

    def find(self, flow: Flow) -> Deployment:
        """Find a registered deployment for a given flow.

        Args:
            flow: A Prefect flow object

        Returns:
            Deployment: A registered deployment.
        """
        return self.deployments[flow]  # type: ignore

    def run(
        self,
        flow: Flow,
        parameters: Optional[dict[str, Any]] = None,
        timeout: float = 0,
        **kwargs: Any,
    ) -> Any:
        """Run deployment for a given flow.

        Args:
            flow: A flow function.
            parameters: Dictionary of arguments to pass to the deployment.
            timeout: Timeout to wait before returning.
            **kwargs: Additional keyword arguments.

        Returns:
            Any: The return value of running the deployment.

        """
        deployment = self.find(flow)
        return run_deployment(
            f"{deployment.flow_name}/{deployment.name}",
            parameters=parameters,
            timeout=timeout,
            **kwargs,
        )
