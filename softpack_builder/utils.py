"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""


from typing import Any, Callable


async def async_exec(func: Callable, *args: str) -> Any:
    """Execute an exec function.

    Args:
        func: Function to call.
        *args: List of arguments to pass to the function.

    Returns:
        Any: Return value from the function called.
    """
    return func(*args)
