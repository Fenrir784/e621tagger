import os

from math import ceil
from typing import Iterable, cast

import torch
from torch import Tensor
from torch.nn import Identity

from PIL import Image

from safetensors import safe_open

from image import process_srgb, put_srgb_patch
from siglip2 import NaFlexVit

def sdpa_attn_mask(
    patch_valid: Tensor,
    num_prefix_tokens: int = 0,
    symmetric: bool = True,
    q_len: int | None = None,
    dtype: torch.dtype | None = None,
) -> Tensor:
    mask = patch_valid.unflatten(-1, (1, 1, -1))

    if num_prefix_tokens:
        mask = torch.cat((
            torch.ones(
                *mask.shape[:-1], num_prefix_tokens,
                device=patch_valid.device, dtype=torch.bool
            ), mask
        ), dim=-1)

    return mask

def get_image_size_for_seq(
    image_hw: tuple[int, int],
    patch_size: int = 16,
    max_seq_len: int = 1024,
    max_ratio: float = 1.0,
    eps: float = 1e-5,
) -> tuple[int, int]:
    """Determine image size for sequence length constraint."""

    assert max_ratio >= 1.0
    assert eps * 2 < max_ratio

    h, w = image_hw
    max_py = int(max((h * max_ratio) // patch_size, 1))
    max_px = int(max((w * max_ratio) // patch_size, 1))

    if (max_py * max_px) <= max_seq_len:
        return max_py * patch_size, max_px * patch_size

    def patchify(ratio: float) -> tuple[int, int]:
        return (
            min(int(ceil((h * ratio) / patch_size)), max_py),
            min(int(ceil((w * ratio) / patch_size)), max_px)
        )

    py, px = patchify(eps)
    if (py * px) > max_seq_len:
        raise ValueError(f"Image of size {w}x{h} is too large.")

    ratio = eps
    while (max_ratio - ratio) >= eps:
        mid = (ratio + max_ratio) / 2.0

        mpy, mpx = patchify(mid)
        seq_len = mpy * mpx

        if seq_len > max_seq_len:
            max_ratio = mid
            continue

        ratio = mid
        py = mpy
        px = mpx

        if seq_len == max_seq_len:
            break

    assert py >= 1 and px >= 1
    return py * patch_size, px * patch_size

def process_image(img: Image.Image, patch_size: int, max_seq_len: int) -> Image.Image:
    def compute_resize(wh: tuple[int, int]) -> tuple[int, int]:
        h, w = get_image_size_for_seq((wh[1], wh[0]), patch_size, max_seq_len)
        return w, h

    return process_srgb(img, resize=compute_resize)

def patchify_image(img: Image.Image, patch_size: int, max_seq_len: int, share_memory: bool = False) -> tuple[Tensor, Tensor, Tensor]:
    patches = torch.zeros(max_seq_len, patch_size * patch_size * 3, device="cpu", dtype=torch.uint8)
    patch_coords = torch.zeros(max_seq_len, 2, device="cpu", dtype=torch.int16)
    patch_valid = torch.zeros(max_seq_len, device="cpu", dtype=torch.bool)

    if share_memory:
        patches.share_memory_()
        patch_coords.share_memory_()
        patch_valid.share_memory_()

    put_srgb_patch(img, patches, patch_coords, patch_valid, patch_size)
    return patches, patch_coords, patch_valid

def load_image(
    path: str,
    patch_size: int = 16,
    max_seq_len: int = 1024,
    share_memory: bool = False
) -> tuple[Tensor, Tensor, Tensor]:
    with open(path, "rb", buffering=(1024 * 1024)) as file:
        img: Image.Image = Image.open(file)

        try:
            processed = process_image(img, patch_size, max_seq_len)
        except:
            img.close()
            raise

    if img is not processed:
        img.close()

    return patchify_image(processed, patch_size, max_seq_len, share_memory)

def load_model(
    path: str,
    *,
    extensions: Iterable[str] = (),
    device: torch.device | str | None = None
) -> tuple[NaFlexVit, list[str], dict[str, dict[str, str]]]:
    with safe_open(path, framework="pt", device="cpu") as file:
        metadata = file.metadata()

        state_dict = {
            key: file.get_tensor(key)
            for key in file.keys()
        }

    arch = metadata["modelspec.architecture"]
    if not arch.startswith("naflexvit_so400m_patch16_siglip"):
        raise ValueError(f"Unrecognized model architecture: {arch}")

    labels = metadata["classifier.labels"].split("\n")

    model = NaFlexVit(len(labels), device="cpu", dtype=torch.bfloat16)

    match arch[31:]:
        case "+rr_hydra":
            from hydra_pool import HydraPool
            attn_pool = HydraPool.for_state(
                state_dict, "attn_pool.",
                device=device, dtype=torch.bfloat16
            )

            model.attn_pool = attn_pool          # type: ignore
            model.head = attn_pool.create_head() # type: ignore

            state_dict["attn_pool._extra_state"] = { "q_normed": True }

        case _:
            raise ValueError(f"Unrecognized model architecture: {arch}")

    model.eval()
    model.load_state_dict(state_dict, strict=True)

    setattr(model, "architecture", arch)

    ext_labels: dict[str, str] = {}
    ext_data: list[tuple[int | None, dict[str, Tensor]]] = []
    ext_info: dict[str, dict[str, str]] = {}

    for ext_path in extensions:
        ext_metadata, ext_weights = load_extension(ext_path)
        ext_arch  = ext_metadata["architecture"]
        ext_label = ext_metadata["label"]

        if ext_metadata["architecture"] != arch:
            raise RuntimeError(f"Extension {repr(ext_path)} has incompatible architecture {repr(ext_arch)}, expected {repr(arch)}.")

        if (conflict_path := ext_labels.get(ext_label)) is not None:
            raise RuntimeError(f"Extension {repr(ext_path)} conflicts with extension {repr(conflict_path)} over label {repr(ext_label)}.")

        ext_labels[ext_label] = ext_path

        ext_idx: int | None = None
        try:
            ext_idx = labels.index(ext_label)
        except ValueError:
            labels.append(ext_label)

        ext_data.append((ext_idx, ext_weights))
        ext_info[ext_path] = ext_metadata

    if ext_data:
        attn_pool.load_extensions(ext_data)
        model.num_classes = attn_pool.n_classes

    model.to(device=device)
    return model, labels, ext_info

def load_extension(path: str) -> tuple[dict[str, str], dict[str, Tensor]]:
    with safe_open(path, framework="pt", device="cpu") as file:
        metadata = file.metadata()

        impl = metadata.get("modelspec.implementation")
        match impl:
            case None:
                raise RuntimeError(f"File {repr(path)} is missing SAI modelspec metadata.")

            case "redrocket.extension.label.v1":
                info = {
                    "architecture": metadata["modelspec.architecture"],
                    "label": metadata["classifier.label"],
                    "category": metadata.get("classifier.label.category", "general"),
                    "implies": metadata.get("classifier.label.implies", ""),
                }

            case _:
                raise RuntimeError(f"File {repr(path)} has unrecognized implementation {repr(impl)}.")

        return info, { key: file.get_tensor(key) for key in file.keys() }

def discover_extensions(paths: Iterable[str] | str) -> Iterable[str]:
    if isinstance(paths, str):
        paths = (paths,)

    for path in paths:
        if os.path.isdir(path):
            for entry in os.scandir(path):
                if (
                    entry.is_file()
                    and entry.name.endswith(".safetensors")
                    and not entry.name.startswith(".")
                ):
                    yield entry.path
        else:
            yield path
