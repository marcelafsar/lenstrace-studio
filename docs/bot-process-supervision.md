# Bot process supervision

The backend supervises each bot as a separate child process
(`backend/services/bot_supervisor.py` + `bot_process.py`).

## Guarantees (implemented + unit-tested)

- Bots run as separate child processes launched with the same virtual-env
  interpreter, via an explicit argument list — **never `shell=True`**.
- The token is injected through the child **environment**, never as a
  command-line argument.
- Duplicate instances are prevented (starting a running bot is rejected).
- Tracks PID, start time, exit code, and restart count.
- Captures stdout/stderr into a **bounded, redacted** in-memory ring buffer
  (token-shaped strings are scrubbed before storage).
- Stops **gracefully** (`terminate`) and **forces** (`kill`) after a timeout.
- Detects unexpected exits (crashes) without leaking secrets.
- Cleans up child processes when LensTrace exits (`stop_bots_on_exit`, default
  on), so no orphan bot processes remain.
- Only the authenticated local desktop API can start/stop bots.

## Lifecycle options

| Setting | Default | Meaning |
|---------|---------|---------|
| auto-start (per bot) | off | start on app open (only if configured) |
| `LENSTRACE_STOP_BOTS_ON_EXIT` | true | stop child bots when LensTrace closes |
| `LENSTRACE_RESTART_AFTER_CRASH` | false | auto-restart a crashed bot |
| `LENSTRACE_MAX_RESTARTS` | 3 | cap on automatic restarts |

Automatic recovery, when enabled, uses **exponential backoff** and a **maximum
restart count** — it never restarts indefinitely.

## Not in scope (this phase)

- No persistent Windows service. Supervision lasts only while the backend runs.
- Interpreter/executable resolution is isolated behind a helper
  (`_python_executable`) so a future packaged build can substitute a bundled
  runtime without changing the supervisor.

## Health

Status is derived from the supervised process state plus the child's structured
stdout (captured in the ring buffer). No second unauthenticated server is
opened. Manual token-validation actions are rate-limited to avoid hammering the
Telegram/Discord APIs.
