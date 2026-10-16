# Bambu Lab P1S connector for Claude (MCP)

An MCP server that lets Claude monitor and operate a Bambu Lab P1S over your local network
(LAN mode: MQTT :8883, FTPS :990, camera :6000). No cloud account needed.

## Setup

1. On the printer: **Settings → WLAN** → note the IP and **Access Code**; enable **LAN Mode**
   (and LAN-mode liveview for the camera). Serial number is under **Settings → Device**.
2. `pip install -r requirements.txt` (Python 3.10+).
3. Register with Claude Code:

```bash
claude mcp add bambu-p1s \
  -e P1S_HOST=192.168.1.50 -e P1S_SERIAL=01P00A000000000 -e P1S_ACCESS_CODE=12345678 \
  -- python3 /path/to/p1s-mcp/p1s_mcp.py
```

For Claude Desktop add the same command/env to `claude_desktop_config.json` under `mcpServers`.
The server must run on a machine on the same LAN as the printer (not the cloud sandbox).

## Tools

| Tool | What it does |
|---|---|
| `p1s_status` | State, progress, ETA, layer, temps, fans, lights, AMS slots, errors |
| `p1s_camera_snapshot` | JPEG from the chamber camera |
| `p1s_pause` / `p1s_resume` | Pause / resume a print |
| `p1s_stop` | Cancel print (needs `confirm=True`) |
| `p1s_set_light` | Chamber / work light |
| `p1s_set_speed` | silent / standard / sport / ludicrous |
| `p1s_set_temperature` | Nozzle ≤ 300 °C, bed ≤ 100 °C (P1S limits) |
| `p1s_set_fan` | part / aux / chamber, 0–100 % |
| `p1s_home` | G28 |
| `p1s_send_gcode` | Raw G-code (needs `confirm=True`, refused mid-print) |
| `p1s_list_files` / `p1s_upload` | Browse / upload sliced `.gcode.3mf` via FTPS |
| `p1s_start_print` | Start a stored file (needs `bed_cleared=True` **and** `confirm=True`) |

## Safety

Starting and stopping prints are gated: Claude is told to get your explicit go-ahead that the bed is clear,
the right plate is fitted and the AMS mapping is right before it can start a job. Upload files must be
**sliced** (`Export plate sliced file` in Bambu Studio); the connector does not slice.

## Notes

* The access code is read from the environment only; it is never logged.
* The printer's TLS certificate is self-signed, so certificate verification is disabled for the LAN connections.
* Tested against a mocked camera and the status-merge logic; MQTT/FTPS paths follow the community-documented
  protocol but have not been run against real hardware yet — try `p1s_status` first, then the light, before printing.
