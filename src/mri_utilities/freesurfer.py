import subprocess
from typing import TYPE_CHECKING

from loguru import logger

from mri_utilities._utilities import (
    CONTAINERS_HOME,
    build_apptainer_container,
    get_freesurfer_license_path,
)

if TYPE_CHECKING:
    from pathlib import Path

FREESURFER_VERSION = "8.2.0"


def run_subregion_segmentation(
    subject: str,
    *,
    subregion: str,
    subjects_dir: Path,
    containers_dir: Path = CONTAINERS_HOME,
    fs_license: Path | None = None,
    nprocs: int = 16,
    version: str = FREESURFER_VERSION,
) -> None:
    freesurfer_filepath = build_apptainer_container(
        directory=containers_dir,
        organization="freesurfer",
        package="freesurfer",
        version=version,
    )

    fs_license = fs_license or get_freesurfer_license_path()

    command = [
        "/usr/bin/env",
        "apptainer",
        "exec",
        "--cleanenv",
        "--bind",
        f"{subjects_dir}:/subjects_dir",
        "--bind",
        f"{fs_license.parent}:/freesurfer",
        "--env",
        "FS_LICENSE=/freesurfer/license.txt",
        str(freesurfer_filepath),
        "segment_subregions",
        subregion,
        "--cross",
        f"sub-{subject}",
        "--sd",
        "/subjects_dir",
        "--threads",
        f"{nprocs}",
    ]
    logger.info(
        "Running {subregion} segmentation for subject sub-{subject}"
        " using FreeSurfer container at {freesurfer_filepath} ...",
        subregion=subregion,
        subject=subject,
        freesurfer_filepath=freesurfer_filepath,
    )

    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info(
            "Successfully ran {subregion} segmentation for subject sub-{subject}.",
            subregion=subregion,
            subject=subject,
        )
    else:
        logger.error(
            "Failed to run {subregion} segmentation for subject sub-{subject}.",
            subregion=subregion,
            subject=subject,
        )
