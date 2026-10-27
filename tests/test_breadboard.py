import json

from fastapi.testclient import TestClient

from aura.engineering_graph.serialization import graph_from_dict
from aura.infrastructure.llm.provider import ModelGenerationResult
from aura.verification.catalogue import BY_ID
from aura.workspace.assembly import engineering_assembly
from aura.workspace.ideas import TURN_SCHEMA, wants_breadboard


def slots(function, power="USB 5 V"):
    return {"function": {"value": function}, "power": {"value": power}, "budget": {"value": ""}}


def turn(function):
    return {"slots": [{"slot": "function", "value": function, "source": "user", "status": "agreed", "tradeoff": ""},
                      {"slot": "power", "value": "USB 5 V", "source": "user", "status": "agreed", "tradeoff": ""}],
            "questions": [], "families": ["soil_moisture_sensor", "small_dc_pump"],
            "scope": {"status": "IN_SCOPE", "reasons": [], "alternative": None}, "reply": "Ready."}


class Provider:
    def __init__(self, function="water my plant when the soil moisture is low using a pump"):
        self.function = function

    def generate_structured(self, messages, *, system_prompt=None, max_tokens=1200, response_schema=None):
        if response_schema != TURN_SCHEMA: raise RuntimeError("rules unavailable in this test")
        return ModelGenerationResult(json.dumps(turn(self.function)))

    def get_diagnostics(self): return {"backend": "fake"}


def test_catalogue_breadboard_is_nominal_and_unrated():
    item = BY_ID["breadboard-830"]
    assert item.family == "breadboard" and item.properties["dimensions"].value == [165.1, 54.6, 8.5]
    assert item.properties["dimensions"].qualifier == "nominal standard size" and "supply_voltage_range" not in item.properties
    assert item.price is None and item.interfaces == ()


def test_wants_breadboard_for_prototypes_only():
    assert wants_breadboard(slots("water my plant when the soil is dry"), ["soil_moisture_sensor", "small_dc_pump"])
    for text in ("on a custom PCB", "inside an enclosure", "in a 3D printed case", "with a housing"):
        assert not wants_breadboard(slots(f"water my plant {text}"), ["soil_moisture_sensor"])
    assert not wants_breadboard(slots("water my plant"), [])


def approve(tmp_path, **body):
    with TestClient(__import__("aura.workspace.server", fromlist=["create_app"]).create_app(
            provider=Provider(), storage_mode="sqlite", db_path=tmp_path / "w.db", artifact_dir=tmp_path / "a")) as client:
        session_id = client.post("/api/ideas", json={"idea": "water my plant", "planningMode": "deterministic_test"}).json()["sessionId"]
        card = client.post(f"/api/ideas/{session_id}/proposal").json()
        response = client.post(f"/api/ideas/{session_id}/approve", json={"proposalId": card["proposalId"], **body})
        assert response.status_code == 201, response.text
        project_id = response.json()["projectId"]
        return card, graph_from_dict(client.get(f"/api/projects/{project_id}/graph").json())


def boards(graph):
    return [e for e in graph.entities.values() if e.kind.value == "component" and e.metadata.get("family") == "breadboard"]


def test_approve_adds_breadboard_by_default_and_modules_sit_on_it(tmp_path):
    card, graph = approve(tmp_path)
    assert card["breadboard"]["included"] is True and "nominal standard size" in card["breadboard"]["reason"]
    assert len(boards(graph)) == 1 and boards(graph)[0].metadata["dimensions_qualifier"] == "nominal standard size"
    parts = {p["semanticId"]: p for p in engineering_assembly(graph)["parts"]}
    board = parts[boards(graph)[0].id]
    (bx, by, bz), (bw, bd, bh) = board["assembledTransform"]["position"], board["dimensions"]
    on_board = [p for p in parts.values() if p["family"] in {"microcontroller_board", "mosfet_driver"}]
    assert on_board
    for part in on_board:
        (x, y, z), (w, d, h) = part["assembledTransform"]["position"], part["dimensions"]
        assert z - h / 2 >= bz + bh / 2 - 1e-6
        assert bx - bw / 2 <= x - w / 2 and x + w / 2 <= bx + bw / 2 and by - bd / 2 <= y - d / 2 and y + d / 2 <= by + bd / 2


def test_approve_can_leave_breadboard_out(tmp_path):
    _, graph = approve(tmp_path, breadboard=False)
    assert boards(graph) == []
