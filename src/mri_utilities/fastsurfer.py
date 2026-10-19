import os
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from loguru import logger

from mri_utilities._utilities import (
    CONTAINERS_HOME,
    build_apptainer_container,
    get_freesurfer_license_path,
)

if TYPE_CHECKING:
    import nibabel as nib

FASTSURFER_VERSION = "cpu-v2.6.0"


def run_fastsurfer(
    *,
    subject: str,
    t1w: nib.nifti1.Nifti1Image,
    data_dir: Path,
    version: str,
    containers_dir: Path = CONTAINERS_HOME,
    fs_license: Path | None = None,
    slurm: bool = False,
    slurm_options: list[str] | None = None,
) -> None:
    container_path = build_apptainer_container(
        directory=containers_dir,
        organization="deepmi",
        package="fastsurfer",
        version=version,
    )

    (data_dir / "derivatives" / f"fastsurfer-{version}").mkdir(
        exist_ok=True,
        parents=True,
    )

    fastsurfer_min_voxel_size = 0.7
    min_voxel_size = min(t1w.header.get_zooms())
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

    apptainer_options = [
        "--cleanenv",
        "--no-home",
        "--bind",
        f"{data_dir}:{data_dir}",
        "--bind",
        f"{fs_license}:{fs_license}",
    ]

    shared_fastsurfer_args = [
        "--fs_license",
        f"{fs_license}",
        "--sd",
        f"{data_dir}/derivatives/fastsurfer-{version}",
        "--sid",
        f"sub-{subject}",
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

    with tempfile.TemporaryDirectory() as temp_dir:
        t1w_path = Path(temp_dir) / f"sub-{subject}_T1w.nii.gz"
        t1w.to_filename(t1w_path)
        apptainer_options.extend([
            "--bind",
            f"{t1w_path.parent}:{t1w_path.parent}",
        ])

        if slurm:
            tag = version.rsplit("-", maxsplit=1)[-1]
            filenames = [
                "srun_fastsurfer.sh",
                "brun_fastsurfer.sh",
                "stools.sh",
            ]

            for filename in filenames:
                script_path = Path(temp_dir) / filename
                url = (
                    "https://raw.githubusercontent.com/Deep-MI/FastSurfer/"
                    f"{tag}/{filename}"
                )

                response = requests.get(url, timeout=30)
                response.raise_for_status()
                script_path.write_bytes(response.content)

            cache_home = Path(
                os.getenv(
                    "CACHE_HOME",
                    os.getenv("XDG_CACHE_HOME", str(Path.home() / ".cache")),
                ),
            )
            cache_dir = cache_home / f"fastsurfer-{version}" / f"sub-{subject}"
            cache_dir.mkdir(exist_ok=True, parents=True)
            apptainer_options.extend([
                "--bind",
                f"{cache_dir}:{cache_dir}",
            ])

            command = [
                "/usr/bin/env",
                "bash",
                str(Path(temp_dir) / "srun_fastsurfer.sh"),
                "--data",
                f"{t1w_path.parent}",
                "--work",
                str(cache_dir),
                "--singularity_image",
                str(container_path),
                "--extra_singularity_options",
                " ".join(apptainer_options),
                *(slurm_options or []),
                *shared_fastsurfer_args,
            ]
            _run_command(command=command, subject=subject)
        else:
            command = [
                "/usr/bin/env",
                "apptainer",
                "exec",
                *apptainer_options,
                "--nv",
                str(container_path),
                "/fastsurfer/run_fastsurfer.sh",
                *shared_fastsurfer_args,
                "--t1",
                f"{t1w_path}",
            ]
            _run_command(command=command, subject=subject)


def _run_command(*, command: list[str], subject: str) -> None:
    logger.info("{command}", command=" ".join(command))
    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if output.stdout:
        logger.info("FastSurfer stdout: {output}", output=output.stdout.rstrip())

    if output.stderr:
        logger.warning("FastSurfer stderr: {error}", error=output.stderr.rstrip())

    if output.returncode == 0:
        logger.success(
            "Successfully ran FastSurfer for subject sub-{subject}.",
            subject=subject,
        )
    else:
        logger.error(
            "Failed to run FastSurfer for subject sub-{subject} (exit code {code}).",
            subject=subject,
            code=output.returncode,
        )
