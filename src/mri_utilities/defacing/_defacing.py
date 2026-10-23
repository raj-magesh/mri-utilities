import importlib.resources

import nibabel as nib
import numpy as np
from dipy.align import affine_registration
from dipy.align.imaffine import AffineMap


def deface(
    img: nib.nifti1.Nifti1Image,
    *,
    template_img: nib.nifti1.Nifti1Image | None = None,
    template_mask: nib.nifti1.Nifti1Image | None = None,
    precomputed_mask: nib.nifti1.Nifti1Image | None = None,
    **registration_kws,  # ruff: ignore[missing-type-kwargs]
) -> tuple[nib.nifti1.Nifti1Image, nib.nifti1.Nifti1Image]:
    """Deface a NIfTI-1 brain image to anonymize it.

    Adapted from https://github.com/neurolabusc/mydeface.

    We use DIPY to register an anatomical template with a corresponding defacing mask to the provided image. The defacing mask is resampled into the input space and applied to the input image. Then, the defaced image and its corresponding defacing mask are returned.

    Parameters
    ----------
    img
        Input image to deface.
    template_img, optional
        Template image to align to the input image, by default None. If None,
        uses the PyDeface template.
    template_mask, optional
        Defacing mask corresponding to `template_img`, by default None. If None, uses the PyDeface defacing mask.
    precomputed_mask, optional
        If provided, this mask will be used directly for defacing and no alignment is performed.
    registration_kwargs: optional
        Extra keyword arguments passed to `dipy.align.affine_registration`.

    Returns
    -------
        The defaced image and its corresponding defacing mask
    """
    if precomputed_mask is None:
        if template_img is None or template_mask is None:
            deface_package = importlib.resources.files("mri_utilities.defacing")
            with (
                importlib.resources.as_file(
                    deface_package / "pydeface" / "template.nii.gz",
                ) as f_template,
                importlib.resources.as_file(
                    deface_package / "pydeface" / "mask.nii.gz",
                ) as f_mask,
            ):
                template_img = nib.nifti1.load(f_template)
                template_mask = nib.nifti1.load(f_mask)

        _, affine = affine_registration(
            moving=template_img,
            static=img,
            **{"sampling_proportion": 0.2} | registration_kws,
        )

        affine_map = AffineMap(
            affine,
            codomain_grid_shape=template_mask.shape,
            codomain_grid2world=template_mask.affine,
            domain_grid_shape=img.shape,
            domain_grid2world=img.affine,
        )

        deface_mask = affine_map.transform(
            template_mask.get_fdata(),
            interpolation="linear",
        )

        threshold = 0.5
        deface_mask = deface_mask > threshold
    else:
        deface_mask = precomputed_mask.get_fdata()

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
