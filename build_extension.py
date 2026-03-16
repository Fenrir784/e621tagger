import os

from argparse import ArgumentParser
from datetime import date
from typing import Any

import torch
from torch import Tensor
from torch.nn.functional import normalize
from safetensors.torch import save_file

TAG_CATEGORIES = [
    "general",
    "artist",
    "copyright",
    "character",
    "species",
    "meta",
    "lore",
]

def _apply_optimizer_state(
    checkpoint: dict[str, torch.Tensor],
    optimizer: dict[str, Any]
) -> None:
    for group in optimizer["param_groups"]:
        if not group.get("train_mode"):
            continue

        z_weight = 1.0 - (1.0 / group["beta1"])

        for idx, name in zip(group["params"], group["param_names"]):
            if not name.startswith("attn_pool."):
                continue

            print(f"  Apply optimizer state: {name}")

            param = checkpoint[name[10:]]
            z = optimizer["state"][idx]["z"]
            param.lerp_(z, z_weight)
            del param, z

@torch.inference_mode()
def main() -> None:
    default_dir = "extensions/jtp-3-hydra"

    parser = ArgumentParser(
        description="JTP-3 Hydra Extension Builder",
        epilog="Visit https://huggingface.co/spaces/RedRocket/JTP-3 for more information.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "-o", "--output-dir",
        metavar="PATH",
        help=f"Directory to save extension to. (Default: {default_dir})"
    )
    parser.add_argument(
        "-r", "--replace", action="store_true",
        help="Overwrite existing extension."
    )
    parser.add_argument(
        "-a", "--author",
        help="SAI modelspec author field."
    )
    parser.add_argument(
        "-l", "--license", default="MIT",
        help="SAI modelspec SPDX licence field. (Default: MIT)"
    )
    parser.add_argument(
        "-T", "--title",
        help="SAI modelspec title field. (Default: 'JTP-3 Hydra Extension: <tag>')."
    )
    parser.add_argument(
        "-L", "--language", default="en/US",
        metavar="LANG",
        help="SAI modelspec language field. (Default: en/US)"
    )

    parser.add_argument(
        "-i", "--implies", action="append", default=[],
        metavar="TAG",
        help="Imply the specified tag. May be specified multiple times."
    )

    parser.add_argument(
        "checkpoint",
        metavar="CHECKPOINT_PATH",
        help="Path to checkpoint."
    )
    parser.add_argument(
        "tag",
        metavar="TAG",
        help="Tag name."
    )
    parser.add_argument(
        "category", choices=TAG_CATEGORIES,
        metavar="CATEGORY",
        help=f"e621 tag category. ({' '.join(TAG_CATEGORIES)})"
    )
    parser.add_argument(
        "file_name", nargs="?",
        metavar="FILE_NAME",
        help="Alternative name for output file, without extension."
    )

    args = parser.parse_args()

    print(f"Loading checkpoint {repr(args.checkpoint)}...")
    data = torch.load(args.checkpoint, weights_only=True, map_location="cpu")
    checkpoint: dict[str, Any] = data["attn_pool"]
    optimizer: dict[str, Any] = data["optimizer"]
    validation: Tensor | None = data["validation"]

    if validation is None:
        print("WARNING: Checkpoint has no validation data. Calibration will not be supported.")

    print("Preparing metadata...")
    if (
        args.tag == ""
        or " " in args.tag
        or "\\" in args.tag
        or "\t" in args.tag
        or "\r" in args.tag
        or "\n" in args.tag
    ):
        parser.error("Invalid tag.")

    if args.file_name is None:
        file_name = args.tag.replace("/", "_").replace(".", "_")
    else:
        file_name = args.file_name

    if (
        file_name == ""
        or "/" in file_name
        or "\\" in file_name
        or "." in file_name
    ):
        parser.error("Invalid file name.")

    for impl in args.implies:
        if (
            impl == ""
            or " " in impl
            or "\\" in impl
            or "\t" in impl
            or "\r" in impl
            or "\n" in impl
        ):
            parser.error("Invalid implication: {repr(impl)}")

    if args.title is None:
        args.title = f"JTP-3 Hydra Extension: {args.tag}"

    if args.output_dir is None:
        args.output_dir = default_dir
        os.makedirs(args.output_dir, exist_ok=True)

    out_path = os.path.join(args.output_dir, f"{file_name}.safetensors")
    if not args.replace and os.path.exists(out_path):
        ex = FileExistsError(f"Extension {repr(out_path)} already exists.")
        ex.add_note("Provide a different file name, or specify --replace to replace the existing extension.")
        raise ex

    metadata = {
        "modelspec.sai_model_spec": "1.0.0",                                  # required
        "modelspec.architecture": "naflexvit_so400m_patch16_siglip+rr_hydra", # essential
        "modelspec.implementation": "redrocket.extension.label.v1",           # essential
        "modelspec.description":
            "This is an extension for the RedRocket JTP-3 Hydra image classifier. "
            "You can find usage instructions at https://huggingface.co/RedRocket/JTP-3."
        ,
        "modelspec.date": str(date.today()),
        "modelspec.tags": "Image Classification",

        "classifier.label": args.tag,                                         # essential
        "classifier.label.category": args.category,                           # technically optional
    }

    if args.title:
        metadata["modelspec.title"] = args.title

    if args.author:
        metadata["modelspec.author"] = args.author

    if args.license:
        metadata["modelspec.license"] = args.license

    if args.language:
        metadata["modelspec.language"] = args.language

    if args.implies:
        metadata["classifier.label.implies"] = ' '.join(sorted(args.implies))

    for key, value in metadata.items():
        print(f"  {key}: {repr(value)}")

    print("Building extension...")
    _apply_optimizer_state(checkpoint, optimizer)

    print("  Normalize: attn_pool.q")
    normalize(checkpoint["q"], dim=-1, eps=1e-5, out=checkpoint["q"])

    if validation is not None:
        checkpoint["validation"] = validation

    del checkpoint["_extra_state"]

    print(f"Saving extension {repr(out_path)}...")
    save_file(checkpoint, out_path, metadata)

if __name__ == "__main__":
    main()
