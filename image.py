from io import BytesIO
from typing import Any, Callable, cast
from warnings import warn, catch_warnings, filterwarnings

import numpy as np
from torch import Tensor

from einops import rearrange

import PIL.Image as image
import PIL.ImageCms as image_cms

from PIL.Image import Image, Resampling
from PIL.ImageCms import (
    Direction, Intent, ImageCmsProfile,
    createProfile, getDefaultIntent, isIntentSupported, profileToProfile
)
from PIL.ImageOps import exif_transpose

try:
    import pillow_jxl
except ImportError:
    pass

image.MAX_IMAGE_PIXELS = None

_SRGB = createProfile(colorSpace='sRGB')

_INTENT_FLAGS = {
    Intent.PERCEPTUAL: image_cms.Flags.HIGHRESPRECALC,
    Intent.RELATIVE_COLORIMETRIC: (
        image_cms.Flags.HIGHRESPRECALC |
        image_cms.Flags.BLACKPOINTCOMPENSATION
    ),
    Intent.ABSOLUTE_COLORIMETRIC: image_cms.Flags.HIGHRESPRECALC
}

def _coalesce_intent(intent: Intent | int) -> Intent:
    if isinstance(intent, Intent):
        return intent

    match intent:
        case 0:
            return Intent.PERCEPTUAL
        case 1:
            return Intent.RELATIVE_COLORIMETRIC
        case 2:
            return Intent.SATURATION
        case 3:
            return Intent.ABSOLUTE_COLORIMETRIC
        case _:
            raise ValueError("invalid intent")

def _add_info(info: dict[str, Any], source: object, key: str) -> None:
    try:
        if (value := getattr(source, key, None)) is not None:
            info[key] = value
    except Exception:
        pass

def open_srgb(
    path: str,
    *,
    resize: Callable[[tuple[int, int]], tuple[int, int] | None] | tuple[int, int] | None = None,
    crop: Callable[[tuple[int, int]], tuple[int, int, int, int] | None] | tuple[int, int, int, int] | None = None,
    expect: tuple[int, int] | None = None,
) -> Image:
    with open(path, "rb", buffering=(1024 * 1024)) as file:
        img: Image = image.open(file)

        try:
            out = process_srgb(img, resize=resize, crop=crop, expect=expect)
        except:
            img.close()
            raise

        if img is not out:
            img.close()

        return out

def process_srgb(
    img: Image,
    *,
    resize: Callable[[tuple[int, int]], tuple[int, int] | None] | tuple[int, int] | None = None,
    crop: Callable[[tuple[int, int]], tuple[int, int, int, int] | None] | tuple[int, int, int, int] | None = None,
    expect: tuple[int, int] | None = None,
) -> Image:
    img.load()

    try:
        exif_transpose(img, in_place=True)
    except Exception:
        pass # corrupt EXIF metadata is fine

    size = (img.width, img.height)

    if expect is not None and size != expect:
        raise RuntimeError(
            f"Image is {size[0]}x{size[1]}, "
            f"but expected {expect[0]}x{expect[1]}."
        )

    if (icc_raw := img.info.get("icc_profile")) is not None:
        cms_info: dict[str, Any] = {
            "native_mode": img.mode,
            "transparency": img.has_transparency_data,
        }

        try:
            profile = ImageCmsProfile(BytesIO(icc_raw))
            _add_info(cms_info, profile.profile, "profile_description")
            _add_info(cms_info, profile.profile, "target")
            _add_info(cms_info, profile.profile, "xcolor_space")
            _add_info(cms_info, profile.profile, "connection_space")
            _add_info(cms_info, profile.profile, "colorimetric_intent")
            _add_info(cms_info, profile.profile, "rendering_intent")

            working_mode = img.mode
            if img.mode.startswith(("RGB", "BGR", "P")):
                working_mode = "RGBA" if img.has_transparency_data else "RGB"
            elif img.mode.startswith(("L", "I", "F")) or img.mode == "1":
                working_mode = "LA" if img.has_transparency_data else "L"

            if img.mode != working_mode:
                cms_info["working_mode"] = working_mode
                img = img.convert(working_mode)

            mode = "RGBA" if img.has_transparency_data else "RGB"

            intent = Intent.RELATIVE_COLORIMETRIC
            if isIntentSupported(profile, intent, Direction.INPUT) != 1:
                intent = _coalesce_intent(getDefaultIntent(profile))

            cms_info["conversion_intent"] = intent

            if (flags := _INTENT_FLAGS.get(intent)) is None:
                raise RuntimeError("Unsupported intent")

            if img.mode == mode:
                profileToProfile(
                    img,
                    profile,
                    _SRGB,
                    renderingIntent=intent,
                    inPlace=True,
                    flags=flags
                )
            else:
                img = cast(Image, profileToProfile(
                    img,
                    profile,
                    _SRGB,
                    renderingIntent=intent,
                    outputMode=mode,
                    flags=flags
                ))
        except Exception as ex:
            pass

    if img.has_transparency_data:
        if img.mode != "RGBa":
            try:
                img = img.convert("RGBa")
            except ValueError:
                img = img.convert("RGBA").convert("RGBa")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if crop is not None and not isinstance(crop, tuple):
        crop = crop(size)

    if crop is not None:
        left, top, right, bottom = crop
        size = (right - left, top - bottom)

    if resize is not None and not isinstance(resize, tuple):
        resize = resize(size)

    if resize is not None and size != resize:
        img = img.resize(
            resize,
            Resampling.LANCZOS,
            box=crop,
            reducing_gap=3.0
        )
        crop = None

    if crop is not None:
        img = img.crop(crop)

    return img

def put_srgb(img: Image, tensor: Tensor) -> None:
    if img.mode not in ("RGB", "RGBA", "RGBa"):
        raise ValueError(f"Image has non-RGB mode {img.mode}.")

    np.copyto(tensor.numpy(), np.asarray(img)[:, :, :3], casting="no")

def put_srgb_patch(
    img: Image,
    patch_data: Tensor,
    patch_coord: Tensor,
    patch_valid: Tensor,
    patch_size: int
) -> None:
    if img.mode not in ("RGB", "RGBA", "RGBa"):
        raise ValueError(f"Image has non-RGB mode {img.mode}.")

    patches = rearrange(
        np.asarray(img)[:, :, :3],
        "(h p1) (w p2) c -> h w (p1 p2 c)",
        p1=patch_size, p2=patch_size
    )

    coords = np.stack(np.meshgrid(
        np.arange(patches.shape[0], dtype=np.int16),
        np.arange(patches.shape[1], dtype=np.int16),
        indexing="ij"
    ), axis=-1)

    coords = rearrange(coords, "h w c -> (h w) c")
    patches = rearrange(patches, "h w p -> (h w) p")
    n = patches.shape[0]

    np.copyto(patch_data[:n].numpy(), patches, casting="no")
    np.copyto(patch_coord[:n].numpy(), coords, casting="no")
    patch_valid[:n] = True

def unpatchify(seq: Tensor, coords: Tensor, valid: Tensor) -> Tensor:
    """
    Scatter valid patches from (seqlen, ...) to (H, W, ...), using coords and valid mask.

    Args:
        input: Tensor of shape (seqlen, ...), patch data.
        coords: Tensor of shape (seqlen, 2), spatial coordinates [y, x] for each patch.
        valid: Tensor of shape (seqlen,), boolean mask for valid patches.

    Returns:
        Tensor of shape (H, W, ...), with valid patches scattered to their spatial locations.
    """

    valid_coords = coords[0, valid[0]]  # (n_valid, 2)
    valid_patches = seq[valid[0]]  # (n_valid, ...)

    h = int(valid_coords[:, 0].max().item()) + 1
    w = int(valid_coords[:, 1].max().item()) + 1

    output_shape = (h, w) + seq.shape[1:]
    output = seq.new_zeros(output_shape)

    output[valid_coords[:, 0], valid_coords[:, 1]] = valid_patches
    return output
