import argparse
import os
import sys

from math import ceil
from signal import signal, Signals
from random import Random
from time import strftime
from typing import Any, Iterable, cast

if "PYTORCH_CUDA_ALLOC_CONF" not in os.environ:
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "backend:cudaMallocAsync"

import torch
from torch import Tensor
from torch.nn import Module
from torch.nn.functional import binary_cross_entropy_with_logits as bce

from safetensors.torch import load_file, save_file

from tqdm import tqdm

from hydra_pool import HydraPool
from loader import Loader
from model import load_model
from siglip2 import NaFlexVit
from optimizer.bf16sr_adamwsf import AdamWSFSR

try:
    from itertools import batched
except ImportError:
    from itertools import islice

    # polyfill for python 3.11
    def batched(iterable, n: int):
        it = iter(iterable)
        while batch := tuple(islice(it, n)):
            yield batch

def _is_fresh(path: str, cpath: str, check_mtime: bool) -> bool:
    if not check_mtime:
        return os.path.isfile(cpath)

    pstat = os.stat(path)

    try:
        cstat = os.stat(cpath)
    except OSError:
        return False

    return cstat.st_mtime_ns >= pstat.st_mtime_ns

@torch.inference_mode()
def cache_features(
    model: NaFlexVit,
    loader: Loader,
    files: Iterable[tuple[str, bool]],
    *,
    batch_size: int,
    cache_tag: str,
    rebuild_cache: bool = False,
    check_mtime: bool = True,
    device: torch.device | str,
) -> list[tuple[str, bool]]:
    if batch_size < 1:
        raise ValueError("Batch size must be positive.")

    if (
        cache_tag.startswith(".")
        or "/" in cache_tag
        or "\\" in cache_tag
    ):
        raise ValueError("Invalid cache tag.")

    cached_files: list[tuple[str, bool]] = []
    uncached_files: list[tuple[str, str, bool]] = []

    for path, label in files:
        cdir, cname = os.path.split(path)

        cdir = os.path.join(cdir, "_cache")
        cname = f"{cache_tag}__{cname}.safetensors"
        cpath = os.path.join(cdir, cname)

        if not rebuild_cache and _is_fresh(path, cpath, check_mtime):
            cached_files.append((cpath, label))
            continue

        if not os.path.isdir(cdir):
            os.mkdir(cdir)

        uncached_files.append((path, cpath, label))

    if not uncached_files:
        return cached_files

    n_failed = 0
    pbar = tqdm(
        desc="caching",
        initial=len(cached_files),
        total=len(cached_files) + len(uncached_files),
        smoothing=0.01, miniters=batch_size,
        dynamic_ncols=True, leave=True
    )

    for batch in batched(uncached_files, batch_size):
        batch_files = {
            path: (cpath, label)
            for path, cpath, label in batch
        }

        output_files: list[tuple[str, bool]] = []
        patches: list[Tensor] = []
        patch_coords: list[Tensor] = []
        patch_valid: list[Tensor] = []
        for path, result in loader.load(batch_files.keys()).items():
            if not isinstance(result, Exception):
                output_files.append(batch_files[path])
                patches.append(result[0])
                patch_coords.append(result[1])
                patch_valid.append(result[2])
            else:
                n_failed += 1
                pbar.write(f"{repr(path)}: {result}", file=sys.stderr)
                pbar.set_postfix_str(f"failed={n_failed}", refresh=False)
                pbar.update()

            del result

        if not output_files:
            continue

        patches_t = torch.stack(patches).to(device=device, non_blocking=True)
        patch_coords_t = torch.stack(patch_coords).to(device=device, non_blocking=True)
        patch_valid_t = torch.stack(patch_valid).to(device=device, non_blocking=True)
        del patches, patch_coords

        patches_t = patches_t.to(dtype=torch.bfloat16).div_(127.5).sub_(1.0)
        patch_coords_t = patch_coords_t.to(dtype=torch.int32)

        features = cast(dict[str, Tensor], model.forward_features(
            patches_t, patch_coords_t, patch_valid_t
        ))["patches"]
        del patches_t, patch_coords_t, patch_valid_t

        for idx, (cpath, label) in enumerate(output_files):
            seqlen = patch_valid[idx].count_nonzero()

            try:
                save_file({ "features": features[idx, :seqlen] }, cpath)
                cached_files.append((cpath, label))
            except OSError as ex:
                n_failed += 1
                pbar.set_postfix_str(f"failed={n_failed}", refresh=False)
                pbar.write(f"{repr(cpath)}: {ex}", file=sys.stderr)

            del seqlen
            pbar.update()

        del features, patch_valid

    pbar.close()

    return cached_files

def load_dataset(
    model: NaFlexVit,
    data_dir: str,
    *,
    rng: Random,
    n_validation: int,
    n_loaders: int = -1,
    batch_size: int,
    cache_tag: str,
    cache_shm: bool = True,
    check_mtime: bool = True,
    rebuild_cache: bool = False,
    device: torch.device | str,
) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]], float]:
    n_validation = max(n_validation, 0)

    dataset = [
        *(
            (entry.path, True)
            for entry in os.scandir(os.path.join(data_dir, "positive"))
            if (
                entry.is_file()
                and not entry.name.startswith(".")
                and not entry.name.endswith((".txt", ".csv"))
            )
        ),
        *(
            (entry.path, False)
            for entry in os.scandir(os.path.join(data_dir, "negative"))
            if (
                entry.is_file()
                and not entry.name.startswith(".")
                and not entry.name.endswith((".txt", ".csv"))
            )
        )
    ]

    loader = Loader(n_loaders, share_memory=cache_shm)
    try:
        cached = cache_features(
            model, loader, dataset,
            batch_size=batch_size,
            cache_tag=cache_tag,
            check_mtime=check_mtime,
            rebuild_cache=rebuild_cache,
            device=device,
        )
    finally:
        loader.shutdown()

    cached.sort()
    rng.shuffle(cached)

    pos_cached = [
        path
        for path, label in cached
        if label
    ]

    neg_cached = [
        path
        for path, label in cached
        if not label
    ]

    if len(pos_cached) <= n_validation:
        raise ValueError("Positive training set is empty.")

    if len(neg_cached) <= n_validation:
        raise ValueError("Negative training set is empty.")

    train_set = [
        *((path, True) for path in pos_cached[n_validation:]),
        *((path, False) for path in neg_cached[n_validation:]),
    ]
    train_set.sort()

    val_set = [
        *((path, True) for path in pos_cached[:n_validation]),
        *((path, False) for path in neg_cached[:n_validation]),
    ]
    val_set.sort()

    return train_set, val_set, len(pos_cached) / len(neg_cached)

def _load_batch(
    batch: tuple[tuple[str, bool], ...],
    *,
    max_seqlen: int = 1024,
    feature_dim: int = 1152,
    device: torch.device
) -> tuple[Tensor, Tensor, Tensor]:
    features = torch.zeros(
        (len(batch), max_seqlen, feature_dim),
        device=device, dtype=torch.bfloat16
    )
    attn_mask = torch.zeros(
        (len(batch), 1, 1, max_seqlen),
        device=device, dtype=torch.bool
    )
    targets = torch.empty(
        len(batch),
        device="cpu", dtype=torch.bool
    )

    for idx, (path, target) in enumerate(batch):
        f = load_file(path, device="cpu")["features"]

        features[idx, :f.size(0)].copy_(f, non_blocking=True)
        attn_mask[idx, :f.size(0)].fill_(True)
        targets[idx] = target

    targets = targets.to(device=device, non_blocking=True)
    return features, attn_mask, targets

@torch.compile(mode="max-autotune-no-cudagraphs")
def _train_step(
    attn_pool: HydraPool, head: Module,
    features: Tensor, attn_mask: Tensor, targets: Tensor,
    grad_scale: Tensor,
) -> Tensor:
    outputs = head(attn_pool(features, attn_mask)).squeeze(-1)
    loss = bce(outputs, targets.to(dtype=torch.bfloat16))

    (loss * grad_scale).backward()

    return loss

def _train_epoch(
    attn_pool: HydraPool, head: Module,
    train_set: list[tuple[str, bool]],
    batch_size: int, grad_acc: int,
    optimizer: AdamWSFSR, device: torch.device,
    pbar: tqdm, total_steps: int
) -> int:
    grad_scale = torch.tensor(
        1.0 / grad_acc,
        device=device, dtype=torch.bfloat16
    )

    for idx, batch in enumerate(batched(train_set, batch_size)):
        features, attn_mask, targets = _load_batch(batch, device=device)
        loss = _train_step(attn_pool, head, features, attn_mask, targets, grad_scale)
        del features, attn_mask, targets

        acc = (idx % grad_acc) + 1
        if acc == grad_acc:
            optimizer.step()
            optimizer.zero_grad(grad_acc == 1)

        total_steps += 1
        pbar.set_postfix_str(
            f"step={total_steps} acc={acc}/{grad_acc} loss={loss.item():.4f}",
            refresh=False
        )
        pbar.update()

        del loss

    return total_steps

@torch.compile(mode="max-autotune-no-cudagraphs")
def _validation_step(
    attn_pool: HydraPool, head: Module,
    features: Tensor, attn_mask: Tensor, targets: Tensor,
    thresholds: Tensor
) -> tuple[Tensor, Tensor]:
    outputs = head(attn_pool(features, attn_mask)).squeeze(-1)
    loss = bce(outputs, targets.to(dtype=torch.bfloat16), reduction="sum")

    pos = outputs[None, :] >= thresholds[:, None]
    targets = targets[None, :]

    tp = ( pos &  targets).count_nonzero(1)
    fp = ( pos & ~targets).count_nonzero(1)
    tn = (~pos & ~targets).count_nonzero(1)
    fn = (~pos &  targets).count_nonzero(1)

    return loss, torch.stack((tp, fp, tn, fn), dim=1)

@torch.no_grad()
def _validation_epoch(
    attn_pool: HydraPool, head: Module,
    validation_set: list[tuple[str, bool]],
    batch_size: int, epoch: int, n_buckets: int,
    device: torch.device,
    pbar: tqdm,
) -> Tensor:
    thresholds = torch.linspace(
        0.0, 1.0, n_buckets + 2,
        device=device, dtype=torch.float32
    )[1:-1].logit_().to(dtype=torch.bfloat16)

    loss = torch.zeros((), device=device, dtype=torch.float32)
    results = torch.zeros((n_buckets, 4), device=device, dtype=torch.int32)

    for batch in batched(validation_set, batch_size):
        features, attn_mask, targets = _load_batch(batch, device=device)
        batch_loss, batch_results = _validation_step(
            attn_pool, head,
            features, attn_mask, targets,
            thresholds
        )
        del features, attn_mask, targets

        loss.add_(batch_loss)
        results.add_(batch_results)

        pbar.set_postfix_str(f"loss={loss.item():.4f}", refresh=False)
        pbar.update()

        del batch_loss, batch_results

    tp, fp, _, fn = results.unbind(dim=1)
    cti = tp / (tp + fp + fn)

    best_cti, best_idx = cti.max(dim=0)
    best_threshold = thresholds[best_idx].float().sigmoid_().item()
    epoch_loss = loss.item() / len(validation_set)
    pbar.write(
        f"EPOCH {epoch} VALIDATION: "
        f"loss={epoch_loss:.4f}, "
        f"cti={best_cti.item():.4f}, "
        f"thr={best_threshold:.4f}"
    )

    return results

def _save_checkpoint(
    checkpoint_dir: str,
    state: dict[str, Any],
    pbar: tqdm
) -> None:
    path = os.path.join(
        checkpoint_dir,
        strftime("%Y%m%d%-H%M%S") + f"_e{state['epoch']}.pt"
    )

    pbar.write(f"Saving checkpoint {repr(path)} ... ", end="")
    torch.save(state, path)
    pbar.write("Done.")

def train(
    attn_pool: HydraPool,
    head: Module,
    train_set: list[tuple[str, bool]],
    val_set: list[tuple[str, bool]],
    checkpoint_dir: str,
    *,
    batch_size: int,
    grad_acc: int,
    hyperparams: dict[str, Any],
    rng: Random,
    seed: int,
    init_from_tag: int | None = None,
    resume_state: dict[str, Any] | None = None,
    max_epochs: int = 0,
    checkpoint_interval: int = 0,
    validation_buckets: int = 99,
    device: torch.device,
) -> None:
    max_epochs = max(max_epochs, 0)

    if batch_size < 1:
        raise ValueError("Batch size must be at least 1.")

    if grad_acc < 1:
        raise ValueError("Gradient accumulation steps must be at least 1.")

    opt_steps = len(train_set) // (batch_size * grad_acc)
    if opt_steps == 0:
        raise ValueError("Accumulated batch size is larger than a single epoch.")

    if resume_state is None:
        if init_from_tag is None:
            attn_pool.reset_classes(1)
        else:
            attn_pool.select_classes(init_from_tag)

        epoch = 0
    else:
        if init_from_tag is not None:
            raise ValueError("Cannot specify both resume_state and init_from_tag.")

        attn_pool.reset_classes(1)
        attn_pool.load_state_dict(resume_state["attn_pool"])

        epoch = resume_state["epoch"]
        rng.setstate(resume_state["rng_state"])

        if epoch >= max_epochs > 0:
            raise ValueError("Checkpoint has already reached maximum epoch.")

    attn_pool.train()
    attn_pool.requires_grad_(False)

    params = [
        ("attn_pool.q", attn_pool.q),
        ("attn_pool.out_proj.weight", attn_pool.out_proj.weight),
        *(
            (f"attn_pool.mid_blocks.{idx}.q_cls", cast(Tensor, block.q_cls))
            for idx, block in enumerate(attn_pool.mid_blocks)
        )
    ]
    for _, param in params:
        param.requires_grad_(True)

        if grad_acc > 1:
            param.grad = torch.zeros_like(param)

    optimizer = AdamWSFSR([{ "params": params }], **hyperparams)
    if resume_state is not None:
        optimizer.load_state_dict(resume_state["optimizer"])

    del resume_state

    optimizer.train()

    train_steps = opt_steps * grad_acc
    val_steps = int(ceil(len(val_set) / batch_size))
    total_steps = 0

    pbar = tqdm(
        desc=f"epoch {epoch}", total=train_steps,
        miniters=1, smoothing=0.01,
        dynamic_ncols=True, leave=True
    )
    pbar.set_postfix_str(f"step=0 acc=0/{grad_acc}")

    interrupted = False
    def interrupt(_signum, _frame) -> None:
        nonlocal interrupted

        if interrupted:
            raise KeyboardInterrupt

        interrupted = True
        pbar.write("Interrupted. Stopping at the end of this epoch.")

    signal(Signals.SIGINT, interrupt)

    while True:
        train_sample = rng.sample(train_set, train_steps * batch_size)
        rng.shuffle(train_sample)

        total_steps = _train_epoch(
            attn_pool, head,
            train_sample,
            batch_size, grad_acc,
            optimizer, device,
            pbar, total_steps,
        )

        epoch += 1

        val_data: Tensor | None = None
        if val_set:
            attn_pool.eval()
            optimizer.eval()

            with tqdm(
                desc="validation", total=val_steps,
                miniters=1, smoothing=0.01,
                position=1, dynamic_ncols=True, leave=False
            ) as vbar:
                val_data = _validation_epoch(
                    attn_pool, head,
                    val_set,
                    batch_size, epoch, validation_buckets,
                    device,
                    vbar,
                )

            attn_pool.train()
            optimizer.train()

        last_epoch = interrupted or epoch >= max_epochs > 0
        if last_epoch or (
            checkpoint_interval > 0
            and epoch % checkpoint_interval == checkpoint_interval - 1
        ):
            _save_checkpoint(checkpoint_dir, {
                "seed": seed,
                "epoch": epoch,
                "rng_state": rng.getstate(),
                "attn_pool": attn_pool.state_dict(),
                "optimizer": optimizer.state_dict(),
                "validation": val_data,
            }, pbar)

        if last_epoch:
            break

        pbar.last_print_n = 0
        pbar.n = 0
        pbar.set_description(f"epoch {epoch}")
        pbar.unpause()

def main() -> None:
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch._dynamo.config.compiled_autograd = True

    parser = argparse.ArgumentParser(
        description="JTP-3 Hydra Extension Trainer",
        epilog="Visit https://huggingface.co/spaces/RedRocket/JTP-3 for more information.",
        allow_abbrev=False,
    )

    parser.add_argument(
        "-D", "--dir", default="train",
        metavar="PATH",
        help="Path to working directory. (Default: train)"
    )
    parser.add_argument(
        "-M", "--model", default="models/jtp-3-hydra.safetensors",
        metavar="PATH",
        help="Path to model file. (Default: models/jtp-3-hydra.safetensors)"
    )
    parser.add_argument(
        "-d", "--device", default="cuda",
        metavar="TORCH_DEVICE",
        help="Torch device. (Default: cuda)"
    )

    group = parser.add_argument_group("initialization")
    group.add_argument(
        "-r", "--resume",
        metavar="CHECKPOINT",
        help="Resume from checkpoint. Path relative to <dir>/checkpoints."
    )
    group.add_argument(
        "-s", "--seed", type=int,
        metavar="SEED",
        help="Random seed. (Default: 3407)"
    )
    group.add_argument(
        "-i", "--init-from-tag",
        metavar="TAG",
        help="Initialize from the specified tag."
    )

    group = parser.add_argument_group("training")
    group.add_argument(
        "-b", "--batch", type=int, default=16,
        metavar="BATCH_SIZE",
        help="Training batch size. (Default: 16)"
    )
    group.add_argument(
        "-a", "--accumulate", type=int, default=1,
        metavar="STEPS",
        help="Gradient accumulation steps. (Default: 1)"
    )
    group.add_argument(
        "-e", "--max-epochs", type=int, default=0,
        metavar="EPOCH",
        help="Maximum number of epochs to train. (0 means unlimited; default: 0)"
    )
    group.add_argument(
        "-c", "--checkpoint-interval", type=int, default=0,
        metavar="EPOCHS",
        help="Checkpoint interval in epochs. (0 means disabled; default: 0)"
    )
    group.add_argument(
        "-v", "--validation-samples", type=int, default=20,
        metavar="COUNT",
        help="Number of positive and negative samples to use for validation. (Default: 20)"
    )
    group.add_argument(
        "-T", "--validation-thresholds", type=int, default=99,
        metavar="COUNT",
        help="Number of thresholds to check for validation. (Default: 99)"
    )
    group.add_argument(
        "--force", action="store_true",
        help="Ignore sanity checks and train anyways."
    )

    group = parser.add_argument_group("hyperparameters")
    group.add_argument(
        "--lr", type=float,
        metavar="LEARNING_RATE",
        help="AdamWSF Learning rate. (Default: 1e-4)"
    )
    group.add_argument(
        "--beta1", type=float,
        metavar="VALUE",
        help="AdamWSF beta1. (Default: 0.9)"
    )
    group.add_argument(
        "--beta2", type=float,
        metavar="VALUE",
        help="AdamWSF beta2. (Default: 0.999)"
    )
    group.add_argument(
        "--beta1-c", type=float,
        metavar="DECOUPLING",
        help="AdamWSF beta1 decoupling constant. (Default: 200)"
    )
    group.add_argument(
        "--weight-decay", type=float,
        metavar="VALUE",
        help="AdamWSF weight decay. (Default: 1e-2)"
    )
    group.add_argument(
        "--warmup-steps", type=int,
        metavar="STEPS",
        help="AdamWSF warmup steps. (Default: 20)"
    )

    group = parser.add_argument_group("caching")
    group.add_argument(
        "-B", "--cache-batch", type=int, default=4,
        metavar="BATCH_SIZE",
        help="Caching batch size. (Default: 4)"
    )
    group.add_argument(
        "-W", "--cache-workers", type=int, default=-1,
        metavar="COUNT",
        help="Number of caching dataloader workers. (-1 uses all cores; 0 uses main thread; default: -1)"
    )
    group.add_argument(
        "--cache-tag", default="jtp3",
        metavar="ID",
        help="Cache identifier for training on different base models. (Default: jtp3)"
    )
    group.add_argument(
        "--rebuild-cache", action="store_true",
        help="Rebuild the feature cache."
    )
    group.add_argument(
        "--no-train", action="store_true",
        help="Only run caching and don't proceed to training."
    )
    group.add_argument(
        "--no-shm", action="store_false", dest="cache_shm",
        help="Disable shared memory use when caching."
    )
    group.add_argument(
        "--no-mtime", action="store_false", dest="check_mtime",
        help="Disable checking file modification time for cache validation."
    )

    parser.add_argument(
        "tag",
        metavar="TAG",
        help="Name of tag to train. (e.g. \"my_tag_(custom)\")"
    )

    args = parser.parse_args()

    if args.resume is not None:
        if (
            args.seed is not None
            or args.init_from_tag is not None
            or args.lr is not None
            or args.beta1 is not None
            or args.beta2 is not None
            or args.c is not None
            or args.weight_decay is not None
            or args.warmup_steps is not None
        ):
            parser.error("Cannot specify initialization or hyperparameters when resuming.")
    else:
        if args.seed is None:
            args.seed = 3407
        if args.lr is None:
            args.lr = 1e-4
        if args.beta1 is None:
            args.beta1 = 0.9
        if args.beta2 is None:
            args.beta2 = 0.999
        if args.beta1_c is None:
            args.beta1_c = 200.0
        if args.weight_decay is None:
            args.weight_decay = 1e-2
        if args.warmup_steps is None:
            args.warmup_steps = 20

    if args.tag == "" or "\\" in args.tag or "\n" in args.tag:
        parser.error("Invalid tag name.")

    tag_dir = (
        args.tag
            .replace(" ", "_")
            .replace("/", "_")
            .replace(".", "_")
    )

    data_dir = os.path.join(args.dir, tag_dir)
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"Data directory {repr(data_dir)} not found.")

    if args.device == "cpu":
        raise RuntimeError("CPU training is not supported due to a dependency on Triton.")

    device = torch.device(args.device)

    checkpoint_dir = os.path.join(data_dir, "checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    print(f"Loading {repr(args.model)} ...", end="")
    model, tags, _ = load_model(args.model, device=device)
    print(f" {len(tags)} tags")

    init_tag_idx = None
    if args.init_from_tag:
        try:
            init_tag_idx = tags.index(args.init_from_tag)
        except ValueError as ex:
            raise ValueError(f"Tag not found: {repr(args.init_from_tag)}") from ex

    resume_state: dict[str, Any] | None = None
    if args.resume:
        resume_path = os.path.join(checkpoint_dir, args.resume)

        print(f"Loading {repr(resume_path)} ...", end="")
        resume_state = torch.load(resume_path, map_location="cpu", weights_only=True)
        print("Done.")

        args.seed = resume_state["seed"]
        # NOTE: Not saving/restoring torch RNG state since training is nondeterministic anyways.

    rng = Random(args.seed)
    torch.manual_seed(args.seed)

    train_set, val_set, train_ratio = load_dataset(
        model,
        data_dir,
        rng=rng,
        n_validation=args.validation_samples,
        n_loaders=args.cache_workers,
        batch_size=args.cache_batch,
        cache_tag=args.cache_tag,
        cache_shm=args.cache_shm,
        check_mtime=args.check_mtime,
        rebuild_cache=args.rebuild_cache,
        device=device,
    )

    if args.no_train:
        return

    if not args.force:
        if len(train_set) < 100:
            raise RuntimeError(f"Training dataset of size {len(train_set)} is too small.")

        if len(val_set) < 40:
            raise RuntimeError(f"Validation dataset of size {len(val_set)} is too small.")

        if not 1.5 >= train_ratio >= 0.25:
            raise RuntimeError("Training dataset is very imbalanced.")

        if args.batch * args.accumulate < 16:
            raise RuntimeError("Accumulated training batch size must be at least 16.")

    attn_pool = cast(HydraPool, model.attn_pool)
    head = model.head
    del model

    hyperparams = {
        "lr": args.lr,
        "beta1": args.beta1,
        "beta2": args.beta2,
        "c": args.beta1_c,
        "weight_decay": args.weight_decay,
        "warmup_steps": args.warmup_steps,
    }

    train(
        attn_pool,
        head,
        train_set,
        val_set,
        checkpoint_dir,
        batch_size=args.batch,
        grad_acc=args.accumulate,
        hyperparams=hyperparams,
        rng=rng,
        seed=args.seed, # type: ignore
        init_from_tag=init_tag_idx,
        resume_state=resume_state,
        max_epochs=args.max_epochs,
        checkpoint_interval=args.checkpoint_interval,
        validation_buckets=args.validation_thresholds,
        device=device,
    )

if __name__ == "__main__":
    main()
