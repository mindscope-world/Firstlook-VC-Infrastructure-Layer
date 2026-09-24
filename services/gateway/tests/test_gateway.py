import pytest
from fastapi.testclient import TestClient

from firstlook_gateway import app as gateway_app
from firstlook_gateway.providers import Completion, _empty_for
from firstlook_gateway.redaction import redact
from firstlook_gateway.routing import cost_usd, route_for

AUTH = {"Authorization": "Bearer local-dev-internal-token"}
SCHEMA = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "string"}}},
          "required": ["items"], "additionalProperties": False}


def test_redaction():
    text, counts = redact("card 4111 1111 1111 1111, pin A123456789Z, password: hunter2, ssn 123-45-6789, "
                          "call +254 712 345 678, email jane@acme.io")
    assert "4111" not in text and "hunter2" not in text and "A123456789Z" not in text and "123-45-6789" not in text
    assert "jane@acme.io" in text and "+254 712 345 678" in text  # kept: needed for relationships
    assert counts == {"card": 1, "kra_pin": 1, "credential": 1, "us_ssn": 1}
    # Luhn-invalid digit runs are not cards.
    assert redact("order 1234 5678 9012 3456")[0] == "order 1234 5678 9012 3456"


def test_routing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    assert route_for("extract.interaction", "structured").provider == "offline"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    r = route_for("extract.interaction", "structured")
    assert (r.provider, r.model) == ("anthropic", "claude-opus-5")
    monkeypatch.setenv("GATEWAY_ROUTE_EXTRACT_INTERACTION", "litellm:gpt-default")
    assert route_for("extract.interaction", "structured").provider == "litellm"
    assert route_for("x", "embed").provider == "local"
    assert cost_usd("claude-opus-5", 1_000_000, 100_000) == pytest.approx(7.5)


def test_offline_empty_matches_schema():
    assert _empty_for(SCHEMA) == {"items": []}


@pytest.mark.db
def test_structured_endpoint_meters_audits_and_enforces_budget(make_tenant, monkeypatch):
    from firstlook_core.db import tenant_tx

    t, _ = make_tenant("Gateway Fund")
    calls = []

    class Stub:
        def structured(self, model, system, user, schema, max_tokens):
            calls.append(user)
            return Completion({"items": ["x"]}, "claude-opus-5", 2_000_000, 100_000, "req_1")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setitem(gateway_app._providers, "anthropic", Stub())
    client = TestClient(gateway_app.app)
    body = {"task": "extract.interaction", "system": "s", "user": "card 4111 1111 1111 1111", "schema": SCHEMA}

    assert client.post("/v1/structured", json=body).status_code == 401
    assert client.post("/v1/structured", json=body, headers=AUTH).status_code == 400  # no tenant

    r = client.post("/v1/structured", json=body, headers={**AUTH, "X-Tenant-Id": str(t)})
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"items": ["x"]} and r.json()["redactions"] == {"card": 1}
    assert "4111" not in calls[0]

    with tenant_tx(t) as conn:
        usage = conn.execute("SELECT model, cost_usd FROM llm_usage").fetchall()
        audit = conn.execute("SELECT details FROM audit_events WHERE action = 'llm.call'").fetchall()
        assert [u["model"] for u in usage] == ["claude-opus-5"]
        assert float(usage[0]["cost_usd"]) == pytest.approx(12.5)
        assert audit[0]["details"]["transcript_uri"].startswith("file://tenants/")
        conn.execute("UPDATE llm_budgets SET monthly_limit_usd = 10")

    r = client.post("/v1/structured", json=body, headers={**AUTH, "X-Tenant-Id": str(t)})
    assert r.status_code == 402


def test_embeddings_local():
    client = TestClient(gateway_app.app)
    r = client.post("/v1/embeddings", json={"input": ["Jane Doe"]},
                    headers={**AUTH, "X-Tenant-Id": "00000000-0000-0000-0000-000000000001"})
    assert r.status_code == 200
    assert len(r.json()["embeddings"][0]) == 1024
