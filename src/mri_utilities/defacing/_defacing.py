import importlib.resources
from contextlib import ExitStack
from typing import TYPE_CHECKING

import ants
import nibabel as nib
import numpy as np
from loguru import logger
from nilearn.image import crop_img

if TYPE_CHECKING:
    from pathlib import Path

deface_package = importlib.resources.files("mri_utilities.defacing")


def deface(
    input_path: Path,
    *,
    output_path: Path | None = None,
    target_template: Path | None = None,
    target_deface_mask: Path | None = None,
    type_of_transform: str = "SyN",
    **registration_kws,  # ruff: ignore[missing-type-kwargs]
) -> None:
    """Deface a NIfTI-1 brain image to anonymize it.

    We use ANTsPy to register the provided image to an anatomical template with
    a corresponding deface mask. The deface mask is resampled back into the
    input space, and a defaced image is written.

    Parameters
    ----------
    input_path
        Path to input NII file.
    output_path, optional
        Path to output file, by default None. If None, will create a new file in
        the parent directory of the input file, prefixed with `deface-`.
    mni_template, optional
        Template image to align the input image to, by default None. If None,
        will use an included 2 mm MNI152 T1 image.
    deface_mask, optional
        Deface mask corresponding to `mni_template`, by default None. If None,
        will use a deface mask corresponding to the included 2 mm MNI152 T1
        image.
    type_of_transform, optional
        Type of transform used in the `ANTs registration step`_, by default "SyN".

        .. _ANTs registration step: https://antspy.readthedocs.io/en/stable/registration.html
    registration_kwargs: optional
        Extra keyword arguments are passed to `ants.registration`.
    """
    with ExitStack() as stack:
        if target_template is None:
            target_template = stack.enter_context(
                importlib.resources.as_file(deface_package / "MNI152_T1_2mm.nii.gz"),
            )

        if target_deface_mask is None:
            target_deface_mask = stack.enter_context(
                importlib.resources.as_file(deface_package / "MNI_mask.nii.gz"),
            )

        source_img = ants.image_read(str(input_path))
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
        source_deface_mask_img = (source_deface_mask_img.numpy() > threshold).astype(
            np.uint8,
        )

        source_img_nii = nib.nifti1.load(input_path)
        masked_source_img = source_img_nii.get_fdata(dtype=np.float32)
        masked_source_img[source_deface_mask_img == 0] = 0

        if output_path is None:
            output_path = input_path.parent / f"defaced-{input_path.name}"

        output_img = nib.nifti1.Nifti1Image(
            masked_source_img.astype(source_img_nii.get_data_dtype()),
            header=source_img_nii.header,
            affine=source_img_nii.affine,
        )
        # remove excessive empty space
        crop_img(output_img).to_filename(output_path)
