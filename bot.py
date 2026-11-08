#!/usr/bin/env python3
"""
Sample AI Agent (`bot.py`) for Hex Dominion: Syndicate Protocol.
Plays a complete match via the documented HTTP/JSON API using zero external dependencies.

Usage:
  python3 bot.py --url http://127.0.0.1:8090 --match HEX-704
"""
import argparse
import json
import time
import urllib.request


def api_call(base_url: str, path: str, payload: dict | None = None) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json", "User-Agent": "HexDominionBot/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def score_move(state: dict, move: dict) -> float:
    act = move["action"]
    if act == "END_TURN":
        return -1.0
    q, r = move.get("q", 0), move.get("r", 0)
    tile = state.get("tiles", {}).get(f"{q},{r}", {})
    is_core = bool(tile.get("isCore"))
    dist_center = (abs(q) + abs(r) + abs(q + r)) / 2.0
    if act == "STRIKE":
        return 95.0 + (35.0 if is_core else 0.0) - dist_center * 3.0
    if act == "EXPAND":
        return 70.0 + (40.0 if is_core else 0.0) - dist_center * 5.0
    if act == "OVERCLOCK":
        return 75.0
    if act == "FORTIFY":
        return 50.0 + (25.0 if is_core else 0.0)
    return 10.0


def run_agent(base_url: str, match_code: str, max_steps: int = 60) -> None:
    print(f"[Agent] Connecting to {base_url} (Match: {match_code})...")
    state = api_call(base_url, f"/api/matches/{match_code}/join", {"name": "SampleHeuristicBot", "role": "agent"})
    for step in range(max_steps):
        if state.get("winner"):
            print(f"[Agent] Match finished! Winner: {state['winner']}")
            for p in state["players"]:
                print(f"  - {p['id']} ({p['name']}): {p['ip']} IP")
            return
        legal = state.get("legal_moves", [])
        best = max(legal, key=lambda m: score_move(state, m)) if legal else {"action": "END_TURN"}
        active = state.get("active_player")
        print(f"[Step {step+1:02d} | R{state['round']}] {active} -> {best}")
        state = api_call(
            base_url,
            f"/api/matches/{match_code}/move",
            {"player_id": active, "action": best["action"], "q": best.get("q"), "r": best.get("r")},
        )
        time.sleep(0.05)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8090", help="Base URL of Hex Dominion server")
    parser.add_argument("--match", default="HEX-704", help="Match code to join")
    args = parser.parse_args()
    run_agent(args.url, args.match)
