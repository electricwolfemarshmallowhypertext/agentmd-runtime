"""
Memory System Data Models
Created: 2025-11-02 20:00:39
Author: electricwolfemarshmallowhypertext
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
import numpy as np
from enum import Enum
import structlog
from uuid import uuid4
from .embedding_contract import DEFAULT_EMBEDDING_DIMENSION, MAX_EMBEDDING_DIMENSION, validate_vector
from .exceptions import MemoryValidationError

# Configure logging
logger = structlog.get_logger("sticky.memory.models")

class MemoryType(str, Enum):
    """Memory type enumeration"""
    FACT = "fact"
    INTERACTION = "interaction"
    PREFERENCE = "preference"
    PERSONALITY = "personality"
    CONTEXT = "context"
    SUMMARY = "summary"

class MemoryState(str, Enum):
    """Memory state enumeration"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PENDING = "pending"

class MemoryMetadata(BaseModel):
    """Memory metadata model"""
    
    source: Optional[str] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    expiration: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    state: MemoryState = MemoryState.ACTIVE
    version: int = 1
    custom: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True

class Memory(BaseModel):
    """Memory data model"""
    
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, description="Unique memory identifier")
    text: str = Field(..., min_length=1, max_length=4096)
    type: MemoryType = Field(..., description="Memory type")
    salience: float = Field(..., ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    thread_id: str = Field(..., description="Conversation thread ID")
    user_id: str = Field(..., description="User ID")
    persona_id: str = Field(..., description="Persona ID")
    embedding_dimension: int = Field(DEFAULT_EMBEDDING_DIMENSION, gt=0, le=MAX_EMBEDDING_DIMENSION)
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")
    metadata: MemoryMetadata = Field(default_factory=MemoryMetadata)
    
    class Config:
        use_enum_values = True
        
    @validator("embedding")
    def validate_embedding(cls, v: Optional[List[float]], values: Dict[str, Any]) -> Optional[List[float]]:
        return validate_vector(v, values.get("embedding_dimension", DEFAULT_EMBEDDING_DIMENSION)) if v is not None else None

class MemoryQuery(BaseModel):
    """Memory query model"""
    
    user_id: str
    thread_id: str
    persona_id: str
    query: str = Field(..., min_length=1, max_length=4096)
    include_memory: bool = True
    top_k: int = Field(3, ge=1, le=10)
    filter_types: Optional[List[MemoryType]] = None
    min_salience: Optional[float] = Field(None, ge=0.0, le=1.0)
    metadata_filter: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True
        
    @validator("metadata_filter")
    def validate_metadata_filter(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Validate metadata filter"""
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("Metadata filter must be a dictionary")
            for key in v.keys():
                if not isinstance(key, str):
                    raise ValueError("Metadata filter keys must be strings")
        return v

class MemoryBatch(BaseModel):
    """Memory batch model"""
    
    memories: List[Memory]
    user_id: str
    thread_id: str
    persona_id: str
    batch_id: str = Field(default_factory=lambda: uuid4().hex, description="Unique batch identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator("memories")
    def validate_batch_size(cls, v: List[Memory]) -> List[Memory]:
        """Validate batch size"""
        if not v:
            raise ValueError("Batch cannot be empty")
        if len(v) > 100:  # Maximum batch size
            raise ValueError("Batch size exceeds maximum (100)")
        return v

class MemoryStats(BaseModel):
    """Memory statistics model"""
    
    total_memories: int = 0
    total_size_bytes: int = 0
    avg_salience: float = 0.0
    type_counts: Dict[str, int] = Field(default_factory=dict)
    state_counts: Dict[str, int] = Field(default_factory=dict)
    persona_counts: Dict[str, int] = Field(default_factory=dict)
    avg_embedding_norm: Optional[float] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class MemoryVector(BaseModel):
    """Memory vector model"""
    
    memory_id: str
    embedding_dimension: int = Field(DEFAULT_EMBEDDING_DIMENSION, gt=0, le=MAX_EMBEDDING_DIMENSION)
    embedding: List[float]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator("embedding")
    def validate_vector(cls, v: List[float], values: Dict[str, Any]) -> List[float]:
        return validate_vector(v, values.get("embedding_dimension", DEFAULT_EMBEDDING_DIMENSION))

    def normalize(self) -> None:
        """Normalize vector to unit length"""
        norm = np.linalg.norm(self.embedding)
        if norm > 0:
            self.embedding = (np.array(self.embedding) / norm).tolist()

def create_memory(
    text: str,
    thread_id: str,
    user_id: str,
    persona_id: str,
    type: Union[str, MemoryType] = MemoryType.FACT,
    salience: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None
) -> Memory:
    """Create memory instance with validation"""
    try:
        # Convert string type to enum
        if isinstance(type, str):
            type = MemoryType(type)
            
        # Create metadata
        meta = MemoryMetadata(**(metadata or {}))
        
        # Create memory
        memory = Memory(
            text=text,
            thread_id=thread_id,
            user_id=user_id,
            persona_id=persona_id,
            type=type,
            salience=salience,
            metadata=meta
        )
        
        return memory
        
    except Exception as e:
        logger.error("Failed to create memory",
            text=text[:100],
            thread_id=thread_id,
            error=str(e)
        )
        raise MemoryValidationError(
            "Invalid memory data",
            details={"error": str(e)}
        )

def create_batch(
    memories: List[Memory],
    user_id: str,
    thread_id: str,
    persona_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> MemoryBatch:
    """Create memory batch with validation"""
    try:
        batch = MemoryBatch(
            memories=memories,
            user_id=user_id,
            thread_id=thread_id,
            persona_id=persona_id,
            metadata=metadata or {}
        )
        
        return batch
        
    except Exception as e:
        logger.error("Failed to create memory batch",
            user_id=user_id,
            thread_id=thread_id,
            error=str(e)
        )
        raise MemoryValidationError(
            "Invalid batch data",
            details={"error": str(e)}
        )