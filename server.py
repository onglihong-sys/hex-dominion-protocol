#!/usr/bin/env python3
"""
HEX DOMINION: SYNDICATE PROTOCOL — Zero-Dependency Multiplayer Strategy Server & HTTP/JSON Agent API
Runs out-of-the-box on any Python 3.9+ installation (`python3 server.py`) with zero third-party packages required.
"""
from __future__ import annotations
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

RELAY_CORES = {"0,0", "0,-2", "2,-2", "2,0", "0,2", "-2,2", "-2,0"}
PLAYER_COLORS = ["#38BDF8", "#F43F5E", "#10B981", "#A855F7"]
SPAWN_COORDS = [
    {"q": -3, "r": 0, "name": "P1 (Commander)", "role": "human"},
    {"q": 3, "r": 0, "name": "P2 (TacticalBot)", "role": "agent"},
    {"q": 0, "r": -3, "name": "P3 (AggroBot)", "role": "agent"},
    {"q": 0, "r": 3, "name": "P4 (FortressBot)", "role": "agent"},
]

MATCHES: Dict[str, Dict[str, Any]] = {}


def hex_key(q: int, r: int) -> str:
    return f"{q},{r}"


def get_neighbors(q: int, r: int) -> List[List[int]]:
    candidates = [[q + 1, r], [q + 1, r - 1], [q, r - 1], [q - 1, r], [q - 1, r + 1], [q, r + 1]]
    return [[nq, nr] for nq, nr in candidates if abs(nq) <= 3 and abs(nr) <= 3 and abs(nq + nr) <= 3]


def create_match_state(code: str = "HEX-704", num_players: int = 2) -> Dict[str, Any]:
    num_players = max(2, min(4, int(num_players)))
    tiles: Dict[str, Dict[str, Any]] = {}
    for q in range(-3, 4):
        for r in range(-3, 4):
            if abs(q + r) <= 3:
                k = hex_key(q, r)
                tiles[k] = {"q": q, "r": r, "owner": None, "shield": 1, "isCore": k in RELAY_CORES}
    players = []
    for i in range(num_players):
        sp = SPAWN_COORDS[i]
        k = hex_key(sp["q"], sp["r"])
        tiles[k]["owner"] = i
        tiles[k]["shield"] = 2
        players.append(
            {
                "id": f"P{i+1}",
                "index": i,
                "name": sp["name"],
                "role": sp["role"],
                "color": PLAYER_COLORS[i],
                "ip": 3,
                "ap": 3 if i == 0 else 0,
                "energy": 1,
            }
        )
    st: Dict[str, Any] = {
        "match_code": code,
        "round": 1,
        "max_rounds": 12,
        "win_ip": 20,
        "turn_index": 0,
        "winner": None,
        "players": players,
        "tiles": tiles,
        "log": [f"[R1] Match {code} created with {num_players} seats."],
        "history": [],
    }
    MATCHES[code] = st
    return st


def compute_legal_moves(st: Dict[str, Any], p_idx: Optional[int] = None) -> List[Dict[str, Any]]:
    if st.get("winner"):
        return []
    if p_idx is None:
        p_idx = st["turn_index"]
    p = st["players"][p_idx]
    moves: List[Dict[str, Any]] = []
    owned = [t for t in st["tiles"].values() if t["owner"] == p_idx]
    seen = set()
    if p["ap"] >= 1:
        for ot in owned:
            if p["energy"] >= 1 and ot["shield"] < 2:
                moves.append({"action": "FORTIFY", "q": ot["q"], "r": ot["r"], "cost_ap": 1, "cost_energy": 1})
            for nq, nr in get_neighbors(ot["q"], ot["r"]):
                nk = hex_key(nq, nr)
                if nk in seen:
                    continue
                nt = st["tiles"].get(nk)
                if not nt:
                    continue
                if nt["owner"] is None:
                    seen.add(nk)
                    moves.append({"action": "EXPAND", "q": nq, "r": nr, "cost_ap": 1, "cost_energy": 0})
                elif nt["owner"] != p_idx and p["ap"] >= 2:
                    support = sum(
                        1
                        for aq, ar in get_neighbors(nq, nr)
                        if st["tiles"].get(hex_key(aq, ar), {}).get("owner") == p_idx
                    )
                    if support >= nt["shield"]:
                        seen.add(nk)
                        moves.append(
                            {"action": "STRIKE", "q": nq, "r": nr, "cost_ap": 2, "cost_energy": 0, "support": support}
                        )
    if p["energy"] >= 2:
        moves.append({"action": "OVERCLOCK", "cost_ap": 0, "cost_energy": 2})
    moves.append({"action": "END_TURN", "cost_ap": 0, "cost_energy": 0})
    return moves


def advance_turn(st: Dict[str, Any]) -> None:
    for p in st["players"]:
        if p["ip"] >= st["win_ip"]:
            st["winner"] = p["id"]
            st["log"].insert(0, f"VICTORY! {p['name']} reached {p['ip']} IP!")
            return
    st["turn_index"] = (st["turn_index"] + 1) % len(st["players"])
    if st["turn_index"] == 0:
        st["round"] += 1
        if st["round"] > st["max_rounds"]:
            top = sorted(st["players"], key=lambda x: x["ip"], reverse=True)[0]
            st["winner"] = top["id"]
            st["log"].insert(0, f"MATCH OVER! {top['name']} wins Round 12 tiebreaker ({top['ip']} IP)!")
            return
    nxt = st["players"][st["turn_index"]]
    cores = sum(1 for t in st["tiles"].values() if t["owner"] == st["turn_index"] and t["isCore"])
    nxt["ap"] = 3
    nxt["energy"] = min(6, nxt["energy"] + 1 + cores)


def apply_move(st: Dict[str, Any], action: str, q: Optional[int] = None, r: Optional[int] = None) -> Dict[str, Any]:
    if st.get("winner"):
        raise ValueError(f"Match already won by {st['winner']}")
    p_idx = st["turn_index"]
    p = st["players"][p_idx]
    action = action.upper()

    if action == "OVERCLOCK":
        if p["energy"] < 2:
            raise ValueError("Need 2 Energy for OVERCLOCK")
        p["energy"] -= 2
        p["ap"] += 1
        p["ip"] += 2
        st["log"].insert(0, f"[R{st['round']}] {p['id']} used OVERCLOCK (+1 AP, +2 IP).")
    elif action == "EXPAND":
        t = st["tiles"].get(hex_key(int(q or 0), int(r or 0)))
        if not t or t["owner"] is not None or p["ap"] < 1:
            raise ValueError("Illegal EXPAND target or insufficient AP")
        adj = any(st["tiles"].get(hex_key(nq, nr), {}).get("owner") == p_idx for nq, nr in get_neighbors(t["q"], t["r"]))
        if not adj:
            raise ValueError("Target hex not adjacent to controlled territory")
        p["ap"] -= 1
        t["owner"] = p_idx
        t["shield"] = 1
        gain = 2 if t["isCore"] else 1
        p["ip"] += gain
        st["log"].insert(0, f"[R{st['round']}] {p['id']} EXPANDED to ({t['q']},{t['r']}) (+{gain} IP).")
    elif action == "FORTIFY":
        t = st["tiles"].get(hex_key(int(q or 0), int(r or 0)))
        if not t or t["owner"] != p_idx or t["shield"] >= 2 or p["ap"] < 1 or p["energy"] < 1:
            raise ValueError("Illegal FORTIFY target or insufficient AP/Energy")
        p["ap"] -= 1
        p["energy"] -= 1
        t["shield"] = 2
        p["ip"] += 1
        st["log"].insert(0, f"[R{st['round']}] {p['id']} FORTIFIED ({t['q']},{t['r']}) to Shield Lv.2 (+1 IP).")
    elif action == "STRIKE":
        t = st["tiles"].get(hex_key(int(q or 0), int(r or 0)))
        if not t or t["owner"] in (None, p_idx) or p["ap"] < 2:
            raise ValueError("Illegal STRIKE target or insufficient AP")
        support = sum(1 for aq, ar in get_neighbors(t["q"], t["r"]) if st["tiles"].get(hex_key(aq, ar), {}).get("owner") == p_idx)
        if support < t["shield"]:
            raise ValueError(f"Insufficient adjacent support ({support} < shield {t['shield']})")
        victim = st["players"][t["owner"]]
        p["ap"] -= 2
        t["owner"] = p_idx
        t["shield"] = 1
        p["ip"] += 2
        victim["ip"] = max(0, victim["ip"] - 1)
        st["log"].insert(0, f"[R{st['round']}] {p['id']} STRUCK {victim['id']} at ({t['q']},{t['r']}) (+2 IP)!")
    elif action == "END_TURN":
        st["log"].insert(0, f"[R{st['round']}] {p['id']} ended turn (IP: {p['ip']}).")
        advance_turn(st)
        return st
    else:
        raise ValueError(f"Unknown action: {action}")

    for pl in st["players"]:
        if pl["ip"] >= st["win_ip"]:
            st["winner"] = pl["id"]
            st["log"].insert(0, f"VICTORY! {pl['name']} reached {pl['ip']} IP!")
            break

    if not st["winner"] and p["ap"] == 0 and p["energy"] < 2:
        advance_turn(st)
    return st


create_match_state("HEX-704", 3)


class HexDominionHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            html_file = Path(__file__).with_name("index.html")
            raw = html_file.read_bytes() if html_file.exists() else b"<h1>Hex Dominion</h1>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        m = re.match(r"^/api/matches/([^/]+)$", path)
        if m:
            code = m.group(1).upper()
            st = MATCHES.get(code) or create_match_state(code, 2)
            self._send_json(
                200,
                {
                    **st,
                    "active_player": st["players"][st["turn_index"]]["id"],
                    "legal_moves": compute_legal_moves(st),
                },
            )
            return

        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}

        if path == "/api/matches":
            code = str(body.get("match_code") or "HEX-704").upper()
            st = create_match_state(code, int(body.get("num_players") or 2))
            self._send_json(
                200,
                {
                    **st,
                    "active_player": st["players"][st["turn_index"]]["id"],
                    "legal_moves": compute_legal_moves(st),
                },
            )
            return

        m_join = re.match(r"^/api/matches/([^/]+)/join$", path)
        if m_join:
            code = m_join.group(1).upper()
            st = MATCHES.get(code) or create_match_state(code, 2)
            name = str(body.get("name") or "AgentBot")
            role = str(body.get("role") or "agent")
            if len(st["players"]) < 4:
                idx = len(st["players"])
                sp = SPAWN_COORDS[idx]
                k = hex_key(sp["q"], sp["r"])
                st["tiles"][k]["owner"] = idx
                st["tiles"][k]["shield"] = 2
                st["players"].append(
                    {
                        "id": f"P{idx+1}",
                        "index": idx,
                        "name": name,
                        "role": role,
                        "color": PLAYER_COLORS[idx],
                        "ip": 3,
                        "ap": 0,
                        "energy": 1,
                    }
                )
            else:
                st["players"][-1]["name"] = name
                st["players"][-1]["role"] = role
            st["log"].insert(0, f"[R{st['round']}] {name} ({role}) joined match {code}.")
            self._send_json(
                200,
                {
                    **st,
                    "active_player": st["players"][st["turn_index"]]["id"],
                    "legal_moves": compute_legal_moves(st),
                },
            )
            return

        m_move = re.match(r"^/api/matches/([^/]+)/move$", path)
        if m_move:
            code = m_move.group(1).upper()
            st = MATCHES.get(code)
            if not st:
                self._send_json(404, {"error": f"Match {code} not found"})
                return
            try:
                apply_move(st, str(body.get("action") or "END_TURN"), body.get("q"), body.get("r"))
                self._send_json(
                    200,
                    {
                        **st,
                        "active_player": st["players"][st["turn_index"]]["id"],
                        "legal_moves": compute_legal_moves(st),
                    },
                )
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        m_sync = re.match(r"^/api/matches/([^/]+)/sync$", path)
        if m_sync:
            code = m_sync.group(1).upper()
            MATCHES[code] = body
            self._send_json(200, {"ok": True, "match_code": code})
            return

        self._send_json(404, {"error": "Endpoint not found"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8090"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), HexDominionHandler)
    print(f"Hex Dominion HTTP/JSON Server listening on http://127.0.0.1:{port}")
    srv.serve_forever()
