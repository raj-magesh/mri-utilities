import subprocess
from typing import TYPE_CHECKING, Literal

from loguru import logger

if TYPE_CHECKING:
    from pathlib import Path


def run_dcm2niix(
    filename: str,
    *,
    input_directory: Path,
    output_directory: Path | None = None,
    bids_sidecar: bool = True,
    anonymize_bids_sidecar: bool = True,
    merge_2d_slices: bool = True,
    single_file_mode: bool = False,
    crop_output: bool = True,
    compress_output: Literal["optimal", "internal"] | bool = "optimal",
    compression_level: Literal[1, 2, 3, 4, 5, 6, 7, 8, 9] = 6,
) -> None:
    match compress_output:
        case "optimal":
            z = "o"
        case "internal":
            z = "i"
        case True:
            z = "y"
        case False:
            z = "n"
        case _:
            raise ValueError

    command = [
        "/usr/bin/env",
        "dcm2niix",
    ]

    options = [
        # create BIDS sidecar
        "-b",
        "y" if bids_sidecar else "n",
        # anonymize BIDS sidecar
        "-ba",
        "y" if anonymize_bids_sidecar else "n",
        # output filename
        "-f",
        filename,
        # merge 2D slices
        "-m",
        "y" if merge_2d_slices else "n",
        # disable single-file mode
        "-s",
        "y" if single_file_mode else "n",
        # crop unnecessary regions
        "-x",
        "y" if crop_output else "n",
        # output compression
        "-z",
        z,
    ]
    if z != "n":
        options.append(f"-{compression_level}")

    if output_directory is not None:
        output_directory.mkdir(exist_ok=True, parents=True)
        options.extend([
            # output directory
            "-o",
            str(output_directory),
        ])

    logger.info(
        "Running dcm2niix on {input_directory} ...",
        input_directory=input_directory,
    )

    output = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
        [
            *command,
            *options,
            str(input_directory),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    logger.debug(output.stdout)

    if output.returncode == 0:
        logger.info("Successfully ran dcm2niix.")
    else:
        logger.error("Failed to run dcm2niix.")
