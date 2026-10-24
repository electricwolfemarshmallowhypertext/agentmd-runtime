"""Real local-model/vector regressions; deliberately outside live API conftest.

No model download is performed by these tests. Set AGENTMD_TEST_MODEL_PATH to an
approved local MiniLM safetensors snapshot. No mocks or fabricated embeddings.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import socket
import sys

import pytest

MODEL = os.environ.get("AGENTMD_TEST_MODEL_PATH")
if not MODEL:
    pytest.skip("Real local MiniLM snapshot required: set AGENTMD_TEST_MODEL_PATH", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/api"))
import numpy as np
from src.memory.memory_engine import MemoryEngine
from src.memory.exceptions import MemoryException
from src.memory.models import Memory, MemoryVector, create_memory, create_batch
from src.memory.validation import MemoryEvent, validate_memory_input

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2@1110a243fdf4706b3f48f1d95db1a4f5529b4d41"


def run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original = socket.socket.connect
    def reject_inet(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            raise OSError("Network disabled for local model regression")
        return original(sock, address)
    monkeypatch.setattr(socket.socket, "connect", reject_inet)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")


def make_engine(root: Path, **kwargs):
    return MemoryEngine(persist_dir=str(root / "store"), embedding_model=MODEL,
                        embedding_model_id=MODEL_ID, max_size_mb=20, **kwargs)


@pytest.fixture()
def engine(tmp_path):
    instance = make_engine(tmp_path)
    run(instance.initialize())
    try:
        yield instance
    finally:
        instance.cleanup()


def store(engine, text="Cats chase mice", user="user-a", thread="thread-a", persona="persona-a", **kwargs):
    return run(engine.store_memory(user, thread, persona, text, "fact", 0.5, **kwargs))


def test_real_model_inference_cache_and_semantics(engine):
    cat = run(engine._get_embedding("Cats chase mice"))
    query = run(engine._get_embedding("Tell me about cats"))
    unrelated = run(engine._get_embedding("The stock market trades corporate bonds"))
    assert engine.embedding_dimension == len(cat) == 384
    assert np.isfinite(cat).all()
    assert np.linalg.norm(cat) == pytest.approx(1.0, abs=1e-5)
    assert np.dot(cat, query) > np.dot(unrelated, query)
    assert cat == run(engine._get_embedding("Cats chase mice"))
    altered = run(engine._get_embedding("Cats chase mice")); altered[0] = 999.0
    assert run(engine._get_embedding("Cats chase mice"))[0] != 999.0
    with pytest.raises(MemoryException):
        run(engine._get_embedding(""))


def test_real_chroma_text_storage_scope_and_ids(engine):
    first = store(engine)
    duplicate = store(engine)
    other_persona = store(engine, persona="persona-b")
    store(engine, text="Another user's secret-free fixture", user="user-b")
    assert first["storage_backend"] == duplicate["storage_backend"] == "chroma"
    assert first["id"] == duplicate["id"] != other_persona["id"]
    records = engine.collections["user_memories"].get(ids=[first["id"]], include=["documents", "metadatas", "embeddings"])
    assert records["documents"] == ["Cats chase mice"]
    assert records["metadatas"][0]["thread_id"] == "thread-a"
    assert len(records["embeddings"][0]) == 384
    session = run(engine.load_session("user-a", "thread-a"))
    assert len(session["messages"]) == 2
    assert all(item["user_id"] == "user-a" for item in session["messages"])
    assert engine.sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0


def test_real_transfer_requests_embeddings_and_preserves_personas(engine):
    source = store(engine)
    moved = run(engine.transfer_context("user-a", "persona-a", "persona-b", "cats"))
    assert moved and moved[0]["id"] != source["id"]
    assert moved[0]["storage_backend"] == "chroma"
    assert engine.collections["user_memories"].count() == 2
    target = run(engine.build_context("user-a", "thread-a", "persona-b", "cats"))
    assert target["memory"] == ["- Cats chase mice"]
    with pytest.raises(MemoryException):
        run(engine.transfer_context("user-a", "persona-a", "persona-a", "cats"))


def test_real_cleanup_reopen_does_not_reset_store(engine, tmp_path):
    first = store(engine)
    engine.cleanup()
    reopened = make_engine(tmp_path)
    try:
        run(reopened.initialize())
        assert reopened.collections["user_memories"].count() == 1
        assert run(reopened.load_session("user-a", "thread-a"))["messages"][0]["id"] == first["id"]
    finally:
        reopened.cleanup()


def test_real_collection_failure_has_queryable_persistent_sqlite_fallback(engine, tmp_path):
    # Actual backend operation removes this synthetic collection; no mocked client.
    engine.client.delete_collection("user_memories")
    event = store(engine, text="Fallback memories persist")
    assert event["storage_backend"] == "sqlite"
    content, vector = engine.sqlite_conn.execute("SELECT content,embedding FROM memories").fetchone()
    import zstandard
    assert zstandard.ZstdDecompressor().decompress(content).decode() == event["text"]
    assert np.frombuffer(vector, dtype=np.float32).shape == (384,)
    assert run(engine.build_context("user-a", "thread-a", "persona-a", "Fallback memories"))["memory"] == ["- Fallback memories persist"]
    engine.cleanup()
    reopened = make_engine(tmp_path)
    try:
        run(reopened.initialize())
        assert run(reopened.load_session("user-a", "thread-a"))["messages"][0]["id"] == event["id"]
        moved = run(reopened.transfer_context("user-a", "persona-a", "persona-b", "Fallback memories"))
        assert moved and moved[0]["storage_backend"] == "chroma"
    finally:
        reopened.cleanup()


def test_model_dimension_and_finiteness_are_enforced_at_storage(engine):
    for vector in [[0.0] * 1024, [float("nan")] * 384, [float("inf")] * 384, [1e100] * 384]:
        with pytest.raises(MemoryException):
            store(engine, embedding=vector)
    assert engine.collections["user_memories"].count() == 0
    assert engine.sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0


def test_model_contract_mismatch_does_not_modify_persisted_records(engine, tmp_path):
    original = store(engine)
    engine.collections["user_memories"].modify(metadata={**engine.collections["user_memories"].metadata, "embedding_dimension": 1024})
    other = make_engine(tmp_path)
    with pytest.raises(MemoryException):
        run(other.initialize())
    assert engine.collections["user_memories"].get(ids=[original["id"]])["ids"] == [original["id"]]


def test_backup_directory_and_retention_are_non_recursive(engine, tmp_path):
    store(engine)
    backup = run(engine._create_backup())
    assert backup.parent == engine.backup_dir
    assert engine.persist_dir not in backup.parents
    assert (backup / "fallback.db").is_file()
    assert not list(backup.rglob("memory_store_*"))
    with pytest.raises(ValueError, match="Backup directory"):
        make_engine(tmp_path, backup_dir=str(engine.persist_dir / "backups"))


def test_budget_failure_does_not_delete_prior_memories(engine):
    first = store(engine)
    engine.max_size_bytes = 1
    with pytest.raises(MemoryException):
        store(engine, text="This write must not occur")
    assert engine.collections["user_memories"].count() == 1
    assert run(engine.load_session("user-a", "thread-a"))["messages"][0]["id"] == first["id"]


def test_schema_helpers_share_actual_default_vector_contract(engine):
    vector = run(engine._get_embedding("A real vector"))
    item = create_memory("A real vector", "thread", "user", "persona")
    assert item.id and create_batch([item], "user", "thread", "persona").batch_id
    assert len(MemoryVector(memory_id=item.id, embedding=vector).embedding) == 384
    assert Memory(**{**item.model_dump(), "embedding": vector}).embedding_dimension == 384
    event = validate_memory_input("A real vector", "thread", "user", "persona")
    assert event["id"] and MemoryEvent(**{**event, "embedding": vector}).embedding_dimension == 384
    with pytest.raises(ValueError):
        MemoryVector(memory_id=item.id, embedding=[float("nan")] * 384)
    # Schema metadata can declare another model, but the actual store still rejects it.
    assert MemoryVector(memory_id=item.id, embedding_dimension=2, embedding=[1.0, 0.0]).embedding_dimension == 2
    with pytest.raises(MemoryException):
        store(engine, embedding=[1.0, 0.0])


@pytest.mark.parametrize("change", ["pooling", "prompt"])
def test_actual_encode_change_same_dimension_and_label_is_rejected(engine, tmp_path, change):
    import shutil
    original = store(engine)
    changed_model = tmp_path / "changed-model"
    shutil.copytree(MODEL, changed_model)
    config_path = changed_model / ("1_Pooling/config.json" if change == "pooling" else "config_sentence_transformers.json")
    config = json.loads(config_path.read_text())
    if change == "pooling":
        config["pooling_mode_mean_tokens"] = False
        config["pooling_mode_cls_token"] = True
    else:
        config["prompts"] = {"changed": "Represent this question for retrieval: "}
        config["default_prompt_name"] = "changed"
    config_path.write_text(json.dumps(config))
    alternate = MemoryEngine(persist_dir=str(engine.persist_dir), embedding_model=str(changed_model),
                             embedding_model_id=MODEL_ID, max_size_mb=20)
    assert alternate.embedding_dimension == engine.embedding_dimension == 384
    assert alternate.embedding_fingerprint != engine.embedding_fingerprint
    with pytest.raises(MemoryException):
        run(alternate.initialize())
    assert engine.collections["user_memories"].get(ids=[original["id"]])["ids"] == [original["id"]]


def test_missing_sqlite_contract_row_never_labels_unknown_vectors(engine, tmp_path):
    engine.client.delete_collection("user_memories")
    event = store(engine, text="Retain unknown-contract fallback")
    engine.sqlite_conn.execute("DELETE FROM engine_metadata WHERE key='embedding_contract'")
    engine.sqlite_conn.commit()
    other = make_engine(tmp_path)
    with pytest.raises(MemoryException):
        run(other.initialize())
    assert engine.sqlite_conn.execute("SELECT COUNT(*) FROM engine_metadata").fetchone()[0] == 0
    assert engine.sqlite_conn.execute("SELECT id FROM memories").fetchone()[0] == event["id"]


def test_failed_backup_copy_does_not_publish_or_prune(engine, monkeypatch):
    import shutil
    before = sorted(engine.backup_dir.iterdir())
    def fail_copy(source, target):
        target.mkdir()
        (target / "partial").write_text("synthetic partial copy")
        raise OSError("synthetic disk failure")
    monkeypatch.setattr(shutil, "copytree", fail_copy)
    with pytest.raises(OSError):
        run(engine._create_backup())
    assert sorted(engine.backup_dir.iterdir()) == before


def test_real_backup_restores_both_chroma_and_sqlite_data(engine, tmp_path):
    import hashlib
    import shutil
    engine.client.delete_collection("user_memories")
    fallback = store(engine, text="SQLite backup record")
    run(engine._setup_collections())
    primary = store(engine, text="Chroma backup record")
    assert fallback["storage_backend"] == "sqlite" and primary["storage_backend"] == "chroma"
    backup = run(engine._create_backup())
    manifest = json.loads((backup / "backup-manifest.json").read_text())
    assert manifest["complete"] is True
    for relative, expected in manifest["file_hashes"].items():
        assert hashlib.sha256((backup / relative).read_bytes()).hexdigest() == expected
    restore_root = tmp_path / "restored"
    shutil.copytree(backup, restore_root / "store")
    restored = make_engine(restore_root)
    try:
        run(restored.initialize())
        messages = run(restored.load_session("user-a", "thread-a"))["messages"]
        assert {message["id"] for message in messages} == {fallback["id"], primary["id"]}
        assert restored.collections["user_memories"].count() == 1
        assert restored.sqlite_conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 1
        context = run(restored.build_context("user-a", "thread-a", "persona-a", "backup record", top_k=2))
        assert set(context["memory"]) == {"- SQLite backup record", "- Chroma backup record"}
    finally:
        restored.cleanup()


def test_backup_retention_cannot_contain_live_external_sqlite(tmp_path):
    backups = tmp_path / "backups"
    with pytest.raises(ValueError, match="Backup directory"):
        MemoryEngine(persist_dir=str(tmp_path / "live"), backup_dir=str(backups),
                     sqlite_fallback_path=str(backups / "memory_store_old" / "live.db"), embedding_model=MODEL)
    assert not backups.exists()
    assert not (tmp_path / "live").exists()
