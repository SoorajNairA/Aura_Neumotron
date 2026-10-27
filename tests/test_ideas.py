from aura.workspace.ideas import (SLOTS, apply_turn, compose_objective, cost_summary, new_session,
                                  rank_alternatives, ready_to_propose)


def turn(**overrides):
    base = {"slots": [], "questions": [], "families": [], "scope": {"status": "IN_SCOPE", "reasons": [], "alternative": None}, "reply": "ok"}
    return base | overrides


def slot(name, value, source="user", status="agreed", tradeoff=""):
    return {"slot": name, "value": value, "source": source, "status": status, "tradeoff": tradeoff}


def test_new_session_has_all_slots_open():
    session = new_session("a fan for my room")
    assert session["sessionId"].startswith("idea-")
    assert session["originalIdea"] == "a fan for my room"
    assert set(session["requirements"]) == set(SLOTS)
    assert all(item["status"] == "open" for item in session["requirements"].values())


def test_unknown_slot_dropped():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("colour", "red"), slot("power", "USB 5 V")]))
    assert "colour" not in session["requirements"]
    assert session["requirements"]["power"]["value"] == "USB 5 V"


def test_apply_turn_records_messages_and_does_not_mutate_input():
    original = new_session("idea")
    updated = apply_turn(original, "it should cool me", turn(reply="What power source?"))
    assert original["messages"] == []
    assert [m["role"] for m in updated["messages"]] == ["user", "assistant"]
    assert updated["messages"][1]["text"] == "What power source?"


def test_unsupported_family_recorded_not_agreed():
    session = apply_turn(new_session("idea"), "hi", turn(families=["fan", "jet_engine"]))
    assert session["families"] == ["fan"]
    assert session["unsupportedNeeds"] == ["jet_engine"]


def test_questions_capped_at_three_and_known_slots_only():
    questions = [{"slot": name, "question": f"{name}?", "suggestedDefault": "x", "tradeoff": "y"} for name in ("budget", "power", "connectivity", "environment", "colour")]
    session = apply_turn(new_session("idea"), "hi", turn(questions=questions))
    assert len(session["openQuestions"]) == 3
    assert all(item["slot"] in SLOTS for item in session["openQuestions"])


def test_scope_unsupported_overrides_model():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "design a full passenger aircraft")]))
    assert session["scope"]["status"] == "OUT_OF_SCOPE"
    assert session["scope"]["reasons"]


def test_model_can_downgrade_but_not_upgrade_scope():
    out = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "cool a desk with a fan")],
                     scope={"status": "OUT_OF_SCOPE", "reasons": ["needs mains"], "alternative": "USB fan"}))
    assert out["scope"]["status"] == "OUT_OF_SCOPE"
    assert out["scope"]["alternative"] == "USB fan"
    vague = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "make life nicer")]))
    assert vague["scope"]["status"] == "UNKNOWN"


def test_supported_families_put_vague_wording_in_scope():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "keep my room comfy")], families=["temperature_sensor", "fan"]))
    assert session["scope"]["status"] == "IN_SCOPE"


def test_ready_requires_function_agreed_and_power_set():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "switch a fan on when hot", status="proposed")], families=["fan"]))
    assert not ready_to_propose(session)
    session = apply_turn(session, "yes", turn(slots=[slot("function", "switch a fan on when hot")]))
    assert not ready_to_propose(session)
    session = apply_turn(session, "default", turn(slots=[slot("power", "USB 5 V", source="default", status="proposed")]))
    assert ready_to_propose(session)


def test_not_ready_when_out_of_scope():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "a passenger aircraft"), slot("power", "jet fuel")]))
    assert not ready_to_propose(session)


def test_compose_objective_contains_function_power_and_parts():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "switch a fan on when the room is hot"), slot("power", "USB 5 V")], families=["temperature_sensor", "fan"]))
    text = compose_objective(session)
    assert "switch a fan on when the room is hot" in text and "USB 5 V" in text and "temperature sensor" in text


def test_alternatives_same_family_ranked_by_price_then_unpriced_last():
    ranked = rank_alternatives("ds18b20-module", "cost")
    assert ranked[0]["componentDefinitionId"] == "ds18b20-module"
    assert {item["family"] for item in ranked} == {"temperature_sensor"}
    priced = [item for item in ranked if item["priceUsd"] is not None]
    assert ranked[:len(priced)] == priced
    assert all("best" not in str(item).lower() for item in ranked)
    assert sum(item["selected"] for item in ranked) == 1


def test_alternatives_by_power_sort_on_documented_current():
    ranked = rank_alternatives("ds18b20-module", "power")
    currents = [item["currentMa"] for item in ranked if item["currentMa"] is not None]
    assert currents == sorted(currents)


def test_cost_summary_lists_excluded():
    summary = cost_summary(["esp32-devkit-v1", "dc-fan-5v", "resistor-4k7", "resistor-4k7"])
    assert summary["estimate"] is True
    assert summary["excluded"] == ["dc-fan-5v"]
    assert round(summary["totalUsd"], 2) == round(15.02 + 0.10 + 0.10, 2)
    assert all(item["source"].startswith("https://") for item in summary["items"])


def test_idea_session_round_trip_survives_reopen(tmp_path):
    from aura.infrastructure.persistence.project_repository import SQLiteProjectRepository
    db = tmp_path / "aura.db"
    session = new_session("a fan that turns on when my room is hot")
    repository = SQLiteProjectRepository(db, tmp_path / "artifacts")
    repository.save_idea_session(session)
    session["messages"].append({"role": "user", "text": "hi", "timestamp": "t"})
    repository.save_idea_session(session)
    repository.close()
    reopened = SQLiteProjectRepository(db, tmp_path / "artifacts")
    assert reopened.get_idea_session(session["sessionId"]) == session
    assert reopened.get_idea_session("idea-missing") is None
    reopened.close()


class FakeProvider:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def generate_structured(self, messages, *, system_prompt=None, max_tokens=1200, response_schema=None):
        import json
        from aura.infrastructure.llm.provider import ModelGenerationResult
        self.calls.append({"messages": messages, "system_prompt": system_prompt, "response_schema": response_schema})
        if self.error: raise self.error
        return ModelGenerationResult(json.dumps(self.payload))


def test_run_turn_passes_schema_and_history():
    from aura.workspace.ideas import TURN_SCHEMA, run_turn
    provider = FakeProvider(turn(slots=[slot("function", "switch a fan on when hot")], families=["fan"], reply="Which power source?"))
    first = run_turn(provider, new_session("hot room fan"), "hot room fan")
    second = run_turn(provider, first, "USB please")
    call = provider.calls[1]
    assert call["response_schema"] == TURN_SCHEMA
    assert [m["role"] for m in call["messages"]] == ["user", "assistant", "user"]
    assert call["messages"][-1]["content"] == "USB please"
    assert "switch a fan on when hot" in call["system_prompt"] and "fan" in call["system_prompt"]
    assert second["messages"][-1]["text"] == "Which power source?"


def test_run_turn_provider_error_leaves_session_unchanged():
    import copy
    import pytest
    from aura.workspace.ideas import run_turn
    session = new_session("idea"); before = copy.deepcopy(session)
    with pytest.raises(RuntimeError):
        run_turn(FakeProvider(error=RuntimeError("401 rejected")), session, "hello")
    assert session == before


def test_latest_family_list_replaces_earlier_guesses():
    session = apply_turn(new_session("idea"), "hi", turn(families=["small_dc_motor", "fan", "jet_engine"]))
    session = apply_turn(session, "more", turn(families=["microcontroller_board", "temperature_sensor", "fan", "mosfet_driver"]))
    assert session["families"] == ["microcontroller_board", "temperature_sensor", "fan", "mosfet_driver"]
    assert session["unsupportedNeeds"] == []
    assert "motor" not in compose_objective(session)
    kept = apply_turn(session, "ok", turn(families=[]))
    assert kept["families"] == session["families"]


def test_fan_objective_omits_its_own_motor():
    session = apply_turn(new_session("idea"), "hi", turn(slots=[slot("function", "cool my desk automatically")],
                         families=["microcontroller_board", "small_dc_motor", "motor_driver", "fan", "mosfet_driver"]))
    text = compose_objective(session)
    assert "fan" in text and "motor" not in text
    pump = apply_turn(new_session("idea"), "hi", turn(families=["small_dc_motor", "servo"]))
    assert "small dc motor" in compose_objective(pump)


def test_new_turn_clears_the_previous_proposal():
    session = new_session("idea"); session["proposal"] = {"proposalId": "proposal-old"}
    assert apply_turn(session, "actually battery", turn())["proposal"] is None

