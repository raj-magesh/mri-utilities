from typing import TYPE_CHECKING

from loguru import logger

from mri_utilities._utilities import (
    CONTAINERS_HOME,
    build_apptainer_container,
    get_freesurfer_license_path,
    run_command,
    run_slurm_job,
)

if TYPE_CHECKING:
    from pathlib import Path

FREESURFER_VERSION = "8.2.0"


def run_subregion_segmentation(
    *,
    subject: str,
    subregion: str,
    subjects_dir: Path,
    containers_dir: Path = CONTAINERS_HOME,
    fs_license: Path | None = None,
    nprocs: int = 16,
    version: str = FREESURFER_VERSION,
    slurm: bool = False,
    mem: str = "32G",
    partition: str = "cpu",
    cpus_per_task: int = 16,
    time: str = "04:00:00",
    extra_slurm_options: list[str] | None = None,
) -> int | None:
    freesurfer_dir = subjects_dir.parent / f"freesurfer-{version}"
    if (
        subregion == "thalamus"
        and (freesurfer_dir / f"sub-{subject}" / "mri" / "ThalamicNuclei.mgz").exists()
    ):
        logger.info(
            "FreeSurfer subregion ({subregion}) segmentation has already been run for sub-{subject}",
            subject=subject,
            subregion=subregion,
        )
        return None
    # TODO: add end conditions for other subregions
    freesurfer_dir.mkdir(exist_ok=True, parents=True)

    container_filepath = build_apptainer_container(
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
        f"{subjects_dir}:{subjects_dir}",
        "--bind",
        f"{fs_license}:{fs_license}",
        "--env",
        f"FS_LICENSE={fs_license}",
        str(container_filepath),
        "segment_subregions",
        subregion,
        "--cross",
        f"sub-{subject}",
        "--sd",
        f"{subjects_dir}",
        "--threads",
        f"{nprocs}",
    ]
    logger.info(
        "Running {subregion} segmentation for subject sub-{subject}"
        " using FreeSurfer container at {freesurfer_filepath} ...",
        subregion=subregion,
        subject=subject,
        freesurfer_filepath=container_filepath,
    )
    if slurm:
        log_dir = freesurfer_dir / "logs"
        log_dir.mkdir(exist_ok=True, parents=True)

        output = run_slurm_job(
            command=command,
            description=f"SLURM job for FreeSurfer subregion segmentation for sub-{subject}",
            slurm_options=[
                "--output",
                f"{log_dir}/sub-{subject}_%x-%j.log",
                "--ntasks",
                "1",
                "--nodes",
                "1",
                "--job-name",
                "FreeSurfer_subregion_segmentation",
                "--partition",
                str(partition),
                "--mem",
                str(mem),
                "--cpus-per-task",
                str(cpus_per_task),
                "--time",
                str(time),
                *(extra_slurm_options or []),
            ],
        )
        return int(output.stdout.strip().split(";")[0])

    run_command(
        command=command,
        description=f"FreeSurfer subregion segmentation for sub-{subject}",
    )
    return None
