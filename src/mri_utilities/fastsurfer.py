import subprocess
from pathlib import Path

import nibabel as nib
from loguru import logger

from mri_utilities._utilities import (
    CONTAINERS_HOME,
    build_apptainer_container,
    get_freesurfer_license_path,
)

FASTSURFER_VERSION = "cuda-v2.5.4"


def run_fastsurfer(
    subject: str,
    *,
    data_dir: Path,
    containers_dir: Path = CONTAINERS_HOME,
    fs_license: Path | None = None,
    version: str = FASTSURFER_VERSION,
) -> None:
    container_path = build_apptainer_container(
        directory=containers_dir,
        organization="deepmi",
        package="fastsurfer",
        version=version,
    )

    (data_dir / "derivatives" / f"fastsurfer-{version}").mkdir(
        exist_ok=True, parents=True
    )
    t1_path = Path(f"rawdata/sub-{subject}/anat/sub-{subject}_rec-defaced_T1w.nii.gz")

    fastsurfer_min_voxel_size = 0.7
    min_voxel_size = min(nib.nifti1.load(data_dir / t1_path).header.get_zooms())
    if min_voxel_size < fastsurfer_min_voxel_size:
        logger.info(
            "Setting `--vox_size {fastsurfer_min_voxel_size}` since FastSurfer isn't validated with higher resolution images (current minimum voxel dimension: {min_voxel_size:.1f} mm)",
            fastsurfer_min_voxel_size=fastsurfer_min_voxel_size,
            min_voxel_size=min_voxel_size,
        )
        vox_size = 0.7
    else:
        vox_size = "min"

    fs_license = fs_license or get_freesurfer_license_path()

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
        f"{fs_license.parent}:/freesurfer",
        str(container_path),
        "/fastsurfer/run_fastsurfer.sh",
        "--fs_license",
        "/freesurfer/license.txt",
        "--t1",
        f"/data/rawdata/sub-{subject}/anat/sub-{subject}_rec-defaced_T1w.nii.gz",
        "--sid",
        f"sub-{subject}",
        "--sd",
        f"/data/derivatives/fastsurfer-{version}",
        "--threads",
        "max",
        "--3T",
        "--vox_size",
        f"{vox_size}",
    ]
    logger.info(
        "Running FastSurfer for subject sub-{subject}"
        " using FastSurfer container at {container_path} ...",
        subject=subject,
        container_path=container_path,
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
            "Successfully ran FastSurfer for subject sub-{subject}.",
            subject=subject,
        )
    else:
        logger.error(
            "Failed to run FastSurfer for subject sub-{subject}.",
            subject=subject,
        )
