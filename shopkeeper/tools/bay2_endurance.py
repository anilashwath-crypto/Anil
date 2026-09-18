#!/usr/bin/env python3
"""
Sixty open/close cycles on bay two, counted three ways.

Counting the POSTs proves nothing: the endpoint answers 202 the moment it
accepts the job and the move runs asynchronously, so a servo that never
twitched would still report sixty successes. So each cycle is confirmed by
polling until busy clears AND the drawer's own open flag has flipped, and the
board's event log is sampled as it goes - LOG_MAX is 60 and this run makes
120 events, so the log has to be harvested during the run, not after it.
"""
import json, sys, time, urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.0.114"
BAY  = int(sys.argv[2]) if len(sys.argv) > 2 else 1   # 0 = bay one, 1 = bay two
N    = int(sys.argv[3]) if len(sys.argv) > 3 else 60
BASE = f"http://{HOST}"

def get(path, t=8):
    with urllib.request.urlopen(BASE + path, timeout=t) as r:
        return json.load(r)

def post(path, obj, t=8):
    rq = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(),
                                headers={"Content-Type": "application/json"},
                                method="POST")
    try:
        with urllib.request.urlopen(rq, timeout=t) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.reason}

def bay(st):
    return next(d for d in st["drawers"] if d["id"] == BAY)

def settle(want, limit=6.0):
    """Wait for the move to finish. Returns (ok, seconds)."""
    t0 = time.time()
    while time.time() - t0 < limit:
        d = bay(get("/api/state"))
        if not d["busy"] and bool(d["open"]) == want:
            return True, time.time() - t0
        time.sleep(0.08)
    return False, time.time() - t0

seen, log_lost = {}, False
def harvest(st):
    global log_lost
    for e in st.get("log", []):
        seen.setdefault((e["t"], e["what"], e["drawer"]), e)

st0 = get("/api/state")
d0 = bay(st0)
print(f"bay two = {d0['name']}, GPIO {d0['pin']}, cal {d0['closed_us']}..{d0['open_us']} us")
print(f"start: open={d0['open']} busy={d0['busy']} uptime={st0['uptime']}s\n")
harvest(st0)
base_events = len(seen)

# Park it shut so cycle 1 starts from a known place.
if d0["open"]:
    post("/api/drawer", {"id": BAY, "open": False}); settle(False)

rows, fail = [], []
t_start = time.time()
for i in range(1, N + 1):
    row = {"cycle": i}
    for phase, want in (("open", True), ("close", False)):
        code, _ = post("/api/drawer", {"id": BAY, "open": want})
        if code != 202:
            fail.append(f"cycle {i} {phase}: HTTP {code}")
            row[phase] = None
            time.sleep(0.5)
            continue
        ok, secs = settle(want)
        row[phase] = round(secs, 3)
        if not ok:
            fail.append(f"cycle {i} {phase}: never settled ({secs:.1f}s)")
    st = get("/api/state")
    harvest(st)
    row["uptime"] = st["uptime"]
    rows.append(row)
    if i % 10 == 0 or i == 1:
        print(f"  cycle {i:3d}/{N}  open {row['open']}s  close {row['close']}s  "
              f"uptime {st['uptime']}s  events {len(seen)-base_events}")

st1 = get("/api/state"); harvest(st1)
elapsed = time.time() - t_start

ev = [e for (t, w, dr), e in seen.items() if dr == BAY]
opened = sum(1 for e in ev if e["what"] == "OPENED")
closed = sum(1 for e in ev if e["what"] == "CLOSED")
done_o = sum(1 for r in rows if r.get("open") is not None)
done_c = sum(1 for r in rows if r.get("close") is not None)

rep = {
    "host": HOST, "bay": BAY, "name": d0["name"], "pin": d0["pin"],
    "requested_cycles": N,
    "confirmed_opens": done_o, "confirmed_closes": done_c,
    "board_log_opened": opened, "board_log_closed": closed,
    "failures": fail,
    "elapsed_s": round(elapsed, 1),
    "uptime_start": st0["uptime"], "uptime_end": st1["uptime"],
    "rebooted": st1["uptime"] < st0["uptime"],
    "mem_start": st0.get("mem"), "mem_end": st1.get("mem"),
    "rows": rows,
}
out = ("/private/tmp/claude-501/-Users-piyushmishra/"
       "5f7839e0-775c-4226-90ac-774bd91f5419/scratchpad/endurance_bay%d.json" % BAY)
json.dump(rep, open(out, "w"), indent=1)

ot = [r["open"] for r in rows if r.get("open")]
ct = [r["close"] for r in rows if r.get("close")]
print(f"\n{'='*54}\nBAY {BAY+1} — {N} CYCLES\n{'='*54}")
print(f"  commanded            {N}")
print(f"  confirmed open       {done_o}/{N}")
print(f"  confirmed close      {done_c}/{N}")
print(f"  board log OPENED     {opened}")
print(f"  board log CLOSED     {closed}")
if ot: print(f"  open  {min(ot):.2f}/{sum(ot)/len(ot):.2f}/{max(ot):.2f} s  (min/mean/max)")
if ct: print(f"  close {min(ct):.2f}/{sum(ct)/len(ct):.2f}/{max(ct):.2f} s")
print(f"  elapsed              {elapsed/60:.1f} min")
print(f"  uptime {st0['uptime']} -> {st1['uptime']}   rebooted={rep['rebooted']}")
print(f"  failures             {len(fail)}")
for f in fail[:10]: print(f"     {f}")
print(f"\n  VERDICT: {str(N)+' CONFIRMED' if done_o == N and done_c == N and not fail else 'INCOMPLETE'}")
print(f"  report -> {out}")
