import os
import shutil

from argparse import ArgumentParser
from typing import Iterable

from safetensors import safe_open
from safetensors.torch import save_file

def _backup_paths(path: str) -> Iterable[str]:
    yield f"{path}.bak"

    i = 1
    while True:
        yield f"{path}.{i}.bak"
        i += 1

def main() -> None:
    parser = ArgumentParser(
        description="Safetensors Metadata Editor",
        allow_abbrev=False,
    )
    parser.add_argument(
        "-B", "--no-backup", action="store_true",
        help="Do not save a backup of the original file."
    )
    parser.add_argument(
        "-o", "--output",
        metavar="PATH",
        help="Write to the specified path instead of overwriting. A backup will not be created."
    )

    parser.add_argument(
        "file",
        metavar="PATH",
        help="Path to safetensors file."
    )
    parser.add_argument(
        "metadata", nargs="*",
        metavar="KEY=[VALUE]",
        help=(
            "New metadata values. If value is empty, delete the specified key. "
            "If no keys are specified, the current metadata is displayed instead."
        )
    )

    args = parser.parse_args()

    with safe_open(args.file, framework="pt", device="cpu") as file:
        metadata = file.metadata()
        data = {
            key: file.get_tensor(key)
            for key in file.keys()
        }

    if not args.metadata:
        if args.output is not None:
            parser.error("Cannot specify --output with no changes.")

        for key, value in sorted(metadata.items()):
            print(f"{repr(key)}: {repr(value)}")

        return

    for arg in args.metadata:
        parts = arg.split('=', 1)
        if len(parts) != 2 or not parts[0]:
            parser.error(f"Invalid argument: {repr(arg)}")

        if parts[1]:
            metadata[parts[0]] = parts[1]
        else:
            metadata.pop(parts[0], None)

    if args.output is None:
        out_path = args.file

        if not args.no_backup:
            for bak in _backup_paths(args.file):
                if not os.path.exists(bak):
                    shutil.copy2(args.file, bak)
                    break
    else:
        out_path = args.output

    save_file(data, out_path, metadata)

if __name__ == "__main__":
    main()
