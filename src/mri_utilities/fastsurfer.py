from pathlib import Path

import nibabel as nib
from loguru import logger

from mri_utilities._utilities import (
    CONTAINERS_HOME,
    build_apptainer_container,
    get_freesurfer_license_path,
    run_command,
    run_slurm_job,
)

FASTSURFER_VERSION = "cpu-v2.6.0"


def run_fastsurfer(
    *,
    subject: str,
    t1w_path: Path,
    data_dir: Path,
    version: str = FASTSURFER_VERSION,
    fs_license: Path | None = None,
    containers_dir: Path = CONTAINERS_HOME,
    seg_threads: int = 16,
    surf_threads: int = 2,
    slurm: bool = False,
    seg_mem: str = "7G",
    seg_partition: str = "gpu",
    seg_cpus_per_task: int = 16,
    seg_time: str = "00:20:00",
    seg_extra_options: list[str] | None = None,
    surf_mem_per_cpu: str = "3G",
    surf_partition: str = "cpu",
    surf_cpus_per_task: int = 2,
    surf_time: str = "04:00:00",
    surf_extra_options: list[str] | None = None,
) -> int | None:
    fastsurfer_dir = data_dir / "derivatives" / f"fastsurfer-{version}"
    if (fastsurfer_dir / f"sub-{subject}" / "scripts" / "recon-surf.done").exists():
        logger.info(
            "FastSurfer has already been run for sub-{subject}",
            subject=subject,
        )
        return None

    fastsurfer_dir.mkdir(exist_ok=True, parents=True)

    container_path = build_apptainer_container(
        directory=containers_dir,
        organization="deepmi",
        package="fastsurfer",
        version=version,
    )

    fastsurfer_min_voxel_size = 0.7
    min_voxel_size = min(nib.nifti1.load(t1w_path).header.get_zooms())
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

    binds = [
        "--bind",
        f"{data_dir}:{data_dir}",
        "--bind",
        f"{fs_license}:{fs_license}",
        "--bind",
        f"{t1w_path.parent}:{t1w_path.parent}",
    ]

    prefix_fastsurfer = [
        "/usr/bin/env",
        "apptainer",
        "exec",
        "--cleanenv",
        "--no-mount",
        "home,cwd",
        "--env",
        "TQDM_DISABLE=1",
        *binds,
    ]

    suffix_fastsurfer = [
        str(container_path),
        "/fastsurfer/run_fastsurfer.sh",
        "--t1",
        f"{t1w_path}",
        "--sid",
        f"sub-{subject}",
        "--fs_license",
        f"{fs_license}",
        "--sd",
        f"{fastsurfer_dir}",
        "--3T",
        "--vox_size",
        f"{vox_size}",
    ]

    command_seg = [
        *prefix_fastsurfer,
        "--nv",
        *suffix_fastsurfer,
        "--seg_only",
        "--threads",
        str(seg_threads),
    ]

    command_surf = [
        *prefix_fastsurfer,
        *suffix_fastsurfer,
        "--surf_only",
        "--threads",
        str(surf_threads),
    ]

    logger.info(
        "Running FastSurfer for subject sub-{subject}"
        " using FastSurfer container at {container_path} ...",
        subject=subject,
        container_path=container_path,
    )

    if slurm:
        log_dir = fastsurfer_dir / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)

        output = run_slurm_job(
            command=command_seg,
            description=f"SLURM job for FastSurfer-seg for sub-{subject}",
            slurm_options=[
                "--output",
                f"{log_dir}/sub-{subject}_%x-%j.log",
                "--ntasks",
                "1",
                "--nodes",
                "1",
                "--job-name",
                "FastSurfer_seg",
                "--partition",
                str(seg_partition),
                "--mem",
                str(seg_mem),
                "--cpus-per-task",
                str(seg_cpus_per_task),
                "--gres=gpu:1",
                "--time",
                str(seg_time),
                *(seg_extra_options or []),
            ],
        )
        seg_job_id = int(output.stdout.strip().split(";")[0])

        output = run_slurm_job(
            command=command_surf,
            description=f"SLURM job for FastSurfer-surf for sub-{subject}",
            slurm_options=[
                "--job-name",
                "FastSurfer_surf",
                "--depend",
                f"afterok:{seg_job_id}",
                "--partition",
                str(surf_partition),
                "--mem-per-cpu",
                str(surf_mem_per_cpu),
                "--cpus-per-task",
                str(surf_cpus_per_task),
                "--time",
                str(surf_time),
                "--hint",
                "nomultithread",
                *(surf_extra_options or []),
            ],
        )
        return int(output.stdout.strip().split(";")[0])

    run_command(
        command=command_seg,
        description=f"FastSurfer-seg for sub-{subject}",
    )
    run_command(
        command=command_seg,
        description=f"FastSurfer-surf for sub-{subject}",
    )
    return None
