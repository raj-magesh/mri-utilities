import gzip
import shutil
import subprocess
from pathlib import Path

import click
from loguru import logger

# FIXME reimplement download_from_url to avoid dependency on neurodatasets.files
from neurodatasets.files import download_from_url

from .environment import CONTAINERS_HOME, FREESURFER_HOME
from .smriprep import _get_smriprep_container


def _prepare_mri_deface_utilities(
    freesurfer_home: Path = FREESURFER_HOME,
) -> tuple[Path, Path]:
    directory = freesurfer_home / "mri_deface"
    directory.mkdir(exist_ok=True, parents=True)

    url = "https://surfer.nmr.mgh.harvard.edu/pub/dist/mri_deface"

    filenames = ("talairach_mixed_with_skull.gca.gz", "face.gca.gz")
    for filename in filenames:
        if not (directory / filename).with_suffix("").exists():
            filepath = download_from_url(
                url=f"{url}/{filename}",
                filepath=directory / filename,
            )
            with (
                gzip.open(filepath, "rb") as f_compressed,
                filepath.with_suffix("").open("wb") as f_decompressed,
            ):
                shutil.copyfileobj(f_compressed, f_decompressed)

    return tuple((directory / filename).with_suffix("") for filename in filenames)


@click.command()
@click.argument(
    "input-path",
    type=click.Path(dir_okay=False, exists=True, path_type=str),
    nargs=1,
)
@click.option(
    "--output-path",
    type=click.Path(path_type=Path),
)
@click.option(
    "--freesurfer-home",
    default=FREESURFER_HOME,
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    help="directory containing FreeSurfer license.txt file",
)
@click.option(
    "--containers-dir",
    default=CONTAINERS_HOME,
    type=click.Path(file_okay=False, path_type=Path),
    help="path where sMRIPrep Apptainer container should be placed",
)
@click.option(
    "--version", default="0.19.2", type=click.STRING, help="sMRIPrep version to use"
)
def run_mri_deface(
    input_path: Path,
    *,
    output_path: Path | None = None,
    freesurfer_home: Path = FREESURFER_HOME,
    containers_dir: Path = CONTAINERS_HOME,
    version: str = "0.19.2",
) -> None:
    smriprep_filepath = _get_smriprep_container(
        directory=containers_dir,
        version=version,
    )
    talairach_path, face_path = _prepare_mri_deface_utilities(freesurfer_home)

    command_prefix = [
        "/usr/bin/env",
        "apptainer",
        "exec",
        "--cleanenv",
        "--bind",
        f"{input_path.parent}:/input_dir",
        "--bind",
        f"{freesurfer_home}:/freesurfer",
        "--env",
        "FS_LICENSE=/freesurfer/license.txt",
    ]

    arguments = [
        str(smriprep_filepath),
        "mri_deface",
        f"/input_dir/{input_path.name}",
        f"/freesurfer/{talairach_path.relative_to(freesurfer_home)}",
        f"/freesurfer/{face_path.relative_to(freesurfer_home)}",
    ]
    if output_path is None:
        arguments.append(f"/input_dir/mri_deface-{input_path.name}")
    else:
        output_path.parent.mkdir(exist_ok=True, parents=True)
        command_prefix.extend(["--bind", f"{output_path.parent}:/output_dir"])
        arguments.append(f"/output_dir/{output_path.name}")

    logger.info(
        f"Running mri_deface on {input_path}"
        f" using sMRIPrep container at {smriprep_filepath} ..."
    )

    output = subprocess.run(  # noqa: S603
        [
            *command_prefix,
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info("Successfully ran mri_deface.")
    else:
        logger.error("Failed to run mri_deface.")
