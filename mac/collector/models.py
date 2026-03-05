from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class QuantitySample(BaseModel):
    sample_id: str = Field(min_length=8)
    kind: Literal["quantity"] = "quantity"
    type: str
    ts: int
    value: float
    unit: str
    source: str
    device: str | None = None
    metadata: dict[str, Any] | None = None


class CategorySample(BaseModel):
    sample_id: str = Field(min_length=8)
    kind: Literal["category"] = "category"
    type: str
    start_ts: int
    end_ts: int
    category: str
    source: str
    device: str | None = None
    metadata: dict[str, Any] | None = None


class IngestPayload(BaseModel):
    batch_id: str = Field(min_length=1)
    device_id: str = Field(min_length=3)
    user_id: str = Field(min_length=1)
    sent_at: int
    samples: list[QuantitySample | CategorySample]


class IngestResult(BaseModel):
    ok: bool
    duplicate_batch: bool
    inserted: int
    skipped: int


class LiveSource(BaseModel):
    kind: Literal["ble"] = "ble"
    vendor: Literal["wahoo"] = "wahoo"
    device_id: str = Field(min_length=1)
    device_name: str | None = None


class LiveEvent(BaseModel):
    type: Literal["hr"] = "hr"
    ts: float
    value: int
    unit: Literal["bpm"] = "bpm"
    source: LiveSource
    session_id: str = Field(min_length=8)
    seq: int = Field(ge=1)


class LiveEventsPayload(BaseModel):
    session_id: str = Field(min_length=8)
    device_id: str = Field(min_length=1)
    events: list[LiveEvent]


class LiveEventsResult(BaseModel):
    ok: bool
    ack_seq: int
