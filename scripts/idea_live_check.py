"""Drive one idea conversation against a running AURA backend and print what happened.

Usage: python scripts/idea_live_check.py [--api http://127.0.0.1:8765] [--idea "..."]
Answers each question with its suggested default, proposes once requirements are ready, then approves.
"""
from __future__ import annotations

import argparse
import json
import sys

import requests


def ready(session: dict) -> bool:
    req = session["requirements"]
    return (req["function"]["status"] == "agreed" and bool(req["power"]["value"]) and req["power"]["status"] != "open"
            and session["scope"]["status"] == "IN_SCOPE")


def call(method: str, url: str, **kwargs) -> dict:
    response = requests.request(method, url, timeout=300, **kwargs)
    if response.status_code >= 400:
        sys.exit(f"{method} {url} -> {response.status_code}: {response.text[:500]}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8765")
    parser.add_argument("--idea", default="a fan that turns on when my room is hot")
    parser.add_argument("--max-turns", type=int, default=6)
    args = parser.parse_args()
    session = call("POST", f"{args.api}/api/ideas", json={"idea": args.idea})
    for _ in range(args.max_turns):
        print(f"AURA: {session['messages'][-1]['text']}")
        if ready(session) or session["scope"]["status"] == "OUT_OF_SCOPE":
            break
        questions = session["openQuestions"]
        answer = ("; ".join(f"Use the default for {q['slot']}: {q['suggestedDefault']}" for q in questions if q["suggestedDefault"])
                  or "Yes, that function and power source are agreed.")
        print(f"USER: {answer}")
        session = call("POST", f"{args.api}/api/ideas/{session['sessionId']}/messages", json={"text": answer})
    print("requirements:", json.dumps({k: (v["value"], v["source"], v["status"]) for k, v in session["requirements"].items()}, indent=1))
    print("scope:", session["scope"])
    if not ready(session):
        sys.exit("not ready to propose after the turn limit")
    card = call("POST", f"{args.api}/api/ideas/{session['sessionId']}/proposal")
    for part in card["components"]:
        price = f"${part['price']['usd']:.2f}" if part["price"] else "price unavailable"
        print(f"  part: {part['name']} [{part['partNumber'] or 'generic proxy'}] {price} · {len(part['alternatives'])} options")
    print("cost:", card["cost"]["totalUsd"], "estimate; unpriced:", card["cost"]["excluded"])
    print("limitations:", len(card["limitations"]))
    project = call("POST", f"{args.api}/api/ideas/{session['sessionId']}/approve", json={"proposalId": card["proposalId"]})
    print("project:", project["projectId"], project["status"], project["planningMode"])


if __name__ == "__main__":
    main()
