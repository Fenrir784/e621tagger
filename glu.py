from abc import abstractmethod
from typing import Literal

from torch import Tensor
from torch.nn import Module
from torch.nn.functional import silu, gelu

class GatedUnit(Module):
    def __init__(self, dim: int = -1) -> None:
        super().__init__()

        self.dim = dim

    @abstractmethod
    def _activation(self, x: Tensor) -> Tensor:
        ...

    def forward(self, x: Tensor) -> Tensor:
        f, g = x.chunk(2, dim=self.dim)
        return self._activation(f) * g

class SwiGLU(GatedUnit):
    def __init__(self, dim: int = -1) -> None:
        super().__init__(dim)

    def _activation(self, x: Tensor) -> Tensor:
        return silu(x)

class GeGLU(GatedUnit):
    def __init__(
        self,
        dim: int = -1,
        approximate: Literal["tanh", "none"] = "tanh"
    ) -> None:
        super().__init__(dim)

        self.approximate = approximate

    def _activation(self, x: Tensor) -> Tensor:
        return gelu(x, self.approximate)
