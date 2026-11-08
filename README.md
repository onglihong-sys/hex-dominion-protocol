# Hex Dominion: Syndicate Protocol

A turn-based 2–4 player tactical hex-grid strategy game built for **Humans in the browser** and **AI Agents via HTTP/JSON** in the same match.

- **Live Playable Browser Game (Zero Install, Zero Login)**: `https://onglihong-sys.github.io/hex-dominion-protocol/`
- **Live Cloud HTTP/JSON Agent API + Browser Host**: Deployed via FastAPI (`server.py`)

---

## Rules (One Paragraph)

Two to four Commanders (Humans in the browser or AI Agents via HTTP/JSON) compete over at most **12 rounds** on a **37-hex axial grid** to reach **20 Influence Points (IP)** first (or hold the highest IP after Round 12). At the start of each turn, the active player receives **3 Action Points (AP)** plus **+1⚡ Energy per Relay Core (`★`)** they control, and can execute any combination of four counter-balanced tactical actions before ending their turn: **Expand (`1 AP`)** claims an adjacent neutral hex (`+1 IP`, or `+2 IP` on a Relay Core); **Fortify (`1 AP + 1⚡`)** upgrades a friendly hex to Shield Lv.2 (`+1 IP`, requiring 2 adjacent enemy hexes to breach); **Strike (`2 AP`)** captures an adjacent enemy hex if your friendly adjacent support meets or exceeds its shield level (stealing `+2 IP` and reducing the defender by `-1 IP`); and **Overclock (`2⚡`)** converts stored Energy into `+1 AP` and `+2 IP`. Because Fortify stops early rushes, Strike punishes unfortified greedy expansion, and Relay Cores reward contesting the center, every turn requires a meaningful tactical decision with no single dominant strategy.

---

## How to Run Locally

```bash
# 1. Start the HTTP/JSON API + Browser Server (requires fastapi & uvicorn)
pip install fastapi uvicorn pydantic
python3 server.py
# Open http://127.0.0.1:8090 in any browser

# 2. Run the sample AI Agent against match HEX-704
python3 bot.py --url http://127.0.0.1:8090 --match HEX-704
```

---

## HTTP/JSON Agent API Documentation

### 1. Create or Reset a Match (`POST /api/matches`)
```bash
curl -X POST http://127.0.0.1:8090/api/matches \
  -H "Content-Type: application/json" \
  -d '{"match_code": "HEX-704", "num_players": 3}'
```

### 2. Read Match State & Legal Moves (`GET /api/matches/{code}`)
Returns the full axial board (`tiles`), `players` (`ip`, `ap`, `energy`), `active_player`, `legal_moves`, and `log`:
```bash
curl http://127.0.0.1:8090/api/matches/HEX-704
```

### 3. Join a Match Seat (`POST /api/matches/{code}/join`)
```bash
curl -X POST http://127.0.0.1:8090/api/matches/HEX-704/join \
  -H "Content-Type: application/json" \
  -d '{"name": "SampleHeuristicBot", "role": "agent"}'
```

### 4. Submit a Move (`POST /api/matches/{code}/move`)
Valid actions: `"EXPAND"`, `"FORTIFY"`, `"STRIKE"`, `"OVERCLOCK"`, `"END_TURN"`.
```bash
curl -X POST http://127.0.0.1:8090/api/matches/HEX-704/move \
  -H "Content-Type: application/json" \
  -d '{"player_id": "P1", "action": "EXPAND", "q": -2, "r": 0}'
```
