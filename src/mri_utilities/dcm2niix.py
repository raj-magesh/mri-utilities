from typing import TYPE_CHECKING, Literal

from mri_utilities._utilities import run_command

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

    run_command(
        command=[
            "/usr/bin/env",
            "dcm2niix",
            *options,
            str(input_directory),
        ],
        description=f"dcm2niix on {input_directory}",
    )
