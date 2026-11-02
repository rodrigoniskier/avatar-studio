"""Carregamento CPU por shard, sem um modelo inicializado e outra cópia integral dos pesos."""
import torch
from safetensors.torch import load_file


def assign_shards(model, paths):
    """Os shards iniciais são disjuntos; o último pode sobrescrever pesos (adaptador)."""
    expected = model.state_dict()
    seen = set()
    for index, path in enumerate(paths):
        tensors = load_file(str(path), device="cpu")
        unexpected = set(tensors) - set(expected)
        if unexpected:
            raise RuntimeError(f"Pesos inesperados no checkpoint: {sorted(unexpected)[:5]}")
        if index < len(paths) - 1 and seen.intersection(tensors):
            raise RuntimeError("Shards base contêm pesos duplicados.")
        for name, value in tensors.items():
            target = expected[name]
            if value.shape != target.shape:
                raise RuntimeError(f"Shape incompatível no checkpoint: {name}.")
            tensors[name] = value.to(dtype=target.dtype)
        model.load_state_dict(tensors, strict=False, assign=True)
        seen.update(tensors)
        del tensors
    missing = set(expected) - seen
    if missing:
        raise RuntimeError(f"Checkpoint incompleto: {sorted(missing)[:5]}")
    return model


def assign_torch_checkpoint(model, path):
    """mmap no formato ZIP moderno; legado ainda evita alocar o modelo antes dos pesos."""
    with open(path, "rb") as source:
        mapped = source.read(4) == b"PK\x03\x04"
    tensors = torch.load(str(path), map_location="cpu", mmap=mapped, weights_only=True)
    expected = model.state_dict()
    if set(tensors) != set(expected):
        raise RuntimeError("Checkpoint T5 incompleto ou incompatível.")
    for name, value in tensors.items():
        if value.shape != expected[name].shape:
            raise RuntimeError(f"Shape incompatível no checkpoint T5: {name}.")
        tensors[name] = value.to(dtype=expected[name].dtype)
    model.load_state_dict(tensors, strict=True, assign=True)
    return model
