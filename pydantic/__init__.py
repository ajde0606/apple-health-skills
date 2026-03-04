"""
Minimal pydantic stub for offline testing.

Only covers what mac/collector/models.py requires:
  - BaseModel with keyword-argument construction
  - Field() that returns None (no runtime validation)
  - Discriminated-union coercion for IngestPayload.samples
"""
from __future__ import annotations


def Field(*args, **kwargs):
    return None


def _all_subclasses(cls):
    result = []
    for sub in cls.__subclasses__():
        result.append(sub)
        result.extend(_all_subclasses(sub))
    return result


def _coerce_sample(d: dict):
    """Find the BaseModel subclass whose class-level `kind` matches d['kind']."""
    kind = d.get("kind", "quantity")
    for cls in _all_subclasses(BaseModel):
        if cls.__dict__.get("kind") == kind:
            return cls(**d)
    return d


class BaseModel:
    def __init__(self, **data):
        for k, v in data.items():
            if k == "samples" and isinstance(v, list):
                setattr(self, k, [
                    _coerce_sample(item) if isinstance(item, dict) else item
                    for item in v
                ])
            else:
                setattr(self, k, v)
