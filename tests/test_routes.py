"""Route-level tests for the voice plugin."""


def test_health_endpoint(client):
    resp = client.get("/voice/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["plugin"] == "voice"


def test_static_index_returns_200(client):
    resp = client.get("/voice/")
    assert resp.status_code == 200


def test_status_endpoint_unconfigured(client, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.get("/voice/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "unconfigured"
    assert data["api_key_set"] is False


def test_status_endpoint_configured(client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    resp = client.get("/voice/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["api_key_set"] is True


def test_sessions_list_empty(client):
    resp = client.get("/voice/sessions")
    assert resp.status_code == 200
    assert resp.json() == []


def test_sessions_stats_empty(client):
    resp = client.get("/voice/sessions/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_sdp_missing_body(client):
    resp = client.post("/voice/sdp", content=b"")
    assert resp.status_code == 400


def test_sdp_missing_auth(client):
    resp = client.post("/voice/sdp", content=b"v=0\r\n")
    assert resp.status_code == 401


def test_tool_execute_missing_name(client):
    resp = client.post("/voice/tools/execute", json={})
    assert resp.status_code == 400
    assert "name" in resp.json()["error"]


def test_tool_execute_unknown_tool(client):
    resp = client.post("/voice/tools/execute", json={"name": "unknown_tool"})
    assert resp.status_code == 400
    assert "Unknown tool" in resp.json()["error"]


def test_tool_delegate_no_session(client):
    resp = client.post(
        "/voice/tools/execute",
        json={"name": "delegate", "arguments": {"instruction": "test"}},
    )
    assert resp.status_code == 400
    assert "No active" in resp.json()["error"]


def test_cancel_invalid_level(client):
    resp = client.post(
        "/voice/cancel",
        json={"session_id": "test", "level": "invalid"},
    )
    assert resp.status_code == 400


def test_end_session_invalid_id(client):
    resp = client.post("/voice/sessions/!!invalid!!/end", json={})
    assert resp.status_code == 400
