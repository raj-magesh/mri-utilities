import tempfile
from pathlib import Path

import requests
from loguru import logger
from tqdm.auto import tqdm

HTTP_OK_RESPONSE_CODE = 200


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
            logger.info(f"Deleting existing file at {filepath}")
            filepath.unlink()
        else:
            logger.info(f"Using existing file at {filepath}")
            return filepath

    logger.info(f"Downloading from {url} to {filepath}")

    response = requests.get(url, stream=stream, timeout=timeout, **kwargs)

    if response.status_code != HTTP_OK_RESPONSE_CODE:
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
    Path(file_handle.name).move(filepath)
    return filepath
