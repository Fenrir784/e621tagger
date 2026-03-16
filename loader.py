import os

from threading import Thread
from typing import Iterable, Self

import multiprocessing
from multiprocessing.queues import SimpleQueue

from torch import Tensor
from torch.multiprocessing.queue import SimpleQueue as TorchQueue

from model import load_image

class EnvScope:
    __slots__ = ("env", "saved")

    def __init__(self, env: dict[str, str | int | float | None]) -> None:
        self.env = {
            env: None if value is None else str(value)
            for env, value in env.items()
        }

        self.saved: dict[str, str | None]

    def __enter__(self) -> Self:
        if hasattr(self, "saved"):
            raise RuntimeError("EnvScope is already in use.")

        self.saved = {}
        for env, value in self.env.items():
            self.saved[env] = os.environ.get(env, None)

            if value is None:
                del os.environ[env]
            else:
                os.environ[env] = value

        return self

    def __exit__(self, exc_type, exc_value, tb) -> None:
        for env, value in self.saved.items():
            if value is None:
                del os.environ[env]
            else:
                os.environ[env] = value

        del self.saved

class Loader:
    def __init__(
        self, n_workers: int = -1, *,
        patch_size: int = 16, max_seqlen: int = 1024,
        share_memory: bool = True
    ) -> None:
        ctx = multiprocessing.get_context("spawn")

        self.patch_size = patch_size
        self.max_seqlen = max_seqlen

        if n_workers < 0:
            if hasattr(os, "process_cpu_count"):
                n_workers = os.process_cpu_count() or 1
            else:
                n_workers = os.cpu_count() or 1

        if n_workers == 0:
            self._workers = []
            return

        self._submission_queue: SimpleQueue[str | None] = SimpleQueue(ctx=ctx)
        self._completion_queue: SimpleQueue[tuple[str, tuple[Tensor, Tensor, Tensor] | Exception] | None] = TorchQueue(ctx=ctx)
        self._workers = [
            ctx.Process(
                target=_worker_fn,
                args=(
                    self._submission_queue,
                    self._completion_queue,
                    patch_size,
                    max_seqlen,
                    share_memory,
                ),
                name=f"loader-{idx}",
                daemon=True
            )
            for idx in range(n_workers)
        ]


        threads = [
            Thread(
                target=proc.start,
                name=f"pstart-{proc.name}",
                daemon=True,
            ) for proc in self._workers
        ]

        with EnvScope({
            "OMP_NUM_THREADS": 1,
            "OPENBLAS_NUM_THREADS": 1,
            "CUDA_VISIBLE_DEVICES": "",
        }):
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

    def load(self, paths: Iterable[str]) -> dict[str, tuple[Tensor, Tensor, Tensor] | Exception]:
        loaded: dict[str, tuple[Tensor, Tensor, Tensor] | Exception] = {}

        if self._workers:
            count = 0
            for path in paths:
                self._submission_queue.put(path)
                count += 1

            for _ in range(count):
                result = self._completion_queue.get()
                assert result is not None
                loaded[result[0]] = result[1]
        else:
            for path in paths:
                try:
                    loaded[path] = load_image(path, self.patch_size, self.max_seqlen, False)
                except Exception as ex:
                    loaded[path] = ex

        return loaded

    def shutdown(self, wait: bool = True) -> None:
        for _ in range(len(self._workers)):
            self._submission_queue.put(None)

        if wait:
            for _ in range(len(self._workers)):
                assert self._completion_queue.get() is None

        self._workers.clear()

def _worker_fn(
    submission_queue: SimpleQueue[str | None],
    completion_queue: SimpleQueue[tuple[str, tuple[Tensor, Tensor, Tensor] | Exception] | None],
    patch_size: int,
    max_seqlen: int,
    share_memory: bool,
):
    while (path := submission_queue.get()) is not None:
        try:
            completion_queue.put((path, load_image(path, patch_size, max_seqlen, share_memory)))
        except Exception as ex:
            completion_queue.put((path, ex))

    completion_queue.put(None)
