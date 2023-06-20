"""Copyright (c) 2023 Genome Research Ltd.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import sys

import cloudpickle


class Serializable:
    """Serializable interface."""

    @classmethod
    def register_serializer(cls) -> None:
        """Register the module with cloudpickle for serialization.

        Returns:
            None.
        """
        if cls.__module__ in cloudpickle.list_registry_pickle_by_value():
            return
        cloudpickle.register_pickle_by_value(sys.modules[cls.__module__])
        for base in cls.__bases__:
            if hasattr(base, "register_serializer"):
                base.register_serializer()
