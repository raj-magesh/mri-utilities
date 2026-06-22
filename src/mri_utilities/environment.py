import os
from pathlib import Path

if freesurfer_home := os.getenv("FREESURFER_HOME"):
    FREESURFER_HOME = Path(freesurfer_home)
elif xdg_data_home := os.getenv("XDG_DATA_HOME"):
    FREESURFER_HOME = Path(xdg_data_home) / "freesurfer"
else:
    FREESURFER_HOME = Path.home() / ".local" / "share" / "freesurfer"

if containers_home := os.getenv("CONTAINERS_HOME"):
    CONTAINERS_HOME = Path(containers_home)
elif xdg_data_home := os.getenv("XDG_DATA_HOME"):
    CONTAINERS_HOME = Path(xdg_data_home) / "containers"
else:
    CONTAINERS_HOME = Path.home() / ".local" / "share" / "containers"
