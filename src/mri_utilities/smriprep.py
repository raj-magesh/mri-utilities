import os
import subprocess
from pathlib import Path

import click
from loguru import logger

from .environment import CONTAINERS_HOME, FREESURFER_HOME

if xdg_cache_home := os.getenv("XDG_CACHE_HOME"):
    WORK_DIR = Path(xdg_cache_home) / "smriprep"
else:
    WORK_DIR = Path.home() / ".cache" / "smriprep"


def _get_smriprep_container(directory: Path, *, version: str) -> Path:
    filepath = directory / f"smriprep-{version}.simg"

    if filepath.exists():
        return filepath

    logger.info(f"Attempting to build sMRIPrep container at {filepath}...")

    output = subprocess.run(  # noqa: S603
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


@click.command()
@click.argument("subject", nargs=1)
@click.argument(
    "data-dir",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    nargs=1,
)
@click.option(
    "--work-dir",
    default=WORK_DIR,
    type=click.Path(file_okay=False, path_type=Path),
    help="path where intermediate results should be stored",
)
@click.option(
    "--containers-dir",
    default=CONTAINERS_HOME,
    type=click.Path(file_okay=False, path_type=Path),
    help="path where sMRIPrep Apptainer container should be placed",
)
@click.option(
    "--freesurfer-home",
    default=FREESURFER_HOME,
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    help="directory containing FreeSurfer license.txt file",
)
@click.option(
    "--bids-filter-file",
    default=None,
    type=click.Path(dir_okay=False, path_type=Path),
    help="a JSON file describing custom BIDS input filters using pybids {<suffix>:{<entity>:<filter>,…},…}",
)
@click.option("--nprocs", default=16, type=int, help="number of CPUs to be used")
@click.option(
    "--mem_gb",
    default=32,
    type=int,
    help="upper bound memory limit for sMRIPrep processes (in GB)",
)
@click.option("--version", default="0.19.2", type=str, help="sMRIPrep version to use")
def run_smriprep(
    subject: str,
    data_dir: Path,
    *,
    work_dir: Path = WORK_DIR,
    containers_dir: Path = CONTAINERS_HOME,
    freesurfer_home: Path = FREESURFER_HOME,
    bids_filter_file: Path | None = None,
    nprocs: int = 16,
    mem_gb: float = 32,
    version: str = "0.19.2",
) -> None:
    smriprep_filepath = _get_smriprep_container(
        directory=containers_dir,
        version=version,
    )

    work_dir.mkdir(exist_ok=True, parents=True)

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
        "--skull-strip-fixed-seed",
        "--nprocs",
        str(nprocs),
        "--mem-gb",
        str(mem_gb),
    ]
    if bids_filter_file is not None:
        options.extend([
            "--bids-filter-file",
            f"/data/{bids_filter_file.relative_to(data_dir)}",
        ])

    logger.info(
        f"Running sMRIPrep for subject {subject}"
        f" using sMRIPrep container at {smriprep_filepath} ..."
    )

    output = subprocess.run(  # noqa: S603
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
