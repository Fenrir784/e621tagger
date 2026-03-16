import re
from math import sqrt
from typing import Any, Iterable, Self, cast

import torch
from torch import Tensor
from torch.nn import (
    Module, ModuleList, Parameter, Buffer,
    Linear, LayerNorm, RMSNorm, Dropout, Flatten,
    init
)
from torch.nn.functional import pad, scaled_dot_product_attention

from einops import rearrange

from glu import SwiGLU

class BatchLinear(Module):
    def __init__(
        self,
        batch_shape: tuple[int, ...] | int,
        in_features: int,
        out_features: int,
        *,
        bias: bool = False,
        flatten: bool = False,
        bias_inplace: bool = True,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        if isinstance(batch_shape, int):
            batch_shape = (batch_shape,)
        elif not batch_shape:
            raise ValueError("At least one batch dimension is required.")

        self.flatten = -(len(batch_shape) + 1) if flatten else 0

        self.weight = Parameter(torch.empty(
            *batch_shape, in_features, out_features,
            device=device, dtype=dtype
        ))

        bt = self.weight.flatten(end_dim=-3).mT
        for idx in range(bt.size(0)):
            init.kaiming_uniform_(bt[idx], a=sqrt(5))

        self.bias = Parameter(torch.zeros(
            *batch_shape, out_features,
            device=device, dtype=dtype
        )) if bias else None

        self.bias_inplace = bias_inplace

    def forward(self, x: Tensor) -> Tensor:
        # ... B... 1 I @ B... I O -> ... B... O
        x = torch.matmul(x.unsqueeze(-2), self.weight).squeeze(-2)

        if self.bias is not None:
            if self.bias_inplace:
                x.add_(self.bias)
            else:
                x = x + self.bias

        if self.flatten:
            x = x.flatten(self.flatten)

        return x

class Mean(Module):
    def __init__(self, dim: tuple[int, ...] | int = -1, *, keepdim: bool = False) -> None:
        super().__init__()

        self.dim = dim
        self.keepdim = keepdim

    def forward(self, x: Tensor) -> Tensor:
        return x.mean(self.dim, self.keepdim)

class _MidBlock(Module):
    def __init__(
        self,
        attn_dim: int,
        head_dim: int,
        n_classes: int,
        *,
        ff_ratio: float,
        ff_dropout: float,
        q_cls_inplace: bool = True,
        device: torch.device | str | None,
        dtype: torch.dtype | None,
    ) -> None:
        super().__init__()

        self.head_dim = head_dim
        self.q_cls_inplace = q_cls_inplace

        hidden_dim = int(attn_dim * ff_ratio)

        self.q_proj = Linear(
            attn_dim, attn_dim, bias=False,
            device=device, dtype=dtype
        )

        self.q_cls = Parameter(torch.zeros(
            n_classes, attn_dim,
            device=device, dtype=dtype
        ))

        self.q_norm = RMSNorm(head_dim, eps=1e-5, elementwise_affine=False)

        self.ff_norm = LayerNorm(
            attn_dim * 2, elementwise_affine=False,
            device=device, dtype=dtype
        )
        self.ff_in = Linear(
            attn_dim * 2, hidden_dim * 2, bias=False,
            device=device, dtype=dtype
        )
        self.ff_act = SwiGLU()
        self.ff_drop = Dropout(ff_dropout)
        self.ff_out = Linear(
            hidden_dim, attn_dim, bias=False,
            device=device, dtype=dtype
        )

    def _forward_q(self, x: Tensor) -> Tensor:
        x = self.q_proj(x)

        if self.q_cls_inplace:
            x.add_(self.q_cls)
        else:
            x = x + self.q_cls

        x = self.q_norm(x)
        return x

    def _forward_attn(self, x: Tensor, k: Tensor, v: Tensor, attn_mask: Tensor | None) -> Tensor:
        x = self._forward_q(x)
        x = rearrange(x, "... s (h e) -> ... h s e", e=self.head_dim)

        x = scaled_dot_product_attention(x, k, v, attn_mask=attn_mask)
        x = rearrange(x, "... h s e -> ... s (h e)")
        return x

    def _forward_ff(self, x: Tensor) -> Tensor:
        x = self.ff_norm(x)
        x = self.ff_in(x)
        x = self.ff_act(x)
        x = self.ff_drop(x)
        x = self.ff_out(x)
        return x

    def forward(self, x: Tensor, k: Tensor, v: Tensor, attn_mask: Tensor | None = None) -> Tensor:
        a = self._forward_attn(x, k, v, attn_mask)
        a = torch.cat((x, a), dim=-1)
        a = self._forward_ff(a)
        return x + a

    def reset_classes(self, n_classes: int) -> None:
        if n_classes < 1:
            raise ValueError("Number of classes must be positive.")

        self.q_cls = Parameter(torch.randn(
            self.q_cls.size(0), n_classes, self.q_cls.size(2),
            device=self.q_cls.device, dtype=self.q_cls.dtype
        ))

    def select_classes(self, classes: Tensor | list[int] | int) -> None:
        if isinstance(classes, int):
            classes = [classes]
        elif len(classes) < 1:
            raise ValueError("Must select at least one class.")

        self.q_cls = Parameter(self.q_cls[:, classes, :])

class HydraPool(Module):
    def __init__(
        self,
        attn_dim: int,
        head_dim: int,
        n_classes: int,
        *,
        mid_blocks: int = 0,
        ff_ratio: float = 3.0,
        ff_dropout: float = 0.0,
        input_dim: int = -1,
        output_dim: int = 1,
        tie_kv: bool = False,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        if input_dim < 0:
            input_dim = attn_dim

        assert attn_dim % head_dim == 0
        n_heads = attn_dim // head_dim

        self.n_classes = n_classes
        self.head_dim = head_dim
        self.output_dim = output_dim
        self.tie_kv = tie_kv

        self._has_ff = False
        self._q_normed = False

        self.q = Parameter(torch.randn(
            n_heads, n_classes, head_dim,
            device=device, dtype=dtype
        ))

        kv_dim = attn_dim if self.tie_kv else attn_dim * 2
        self.kv = Linear(
            input_dim, kv_dim, bias=False,
            device=device, dtype=dtype
        )
        self.qk_norm = RMSNorm(
            head_dim, eps=1e-5, elementwise_affine=False
        )

        if ff_ratio > 0.0:
            self._has_ff = True
            hidden_dim = int(attn_dim * ff_ratio)

            self.ff_norm = LayerNorm(
                attn_dim,
                device=device, dtype=dtype
            )
            self.ff_in = Linear(
                attn_dim, hidden_dim * 2, bias=False,
                device=device, dtype=dtype
            )
            self.ff_act = SwiGLU()
            self.ff_drop = Dropout(ff_dropout)
            self.ff_out = Linear(
                hidden_dim, attn_dim, bias=False,
                device=device, dtype=dtype
            )
        elif mid_blocks > 0:
            raise ValueError("Feedforward required with mid blocks.")

        self.mid_blocks = ModuleList(
            _MidBlock(
                attn_dim, head_dim, n_classes,
                ff_ratio=ff_ratio, ff_dropout=ff_dropout,
                device=device, dtype=dtype
            ) for _ in range(mid_blocks)
        )

        self.out_proj = BatchLinear(
            n_classes, attn_dim, output_dim * 2,
            device=device, dtype=dtype
        )
        self.out_act = SwiGLU()

    def get_extra_state(self) -> dict[str, Any]:
        return { "q_normed": self._q_normed }

    def set_extra_state(self, state: dict[str, Any]) -> None:
        self._q_normed = state["q_normed"]

    def create_head(self) -> Module:
        if self.output_dim == 1:
            return Flatten(-2)

        return Mean(-1)

    def reset_classes(self, n_classes: int) -> None:
        if n_classes < 1:
            raise ValueError("Number of classes must be positive.")

        self.q = Parameter(torch.randn(
            self.q.size(0), n_classes, self.q.size(2),
            device=self.q.device, dtype=self.q.dtype
        ))
        self._q_normed = False

        op = self.out_proj.weight
        self.out_proj = BatchLinear(
            n_classes, op.size(1), op.size(2),
            device=op.device, dtype=op.dtype
        )

        for block in self.mid_blocks:
            cast(_MidBlock, block).reset_classes(n_classes)

        self.n_classes = n_classes

    def select_classes(self, classes: Tensor | list[int] | int) -> None:
        if isinstance(classes, int):
            classes = [classes]
        elif len(classes) < 1:
            raise ValueError("Must select at least one class.")

        self.q = Parameter(self.q[:, classes, :])
        self.out_proj.weight = Parameter(self.out_proj.weight[classes, :, :])

        for block in self.mid_blocks:
            cast(_MidBlock, block).select_classes(classes)

        self.n_classes = len(classes)

    @torch.no_grad()
    def load_extensions(
        self,
        extensions: Iterable[tuple[int | None, dict[str, Tensor]]]
    ) -> None:
        q_shape = (self.q.shape[0], 1, self.q.shape[2])
        o_shape = (1, self.out_proj.weight.shape[1], self.out_proj.weight.shape[2])
        mq_shape = (1, self.q.shape[0])

        n = 0
        q: list[Tensor] = [self.q]
        o: list[Tensor] = [self.out_proj.weight]
        mqs: list[list[Tensor]] = [
            [cast(_MidBlock, block).q_cls]
            for block in self.mid_blocks
        ]

        for idx, ext in extensions:
            q_ext = ext["q"].to(device=self.q.device, non_blocking=True)
            o_ext = ext["out_proj.weight"].to(device=self.out_proj.weight.device, non_blocking=True)

            if q_ext.shape != q_shape:
                raise ValueError(f"Extension has unexpected q shape {q_ext.shape}, expected {q_shape}.")

            if o_ext.shape != o_shape:
                raise ValueError(f"Extension has unexpected out_proj.weight shape {o_ext.shape}, expected {o_shape}.")

            mqs_ext: list[Tensor] = []
            for m_idx in range(len(self.mid_blocks)):
                mq_ext = ext[f"mid_blocks.{m_idx}.q_cls"]
                if mq_ext.shape != mq_shape:
                    raise ValueError(f"Extension has unexpected mid_blocks.{m_idx}.q_cls shape {mq_ext.shape}, expected {mq_shape}.")

                mqs_ext.append(mq_ext)

            if f"mid_blocks.{len(self.mid_blocks)}.q_cls" in ext:
                raise ValueError("Extension has too many mid_blocks.")

            if idx is None:
                n += 1
                q.append(q_ext)
                o.append(o_ext)

                for mq, mq_ext in zip(mqs, mqs_ext):
                    mq.append(mq_ext)
            else:
                self.q[:, idx, :].copy_(q_ext[:, 0, :])
                self.out_proj.weight[idx, :, :].copy_(q_ext[0, :, :])

                for block, mq_ext in zip(self.mid_blocks, mqs_ext):
                    cast(_MidBlock, block).q_cls[idx, :].copy_(mq_ext[0, :])

        if n:
            self.n_classes += n
            self.q = Parameter(torch.cat(q, dim=1))
            self.out_proj.weight = Parameter(torch.cat(o, dim=0))

            for block, mq in zip(self.mid_blocks, mqs):
                cast(_MidBlock, block).q_cls = Parameter(torch.cat(mq, dim=0))

    def train(self, mode: bool = True) -> Self:
        super().train(mode)

        if mode:
            self._q_normed = False

        return self

    def inference(self) -> Self:
        super().train(False)

        if not self._q_normed:
            with torch.no_grad():
                self.q.copy_(self._forward_q())

            self._q_normed = True

        return self

    def _forward_q(self) -> Tensor:
        return self.q if self._q_normed else self.qk_norm(self.q)

    def _forward_attn(self, x: Tensor, attn_mask: Tensor | None) -> tuple[Tensor, Tensor, Tensor]:
        q = self._forward_q().expand(*x.shape[:-2], -1, -1, -1)

        x = self.kv(x)
        k, v = rearrange(x, "... s (n h e) -> n ... h s e", n=2, e=self.head_dim).unbind(0)
        k = self.qk_norm(k)

        x = scaled_dot_product_attention(q, k, v, attn_mask=attn_mask)
        return rearrange(x, "... h s e -> ... s (h e)"), k, v

    def _forward_ff(self, x: Tensor) -> Tensor:
        if not self._has_ff:
            return x

        f = self.ff_norm(x)
        f = self.ff_in(f)
        f = self.ff_act(f)
        f = self.ff_drop(f)
        f = self.ff_out(f)
        return x + f

    def _forward_out(self, x: Tensor) -> Tensor:
        x = self.out_proj(x)
        x = self.out_act(x)
        return x

    def forward(self, x: Tensor, attn_mask: Tensor | None = None) -> Tensor:
        x, k, v = self._forward_attn(x, attn_mask)
        x = self._forward_ff(x)

        for block in self.mid_blocks:
            x = block(x, k, v, attn_mask)

        x = self._forward_out(x)
        return x

    @staticmethod
    def for_state(
        state_dict: dict[str, Any],
        prefix: str = "",
        *,
        ff_dropout: float = 0.0,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> "HydraPool":
        n_heads, n_classes, head_dim = state_dict[f"{prefix}q"].shape
        attn_dim = n_heads * head_dim

        input_dim = state_dict[f"{prefix}kv.weight"].size(1)
        output_dim = state_dict[f"{prefix}out_proj.weight"].size(2) // 2

        # avoid off-by-one issue due to truncation
        ffout_t = state_dict.get(f"{prefix}ff_out.weight")
        hidden_dim = ffout_t.size(1) + 0.5 if ffout_t is not None else 0
        ff_ratio = hidden_dim / attn_dim

        tie_kv = state_dict[f"{prefix}kv.weight"].size(0) == attn_dim

        pattern = re.compile(rf"^{re.escape(prefix)}mid_blocks\.([0-9]+)\.")
        mid_blocks = max([-1, *(
            int(match[1])
            for key in state_dict
            if (match := pattern.match(key)) is not None
        )]) + 1

        return HydraPool(
            attn_dim,
            head_dim,
            n_classes,
            mid_blocks=mid_blocks,
            ff_ratio=ff_ratio,
            ff_dropout=ff_dropout,
            input_dim=input_dim,
            output_dim=output_dim,
            tie_kv=tie_kv,
            device=device,
            dtype=dtype
        )
