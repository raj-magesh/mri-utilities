import os
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from loguru import logger
from platformdirs import user_data_path
from tqdm.auto import tqdm

if containers_home := os.getenv("CONTAINERS_HOME"):
    CONTAINERS_HOME = Path(containers_home)
else:
    CONTAINERS_HOME = user_data_path("containers")


def get_freesurfer_license_path() -> Path:
    fs_license = os.getenv("FS_LICENSE")
    if fs_license is None:
        error = "The environment FS_LICENSE must be set to the path of the FreeSurfer license agreement if fs_license is not provided as an input path!"
        raise ValueError(error)
    return Path(fs_license)


def download_from_url(
    url: str,
    *,
    filepath: Path | None,
    stream: bool = True,
    chunk_size: int = 2**20,
    timeout: float = 10,
    overwrite: bool = False,
    **kwargs,
) -> Path:
    if filepath is not None and filepath.exists():
        if overwrite:
            logger.info("Deleting existing file at {filepath}", filepath=filepath)
            filepath.unlink()
        else:
            logger.info("Using existing file at {filepath}", filepath=filepath)
            return filepath

    logger.info("Downloading from {url} to {filepath}", url=url, filepath=filepath)

    response = requests.get(url, stream=stream, timeout=timeout, **kwargs)

    http_ok_response_code = 200
    if response.status_code != http_ok_response_code:
        response.raise_for_status()
        error = f"Request to {url} returned status code {response.status_code}"
        raise RuntimeError(error)

    # stream url contents to a temporary file
    with (
        tempfile.NamedTemporaryFile(delete=False) as file_handle,
        tqdm(
            total=int(response.headers.get("Content-Length", 0)),
            desc="download",
            unit="B",
            unit_scale=True,
            leave=False,
        ) as progress_bar,
    ):
        for chunk in response.iter_content(chunk_size):
            file_handle.write(chunk)
            progress_bar.update(len(chunk))

    # if filepath is unspecified, return path to temporary file
    if filepath is None:
        return Path(file_handle.name)

    filepath.parent.mkdir(exist_ok=True, parents=True)
    shutil.move(file_handle.name, filepath)
    return filepath


def build_apptainer_container(
    directory: Path,
    *,
    organization: str,
    package: str,
    version: str,
) -> Path:
    filepath = directory / f"{package}-{version}.simg"

    if filepath.exists():
        return filepath

    command = [
        "/usr/bin/env",
        "apptainer",
        "build",
        str(filepath),
        f"docker://{organization}/{package}:{version}",
    ]

    run_command(
        command=command,
        description=f"Building {package}-{version} Apptainer container at {filepath}",
    )

    return filepath


def run_command(
    *,
    command: list[str],
    description: str = "",
) -> subprocess.CompletedProcess:
    logger.debug(
        "{description} command: {command}",
        description=description,
        command=" ".join(command),
    )

    output = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if output.stdout:
        logger.info(
            "{description} stdout: {output}",
            description=description,
            output=output.stdout.rstrip(),
        )

    if output.stderr:
        logger.warning(
            "{description} stderr: {error}",
            description=description,
            error=output.stderr.rstrip(),
        )

    if output.returncode == 0:
        logger.success(
            "Successfully ran command ({description})",
            description=description,
        )
    else:
        logger.error(
            "Failed to run command ({description}) (exit code {code}).",
            description=description,
            code=output.returncode,
        )

    return output


def run_slurm_job(
    *,
    command: list[str],
    description: str,
    slurm_options: list[str],
) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory(prefix=f"{description}-") as tmp:
        tmpdir = Path(tmp)

        script_path = tmpdir / f"{description}.sh"
        write_srun_script(path=script_path, command=command)

        return run_command(
            command=[
                "sbatch",
                "--parsable",
                *slurm_options,
                str(script_path),
            ],
            description=description,
        )


def write_srun_script(*, path: Path, command: list[str]) -> None:
    path.write_text(
        f"#!/usr/bin/env bash\nset -euo pipefail\nsrun {shlex.join(command)}\n",
        encoding="UTF-8",
    )
