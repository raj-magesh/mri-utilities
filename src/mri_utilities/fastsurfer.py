import subprocess
from pathlib import Path

import nibabel as nib
from loguru import logger

from ._utilities import CONTAINERS_HOME, FREESURFER_HOME, build_apptainer_container

FASTSURFER_VERSION = "cuda-v2.5.4"
FREESURFER_VERSION = "8.2.0"


def run_fastsurfer(
    subject: str,
    *,
    data_dir: Path,
    containers_dir: Path = CONTAINERS_HOME,
    freesurfer_home: Path = FREESURFER_HOME,
    version: str = FASTSURFER_VERSION,
) -> None:
    fastsurfer_filepath = build_apptainer_container(
        directory=containers_dir,
        organization="deepmi",
        package="fastsurfer",
        version=version,
    )

    (data_dir / "derivatives" / "fastsurfer").mkdir(exist_ok=True, parents=True)
    t1_path = Path(f"rawdata/sub-{subject}/anat/sub-{subject}_rec-defaced_T1w.nii.gz")

    fastsurfer_min_voxel_size = 0.7
    min_voxel_size = min(nib.nifti1.load(data_dir / t1_path).header.get_zooms())
    if min_voxel_size < fastsurfer_min_voxel_size:
        logger.info(
            f"Setting `--vox_size {fastsurfer_min_voxel_size}` since FastSurfer isn't validated with higher resolution images (current minimum voxel dimension: {min_voxel_size:.1f} mm)",
        )
        vox_size = 0.7
    else:
        vox_size = "min"

    command = [
        "/usr/bin/env",
        "apptainer",
        "exec",
        "--cleanenv",
        "--no-home",
        "--nv",  # use Nvidia GPU
        "--bind",
        f"{data_dir}:/data",
        "--bind",
        f"{freesurfer_home}:/freesurfer",
        str(fastsurfer_filepath),
        "/fastsurfer/run_fastsurfer.sh",
        "--fs_license",
        "/freesurfer/license.txt",
        "--t1",
        f"/data/rawdata/sub-{subject}/anat/sub-{subject}_rec-defaced_T1w.nii.gz",
        "--sid",
        f"sub-{subject}",
        "--sd",
        "/data/derivatives/fastsurfer",
        "--threads",
        "max",
        "--3T",
        "--vox_size",
        f"{vox_size}",
    ]
    logger.info(
        f"Running FastSurfer for subject sub-{subject}"
        f" using FastSurfer container at {fastsurfer_filepath} ...",
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
            f"Successfully ran FastSurfer for subject sub-{subject}.",
        )
    else:
        logger.error(f"Failed to run FastSurfer for subject sub-{subject}.")


def run_subregion_segmentation(
    subject: str,
    *,
    subregion: str,
    subjects_dir: Path,
    containers_dir: Path = CONTAINERS_HOME,
    freesurfer_home: Path = FREESURFER_HOME,
    nprocs: int = 16,
    version: str = FREESURFER_VERSION,
) -> None:
    freesurfer_filepath = build_apptainer_container(
        directory=containers_dir,
        organization="freesurfer",
        package="freesurfer",
        version=version,
    )

    command = [
        "/usr/bin/env",
        "apptainer",
        "exec",
        "--cleanenv",
        "--bind",
        f"{subjects_dir}:/subjects_dir",
        "--bind",
        f"{freesurfer_home}:/freesurfer",
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
        f"Running {subregion} segmentation for subject sub-{subject}"
        f" using FreeSurfer container at {freesurfer_filepath} ...",
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
            f"Successfully ran subregion segmentation for subject sub-{subject}.",
        )
    else:
        logger.error(f"Failed to run subregion segmentation for subject sub-{subject}.")
