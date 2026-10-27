from __future__ import annotations

import json
import logging

import keyring
import pytest
from fastapi.testclient import TestClient

from aura.infrastructure.llm.nebius import NebiusPlannerProvider
from aura.workspace.server import create_app
from tests.test_model_profiles import KEY, OLLAMA, OPENAI, MemoryKeyring, Response, Session, envelope


@pytest.fixture
def api(tmp_path, monkeypatch):
    """App wired to a temporary data dir and an in-memory keyring (never the real credential store)."""
    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    previous = keyring.get_keyring()
    memory = MemoryKeyring()
    keyring.set_keyring(memory)
    app = create_app(storage_mode="memory")
    client = TestClient(app)
    client.application = app.state.workspace
    client.keyring = memory
    client.data_dir = tmp_path
    yield client
    keyring.set_keyring(previous)


def put_profile(api, profile=OPENAI):
    return api.put(f"/api/model-profiles/{profile['profileId']}", json={k: v for k, v in profile.items() if k != "profileId"})


def test_list_starts_with_env_default_and_no_active(api):
    body = api.get("/api/model-profiles").json()
    assert body["active"] is None and body["activeSource"] == "environment"
    assert [p["profileId"] for p in body["profiles"]] == ["nemotron-nebius"] and body["profiles"][0]["builtIn"] is True


def test_key_put_then_get_has_key_and_no_key_text_anywhere(api, caplog):
    caplog.set_level(logging.DEBUG)
    assert put_profile(api).status_code == 200
    response = api.put("/api/model-profiles/work-openai/key", json={"key": KEY})
    assert response.status_code == 204 and response.content == b""
    listing = api.get("/api/model-profiles")
    assert next(p for p in listing.json()["profiles"] if p["profileId"] == "work-openai")["hasKey"] is True
    assert KEY not in listing.text and KEY not in put_profile(api).text
    assert api.keyring.data == {("aura-model", "work-openai"): KEY}
    for path in api.data_dir.rglob("*"):
        if path.is_file():
            assert KEY not in path.read_text(encoding="utf-8", errors="ignore")
    assert KEY not in caplog.text


def test_invalid_profiles_are_422_with_errors(api):
    response = api.put("/api/model-profiles/only-key", json={"key": KEY})
    assert response.status_code == 422 and KEY not in response.text
    detail = response.json()["detail"]
    assert detail["code"] == "PROFILE_INVALID" and any("baseUrl" in e for e in detail["errors"])
    response = api.put("/api/model-profiles/work-openai", json=OPENAI | {"baseUrl": "http://api.example.test/v1"})
    assert response.status_code == 422 and any("https" in e for e in response.json()["detail"]["errors"])
    assert api.put("/api/model-profiles/work-openai", json=OPENAI | {"profileId": "other"}).status_code == 422
    assert api.get("/api/model-profiles").json()["profiles"][0]["profileId"] == "nemotron-nebius"


def test_key_endpoint_does_not_echo_malformed_secret_bodies(api):
    put_profile(api)
    for payload in ('"' + KEY + '"', json.dumps({"key": 12345}), json.dumps({"other": KEY}), "not json " + KEY):
        response = api.put("/api/model-profiles/work-openai/key", content=payload, headers={"content-type": "application/json"})
        assert response.status_code == 422 and KEY not in response.text
    assert api.put("/api/model-profiles/missing/key", json={"key": KEY}).status_code == 404
    assert api.keyring.data == {}


def test_set_active_changes_provider_used_by_next_call(api):
    application = api.application
    put_profile(api)
    api.put("/api/model-profiles/work-openai/key", json={"key": KEY})
    put_profile(api, OLLAMA)
    api.post("/api/model-profiles/active", json={"profileId": "local-llama"})
    application.provider = application.provider or application._default_provider()  # what a model-backed route does
    assert application.provider.model == "llama3.1"
    assert api.post("/api/model-profiles/active", json={"profileId": "work-openai"}).json()["active"] == "work-openai"
    assert application.provider is None
    provider = application.provider or application._default_provider()
    assert provider.model == "gpt-test" and provider.get_diagnostics()["backend"] == "openai_compatible"
    application.provider = provider
    api.post("/api/model-profiles/active", json={"profileId": "local-llama"})
    assert application.provider is None
    switched = application.provider or application._default_provider()
    assert switched.model == "llama3.1" and switched.get_diagnostics()["backend"] == "ollama"


def test_injected_provider_is_not_replaced_by_profile_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    previous = keyring.get_keyring()
    keyring.set_keyring(MemoryKeyring())
    try:
        sentinel = object()
        client = TestClient(create_app(provider=sentinel, storage_mode="memory"))
        client.put("/api/model-profiles/local-llama", json={k: v for k, v in OLLAMA.items() if k != "profileId"})
        client.post("/api/model-profiles/active", json={"profileId": "local-llama"})
        assert client.app.state.workspace.provider is sentinel
    finally:
        keyring.set_keyring(previous)


def test_unknown_active_profile_is_404_and_changes_nothing(api):
    response = api.post("/api/model-profiles/active", json={"profileId": "nope"})
    assert response.status_code == 404 and api.get("/api/model-profiles").json()["active"] is None


def test_active_profile_failure_surfaces_and_never_falls_back(api, monkeypatch):
    application = api.application
    put_profile(api)
    put_profile(api, OLLAMA)
    api.put("/api/model-profiles/work-openai/key", json={"key": KEY})
    api.post("/api/model-profiles/active", json={"profileId": "work-openai"})
    api.keyring.delete_password("aura-model", "work-openai")  # the key vanishes from the credential store
    monkeypatch.setenv("NEBIUS_API_KEY", "env-key")
    with pytest.raises(RuntimeError) as caught:
        application._default_provider()
    assert "work-openai" in str(caught.value) and KEY not in str(caught.value)


def test_delete_removes_profile_key_and_active_selection(api):
    put_profile(api)
    api.put("/api/model-profiles/work-openai/key", json={"key": KEY})
    api.post("/api/model-profiles/active", json={"profileId": "work-openai"})
    assert api.delete("/api/model-profiles/work-openai").status_code == 204
    body = api.get("/api/model-profiles").json()
    assert body["active"] is None and [p["profileId"] for p in body["profiles"]] == ["nemotron-nebius"] and api.keyring.data == {}
    assert api.delete("/api/model-profiles/work-openai").status_code == 404


def test_test_endpoint_reports_ok_and_real_error_classes_without_the_key(api, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    put_profile(api)
    api.put("/api/model-profiles/work-openai/key", json={"key": KEY})
    sessions = iter([Session(Response(data=envelope('{"ok":true}'))), Session(Response(401, text=f"bad {KEY}")), Session(ConnectionError(KEY)),
                     Session(Response(data={"bad": True}))])
    monkeypatch.setattr(NebiusPlannerProvider, "_http", lambda self: next(sessions))
    ok = api.post("/api/model-profiles/work-openai/test").json()
    assert ok["ok"] is True and "latencyMs" in ok
    codes = []
    for _ in range(3):
        result = api.post("/api/model-profiles/work-openai/test")
        assert result.status_code == 200 and KEY not in result.text
        codes.append(result.json()["code"])
    assert codes == ["MODEL_AUTHENTICATION", "MODEL_UNAVAILABLE", "MODEL_RESPONSE_INVALID"]
    assert KEY not in caplog.text
    assert api.post("/api/model-profiles/missing/test").status_code == 404


def test_unreadable_profile_file_is_reported(api):
    (api.data_dir / "model_profiles.json").write_text("{broken", encoding="utf-8")
    response = api.get("/api/model-profiles")
    assert response.status_code == 500 and response.json()["detail"]["code"] == "PROFILES_UNREADABLE"
