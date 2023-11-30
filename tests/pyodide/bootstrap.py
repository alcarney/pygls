import pathlib
import subprocess
import sys
from typing import Optional

# Common paths
REPO = pathlib.Path(__file__).parent.parent.parent
PYODIDE_DIR = REPO / "tests" / "pyodide"
PYODIDE_INDEX = PYODIDE_DIR / "node_modules" / "pyodide"


def build_pygls():
    """Build pygls' whl file and place it in pyodide's local index."""
    run(
        sys.executable,
        "-m",
        "build",
        "--wheel",
        "--outdir",
        str(PYODIDE_INDEX),
        cwd=str(REPO),
    )


def install_pyodide():
    """Install pyodide and related node dependencies."""
    run("npm", "ci", cwd=str(PYODIDE_DIR))


def download_dependencies():
    """Download pygls' dependencies so that we have the wheels locally for pyodide to
    use."""
    requirements = PYODIDE_DIR / "requirements.txt"

    run(
        "poetry",
        "export",
        "-f",
        "requirements.txt",
        "--output",
        str(requirements),
        cwd=str(REPO),
    )

    # Ensure that pip uses packages compatible with the pyodide runtime.
    run(
        "pip",
        "download",
        "--no-deps",
        "--python-version",
        "3.11",  # The version of Python pyodide compiled to WASM
        "--implementation",
        "py",  # Use only pure python packages.
        "-r",
        str(requirements),
        "--dest",
        str(PYODIDE_INDEX),
        cwd=str(REPO),
    )


def run(*cmd, cwd: Optional[str] = None, capture: bool = False) -> Optional[str]:
    """Run a command."""

    result = subprocess.run(cmd, cwd=cwd, capture_output=capture)
    if result.returncode != 0:
        if capture:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.flush()
            sys.stderr.buffer.write(result.stderr)
            sys.stderr.flush()

        sys.exit(result.returncode)

    if capture:
        return result.stdout.decode("utf8").strip()

    return None


def main():
    """Bootstrap the pyodide environment."""
    install_pyodide()

    # NOTE: Disabled for now as it's non-trivial to get mircopip to look in the local
    # folder in the general case - we'd need to implement PyPi's JSON API!
    #
    # download_dependencies()

    build_pygls()

    return 0


if __name__ == "__main__":
    sys.exit(main())
