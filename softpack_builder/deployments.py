"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from typing import Any, Optional

from prefect import Flow
from prefect.deployments import Deployment, run_deployment


class Deployments(dict):
    """Wrapper for building and running deployments."""

    @classmethod
    def register(cls, *flows: Any) -> "Deployments":
        """Build deployments from flows.

        Args:
            *flows: A list of flows

        Returns:
            dict: A dictionary of flows and their corresponding deployments.
        """
        return cls(
            {
                flow: Deployment.build_from_flow(
                    flow=flow,
                    name=f"{flow.__name__}-deployment",
                    apply=True,
                )
                for flow in list(flows)
            }
        )

    def run(
        self,
        flow: Flow,
        parameters: Optional[dict] = None,
        timeout: float = 0,
        **kwargs: Any,
    ) -> Any:
        """Run deployment for a given flow.

        Args:
            flow: A flow function.
            parameters: Dictionary of arguments to pass to the deployment
            timeout: Timeout to wait before returning
            **kwargs: Additional keyword arguments

        Returns:
            Any: The return value of running the deployment.

        """
        deployment = self[flow]
        name = f"{deployment.flow_name}/{deployment.name}"
        status = run_deployment(
            name, parameters=parameters, timeout=timeout, **kwargs
        )
        return status
