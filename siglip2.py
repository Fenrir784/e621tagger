from typing import TypedDict

import torch
from torch import Tensor
from torch.nn import Module, ModuleList, LayerNorm, Parameter, Linear, Identity
from torch.nn.functional import interpolate, scaled_dot_product_attention, gelu

try:
    from torch.nn.attention.varlen import varlen_attn
except ImportError:
    pass

from einops import rearrange

class NaFlexEmbeds(Module):
    def __init__(
        self,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        self.pos_embed = Parameter(torch.empty(1, 16, 16, 1152, device=device, dtype=dtype))
        self.proj = Linear(768, 1152, device=device, dtype=dtype)

    def forward(self, patches: Tensor, patch_coord: Tensor) -> Tensor:
        return self._apply_pos_embed(*self._forward_grid(patches, patch_coord))

    def forward_varlen(self, patches: Tensor, patch_coord: Tensor) -> tuple[Tensor, Tensor, int]:
        return self._apply_pos_embed_varlen(*self._forward_grid(patches, patch_coord))

    def _forward_grid(self, patches: Tensor, patch_coord: Tensor) -> tuple[Tensor, Tensor]:
        if patches.ndim == 5:
            patches = rearrange(patches, "n s p1 p2 c -> n s (p1 p2 c)")
        else:
            assert patches.ndim == 3

        assert patch_coord.shape == (*patches.shape[:2], 2)

        return self.proj(patches), patch_coord.amax(dim=1).add_(1)

    @torch.compiler.disable()
    def _apply_pos_embed(self, patches: Tensor, grid_sizes: Tensor) -> Tensor:
        interpolated = { (16, 16): rearrange(self.pos_embed, "1 h w c -> (h w) c") }
        sequences: list[Tensor] = []
        pos_embeds: list[Tensor] = []

        for (y, x), seq in zip(grid_sizes.tolist(), patches.unbind(0)):
            sequences.append(seq[:y*x])
            pos_embeds.append(self._get_pos_embed((y, x), interpolated))

        torch._foreach_add_(sequences, pos_embeds)
        return patches

    @torch.compiler.disable()
    def _apply_pos_embed_varlen(self, patches: Tensor, grid_sizes: Tensor) -> tuple[Tensor, Tensor, int]:
        interpolated = { (16, 16): rearrange(self.pos_embed, "1 h w c -> (h w) c") }
        sequences: list[Tensor] = []
        pos_embeds: list[Tensor] = []

        offset = 0
        max_seq = 0
        cu_seq: list[int] = []

        for (y, x), seq in zip(grid_sizes.tolist(), patches.unbind(0)):
            seqlen = y * x

            sequences.append(seq[:seqlen])
            pos_embeds.append(self._get_pos_embed((y, x), interpolated))

            cu_seq.append(offset)
            offset += seqlen

            max_seq = max(max_seq, seqlen)

        patches = torch.empty(offset, 1152, device=patches.device, dtype=patches.dtype)
        torch._dynamo.mark_dynamic(patches, 0)
        torch._foreach_add(sequences, pos_embeds, out=patches.tensor_split(cu_seq[1:]))

        cu_seq.append(offset)
        cu_seq_t = torch.tensor(cu_seq, device=patches.device)

        if 0 in getattr(patches, "_dynamo_dynamic_indices", ()):
            torch._dynamo.mark_dynamic(cu_seq, 0)

        return patches, cu_seq_t, max_seq

    def _get_pos_embed(self, grid_size: tuple[int, int], cache: dict[tuple[int, int], Tensor]) -> Tensor:
        if (pos_embed := cache.get(grid_size)) is None:
            embed_chw = rearrange(self.pos_embed, "1 h w c -> 1 c h w")
            pos_embed = interpolate(embed_chw, grid_size, mode="bilinear", antialias=True)
            pos_embed = rearrange(pos_embed, "1 c h w -> (h w) c")
            cache[grid_size] = pos_embed

        return pos_embed

class NaFlexBlock(Module):
    def __init__(
        self, *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        self.attn = NaFlexAttn(device=device, dtype=dtype)
        self.mlp = NaFlexMlp(device=device, dtype=dtype)
        self.norm1 = LayerNorm(1152, device=device, dtype=dtype)
        self.norm2 = LayerNorm(1152, device=device, dtype=dtype)

    def forward(self, x: Tensor, attn_mask: Tensor) -> Tensor:
        x = x + self.attn(self.norm1(x), attn_mask)
        x = x + self.mlp(self.norm2(x))
        return x

    def forward_varlen(self, x: Tensor, cu_seq: Tensor, max_seq: int) -> Tensor:
        x = x + self.attn.forward_varlen(self.norm1(x), cu_seq, max_seq)
        x = x + self.mlp(self.norm2(x))
        return x

class NaFlexAttn(Module):
    def __init__(
        self, *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        self.qkv = Linear(1152, 3456, device=device, dtype=dtype)
        self.proj = Linear(1152, 1152, device=device, dtype=dtype)

    def forward(self, x: Tensor, attn_mask: Tensor) -> Tensor:
        x = self.qkv(x)

        q, k, v = rearrange(x, "... s (n h e) -> n ... h s e", n=3, h=16).unbind(0)
        x = scaled_dot_product_attention(q, k, v, attn_mask=attn_mask)
        x = rearrange(x, "... h s e -> ... s (h e)")

        x = self.proj(x)
        return x

    def forward_varlen(self, x: Tensor, cu_seq: Tensor, max_seq: int) -> Tensor:
        x = self.qkv(x)

        q, k, v = rearrange(x, "s (n h e) -> n s h e", n=3, h=16).unbind(0)
        x = varlen_attn(q, k, v, cu_seq, cu_seq, max_seq, max_seq)
        x = rearrange(x, "s h e -> s (h e)")

        x = self.proj(x)
        return x

class NaFlexMlp(Module):
    def __init__(
        self, *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        self.fc1 = Linear(1152, 4304, device=device, dtype=dtype)
        self.fc2 = Linear(4304, 1152, device=device, dtype=dtype)

    def forward(self, x: Tensor) -> Tensor:
        x = self.fc1(x)
        x = gelu(x, approximate="tanh")
        x = self.fc2(x)
        return x

class NaFlexOutputIntermediates(TypedDict):
    image_intermediates: list[Tensor]
    image_features: Tensor
    patch_valid: Tensor

class NaFlexOutputIntermediatesVarlen(TypedDict):
    image_intermediates: list[Tensor]
    image_features: Tensor
    cu_seq: Tensor
    max_seq: int

class NaFlexOutputFeatures(TypedDict):
    patches: Tensor
    patch_valid: Tensor

class NaFlexOutputFeaturesVarlen(TypedDict):
    patches: Tensor
    cu_seq: Tensor
    max_seq: int

class NaFlexVit(Module):
    def __init__(
        self,
        num_classes: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()

        self.num_classes = num_classes

        self.embeds = NaFlexEmbeds(device=device, dtype=dtype)
        self.blocks = ModuleList(
            NaFlexBlock(device=device, dtype=dtype)
            for _ in range(0, 27)
        )
        self.norm = LayerNorm(1152, device=device, dtype=dtype)

        self.attn_pool: Module = Identity()
        self.head: Module = Identity()

    def forward_intermediates(
        self, x: Tensor,
        patch_coord: Tensor,
        patch_valid: Tensor,
        indices: list[int] | int | None = None,
        output_dict: bool = True,
        output_fmt: str = "NLC",
    ) -> NaFlexOutputIntermediates:
        assert output_dict
        assert output_fmt == "NLC"

        if indices is None:
            indices = list(range(0, 27))
        elif isinstance(indices, int):
            indices = list(range(27 - indices, 27))
        else:
            indices = [
                idx if idx >= 0 else 27 + idx
                for idx in indices
            ]

        attn_mask = patch_valid.unflatten(-1, (1, 1, -1))

        x = self.embeds(x, patch_coord)

        intermediates: list[Tensor] = []
        for idx, block in enumerate(self.blocks):
            x = block(x, attn_mask)

            if idx in indices:
                intermediates.append(x)

        return {
            "image_intermediates": intermediates,
            "image_features": self.norm(x),
            "patch_valid": patch_valid,
        }

    def forward_intermediates_varlen(
        self, x: Tensor,
        patch_coord: Tensor,
        max_seq: int | None = None,
        indices: list[int] | int | None = None,
    ) -> NaFlexOutputIntermediatesVarlen:
        if indices is None:
            indices = list(range(0, 27))
        elif isinstance(indices, int):
            indices = list(range(27 - indices, 27))
        else:
            indices = [
                idx if idx >= 0 else 27 + idx
                for idx in indices
            ]

        if max_seq is None:
            x, cu_seq, max_seq = self.embeds.forward_varlen(x, patch_coord)
        else:
            x, cu_seq, _ = self.embeds.forward_varlen(x, patch_coord)

        intermediates: list[Tensor] = []
        for idx, block in enumerate(self.blocks):
            x = block.forward_varlen(x, cu_seq, max_seq)

            if idx in indices:
                intermediates.append(x)

        return {
            "image_intermediates": intermediates,
            "image_features": self.norm(x),
            "cu_seq": cu_seq,
            "max_seq": max_seq,
        }

    def forward_features(self, x: Tensor, patch_coord: Tensor, patch_valid: Tensor) -> NaFlexOutputFeatures:
        output = self.forward_intermediates(x, patch_coord, patch_valid, [])
        return {
            "patches": output["image_features"],
            "patch_valid": output["patch_valid"],
        }

    def forward_features_varlen(self, x: Tensor, patch_coord: Tensor, max_seq: int | None = None) -> NaFlexOutputFeaturesVarlen:
        output = self.forward_intermediates_varlen(x, patch_coord, max_seq, [])
        return {
            "patches": output["image_features"],
            "cu_seq": output["cu_seq"],
            "max_seq": output["max_seq"],
        }

    def forward_head(self, patches: Tensor, patch_valid: Tensor) -> Tensor:
        patches = self.attn_pool(patches, attn_mask=patch_valid.unflatten(-1, (1, 1, -1)))
        return self.head(patches)

    def forward_head_varlen(self, patches: Tensor, cu_seq: Tensor, max_seq: int) -> Tensor:
        patches = self.attn_pool.forward_varlen(patches, cu_seq, max_seq)
        return self.head(patches)

    def forward(self, patches: Tensor, patch_coord: Tensor, patch_valid: Tensor) -> Tensor:
        output = self.forward_intermediates(patches, patch_coord, patch_valid, [])
        return self.forward_head(output["image_features"], output["patch_valid"])

    def forward_varlen(self, patches: Tensor, patch_coord: Tensor, max_seq: int | None = None) -> Tensor:
        output = self.forward_intermediates_varlen(patches, patch_coord, max_seq, [])
        return self.forward_head_varlen(output["image_features"], output["cu_seq"], output["max_seq"])
