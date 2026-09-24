"""Contract tests every adapter implementation must pass.

Local implementations run always. Cloud implementations added in Phase 4 are
appended to the parametrised lists (and the S3/Kafka ones run when the local
stack is up: `make up`).
"""

import os
import socket

import pytest
from cryptography.exceptions import InvalidTag

from firstlook_core.adapters.bus import InMemoryBus
from firstlook_core.adapters.kms import LocalKms
from firstlook_core.adapters.storage import LocalFsStore, S3Store, content_key
from firstlook_core.crypto import TenantCipher


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def stores(tmp_path):
    out = [LocalFsStore(tmp_path)]
    if _port_open("localhost", 18333):
        out.append(
            S3Store(
                "firstlook-contract-test",
                "http://localhost:18333",
                "firstlook",
                "firstlook-secret",
                "us-east-1",
            )
        )
    return out


def test_object_store_contract(tmp_path):
    for store in stores(tmp_path):
        key = content_key("t1", "raw/email", b"hello")
        uri = store.put(key, b"hello", "text/plain")
        assert uri == store.uri_for(key)
        assert store.exists(uri)
        assert store.get(uri) == b"hello"
        assert not store.exists(store.uri_for(content_key("t1", "raw/email", b"other")))
        # Content addressing: same bytes, same key.
        assert content_key("t1", "raw/email", b"hello") == key
        assert key.startswith("tenants/t1/")


def test_local_store_rejects_path_escape(tmp_path):
    store = LocalFsStore(tmp_path)
    with pytest.raises(ValueError):
        store.put("../../etc/passwd", b"x")


def test_kms_contract():
    kms = LocalKms(os.urandom(32))
    dek = os.urandom(32)
    wrapped = kms.wrap(dek, b"tenant-a")
    assert wrapped != dek
    assert kms.unwrap(wrapped, b"tenant-a") == dek
    with pytest.raises(InvalidTag):
        kms.unwrap(wrapped, b"tenant-b")  # context-bound
    with pytest.raises(InvalidTag):
        LocalKms(os.urandom(32)).unwrap(wrapped, b"tenant-a")  # different master key


def test_tenant_cipher_binds_tenant():
    dek = os.urandom(32)
    a = TenantCipher("a", dek)
    blob = a.encrypt_json({"token": "secret"})
    assert b"secret" not in blob
    assert a.decrypt_json(blob) == {"token": "secret"}
    with pytest.raises(InvalidTag):
        TenantCipher("b", dek).decrypt(blob)


def buses():
    out = [InMemoryBus()]
    if _port_open("localhost", 19092):
        from firstlook_core.adapters.bus import KafkaBus

        out.append(KafkaBus("localhost:19092"))
    return out


def test_bus_contract():
    import uuid

    for bus in buses():
        topic = f"contract-{uuid.uuid4().hex[:8]}"
        bus.publish(topic, {"n": 1}, key="k")
        bus.publish(topic, {"n": 2}, key="k")
        bus.flush()
        seen = []
        kwargs = {"idle_timeout": 10} if not isinstance(bus, InMemoryBus) else {}
        n = bus.consume(
            [topic], "g1", lambda e, seen=seen: seen.append(e.payload["n"]), max_events=2, **kwargs
        )
        assert n == 2 and seen == [1, 2]
        # A consumer group resumes after committed events.
        more = bus.consume(
            [topic],
            "g1",
            lambda e, seen=seen: seen.append(e.payload["n"]),
            max_events=1,
            **({"idle_timeout": 3} if kwargs else {}),
        )
        assert more == 0


def test_dead_letter_queue():
    from firstlook_core.adapters.bus import run_consumer

    bus = InMemoryBus()
    bus.publish("t", {"ok": False})
    bus.publish("t", {"ok": True})
    handled = []

    def handler(e):
        if not e.payload["ok"]:
            raise ValueError("boom")
        handled.append(e)

    run_consumer(["t"], "g", handler, bus=bus)
    assert len(handled) == 1
    dlq = bus.topics["t.dlq"]
    assert len(dlq) == 1 and "boom" in dlq[0].payload["error"]
