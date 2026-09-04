import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from collections.abc import Sequence
from pathlib import Path

from loguru import logger

from ._utilities import CONTAINERS_HOME, FREESURFER_HOME

if xdg_cache_home := os.getenv("XDG_CACHE_HOME"):
    WORK_DIR = Path(xdg_cache_home) / "smriprep"
else:
    WORK_DIR = Path.home() / ".cache" / "smriprep"


def _get_smriprep_container(directory: Path, *, version: str) -> Path:
    filepath = directory / f"smriprep-{version}.simg"

    if filepath.exists():
        return filepath

    logger.info(f"Attempting to build sMRIPrep container at {filepath}...")

    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            "/usr/bin/env",
            "apptainer",
            "build",
            str(filepath),
            f"docker://nipreps/smriprep:{version}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info(f"Successfully built sMRIPrep container at {filepath}.")
    else:
        logger.error(f"Failed to build sMRIPrep container at {filepath}.")

    return filepath


def run_smriprep(
    subject: str,
    data_dir: Path,
    *,
    work_dir: Path = WORK_DIR,
    containers_dir: Path = CONTAINERS_HOME,
    freesurfer_home: Path = FREESURFER_HOME,
    bids_filter_file: Path | None = None,
    output_spaces: Sequence[str] | None = None,
    use_fastsurfer_outputs: bool = True,
    nprocs: int = 16,
    mem_gb: float = 32,
    version: str = "0.20.0",
) -> None:
    smriprep_filepath = _get_smriprep_container(
        directory=containers_dir,
        version=version,
    )

    work_dir.mkdir(exist_ok=True, parents=True)

    if output_spaces is None:
        output_spaces = ["MNI152NLin2009cAsym", "T1w", "fsnative"]

    command_prefix = [
        "/usr/bin/env",
        "apptainer",
        "run",
        "--cleanenv",
        "--bind",
        f"{data_dir}:/data",
        "--bind",
        f"{work_dir}:/work",
        "--bind",
        f"{freesurfer_home}:/freesurfer",
        "--env",
        "FS_LICENSE=/freesurfer/license.txt",
        str(smriprep_filepath),
        "/data/rawdata",
        "/data/derivatives",
        "participant",
    ]
    options = [
        "--participant-label",
        subject,
        "--fs-license-file",
        "/freesurfer/license.txt",
        "--work-dir",
        "/work/smriprep",
        "--derivatives",
        "/data/derivatives",
        "--output-spaces",
        *output_spaces,
        "--skull-strip-fixed-seed",
        "--nprocs",
        str(nprocs),
        "--mem-gb",
        str(mem_gb),
    ]
    if bids_filter_file is not None:
        options.extend(
            [
                "--bids-filter-file",
                f"/data/{bids_filter_file.relative_to(data_dir)}",
            ],
        )
    if use_fastsurfer_outputs:
        options.extend(
            ["--fs-subjects-dir", "/data/derivatives/fastsurfer", "--fs-no-resume"],
        )

    logger.info(
        f"Running sMRIPrep for subject {subject}"
        f" using sMRIPrep container at {smriprep_filepath} ...",
    )

    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [*command_prefix, *options],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info(f"Successfully ran sMRIPrep for subject {subject}.")
    else:
        logger.error(f"Failed to run sMRIPrep for subject {subject}.")
        raise RuntimeError
