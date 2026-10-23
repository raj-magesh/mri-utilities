from typing import TYPE_CHECKING

from mri_utilities._utilities import run_command

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def run_heudiconv(
    *,
    dicoms: list[Path],
    output_directory: Path,
    heuristic: Path,
    subject: str,
    extra_options: Sequence[str] = (),
) -> None:
    output_directory.parent.mkdir(exist_ok=True, parents=True)

    command = [
        "/usr/bin/env",
        "heudiconv",
        "--files",
        *[str(filepath) for filepath in dicoms],
        "--outdir",
        str(output_directory),
        "--heuristic",
        str(heuristic),
        "--subjects",
        subject,
        "--converter",
        "dcm2niix",
        "--bids",
        "notop",
        "--minmeta",
        "--overwrite",
        "--random-seed",
        "0",
        *extra_options,
    ]

    run_command(
        command=command,
        description=f"HeuDiConv for sub-{subject}",
    )
