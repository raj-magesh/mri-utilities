import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from loguru import logger

from mri_utilities._utilities import (
    CONTAINERS_HOME,
    build_apptainer_container,
    get_freesurfer_license_path,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

MRIPrep = Literal["fMRIPrep", "sMRIPrep"]

SMRIPREP_VERSION = "0.20.0"
FMRIPREP_VERSION = "25.2.5"


def run_fmriprep(*args, **kwargs) -> None:  # ruff: ignore[missing-type-args, missing-type-kwargs]
    return _run_mriprep(*args, mriprep="fMRIPrep", **kwargs)


def run_smriprep(*args, **kwargs) -> None:  # ruff: ignore[missing-type-args, missing-type-kwargs]
    return _run_mriprep(*args, mriprep="sMRIPrep", **kwargs)


def _run_mriprep(
    subject: str,
    data_dir: Path,
    *,
    mriprep: MRIPrep,
    version: str | None = None,
    work_dir: Path | None = None,
    containers_dir: Path = CONTAINERS_HOME,
    fs_license: Path | None = None,
    bids_filter_file: Path | None = None,
    output_spaces: Sequence[str] = ("MNI152NLin2009cAsym", "T1w", "fsnative"),
    use_fastsurfer_outputs: bool = True,
    extra_options: Sequence[str] = (),
) -> None:
    if work_dir is None:
        if xdg_cache_home := os.getenv("XDG_CACHE_HOME"):
            work_dir = Path(xdg_cache_home) / f"{mriprep}-{version}"
        else:
            work_dir = Path.home() / ".cache" / f"{mriprep}-{version}"
    work_dir.mkdir(exist_ok=True, parents=True)

    if version is None:
        match mriprep:
            case "sMRIPrep":
                version = SMRIPREP_VERSION
            case "fMRIPrep":
                version = FMRIPREP_VERSION

    (data_dir / "derivatives" / f"{mriprep.lower()}-{version}").mkdir(
        exist_ok=True,
        parents=True,
    )

    container_path = build_apptainer_container(
        directory=containers_dir,
        organization="nipreps",
        package=mriprep.lower(),
        version=version,
    )

    fs_license = fs_license or get_freesurfer_license_path()

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
        f"{fs_license.parent}:/freesurfer",
        "--env",
        "FS_LICENSE=/freesurfer/license.txt",
        str(container_path),
        "/data/rawdata",
        f"/data/derivatives/{mriprep.lower()}-{version}",
        "participant",
    ]
    options = [
        "--participant-label",
        subject,
        "--fs-license-file",
        "/freesurfer/license.txt",
        "--work-dir",
        f"/work/{mriprep.lower()}-{version}",
        "--derivatives",
        f"/data/derivatives/{mriprep.lower()}-{version}",
        "--output-spaces",
        *output_spaces,
        "--skull-strip-fixed-seed",
    ]

    if bids_filter_file is not None:
        options.extend(
            [
                "--bids-filter-file",
                f"/data/{bids_filter_file.relative_to(data_dir)}",
            ],
        )

    if use_fastsurfer_outputs:
        fastsurfer_dir = list((data_dir / "derivatives").glob("fastsurfer*"))
        if len(fastsurfer_dir) == 0:
            error = "No FastSurfer outputs provided!"
            raise ValueError(error)
        fastsurfer_dir = fastsurfer_dir[0].name

        options.extend(
            [
                "--fs-subjects-dir",
                f"/data/derivatives/{fastsurfer_dir}",
                "--fs-no-resume",
            ],
        )

    if mriprep == "fMRIPrep":
        options.extend(["--random-seed", "0"])

    options.extend(list(extra_options))

    print(" ".join([*command_prefix, *options]))
    return
    logger.info(
        "Running {mriprep} for subject {subject}"
        " using {mriprep} container at {mriprep_filepath} ...",
        mriprep=mriprep,
        subject=subject,
        mriprep_filepath=container_path,
    )

    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [*command_prefix, *options],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info(
            "Successfully ran {mriprep} for subject {subject}.",
            mriprep=mriprep,
            subject=subject,
        )
    else:
        logger.error(
            "Failed to run {mriprep} for subject {subject}.",
            mriprep=mriprep,
            subject=subject,
        )
        raise RuntimeError
