"""
Validation models and helpers aligned with models.py.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
import json
from datetime import datetime
import xxhash
import structlog
from uuid import uuid4
from .embedding_contract import DEFAULT_EMBEDDING_DIMENSION, MAX_EMBEDDING_DIMENSION, validate_vector

from .models import MemoryType, MemoryState, MemoryMetadata  # re-exported enums/model

logger = structlog.get_logger("memory.validation")


class MemoryEvent(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1)
    text: str = Field(..., min_length=1, max_length=4096)
    type: MemoryType
    salience: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime
    thread_id: str
    user_id: str
    persona_id: str
    embedding_dimension: int = Field(DEFAULT_EMBEDDING_DIMENSION, gt=0, le=MAX_EMBEDDING_DIMENSION)
    embedding: Optional[List[float]] = None
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)

    @validator("embedding")
    def validate_embedding(cls, v: Optional[List[float]], values: Dict[str, Any]) -> Optional[List[float]]:
        return validate_vector(v, values.get("embedding_dimension", DEFAULT_EMBEDDING_DIMENSION)) if v is not None else None

    @validator("metadata")
    def validate_metadata(cls, v: MemoryMetadata) -> MemoryMetadata:
        size = len(json.dumps(v.model_dump(mode="json")).encode("utf-8"))
        if size > 10 * 1024:
            raise ValueError("Metadata too large")
        return v


class MemoryQuery(BaseModel):
    user_id: str
    thread_id: str
    persona_id: str
    query: str = Field(..., min_length=1, max_length=4096)
    include_memory: bool = True
    top_k: int = Field(3, ge=1, le=10)

    @validator("query")
    def validate_query(cls, v: str) -> str:
        if len(v.strip()) == 0:
            raise ValueError("Query cannot be empty")
        return v.strip()


class MemoryTransfer(BaseModel):
    user_id: str
    from_persona: str
    to_persona: str
    query: str = Field(..., min_length=1, max_length=4096)

    @validator("from_persona", "to_persona")
    def validate_personas(cls, v: str) -> str:
        if not v:
            raise ValueError("Persona ID cannot be empty")
        return v

    @validator("to_persona")
    def validate_different_personas(cls, v: str, values: Dict[str, Any]) -> str:
        if v == values.get("from_persona"):
            raise ValueError("Source and destination personas must be different")
        return v


def validate_memory_input(
    text: str,
    thread_id: str,
    user_id: str,
    persona_id: str,
    type: MemoryType = MemoryType.FACT,
    salience: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    event = MemoryEvent(
        text=text,
        thread_id=thread_id,
        user_id=user_id,
        persona_id=persona_id,
        type=type if isinstance(type, MemoryType) else MemoryType(type),
        salience=salience,
        created_at=datetime.utcnow(),
        metadata=MemoryMetadata(**(metadata or {})),
    )
    return event.dict()


def validate_query_input(
    user_id: str,
    thread_id: str,
    persona_id: str,
    query: str,
    include_memory: bool = True,
    top_k: int = 3,
) -> Dict[str, Any]:
    model = MemoryQuery(
        user_id=user_id,
        thread_id=thread_id,
        persona_id=persona_id,
        query=query,
        include_memory=include_memory,
        top_k=top_k,
    )
    return model.dict()


def validate_transfer_input(
    user_id: str,
    from_persona: str,
    to_persona: str,
    query: str,
) -> Dict[str, Any]:
    model = MemoryTransfer(
        user_id=user_id,
        from_persona=from_persona,
        to_persona=to_persona,
        query=query,
    )
    return model.dict()


def sanitize_memory_output(memory: Dict[str, Any], include_embedding: bool = False) -> Dict[str, Any]:
    output = {
        "id": memory["id"],
        "text": memory["text"],
        "type": memory["type"],
        "salience": memory["salience"],
        "created_at": memory["created_at"],
        "thread_id": memory["thread_id"],
        "persona_id": memory["persona_id"],
    }

    if include_embedding and "embedding" in memory and memory["embedding"] is not None:
        output["embedding"] = memory["embedding"]

    meta = memory.get("metadata")
    if meta:
        if isinstance(meta, dict):
            safe_meta = {k: v for k, v in meta.items() if not str(k).startswith("_")}
        else:
            # MemoryMetadata
            safe_meta = {k: v for k, v in meta.dict().items() if not str(k).startswith("_")}
        if safe_meta:
            output["metadata"] = safe_meta

    return output

# Re-exports for tests that import from validation
__all__ = ["MemoryEvent", "MemoryQuery", "MemoryTransfer", "MemoryType", "MemoryState", "MemoryMetadata"]