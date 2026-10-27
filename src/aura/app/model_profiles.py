"""User-chosen model profiles: non-secret settings in a JSON file, API keys in the OS keyring.

Keys are write-only: nothing here returns, logs or persists one outside the keyring.
The active profile changes only through ``set_active``; failures are reported, never rerouted.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from aura.infrastructure.llm.nebius import (
    NebiusAuthenticationError,
    NebiusPlannerProvider,
    NebiusProviderError,
    NebiusResponseError,
    NebiusTimeoutError,
)

KEYRING_SERVICE = "aura-model"
DEFAULT_PROFILE_ID = "nemotron-nebius"
KINDS = ("nebius", "openai_compatible", "ollama_local")
PROVIDER_NAMES = {"nebius": "nebius", "openai_compatible": "openai_compatible", "ollama_local": "ollama"}
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
_STATUS = {"PROFILE_INVALID": 422, "PROFILE_NOT_FOUND": 404, "PROFILE_KEY_MISSING": 409,
           "KEYRING_UNAVAILABLE": 503, "PROFILES_UNREADABLE": 500}


class ProfileError(RuntimeError):
    """Profile problem with a stable code; messages never contain an API key."""

    def __init__(self, code: str, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.errors = code, message, list(errors or [])
        self.status = _STATUS.get(code, 400)


def validate_profile(profile: dict[str, Any]) -> list[str]:
    """Return human-readable problems; an empty list means usable. A key alone is never a profile."""
    errors: list[str] = []
    profile_id = str(profile.get("profileId") or "").strip()
    if not _ID.match(profile_id):
        errors.append("profileId must be 1-48 characters: lowercase letters, digits, '-' or '_'")
    kind = str(profile.get("kind") or "").strip()
    if kind not in KINDS:
        errors.append(f"kind is required and must be one of: {', '.join(KINDS)}")
    model = str(profile.get("model") or "").strip()
    if not model:
        errors.append("model is required")
    elif len(model) > 200 or re.search(r"\s", model):
        errors.append("model must be a single token of at most 200 characters")
    label = str(profile.get("label") or "").strip()
    if len(label) > 80:
        errors.append("label must be at most 80 characters")
    errors.extend(_validate_base_url(str(profile.get("baseUrl") or "").strip()))
    return errors


def _validate_base_url(url: str) -> list[str]:
    if not url:
        return ["baseUrl is required"]
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        parsed.port  # noqa: B018 - raises ValueError for a malformed port
    except ValueError:
        return ["baseUrl is not a valid URL"]
    if parsed.scheme not in {"http", "https"} or not host:
        return ["baseUrl must be an http(s) URL with a host"]
    if parsed.username or parsed.password:
        return ["baseUrl must not contain credentials; store the key with the key field"]
    if parsed.query or parsed.fragment:
        return ["baseUrl must not include a query string or fragment"]
    if parsed.scheme == "http" and host.lower() not in LOCAL_HOSTS:
        return ["baseUrl must use https unless it points to localhost or 127.0.0.1"]
    return []


def scrub(text: str, *secrets: str) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def model_error_info(exc: BaseException) -> dict[str, Any]:
    """Stable code, HTTP status and class for a provider failure, shared by the settings test and model-backed routes."""
    if isinstance(exc, NebiusAuthenticationError):
        return {"code": "MODEL_AUTHENTICATION", "status": 502}
    if isinstance(exc, NebiusTimeoutError):
        return {"code": "MODEL_TIMEOUT", "status": 504}
    if isinstance(exc, NebiusResponseError):
        return {"code": "MODEL_RESPONSE_INVALID", "status": 502}
    return {"code": "MODEL_UNAVAILABLE", "status": 503}


class ProfileStore:
    def __init__(self, path: Path, keyring_backend: Any | None = None) -> None:
        self.path = Path(path)
        self._keyring_backend = keyring_backend

    # -- persistence -------------------------------------------------------
    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"active": None, "profiles": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            profiles = data["profiles"]
            if not isinstance(profiles, dict) or not isinstance(data.get("active"), (str, type(None))):
                raise ValueError("unexpected structure")
            return {"active": data.get("active"), "profiles": profiles}
        except (OSError, ValueError, KeyError, TypeError):
            raise ProfileError("PROFILES_UNREADABLE", "The model profiles file could not be read; fix or remove it in the AURA data folder") from None

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    # -- keyring -----------------------------------------------------------
    def _keyring(self) -> Any:
        if self._keyring_backend is None:
            import keyring
            self._keyring_backend = keyring.get_keyring()
        return self._keyring_backend

    def _get_key(self, profile_id: str) -> str:
        try:
            return (self._keyring().get_password(KEYRING_SERVICE, profile_id) or "").strip()
        except Exception as exc:  # keyring raises backend-specific errors; none may carry a secret
            raise ProfileError("KEYRING_UNAVAILABLE", f"The system keyring is unavailable ({exc.__class__.__name__})") from None

    def _env_key(self, profile_id: str) -> str:
        if profile_id != DEFAULT_PROFILE_ID:
            return ""
        from urllib.parse import urlsplit
        from aura.app.config import Settings
        settings = Settings(); profile = self._profile(profile_id)
        same_host = urlsplit(profile.get("baseUrl", "")).hostname == urlsplit(settings.nebius_base_url).hostname
        return settings.nebius_api_key if profile.get("kind") == "nebius" and same_host else ""

    def _key_for(self, profile_id: str) -> str:
        return self._get_key(profile_id) or self._env_key(profile_id)

    # -- profiles ----------------------------------------------------------
    @staticmethod
    def _default() -> dict[str, Any]:
        from aura.app.config import Settings
        settings = Settings()
        return {"profileId": DEFAULT_PROFILE_ID, "label": "Nemotron on Nebius", "kind": "nebius",
                "baseUrl": settings.nebius_base_url, "model": settings.nebius_model}

    def _public(self, profile: dict[str, Any], *, built_in: bool = False) -> dict[str, Any]:
        try:
            has_key = bool(self._key_for(profile["profileId"]))
        except ProfileError:
            has_key = False
        result = {"profileId": profile["profileId"], "label": profile["label"], "kind": profile["kind"],
                  "baseUrl": profile["baseUrl"], "model": profile["model"], "hasKey": has_key}
        if built_in:
            result["builtIn"] = True
        return result

    def list(self) -> list[dict[str, Any]]:
        stored = self._read()["profiles"]
        profiles = [] if DEFAULT_PROFILE_ID in stored else [self._public(self._default(), built_in=True)]
        return profiles + [self._public(stored[profile_id]) for profile_id in sorted(stored)]

    def _profile(self, profile_id: str) -> dict[str, Any]:
        stored = self._read()["profiles"]
        if profile_id in stored:
            return stored[profile_id]
        if profile_id == DEFAULT_PROFILE_ID:
            return self._default()
        raise ProfileError("PROFILE_NOT_FOUND", f"Model profile '{profile_id}' does not exist")

    def get(self, profile_id: str) -> dict[str, Any]:
        return self._public(self._profile(profile_id), built_in=profile_id not in self._read()["profiles"])

    def upsert(self, profile: dict[str, Any]) -> dict[str, Any]:
        errors = validate_profile(profile)
        if errors:
            raise ProfileError("PROFILE_INVALID", "The model profile is not valid: " + "; ".join(errors), errors)
        clean = {name: str(profile.get(name) or "").strip() for name in ("profileId", "kind", "baseUrl", "model")}
        clean["label"] = str(profile.get("label") or "").strip() or clean["profileId"]
        clean["baseUrl"] = self._normalise_url(clean["kind"], clean["baseUrl"])
        data = self._read()
        data["profiles"][clean["profileId"]] = clean
        self._write(data)
        return self._public(clean)

    @staticmethod
    def _normalise_url(kind: str, url: str) -> str:
        # Ollama serves its OpenAI-compatible API under /v1; users usually paste only host:port.
        return url.rstrip("/") + "/v1" if kind == "ollama_local" and urlparse(url).path.strip("/") == "" else url

    def set_key(self, profile_id: str, key: str) -> None:
        self._profile(profile_id)
        key = (key or "").strip()
        if not key:
            raise ProfileError("PROFILE_INVALID", "The API key must not be blank", ["key is required"])
        try:
            self._keyring().set_password(KEYRING_SERVICE, profile_id, key)
        except Exception as exc:
            raise ProfileError("KEYRING_UNAVAILABLE", f"The system keyring is unavailable ({exc.__class__.__name__})") from None

    def delete(self, profile_id: str) -> None:
        data = self._read()
        if profile_id not in data["profiles"]:
            if profile_id == DEFAULT_PROFILE_ID:
                return  # the environment default is not stored, so there is nothing to remove
            raise ProfileError("PROFILE_NOT_FOUND", f"Model profile '{profile_id}' does not exist")
        del data["profiles"][profile_id]
        if data["active"] == profile_id:
            data["active"] = None
        self._write(data)
        try:
            self._keyring().delete_password(KEYRING_SERVICE, profile_id)
        except Exception:
            pass  # no stored key (or an unavailable keyring): the profile is gone either way

    def active_id(self) -> str | None:
        """Id the user explicitly activated, or None when the environment configuration still decides."""
        active = self._read()["active"]
        return active or None

    def active(self) -> dict[str, Any] | None:
        active = self.active_id()
        return self._public(self._profile(active)) if active else None

    def set_active(self, profile_id: str) -> None:
        profile = self._profile(profile_id)
        data = self._read()
        data["active"] = profile["profileId"]
        self._write(data)

    # -- providers ---------------------------------------------------------
    def build_provider(self, profile_id: str | None = None, timeout: float = 25, *, session: Any | None = None,
                       max_retries: int = 1) -> NebiusPlannerProvider:
        profile_id = profile_id or self.active_id() or DEFAULT_PROFILE_ID
        profile = self._profile(profile_id)
        errors = validate_profile(profile)
        if errors:
            raise ProfileError("PROFILE_INVALID", f"Model profile '{profile_id}' is not valid: " + "; ".join(errors), errors)
        needs_key = profile["kind"] != "ollama_local"
        key = self._key_for(profile_id)
        if needs_key and not key:
            raise ProfileError("PROFILE_KEY_MISSING", f"Model profile '{profile_id}' has no API key; add one in Model settings")
        return NebiusPlannerProvider(key, self._normalise_url(profile["kind"], profile["baseUrl"]), profile["model"], timeout, max_retries,
                                     session=session, provider_name=PROVIDER_NAMES[profile["kind"]], require_key=needs_key)

    def test(self, profile_id: str, *, session: Any | None = None, timeout: float = 15) -> dict[str, Any]:
        """One tiny structured request. Returns ok, or the real error class and a message with the key removed."""
        try:
            secrets = (self._key_for(profile_id),)
        except ProfileError:
            secrets = ()
        started = time.perf_counter()
        try:
            provider = self.build_provider(profile_id, timeout, session=session, max_retries=0)
            provider.generate_structured([{"role": "user", "content": 'Reply with the JSON object {"ok": true}.'}], max_tokens=32,
                                         response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]})
        except ProfileError as exc:
            return {"ok": False, "code": exc.code, "message": scrub(exc.message, *secrets)}
        except Exception as exc:
            info = model_error_info(exc)
            message = str(exc) if isinstance(exc, NebiusProviderError) else f"Request failed ({exc.__class__.__name__})"
            return {"ok": False, "code": info["code"], "message": scrub(message, *secrets)}
        return {"ok": True, "latencyMs": round((time.perf_counter() - started) * 1000)}
