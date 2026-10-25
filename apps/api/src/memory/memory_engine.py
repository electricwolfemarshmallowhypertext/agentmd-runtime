"""Local Sentence Transformers embeddings with persistent Chroma/SQLite storage.

No provider, Firebase or cloud service is required. Model files must already be
present unless the caller explicitly opts into a model download. Existing stores
without a matching model contract are rejected, never silently re-embedded/reset.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any

import chromadb
from chromadb.config import Settings
import numpy as np
from prometheus_client import Counter, Gauge, Histogram
from sentence_transformers import SentenceTransformer
import structlog
import torch
import zstandard as zstd

from .embedding_contract import validate_vector
from .exceptions import MemoryException

logger = structlog.get_logger("sticky.memory.engine")
MEMORY_SIZE = Gauge("sticky_memory_size_bytes", "Memory store size in bytes", ["store"])
MEMORY_OPS = Counter("sticky_memory_operations_total", "Memory operations count", ["operation"])
MEMORY_OP_DURATION = Histogram("sticky_memory_operation_duration_seconds", "Memory operation duration")
EMBEDDING_DURATION = Histogram("sticky_embedding_generation_duration_seconds", "Embedding generation duration")
CACHE_HITS = Counter("sticky_memory_cache_hits_total", "Memory cache hit count")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _loaded_model_fingerprint(model: SentenceTransformer) -> str:
    """Bind actual loaded parameters and tokenizer/pooling semantics, not a label."""
    modules = []
    for name, module in model.named_children():
        config = dict(module.get_config_dict()) if hasattr(module, "get_config_dict") else {}
        if hasattr(module, "auto_model"):
            transformer = module.auto_model.config.to_dict()
            for incidental in ("_name_or_path", "transformers_version"):
                transformer.pop(incidental, None)
            config["transformer"] = transformer
        modules.append({"name": name, "type": f"{type(module).__module__}.{type(module).__name__}", "config": config})
    tokenizer = model.tokenizer
    tokenizer_state = (tokenizer.backend_tokenizer.to_str() if hasattr(tokenizer, "backend_tokenizer")
                       else {"vocab": tokenizer.get_vocab(), "special_tokens": tokenizer.special_tokens_map})
    semantic_config = {"modules": modules, "tokenizer": tokenizer_state, "normalize_embeddings": True,
                       "prompts": getattr(model, "prompts", {}),
                       "default_prompt_name": getattr(model, "default_prompt_name", None),
                       "truncate_dim": getattr(model, "truncate_dim", None),
                       "dimension": model.get_embedding_dimension(),
                       "libraries": {name: version(name) for name in ("sentence-transformers", "transformers", "torch")}}
    digest = hashlib.sha256(json.dumps(semantic_config, sort_keys=True, separators=(",", ":"), default=str).encode())
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(json.dumps([name, str(tensor.dtype), list(tensor.shape)], separators=(",", ":")).encode())
        digest.update(tensor.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
    return digest.hexdigest()


class MemoryEngine:
    """Single-writer local vector store; synchronous model work inside async API."""

    def __init__(
        self,
        persist_dir: str = "memory_store",
        sqlite_fallback_path: str | None = None,
        max_size_mb: int = 5,
        backup_dir: str | None = None,
        env: str = "production",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        embedding_cache_size: int = 1000,
        embedding_batch_size: int = 32,
        embedding_revision: str | None = None,
        embedding_model_id: str | None = None,
        local_files_only: bool = True,
    ):
        self.persist_dir = Path(persist_dir).resolve()
        self.sqlite_path = Path(sqlite_fallback_path).resolve() if sqlite_fallback_path else self.persist_dir / "fallback.db"
        self.backup_dir = Path(backup_dir).resolve() if backup_dir else self.persist_dir.with_name(self.persist_dir.name + "-backups")
        if (self.backup_dir == self.persist_dir or self.persist_dir in self.backup_dir.parents
            or self.backup_dir in self.persist_dir.parents or self.sqlite_path == self.backup_dir
            or self.backup_dir in self.sqlite_path.parents or self.sqlite_path in self.backup_dir.parents):
            raise ValueError("Backup directory must not overlap live Chroma or SQLite storage")
        if max_size_mb <= 0 or embedding_cache_size < 0 or embedding_batch_size <= 0:
            raise ValueError("Invalid storage/cache/batch limits")
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.env = env
        self.client = None
        self.collections: dict[str, Any] = {}
        self.sqlite_conn: sqlite3.Connection | None = None
        self.initialized = False
        self.storage_degraded = False
        self.embedding_model = SentenceTransformer(
            embedding_model, revision=embedding_revision, device="cpu",
            trust_remote_code=False, local_files_only=local_files_only,
            model_kwargs={"use_safetensors": True},
        )
        dimension = self.embedding_model.get_embedding_dimension()
        if not isinstance(dimension, int) or dimension <= 0:
            raise ValueError("Loaded model has no fixed embedding dimension")
        self.embedding_dimension = dimension
        self.embedding_identity = embedding_model_id or f"{embedding_model}@{embedding_revision or 'local'}"
        self.embedding_fingerprint = _loaded_model_fingerprint(self.embedding_model)
        self.embedding_cache: dict[str, list[float]] = {}
        self.embedding_cache_size = embedding_cache_size
        self.embedding_batch_size = embedding_batch_size
        self.compressor = zstd.ZstdCompressor(level=3)

    @property
    def _contract(self) -> dict[str, Any]:
        return {"embedding_dimension": self.embedding_dimension, "embedding_model": self.embedding_identity,
                "embedding_fingerprint": self.embedding_fingerprint}

    async def initialize(self) -> None:
        if self.initialized:
            return
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )
            await self._setup_collections()
            await self._setup_sqlite_fallback()
            await self._check_storage_limits()
            await self._create_backup()
            self.initialized = True
        except Exception as error:
            self.cleanup()
            raise MemoryException("Memory initialization failed; inspect store/model compatibility") from error

    async def _setup_collections(self) -> None:
        existing = {collection.name for collection in self.client.list_collections()}
        for name, connections in (("user_memories", 16), ("persona_contexts", 8)):
            metadata = {"hnsw:space": "cosine", "hnsw:M": connections, **self._contract}
            if name in existing:
                collection = self.client.get_collection(name, embedding_function=None)
                current = collection.metadata or {}
                if any(current.get(key) != value for key, value in self._contract.items()):
                    # Even an empty existing store needs an explicit migration if it
                    # declares another model. Never overwrite model identity silently.
                    if collection.count() or any(key in current for key in self._contract):
                        raise ValueError("Existing collection model/dimension mismatch; migrate a copy explicitly")
                    collection.modify(metadata=metadata)
            else:
                collection = self.client.create_collection(name, metadata=metadata, embedding_function=None)
            self.collections[name] = collection

    async def _setup_sqlite_fallback(self) -> None:
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        tables = {row[0] for row in self.sqlite_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "memories" in tables and "engine_metadata" not in tables:
            if self.sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]:
                raise ValueError("Existing fallback data has no model contract; migrate a copy explicitly")
        self.sqlite_conn.execute("CREATE TABLE IF NOT EXISTS engine_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        expected = json.dumps(self._contract, sort_keys=True)
        row = self.sqlite_conn.execute("SELECT value FROM engine_metadata WHERE key='embedding_contract'").fetchone()
        if row and row[0] != expected:
            raise ValueError("SQLite embedding model/dimension mismatch")
        if not row and "memories" in tables and self.sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]:
            raise ValueError("Existing fallback data has no model contract; migrate a copy explicitly")
        self.sqlite_conn.execute("INSERT OR IGNORE INTO engine_metadata VALUES ('embedding_contract', ?)", (expected,))
        self.sqlite_conn.execute("""CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY, user_id TEXT, persona_id TEXT, content BLOB,
            embedding BLOB, created_at TEXT, metadata TEXT)""")
        self.sqlite_conn.execute("CREATE INDEX IF NOT EXISTS idx_user_persona ON memories(user_id, persona_id)")
        self.sqlite_conn.commit()

    def _require_initialized(self) -> None:
        if not self.initialized or self.sqlite_conn is None:
            raise MemoryException("Memory engine is not initialized")

    async def _get_embedding(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise MemoryException("Embedding input must be nonempty text")
        key = hashlib.sha256(text.encode()).hexdigest()
        if key in self.embedding_cache:
            CACHE_HITS.inc()
            return list(self.embedding_cache[key])
        try:
            with EMBEDDING_DURATION.time():
                vector = self.embedding_model.encode(
                    text, batch_size=self.embedding_batch_size, convert_to_numpy=True,
                    normalize_embeddings=True, show_progress_bar=False,
                )
            result = validate_vector(vector.tolist(), self.embedding_dimension)
            if self.embedding_cache_size:
                self.embedding_cache[key] = result
                while len(self.embedding_cache) > self.embedding_cache_size:
                    self.embedding_cache.pop(next(iter(self.embedding_cache)))
            return list(result)
        except Exception as error:
            raise MemoryException("Embedding generation failed") from error

    async def store_memory(self, user_id: str, thread_id: str, persona_id: str, text: str,
                           type: str, salience: float, embedding: list[float] | None = None) -> dict:
        self._require_initialized()
        try:
            if not all(isinstance(value, str) and value.strip() for value in (user_id, thread_id, persona_id, text, type)):
                raise ValueError("Missing required fields")
            if len(text) > 4096 or not np.isfinite(salience) or not 0 <= salience <= 1:
                raise ValueError("Invalid text size or salience")
            vector = validate_vector(embedding if embedding is not None else await self._get_embedding(text), self.embedding_dimension)
            material = json.dumps([user_id, thread_id, persona_id, text], separators=(",", ":")).encode()
            memory_id = hashlib.sha256(material).hexdigest()
            event = {"id": memory_id, "text": text, "type": type, "salience": salience,
                     "created_at": _now(), "thread_id": thread_id, "user_id": user_id, "persona_id": persona_id}
            await self._check_storage_limits(additional_bytes=len(text.encode()) + len(vector) * 4 + len(json.dumps(event).encode()))
            try:
                with MEMORY_OP_DURATION.time():
                    self.collections["user_memories"].upsert(
                        ids=[memory_id], embeddings=[vector], documents=[text],
                        metadatas=[{"user_id": user_id, "thread_id": thread_id, "persona_id": persona_id,
                                    "memory": json.dumps(event)}],
                    )
                self.sqlite_conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
                self.sqlite_conn.commit()
                backend = "chroma"
            except Exception as error:
                self.storage_degraded = True
                logger.warning("Vector write failed; persisting queryable SQLite fallback", error_type=type_name(error))
                self.sqlite_conn.execute("""INSERT OR REPLACE INTO memories
                    (id,user_id,persona_id,content,embedding,created_at,metadata) VALUES (?,?,?,?,?,?,?)""",
                    (memory_id, user_id, persona_id, self.compressor.compress(text.encode()),
                     np.asarray(vector, dtype=np.float32).tobytes(), event["created_at"], json.dumps(event)))
                self.sqlite_conn.commit()
                backend = "sqlite"
            MEMORY_OPS.labels("store").inc()
            return {**event, "storage_backend": backend}
        except Exception as error:
            raise MemoryException("Memory storage failed") from error

    def _fallback_rows(self, user_id: str, persona_id: str | None = None) -> list[tuple[dict, list[float]]]:
        sql, params = "SELECT metadata,embedding FROM memories WHERE user_id=?", [user_id]
        if persona_id is not None:
            sql += " AND persona_id=?"
            params.append(persona_id)
        return [(json.loads(meta), validate_vector(np.frombuffer(vector, dtype=np.float32).tolist(), self.embedding_dimension))
                for meta, vector in self.sqlite_conn.execute(sql, params)]

    async def load_session(self, user_id: str, thread_id: str) -> dict:
        self._require_initialized()
        if not user_id or not thread_id:
            raise MemoryException("Missing user_id or thread_id")
        memories: dict[str, dict] = {}
        try:
            records = self.collections["user_memories"].get(
                where={"$and": [{"user_id": user_id}, {"thread_id": thread_id}]}, include=["metadatas"])
            for meta in records["metadatas"] or []:
                event = json.loads(meta["memory"])
                memories[event["id"]] = event
        except Exception as error:
            self.storage_degraded = True
            logger.warning("Vector read failed; returning available SQLite fallback", error_type=type_name(error))
        for event, _ in self._fallback_rows(user_id):
            if event["thread_id"] == thread_id:
                memories[event["id"]] = event
        ordered = sorted(memories.values(), key=lambda event: (event["created_at"], event["id"]))
        MEMORY_OPS.labels("retrieve").inc()
        return {"thread_id": thread_id, "user_id": user_id, "messages": ordered,
                "created_at": ordered[0]["created_at"] if ordered else _now(), "storage_degraded": self.storage_degraded}

    async def _query(self, user_id: str, persona_id: str, query: str, top_k: int) -> list[tuple[dict, list[float]]]:
        self._require_initialized()
        if not user_id or not persona_id or not isinstance(top_k, int) or not 1 <= top_k <= 100:
            raise MemoryException("Invalid query scope or top_k")
        vector = await self._get_embedding(query)
        candidates: dict[str, tuple[float, dict, list[float]]] = {}
        try:
            collection = self.collections["user_memories"]
            if collection.count():
                results = collection.query(query_embeddings=[vector],
                    where={"$and": [{"user_id": user_id}, {"persona_id": persona_id}]},
                    n_results=min(top_k, collection.count()), include=["metadatas", "embeddings", "distances"])
                for meta, embedding, distance in zip(results["metadatas"][0], results["embeddings"][0], results["distances"][0]):
                    event = json.loads(meta["memory"])
                    candidates[event["id"]] = (float(distance), event, list(embedding))
        except Exception as error:
            self.storage_degraded = True
            logger.warning("Vector search failed; querying SQLite fallback", error_type=type_name(error))
        query_vector = np.asarray(vector)
        for event, embedding in self._fallback_rows(user_id, persona_id):
            stored = np.asarray(embedding)
            norm = float(np.linalg.norm(query_vector) * np.linalg.norm(stored))
            distance = 1 - float(np.dot(query_vector, stored)) / norm if norm else 1.0
            candidates[event["id"]] = (distance, event, embedding)
        MEMORY_OPS.labels("search").inc()
        ordered = sorted(candidates.values(), key=lambda item: (item[0], item[1]["id"]))[:top_k]
        return [(event, embedding) for _, event, embedding in ordered]

    async def build_context(self, user_id: str, thread_id: str, persona_id: str, query: str,
                            include_memory: bool = True, top_k: int = 3) -> dict:
        session = await self.load_session(user_id, thread_id)
        matches = await self._query(user_id, persona_id, query, top_k) if include_memory else []
        return {"messages": session["messages"], "memory": self._format_memories([event for event, _ in matches]),
                "storage_degraded": self.storage_degraded}

    async def transfer_context(self, user_id: str, from_persona: str, to_persona: str, query: str) -> list[dict]:
        if not to_persona or to_persona == from_persona:
            raise MemoryException("Transfer requires different source and destination personas")
        matches = await self._query(user_id, from_persona, query, 5)
        return [await self.store_memory(user_id, event["thread_id"], to_persona, event["text"],
                                       "transferred", event["salience"], embedding)
                for event, embedding in matches]

    async def _check_storage_limits(self, additional_bytes: int = 0) -> None:
        paths = {path.resolve() for path in self.persist_dir.rglob("*") if path.is_file()}
        if self.sqlite_path.is_file():
            paths.add(self.sqlite_path)
        total = sum(path.stat().st_size for path in paths)
        MEMORY_SIZE.labels("total").set(total)
        if total + additional_bytes > self.max_size_bytes:
            raise MemoryException("Memory size exceeds configured limit; archive data explicitly")

    async def _cleanup_old_data(self) -> None:
        """Explicit retention operation; never called by ordinary close or writes."""
        self._require_initialized()
        collection = self.collections["user_memories"]
        records = collection.get(include=["metadatas"])
        ordered = sorted(zip(records["ids"], records["metadatas"]), key=lambda item: json.loads(item[1]["memory"])["created_at"])
        if ordered:
            collection.delete(ids=[identifier for identifier, _ in ordered[:max(1, len(ordered) // 5)]])
        count = self.sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        if count:
            self.sqlite_conn.execute("DELETE FROM memories WHERE id IN (SELECT id FROM memories ORDER BY created_at LIMIT ?)", (max(1, count // 5),))
            self.sqlite_conn.commit()
            self.sqlite_conn.execute("VACUUM")

    async def _create_backup(self) -> Path:
        """Publish a complete snapshot of a quiescent single-writer store.

        Failed copies are not published or counted by retention. The manifest
        permits independent file-integrity checks; concurrent writes are unsupported.
        """
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup = self.backup_dir / ("memory_store_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S%f"))
        with tempfile.TemporaryDirectory(prefix=".pending-", dir=self.backup_dir) as temporary:
            staged = Path(temporary) / "snapshot"
            shutil.copytree(self.persist_dir, staged)
            if self.sqlite_conn is not None:
                with sqlite3.connect(staged / "fallback.db") as destination:
                    self.sqlite_conn.backup(destination)
            hashes = {}
            for path in sorted(staged.rglob("*")):
                if path.is_file() and path.name != "backup-manifest.json":
                    digest = hashlib.sha256()
                    with path.open("rb") as source:
                        for block in iter(lambda: source.read(65536), b""):
                            digest.update(block)
                    hashes[path.relative_to(staged).as_posix()] = digest.hexdigest()
            (staged / "backup-manifest.json").write_text(json.dumps(
                {"complete": True, "created_at": _now(), "model_contract": self._contract, "file_hashes": hashes},
                sort_keys=True, indent=2) + "\n", encoding="utf-8")
            staged.replace(backup)
        completed = [path for path in sorted(self.backup_dir.glob("memory_store_*"))
                     if path.is_dir() and (path / "backup-manifest.json").is_file()]
        for old in completed[:-5]:
            shutil.rmtree(old)
        return backup

    def cleanup(self) -> None:
        """Close this instance without resetting/deleting persisted user data."""
        if self.sqlite_conn is not None:
            self.sqlite_conn.close()
            self.sqlite_conn = None
        self.collections.clear()
        self.client = None  # Chroma owns native handle lifecycle; persistence is automatic.
        self.embedding_cache.clear()
        self.initialized = False

    @staticmethod
    def _format_memories(memories: list[dict]) -> list[str]:
        return [f"- {memory['text']}" for memory in memories]


def type_name(error: Exception) -> str:
    return error.__class__.__name__
