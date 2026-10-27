from __future__ import annotations

import json
import logging
from dataclasses import replace

import pytest
from keyring.backend import KeyringBackend
from keyring.errors import PasswordDeleteError

from aura.app.model_profiles import ProfileError, ProfileStore, validate_profile
from aura.infrastructure.llm.nebius import NebiusPlannerProvider

KEY = "sk-test-secret-0123456789"
OPENAI = {"profileId": "work-openai", "label": "Work OpenAI", "kind": "openai_compatible",
          "baseUrl": "https://api.example.test/v1", "model": "gpt-test"}
OLLAMA = {"profileId": "local-llama", "label": "Local llama", "kind": "ollama_local",
          "baseUrl": "http://localhost:11434", "model": "llama3.1"}


class MemoryKeyring(KeyringBackend):
    """In-memory keyring so tests never touch the real credential store."""
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.data: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.data.get((service, username))

    def set_password(self, service, username, password):
        self.data[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.data:
            raise PasswordDeleteError("missing")
        del self.data[(service, username)]


class Response:
    def __init__(self, status=200, data=None, headers=None, text=""):
        self.status_code, self._data, self.headers, self.text = status, data, headers or {}, text

    def json(self):
        return self._data


class Session:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def envelope(text):
    return {"model": "m", "choices": [{"finish_reason": "stop", "message": {"content": text}}], "usage": {}}


def stored_ids(store):
    return [p["profileId"] for p in store.list() if not p.get("builtIn")]


@pytest.fixture
def store(tmp_path):
    return ProfileStore(tmp_path / "model_profiles.json", MemoryKeyring())


@pytest.fixture
def env_settings(monkeypatch):
    import aura.app.config as config
    base = config.Settings()
    monkeypatch.setattr(config, "Settings", lambda: replace(
        base, nebius_api_key="env-nebius-key", nebius_base_url="https://api.tokenfactory.example/v1/",
        nebius_model="nvidia/nemotron-test", planner_provider="nebius"))


def test_key_only_profile_rejected(store):
    errors = validate_profile({"profileId": "only-key", "key": KEY})
    assert any("kind" in e for e in errors) and any("baseUrl" in e for e in errors) and any("model" in e for e in errors)
    with pytest.raises(ProfileError) as caught:
        store.upsert({"profileId": "only-key", "key": KEY})
    assert caught.value.code == "PROFILE_INVALID" and KEY not in str(caught.value) and KEY not in json.dumps(caught.value.errors)
    assert stored_ids(store) == []


def test_http_non_local_rejected_localhost_allowed(store):
    assert any("https" in e for e in validate_profile(OPENAI | {"baseUrl": "http://api.example.test/v1"}))
    assert validate_profile(OPENAI | {"baseUrl": "https://api.example.test/v1"}) == []
    assert validate_profile(OPENAI | {"baseUrl": "http://localhost:8000/v1"}) == []
    assert validate_profile(OPENAI | {"baseUrl": "http://127.0.0.1:8000/v1"}) == []
    assert any("https" in e for e in validate_profile(OPENAI | {"baseUrl": "http://localhost.evil.test/v1"}))
    assert validate_profile(OPENAI | {"baseUrl": "ftp://localhost/v1"})
    assert any("credentials" in e for e in validate_profile(OPENAI | {"baseUrl": "https://user:pw@api.example.test/v1"}))


def test_profile_validation_rejects_unknown_kind_bad_id_and_blank_model():
    assert any("kind" in e for e in validate_profile(OPENAI | {"kind": "anthropic"}))
    assert any("profileId" in e for e in validate_profile(OPENAI | {"profileId": "../evil"}))
    assert any("model" in e for e in validate_profile(OPENAI | {"model": "  "}))


def test_list_never_contains_key_and_file_never_holds_it(store, tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    store.upsert(OPENAI)
    store.set_key("work-openai", KEY)
    store.set_active("work-openai")
    listing = store.list()
    assert KEY not in json.dumps(listing) and KEY not in json.dumps(store.active())
    assert next(p for p in listing if p["profileId"] == "work-openai")["hasKey"] is True
    assert KEY not in (tmp_path / "model_profiles.json").read_text(encoding="utf-8")
    assert KEY not in caplog.text
    assert not any("key" in profile and profile["key"] for profile in listing)


def test_key_goes_to_keyring_under_service_and_profile_id(tmp_path):
    keyring = MemoryKeyring()
    store = ProfileStore(tmp_path / "p.json", keyring)
    store.upsert(OPENAI)
    store.set_key("work-openai", f"  {KEY}  ")
    assert keyring.data == {("aura-model", "work-openai"): KEY}
    store.delete("work-openai")
    assert keyring.data == {} and stored_ids(store) == []


def test_set_key_requires_existing_profile_and_nonblank_key(store):
    with pytest.raises(ProfileError) as caught:
        store.set_key("missing", KEY)
    assert caught.value.code == "PROFILE_NOT_FOUND"
    store.upsert(OPENAI)
    with pytest.raises(ProfileError) as caught:
        store.set_key("work-openai", "   ")
    assert caught.value.code == "PROFILE_INVALID"


def test_ollama_local_needs_no_key_and_sends_no_authorization(store):
    store.upsert(OLLAMA)
    session = Session(Response(data=envelope('{"ok":true}')))
    provider = store.build_provider("local-llama", session=session)
    assert provider.base_url == "http://localhost:11434/v1" and provider.get_diagnostics()["backend"] == "ollama"
    provider.generate_structured([{"role": "user", "content": "hi"}])
    url, request = session.calls[0]
    assert url == "http://localhost:11434/v1/chat/completions" and "Authorization" not in request["headers"]
    assert "chat_template_kwargs" not in request["json"]


def test_remote_kinds_need_a_key_to_build(store):
    store.upsert(OPENAI)
    with pytest.raises(ProfileError) as caught:
        store.build_provider("work-openai")
    assert caught.value.code == "PROFILE_KEY_MISSING"


def test_default_profile_from_env(store, env_settings):
    listing = store.list()
    default = next(p for p in listing if p["profileId"] == "nemotron-nebius")
    assert default == {"profileId": "nemotron-nebius", "label": "Nemotron on Nebius", "kind": "nebius",
                       "baseUrl": "https://api.tokenfactory.example/v1/", "model": "nvidia/nemotron-test", "hasKey": True,
                       "builtIn": True}
    assert "env-nebius-key" not in json.dumps(listing)
    provider = store.build_provider("nemotron-nebius")
    assert isinstance(provider, NebiusPlannerProvider) and provider.model == "nvidia/nemotron-test"
    assert store.active_id() is None  # nothing chosen yet: environment configuration stays in charge


def test_default_profile_without_env_key_reports_no_key(store, monkeypatch):
    import aura.app.config as config
    base = config.Settings()
    monkeypatch.setattr(config, "Settings", lambda: replace(base, nebius_api_key=""))
    assert next(p for p in store.list() if p["profileId"] == "nemotron-nebius")["hasKey"] is False
    with pytest.raises(ProfileError) as caught:
        store.build_provider("nemotron-nebius")
    assert caught.value.code == "PROFILE_KEY_MISSING"


def test_stored_default_overrides_env_and_stored_key_beats_env(store, env_settings):
    store.upsert({"profileId": "nemotron-nebius", "label": "Nebius mine", "kind": "nebius",
                  "baseUrl": "https://api.tokenfactory.example/v1", "model": "nvidia/nemotron-other"})
    store.set_key("nemotron-nebius", KEY)
    session = Session(Response(data=envelope("{}")))
    provider = store.build_provider("nemotron-nebius", session=session)
    provider.generate_structured([{"role": "user", "content": "x"}])
    assert provider.model == "nvidia/nemotron-other" and session.calls[0][1]["headers"]["Authorization"] == f"Bearer {KEY}"
    assert len([p for p in store.list() if p["profileId"] == "nemotron-nebius"]) == 1
    store.delete("nemotron-nebius")  # removes the override; the env default returns
    assert next(p for p in store.list() if p["profileId"] == "nemotron-nebius")["model"] == "nvidia/nemotron-test"


def test_build_provider_uses_profile(store):
    store.upsert(OPENAI)
    store.set_key("work-openai", KEY)
    store.set_active("work-openai")
    provider = store.build_provider(timeout=7)
    assert provider.model == "gpt-test" and provider.base_url == "https://api.example.test/v1" and provider.timeout_seconds == 7
    assert provider.get_diagnostics()["backend"] == "openai_compatible"
    assert KEY not in json.dumps(provider.get_diagnostics())


def test_active_changes_only_by_user_action_and_delete_clears_it(store):
    store.upsert(OPENAI)
    store.upsert(OLLAMA)
    assert store.active_id() is None
    store.set_active("local-llama")
    assert store.active()["profileId"] == "local-llama"
    store.delete("local-llama")
    assert store.active_id() is None
    with pytest.raises(ProfileError) as caught:
        store.set_active("nope")
    assert caught.value.code == "PROFILE_NOT_FOUND"


def test_corrupt_profile_file_is_an_error_not_an_empty_store(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ProfileError) as caught:
        ProfileStore(path, MemoryKeyring()).active_id()
    assert caught.value.code == "PROFILES_UNREADABLE"


def test_nemotron_only_template_kwargs():
    def payload(model, name="nebius"):
        return NebiusPlannerProvider(KEY, "https://x.test/v1", model, provider_name=name).request_payload([{"role": "user", "content": "x"}], None, 10)
    assert payload("nvidia/Nemotron-3-super")["chat_template_kwargs"] == {"enable_thinking": False}
    assert "chat_template_kwargs" not in payload("gpt-4o-mini", "openai_compatible")
    assert "chat_template_kwargs" not in payload("llama3.1", "ollama")


def test_provider_name_in_diagnostics_metadata_and_errors():
    session = Session(Response(401, text="nope"))
    provider = NebiusPlannerProvider(KEY, "https://x.test/v1", "m", session=session, provider_name="openai_compatible")
    with pytest.raises(Exception) as caught:
        provider.generate([{"role": "user", "content": "x"}])
    assert "openai_compatible" in str(caught.value) and "NEBIUS" not in str(caught.value)
    ok = NebiusPlannerProvider(KEY, "https://x.test/v1", "m", session=Session(Response(data=envelope("{}"))), provider_name="ollama")
    assert ok.generate_structured([{"role": "user", "content": "x"}]).metadata["provider"] == "ollama"


def test_empty_key_rejected_unless_key_not_required():
    with pytest.raises(ValueError):
        NebiusPlannerProvider("", "https://x.test/v1", "m")
    assert NebiusPlannerProvider("", "http://localhost:11434/v1", "m", require_key=False).is_available()


def test_test_connection_ok_sends_one_tiny_structured_request(store):
    store.upsert(OPENAI)
    store.set_key("work-openai", KEY)
    session = Session(Response(data=envelope('{"ok":true}')))
    result = store.test("work-openai", session=session)
    assert result["ok"] is True and result["latencyMs"] >= 0 and "code" not in result
    assert len(session.calls) == 1 and session.calls[0][1]["json"]["max_tokens"] <= 64
    assert "json_schema" in session.calls[0][1]["json"]["response_format"]["type"]


def test_test_connection_maps_401_and_timeout(store):
    store.upsert(OPENAI)
    store.set_key("work-openai", KEY)

    class ReadTimeout(Exception):
        pass

    cases = [
        (Response(401, text="bad"), "MODEL_AUTHENTICATION"),
        (Response(403, text="bad"), "MODEL_AUTHENTICATION"),
        (ReadTimeout(), "MODEL_TIMEOUT"),
        (ConnectionError(f"refused {KEY}"), "MODEL_UNAVAILABLE"),
        (Response(500, text="boom"), "MODEL_UNAVAILABLE"),
        (Response(data={"bad": True}), "MODEL_RESPONSE_INVALID"),
        (Response(data=envelope("not json")), "MODEL_RESPONSE_INVALID"),
    ]
    for response, code in cases:
        session = Session(response, response, response)
        result = store.test("work-openai", session=session)
        assert result["ok"] is False and result["code"] == code and result["message"], (code, result)
        assert KEY not in json.dumps(result)


def test_test_connection_without_key_reports_missing_key_without_network(store):
    store.upsert(OPENAI)
    result = store.test("work-openai", session=Session())
    assert result["ok"] is False and result["code"] == "PROFILE_KEY_MISSING"


def test_errors_scrub_key(store):
    store.upsert(OPENAI)
    store.set_key("work-openai", KEY)
    padded = ("x" * 280) + KEY + " tail"  # the key straddles the old 300 character truncation point
    result = store.test("work-openai", session=Session(Response(500, text=padded), Response(500, text=padded), Response(500, text=padded)))
    assert result["ok"] is False and KEY not in json.dumps(result) and KEY[:8] not in result["message"][-20:]
    result = store.test("work-openai", session=Session(Response(401, text=KEY), Response(401, text=KEY)))
    assert KEY not in json.dumps(result)


def test_workspace_uses_active_profile_and_never_tries_another(tmp_path, monkeypatch, env_settings):
    from aura.workspace.server import WorkspaceApplication
    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    application = WorkspaceApplication(storage_mode="memory")
    keyring = MemoryKeyring()
    application._model_profiles = store = ProfileStore(tmp_path / "model_profiles.json", keyring)
    # No active profile: the environment configuration (nebius here) still decides.
    env_provider = application._default_provider()
    assert isinstance(env_provider, NebiusPlannerProvider) and env_provider.model == "nvidia/nemotron-test"
    store.upsert(OPENAI)
    store.set_key("work-openai", KEY)
    store.set_active("work-openai")
    chosen = application._default_provider()
    assert chosen.model == "gpt-test" and chosen.get_diagnostics()["backend"] == "openai_compatible"
    # Active profile loses its key: the error surfaces; neither the env default nor another profile is used.
    store.upsert(OLLAMA)
    keyring.delete_password("aura-model", "work-openai")
    with pytest.raises(RuntimeError) as caught:
        application._default_provider()
    assert "work-openai" in str(caught.value) and KEY not in str(caught.value)


def test_workspace_fails_honestly_when_profile_store_is_unreadable(tmp_path, monkeypatch, env_settings):
    from aura.workspace.server import WorkspaceApplication
    (tmp_path / "model_profiles.json").write_text("{broken", encoding="utf-8")
    monkeypatch.setenv("AURA_DATA_DIR", str(tmp_path))
    application = WorkspaceApplication(storage_mode="memory")
    application._model_profiles = ProfileStore(tmp_path / "model_profiles.json", MemoryKeyring())
    with pytest.raises(RuntimeError):
        application._default_provider()
