import importlib.resources
import tempfile
from contextlib import ExitStack
from pathlib import Path

import ants
import nibabel as nib
import numpy as np
from loguru import logger


def deface(
    img: nib.nifti1.Nifti1Image,
    *,
    target_template: Path | None = None,
    target_deface_mask: Path | None = None,
    type_of_transform: str = "SyN",
    precomputed_mask_path: Path | None = None,
    **registration_kws,  # ruff: ignore[missing-type-kwargs]
) -> tuple[nib.nifti1.Nifti1Image, nib.nifti1.Nifti1Image]:
    """Deface a NIfTI-1 brain image to anonymize it.

    We use ANTsPy to register the provided image to an anatomical template with
    a corresponding deface mask. The deface mask is resampled back into the
    input space, and a defaced image is written.

    Parameters
    ----------
    input_path
        Path to input NII file.
    target_template, optional
        Template image to align the input image to, by default None. If None,
        will use an included 2 mm MNI152 T1 image.
    target_deface_mask, optional
        Deface mask corresponding to `mni_template`, by default None. If None,
        will use a deface mask corresponding to the included 2 mm MNI152 T1
        image.
    type_of_transform, optional
        Type of transform used in the `ANTs registration step`_, by default "SyN".

        .. _ANTs registration step: https://antspy.readthedocs.io/en/stable/registration.html
    precomputed_mask_path, optional
        If provided, this mask will be used directly for defacing and no alignment is performed.
    registration_kwargs: optional
        Extra keyword arguments are passed to `ants.registration`.

    Returns
    -------
        The defaced image and the corresponding defacing mask
    """
    if precomputed_mask_path is None:
        with ExitStack() as stack:
            deface_package = importlib.resources.files("mri_utilities.defacing")

            if target_template is None:
                target_template = stack.enter_context(
                    importlib.resources.as_file(
                        deface_package / "MNI152_T1_2mm.nii.gz",
                    ),
                )

            if target_deface_mask is None:
                target_deface_mask = stack.enter_context(
                    importlib.resources.as_file(deface_package / "MNI_mask.nii.gz"),
                )

            with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as tmp:
                input_path = Path(tmp.name)
                img.to_filename(input_path)

            try:
                source_img = ants.image_read(str(input_path))
            finally:
                input_path.unlink(missing_ok=True)

            target_template_img = ants.image_read(str(target_template))
            target_deface_mask_img = ants.image_read(str(target_deface_mask))

            logger.info("Registering image to MNI space...")
            registration = ants.registration(
                fixed=source_img,
                moving=target_template_img,
                type_of_transform=type_of_transform,
                **registration_kws,
            )

            logger.info("Resampling MNI mask to input space...")
            source_deface_mask_img = ants.apply_transforms(
                fixed=source_img,
                moving=target_deface_mask_img,
                transformlist=registration["fwdtransforms"],
                interpolator="nearestNeighbor",
            )

            threshold = 0.5
            deface_mask = source_deface_mask_img.numpy() > threshold
    else:
        deface_mask = nib.nifti1.load(precomputed_mask_path).get_fdata()

    deface_mask = deface_mask.astype(np.uint8)

    masked = img.get_fdata(dtype=np.float32)
    masked[deface_mask == 0] = 0

    output_img = nib.nifti1.Nifti1Image(
        masked.astype(img.get_data_dtype()),
        header=img.header,
        affine=img.affine,
    )

    output_mask = nib.nifti1.Nifti1Image(
        deface_mask,
        header=img.header,
        affine=img.affine,
    )

    return output_img, output_mask
