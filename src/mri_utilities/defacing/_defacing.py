import importlib.resources

import nibabel as nib
import numpy as np
from dipy.align import affine_registration
from dipy.align.imaffine import AffineMap


def deface(
    source_img: nib.nifti1.Nifti1Image,
    *,
    target_template_img: nib.nifti1.Nifti1Image | None = None,
    target_deface_mask: nib.nifti1.Nifti1Image | None = None,
    precomputed_mask: nib.nifti1.Nifti1Image | None = None,
    **registration_kws,  # ruff: ignore[missing-type-kwargs]
) -> tuple[nib.nifti1.Nifti1Image, nib.nifti1.Nifti1Image]:
    """Deface a NIfTI-1 brain image to anonymize it.

    Adapted from https://github.com/neurolabusc/mydeface.

    We use DIPY to register the provided image to an anatomical template with
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
    precomputed_mask, optional
        If provided, this mask will be used directly for defacing and no alignment is performed.
    registration_kwargs: optional
        Extra keyword arguments passed to `dipy.align._public.syn_registration`.

    Returns
    -------
        The defaced image and the corresponding defacing mask
    """
    if precomputed_mask is None:
        deface_package = importlib.resources.files("mri_utilities.defacing")

        if target_template_img is None:
            with importlib.resources.as_file(
                deface_package / "MNI152_T1_2mm.nii.gz",
            ) as f:
                target_template_img = nib.nifti1.load(f)

        with importlib.resources.as_file(deface_package / "MNI_mask.nii.gz") as f:
            target_deface_mask = nib.nifti1.load(f)

        _, affine = affine_registration(
            moving=target_template_img,
            static=source_img,
            moving_affine=source_img.affine,
            static_affine=target_template_img.affine,
            pipeline=["translation", "rigid", "affine"],
            **{"sampling_proportion": 0.2} | registration_kws,
        )

        affine_map = AffineMap(
            affine,
            domain_grid_shape=source_img.shape,
            domain_grid2world=source_img.affine,
            codomain_grid_shape=target_deface_mask.shape,
            codomain_grid2world=target_deface_mask.affine,
        )

        deface_mask = affine_map.transform(
            target_deface_mask.get_fdata(),
            interpolation="linear",
        )

        threshold = 0.5
        deface_mask = deface_mask > threshold
    else:
        deface_mask = precomputed_mask.get_fdata()

    deface_mask = deface_mask.astype(np.uint8)

    masked = source_img.get_fdata(dtype=np.float32)
    masked[deface_mask == 0] = 0

    output_img = nib.nifti1.Nifti1Image(
        masked.astype(source_img.get_data_dtype()),
        header=source_img.header,
        affine=source_img.affine,
    )

    output_mask = nib.nifti1.Nifti1Image(
        deface_mask,
        header=source_img.header,
        affine=source_img.affine,
    )

    return output_img, output_mask
