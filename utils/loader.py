import os

from collections import deque
from queue import Empty
from threading import Thread
from typing import Iterable, Self

from ctypes import c_bool
from multiprocessing import RawValue, get_context, parent_process
from multiprocessing.queues import Queue as MpQueue

if parent_process() is not None:
    import logging
    logging.getLogger("torch.utils.flop_counter").setLevel(logging.ERROR)

import torch
from torch import Tensor
from torch.multiprocessing.queue import Queue as TorchQueue

from hydra.model import ImageConfig, load_image

__all__ = ("EnvScope", "Loader")

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
        self,
        queue_depth: int,
        config: ImageConfig,
        n_workers: int,
        *,
        share_memory: bool = True,
    ) -> None:
        self._config = config

        if n_workers == 0:
            self._workers = []
            self._queue = deque[str]()
            self.get_one = self._load_one
            self.queue = self._put_one
            return

        ctx = get_context("spawn")

        self._queued = 0
        self._submission_queue: MpQueue[str] = MpQueue(ctx=ctx)
        self._completion_queue = TorchQueue(queue_depth, ctx=ctx)
        self._clearing = RawValue(c_bool) if share_memory else None
        self._workers = [
            ctx.Process(
                target=_worker_fn,
                args=(
                    self._submission_queue,
                    self._completion_queue,
                    self._clearing,
                    self._config,
                    share_memory,
                ),
                name=f"loader-{idx}",
                daemon=True
            )
            for idx in range(n_workers)
        ]

        self.get_one = self._wait_one
        self.queue = self._submit_one

        threads = [
            Thread(
                target=proc.start,
                name=f"pstart-{idx}",
                daemon=True,
            ) for idx, proc in enumerate(self._workers)
        ]

        with EnvScope({
            "CUDA_VISIBLE_DEVICES": "",
            "OMP_NUM_THREADS": 1,
            "OPENBLAS_NUM_THREADS": 1,
            "VIPS_CONCURRENCY": 1,
        }):
            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

    def __bool__(self) -> bool:
        return len(self) > 0

    def __len__(self) -> int:
        return self._queued if self._workers else len(self._queue)

    @property
    def n_workers(self) -> int:
        return len(self._workers)

    def _submit_one(self, path: str) -> None:
        self._queued += 1
        self._submission_queue.put(path)

    def _wait_one(self) -> tuple[str, Tensor | Exception] | None:
        if self._queued == 0:
            return None

        while True:
            try:
                item = self._completion_queue.get(timeout=1)
            except Empty:
                for worker in self._workers:
                    if not worker.is_alive():
                        raise RuntimeError(f"{worker.name} exited with code {worker.exitcode}")
            else:
                break

        self._queued -= 1
        assert item is not None

        return item

    def _put_one(self, path: str) -> None:
        self._queue.append(path)

    def _load_one(self) -> tuple[str, Tensor | Exception] | None:
        if not self._queue:
            return None

        path = self._queue.popleft()
        try:
            return path, load_image(path, self._config)
        except Exception as ex:
            return path, ex

    def queue_from(self, paths: Iterable[str]) -> None:
        for path in paths:
            self.queue(path)

    def get_batch(self, size: int) -> tuple[list[tuple[str, Tensor]], list[tuple[str, Exception]]]:
        batch: list[tuple[str, Tensor]] = []
        errors: list[tuple[str, Exception]] = []

        while len(batch) < size:
            if (item := self.get_one()) is None:
                break

            path, result = item
            if isinstance(result, Exception):
                errors.append((path, result))
            else:
                batch.append((path, result))

        return batch, errors

    def clear(self) -> None:
        if not self._workers:
            self._queue.clear()
            return

        if self._clearing is not None:
            if self._clearing.value:
                raise RuntimeError("Already clearing.")

            self._clearing.value = True

        while self._queued:
            try:
                self._submission_queue.get(block=False)
            except Empty:
                break

            self._queued -= 1

        while self._queued:
            self._completion_queue.get()
            self._queued -= 1

        if self._clearing is not None:
            self._clearing.value = False

    def shutdown(self, *, wait: bool = True) -> None:
        if not self._workers:
            return

        del self.queue
        del self.get_one

        if self._clearing is not None:
            self._clearing.value = True

        try:
            for worker in self._workers:
                worker.terminate()

            if wait:
                for worker in self._workers:
                    worker.join()
        finally:
            self._workers.clear()

    @staticmethod
    def heuristic_workers(workers: int, count: int, batch_size: int) -> int:
        if workers == -1:
            max_workers = min(count // 4, 16)
        else:
            max_workers = count // 2

        if count > 2 and batch_size < count:
            max_workers = max(max_workers, 1)

        if workers < 0:
            if hasattr(os, "process_cpu_count"):
                workers = os.process_cpu_count() or 1
            else:
                workers = os.cpu_count() or 1

        return min(workers, max_workers)

def _worker_fn(
    submission_queue: MpQueue[str],
    completion_queue: TorchQueue,
    clearing: c_bool | None,
    config: ImageConfig,
    share_memory: bool,
):
    while True:
        path = submission_queue.get()

        if clearing is not None and clearing.value:
            completion_queue.put(None)

        try:
            img = load_image(path, config)
            if share_memory:
                img.share_memory_()
        except Exception as ex:
            completion_queue.put((path, ex))
        else:
            completion_queue.put((path, img))
