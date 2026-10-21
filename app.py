import os
import sys

# Ohne Konsole (--noconsole) sind stdout/stderr None, das würde Bibliotheken zum Absturz bringen.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from yavis.ui.main import run  # noqa: E402

if __name__ == "__main__":
    run()
