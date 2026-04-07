import os
from pathlib import Path

from xdg_base_dirs import xdg_data_home

FREESURFER_HOME = Path(
    os.getenv(
        "FREESURFER_HOME",
        str(xdg_data_home() / "freesurfer"),
    ),
)

CONTAINERS_HOME = Path(
    os.getenv(
        "CONTAINERS_HOME",
        str(xdg_data_home() / "containers"),
    ),
)
