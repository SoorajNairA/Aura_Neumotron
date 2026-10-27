import json

from fastapi.testclient import TestClient

from aura.infrastructure.llm.provider import ModelGenerationResult
from aura.workspace.ideas import TURN_SCHEMA
from aura.workspace.server import WorkspaceApplication, create_app


def turn(slots=(), families=(), reply="Noted.", scope="IN_SCOPE", questions=()):
    return {"slots": [{"slot": n, "value": v, "source": "user", "status": "agreed", "tradeoff": ""} for n, v in slots],
            "questions": list(questions), "families": list(families),
            "scope": {"status": scope, "reasons": [], "alternative": None}, "reply": reply}


READY = turn([("function", "switch a fan on when the room is hot"), ("power", "USB 5 V")], ["temperature_sensor", "fan"], "Ready to propose.")


class TurnProvider:
    def __init__(self, *turns, error=None):
        self.turns, self.error, self.turn_calls = list(turns), error, 0

    def generate_structured(self, messages, *, system_prompt=None, max_tokens=1200, response_schema=None):
        assert response_schema == TURN_SCHEMA
        if self.error: raise self.error
        self.turn_calls += 1
        return ModelGenerationResult(json.dumps(self.turns.pop(0)))

    def get_diagnostics(self): return {"backend": "fake"}


def client_for(provider, tmp_path):
    return TestClient(create_app(provider=provider, storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a"))


def start(client, idea="a fan that turns on when my room is hot"):
    return client.post("/api/ideas", json={"idea": idea, "planningMode": "deterministic_test"})


def test_create_session_runs_first_turn(tmp_path):
    with client_for(TurnProvider(turn(reply="What powers it?", questions=[{"slot": "power", "question": "USB or battery?", "suggestedDefault": "USB 5 V", "tradeoff": "needs a cable"}])), tmp_path) as client:
        response = start(client)
        assert response.status_code == 201, response.text
        session = response.json()
        assert session["originalIdea"] == "a fan that turns on when my room is hot"
        assert session["messages"][-1]["text"] == "What powers it?"
        assert session["openQuestions"][0]["suggestedDefault"] == "USB 5 V"


def test_messages_persist_across_restart(tmp_path):
    with client_for(TurnProvider(turn(), READY), tmp_path) as client:
        session_id = start(client).json()["sessionId"]
        assert client.post(f"/api/ideas/{session_id}/messages", json={"text": "USB, and a DS18B20"}).status_code == 200
    with client_for(TurnProvider(), tmp_path) as client:
        session = client.get(f"/api/ideas/{session_id}").json()
        assert [m["role"] for m in session["messages"]] == ["user", "assistant", "user", "assistant"]
        assert session["requirements"]["power"]["value"] == "USB 5 V"
        assert client.get("/api/ideas/idea-missing").status_code == 404


def test_proposal_requires_ready(tmp_path):
    with client_for(TurnProvider(turn()), tmp_path) as client:
        session_id = start(client).json()["sessionId"]
        response = client.post(f"/api/ideas/{session_id}/proposal")
        assert response.status_code == 409 and response.json()["detail"]["code"] == "REQUIREMENTS_INCOMPLETE"


def test_proposal_does_not_create_project_and_shows_cost(tmp_path):
    with client_for(TurnProvider(READY), tmp_path) as client:
        session_id = start(client).json()["sessionId"]
        response = client.post(f"/api/ideas/{session_id}/proposal")
        assert response.status_code == 200, response.text
        card = response.json()
        assert card["proposalId"].startswith("proposal-") and card["components"]
        assert card["cost"]["estimate"] is True and "excluded" in card["cost"]
        assert all("alternatives" in item for item in card["components"])
        assert client.get("/api/projects").json() == []
        assert client.get(f"/api/ideas/{session_id}").json()["proposal"]["proposalId"] == card["proposalId"]


def test_approve_creates_project_from_cached_plan(tmp_path, monkeypatch):
    calls = []
    original = WorkspaceApplication.plan
    monkeypatch.setattr(WorkspaceApplication, "plan", lambda self, body: calls.append(body.objective) or original(self, body))
    with client_for(TurnProvider(READY), tmp_path) as client:
        session_id = start(client).json()["sessionId"]
        card = client.post(f"/api/ideas/{session_id}/proposal").json()
        response = client.post(f"/api/ideas/{session_id}/approve", json={"proposalId": card["proposalId"]})
        assert response.status_code == 201, response.text
        project = response.json()
        assert len(calls) == 1
        assert client.get(f"/api/ideas/{session_id}").json()["projectId"] == project["projectId"]
        assert [p["projectId"] for p in client.get("/api/projects").json()] == [project["projectId"]]


def test_approve_unknown_proposal_409(tmp_path):
    with client_for(TurnProvider(READY), tmp_path) as client:
        session_id = start(client).json()["sessionId"]
        response = client.post(f"/api/ideas/{session_id}/approve", json={"proposalId": "proposal-gone"})
        assert response.status_code == 409 and response.json()["detail"]["code"] == "PROPOSAL_EXPIRED"


def test_out_of_scope_session_cannot_propose(tmp_path):
    with client_for(TurnProvider(turn([("function", "design a full passenger aircraft"), ("power", "jet fuel")])), tmp_path) as client:
        session = start(client, "a passenger aircraft").json()
        assert session["scope"]["status"] == "OUT_OF_SCOPE"
        response = client.post(f"/api/ideas/{session['sessionId']}/proposal")
        assert response.status_code == 409 and response.json()["detail"]["code"] == "OUT_OF_SCOPE"


def test_provider_failure_returns_error_and_keeps_session(tmp_path):
    class NebiusAuthenticationError(RuntimeError): pass
    provider = TurnProvider(turn())
    with client_for(provider, tmp_path) as client:
        session_id = start(client).json()["sessionId"]
        provider.error = NebiusAuthenticationError("Nebius API key was rejected (401)")
        response = client.post(f"/api/ideas/{session_id}/messages", json={"text": "hello"})
        assert response.status_code == 503 and response.json()["detail"]["code"] == "MODEL_AUTHENTICATION"
        assert len(client.get(f"/api/ideas/{session_id}").json()["messages"]) == 2


def test_direct_create_contract_unchanged(tmp_path):
    with client_for(TurnProvider(), tmp_path) as client:
        response = client.post("/api/projects", json={"objective": "Build a temperature-controlled desk fan", "planningMode": "deterministic_test"})
        assert response.status_code == 201, response.text
