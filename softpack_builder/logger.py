"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import importlib
import logging
from typing import Union, cast

import prefect
from box import Box
from prefect.context import FlowRunContext

from .app import app
from .serializable import Serializable


class LogMixin(Serializable):
    """Log mixin."""

    class Logger:
        """Logger class."""

        settings = Box(app.settings.dict())

        def __init__(self) -> None:
            """Constructor."""
            context: FlowRunContext = cast(
                FlowRunContext, prefect.context.FlowRunContext.get()
            )
            self.flow_run_id = context.flow_run.id if context else None
            self.path = self.settings.environments.path / f"{self.flow_run_id}"
            self.path.mkdir(parents=True, exist_ok=True)
            self.flow_logger: logging.LoggerAdapter = self.init_logger()
            self.task_logger: Union[logging.LoggerAdapter, None] = None

        def __call__(self) -> logging.LoggerAdapter:
            """Get context-specific logger.

            Returns:
                Logger: A python LoggerAdapter object.
            """
            if prefect.context.TaskRunContext.get():
                if not self.task_logger:
                    self.task_logger = self.init_logger()
                return self.task_logger
            elif prefect.context.FlowRunContext.get():
                return self.flow_logger
            else:
                raise TypeError(
                    "Called from unexpected context."
                    "Logging is only available in flow and task contexts."
                )

        def init_logger(self) -> logging.LoggerAdapter:
            """Initialize a logger.

            Returns:
                Logger: A python Logger object.
            """
            filename = self.path / self.settings.logging.filename
            handler = logging.FileHandler(filename=str(filename))
            args = self.settings.logging.formatters.prefect.to_dict()
            formatter_class = args.pop("class")
            module, _, cls = formatter_class.rpartition('.')
            formatter = getattr(importlib.import_module(module), cls)(**args)
            handler.setFormatter(formatter)
            logger = prefect.get_run_logger()
            if isinstance(logger, logging.LoggerAdapter):
                logger.logger.addHandler(handler)
                return logger
            else:
                raise TypeError(
                    "Received unexpected logger."
                    "Logging is only available in flow and task contexts."
                )

    def __init__(self) -> None:
        """Constructor."""
        self._logger = self.Logger()

    @property
    def logger(self) -> logging.LoggerAdapter:
        """Get context-specific logger.

        Returns:
            Logger: A python Logger object.
        """
        return self._logger()


LogMixin.register_serializer()
