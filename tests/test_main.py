"""Copyright (c) Wellcome Sanger Institute.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import sys
from pathlib import Path

from softpack_builder.main import main


def test_main(capsys) -> None:
    try:
        main()
    except SystemExit:
        pass
    captured = capsys.readouterr()
    command = Path(sys.argv[0])
    assert f"Usage: {command.name} [OPTIONS] COMMAND [ARGS]" in captured.err
