import subprocess  # ruff: ignore[suspicious-subprocess-import]
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path


def run_heudiconv(
    *,
    dicoms: list[Path],
    output_directory: Path,
    heuristic: Path,
    subject: str,
) -> None:
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
            "--grouping",
            "all",
            "--bids",
            "notop",
            "--minmeta",
            "--overwrite",
            "--random-seed",
            "0",
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
