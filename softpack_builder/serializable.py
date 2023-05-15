"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import sys

import cloudpickle


class Serializable:
    """Serializable interface."""

    @classmethod
    def register_module(cls) -> None:
        """Register the module with cloudpickle for serialization.

        Returns:
            None.
        """
        if cls.__module__ in cloudpickle.list_registry_pickle_by_value():
            return
        cloudpickle.register_pickle_by_value(sys.modules[cls.__module__])
        for base in cls.__bases__:
            if hasattr(base, "register_module"):
                base.register_module()
