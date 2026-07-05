import os

from queue import Queue
from threading import Thread
from time import sleep
from traceback import print_exc
from typing import Any, Callable, ParamSpec

__all__ = ("WorkQueue",)

P = ParamSpec("P")

class WorkQueue(Thread):
    def __init__(
        self, *,
        depth: int = 1,
        name: str = "worker",
        daemon: bool = True
    ) -> None:
        super().__init__(name=name, daemon=daemon)

        self._queue = Queue[tuple[Callable[..., None], tuple[Any, ...], dict[str, Any]] | None](maxsize=depth)
        self._shutdown = False
        self._busy = False

        self.start()

    def run(self) -> None:
        while (work := self._queue.get()) is not None:
            self._busy = True

            try:
                work[0](*work[1], **work[2])
            except:
                print_exc()
            finally:
                self._busy = False
                self._queue.task_done()
                del work

        self._queue.task_done()

    def queue(self, fn: Callable[P, None], /, *args: P.args, **kwargs: P.kwargs) -> None:
        assert not self._shutdown
        self._queue.put((fn, args, kwargs))

        if not self._busy:
            sleep(0)

    def wait(self) -> None:
        self._queue.join()

    def shutdown(self) -> None:
        if not self._shutdown:
            self._shutdown = True
            self._queue.put(None)

        self.join()
