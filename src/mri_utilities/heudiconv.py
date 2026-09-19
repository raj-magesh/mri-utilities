import subprocess  # ruff: ignore[suspicious-subprocess-import]
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def run_heudiconv(
    *,
    dicoms: list[Path],
    output_directory: Path,
    heuristic: Path,
    subject: str,
    extra_options: Sequence[str] = (),
) -> None:
    output_directory.parent.mkdir(exist_ok=True, parents=True)
    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            "/usr/bin/env",
            "heudiconv",
            "--files",
            *[str(filepath) for filepath in dicoms],
            "--outdir",
            str(output_directory),
            "--heuristic",
            str(heuristic),
            "--subjects",
            subject,
            "--converter",
            "dcm2niix",
            "--bids",
            "notop",
            "--minmeta",
            "--overwrite",
            "--random-seed",
            "0",
            *extra_options,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info("Successfully ran heudiconv.")
    else:
        logger.error("Failed to run heudiconv.")
