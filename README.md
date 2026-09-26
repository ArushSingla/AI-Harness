# AI Harness — Autonomous Coding Agent

An autonomous coding-agent harness built for the AI Harness Hackathon 2026. Given a
natural-language software-engineering task and a path to a git repository, the agent
inspects the repo, plans, edits code, runs tests, debugs failures, and independently
verifies its own work before reporting success.

## 1. What this is

A CLI tool (`src/main.py`) that wraps an LLM in a tool-calling loop and points it at a
real repository on disk. It is not a fixed script — the model decides, turn by turn,
which tool to call next based on what it has learned so far.

## 2. Architecture

```
ai-harness/
├── Makefile
├── README.md
├── requirements.txt
├── .env.example
├── pytest.ini
├── src/
│   ├── main.py                 # CLI entry point
│   ├── agent/
│   │   ├── loop.py             # the autonomous while-loop
│   │   ├── planner.py          # initial short plan
│   │   ├── state.py            # compact AgentState (context management)
│   │   ├── context.py          # prompt building, tool descriptions
│   │   └── verifier.py         # independent post-hoc verification
│   ├── model/
│   │   └── model_client.py     # AnthropicModelClient + MockModelClient
│   ├── tools/
│   │   ├── filesystem.py       # sandboxed list/read/write/edit/delete
│   │   ├── search.py           # in-repo text/regex search
│   │   ├── shell.py            # guarded run_command
│   │   ├── git_tools.py        # git_status / git_diff (read-only)
│   │   └── test_runner.py      # detect + run project test suite
│   ├── repository/
│   │   └── analyzer.py         # lightweight repo map
│   └── ui/
│       └── tui.py              # plain-text terminal output
└── tests/
    ├── test_filesystem.py, test_search.py, test_shell.py       # tool tests
    ├── test_repository_analyzer.py
    ├── test_state_context.py                                   # context tests
    ├── test_model_client.py
    ├── test_agent_loop.py                                      # retry/recovery tests
    ├── test_verifier.py
    ├── test_e2e_agent_fixes_bug.py                              # end-to-end test
    └── fake_repo_template/     # tiny repo with a deliberate bug, used by the e2e test
```

## 3. How the autonomous loop works

```
while task not finished:
    understand current state   -> render the compact AgentState as text
    decide next action         -> ask the model for ONE JSON action
    call tool                  -> execute it against the sandboxed workspace
    observe result             -> capture tool output (truncated if huge)
    update context             -> fold the result into AgentState
```

Each turn, the model receives:
1. The current `AgentState` block (task, plan, repo summary, important files,
   changed files, test status, current error, recent activity log).
2. The single most recent tool observation.

It must respond with exactly one JSON object:

```json
{"thought": "brief reasoning", "action": "read_file", "arguments": {"path": "src/auth.py"}}
```

The loop executes that action, appends the observation, and asks again. When the model
believes the task is complete (or unrecoverable), it calls `finish(success, summary)`,
which the harness independently re-verifies before trusting.

## 4. Available tools

| Tool | Purpose |
|---|---|
| `inspect_project()` | Re-summarize the repository (language, test framework, entry points). |
| `list_files(path)` | Depth-limited directory listing. |
| `search_files(query, path)` | Search text/regex across the repo, returns `file:line` matches. |
| `read_file(path, start_line, end_line)` | Read a file, optionally a line range. |
| `write_file(path, content)` | Create or fully overwrite a file. |
| `edit_file(path, old_str, new_str)` | Replace one unique occurrence of `old_str`. |
| `delete_file(path)` | Delete a single file (never a directory). |
| `run_command(command)` | Run a shell command; destructive patterns are blocked. |
| `run_tests(target)` | Auto-detects pytest/npm/go/cargo and runs the suite. |
| `git_diff(path)` / `git_status()` | Read-only repository state. |
| `finish(success, summary)` | Ends the run; triggers independent verification. |

All filesystem/shell tools are scoped to the workspace root — path traversal
(`../../etc/passwd`, absolute paths, etc.) is rejected before any I/O happens.

## 5. Context management

The harness never replays full conversation history. Instead it maintains one
compact, serializable `AgentState`:

```
TASK
PLAN
REPOSITORY SUMMARY
IMPORTANT FILES
CHANGED FILES
TEST STATUS
CURRENT ERROR
RECENT ACTIVITY (last 10 lines; older entries collapse into a single "N steps omitted" line)
```

This bounds token usage regardless of how long the run goes, avoids resending
files the model has already seen, and keeps tool-result truncation (long file
reads, huge command output, huge test logs) automatic and consistent.

## 6. Failure recovery

- Malformed model responses (non-JSON, missing `action`) are fed back to the
  model as an error observation rather than crashing the loop.
- Tool failures increment a consecutive-failure counter; after `MAX_RETRIES = 5`
  consecutive failures the agent stops and reports what it tried, the last
  error, and which files were changed — instead of looping forever.
- A hard iteration cap (`MAX_ITERATIONS = 40`) prevents runaway loops even if
  the model keeps "succeeding" at individual tool calls without finishing.

## 7. Verification

The agent's own `finish(success=True, ...)` claim is never trusted blindly.
After the loop ends, the harness independently:

1. Re-runs the project's test suite from scratch.
2. Checks the exit code / pass-fail counts.
3. Inspects `git diff` for uncommitted changes.

If the agent claimed success but the re-run shows failing tests, the harness
downgrades the result to **NOT VERIFIED** and says so explicitly in the final
summary. The final report distinguishes:

```
IMPLEMENTED: <what the agent changed>
VERIFIED:    <what re-running tests actually showed>
CHANGED:     <files touched>
```

## 8. Installation

Requires Python 3.10+.

```bash
git clone <this-repo>
cd ai-harness
make setup
```

`make setup` creates a `.venv` and installs `requirements.txt` (currently just
`pytest`; the model client uses only the Python standard library — no SDK
dependency required).

## 9. Configuration

Set your API key as an environment variable (never hard-code it):

```bash
export AI_API_KEY="sk-ant-..."
# optional, defaults to claude-sonnet-4-6:
export AI_MODEL="claude-sonnet-4-6"
```

See `.env.example` for the same, in file form (copy to `.env` and `source` it,
or use `direnv`/your process manager of choice — the harness only reads
`os.environ`, it does not parse `.env` itself).

## 10. Running the harness

```bash
export AI_API_KEY="sk-ant-..."
make run REPO=/path/to/target/repo TASK="Add a DELETE /users/:id endpoint and update the tests."
```

Defaults: `REPO=./demo_repo`, `TASK="Fix the login API returning 500 when the email is missing."`
(both overridable on the command line as shown above).

Equivalent direct invocation:

```bash
.venv/bin/python -m src.main --repo /path/to/target/repo --task "..."
```

### Offline / scripted demo mode

For demos or debugging without spending a real API call, pass a JSON file of
scripted model responses:

```bash
.venv/bin/python -m src.main --repo ./tests/fake_repo_template \
  --task "Fix the login API returning 500 when the email is missing." \
  --mock-script tests/fixtures/demo_script.json
```

This is for testing/demo only — normal operation always uses the real
Anthropic API and requires `AI_API_KEY`.

## 11. Running tests

```bash
make test
```

Runs the full pytest suite: tool unit tests (filesystem safety, search, shell
guardrails), repository detection, context/state management, model client,
agent-loop parsing and retry/recovery, the verifier, and one full end-to-end
test that spins up a small fake repository with a deliberate bug and drives a
scripted agent through inspecting, searching, reading, patching, and
re-verifying until the tests pass.

## 12. Example task

Given `tests/fake_repo_template/auth.py`, which crashes with an
`AttributeError` when `login(None, "secret")` is called (simulating a 500 on
missing email), the task:

> "Fix the login API returning 500 when the email is missing."

drives the agent to: search for `login`, read `auth.py`, run tests to confirm
the failure, add a guard (`if not email: return 400`), re-run tests, and
`finish(success=True, ...)` — which the harness then independently re-verifies
by running the test suite one more time from a clean process.

## 13. Security considerations

- **Workspace sandboxing**: every filesystem tool resolves paths against the
  workspace root and rejects anything that escapes it (`..`, absolute paths).
- **No secret exposure**: `AI_API_KEY` is read from the environment only, never
  logged, never written to source, never passed to the model. `run_command`
  blocks patterns like `cat .env` and bare `printenv`/`env`.
- **Destructive-command blocking**: `rm -rf /`, `git reset --hard`,
  `git clean -f`, `git push --force`, `mkfs`, raw-disk `dd`, fork bombs,
  `curl | sh`, `shutdown`/`reboot`, etc. are blocked before execution.
- **No arbitrary deletion**: `delete_file` refuses to delete directories.
- **Bounded execution**: command/test timeouts, retry limits, and an iteration
  cap prevent runaway or hung processes.
- **No blind trust in the model**: every claimed success is independently
  re-verified against real test output and git state.

These are conservative guardrails, not a full security sandbox — the harness
still assumes it is operating inside a disposable/contained environment (e.g.
a container or throwaway VM), as is standard for autonomous coding agents.

## 14. Makefile commands

| Command | Effect |
|---|---|
| `make setup` | Create `.venv`, install `requirements.txt`. |
| `make run` | Run the harness (`REPO=`, `TASK=` overridable); requires `AI_API_KEY`. |
| `make test` | Run the full pytest suite. |
| `make clean` | Remove `.venv`, `__pycache__`, and pytest caches. |

## Known limitations

- The model-interaction protocol is a hand-rolled JSON-per-turn scheme rather
  than a provider's native tool-use/function-calling API; this was chosen for
  simplicity, portability across models, and because it matches the spec's own
  example format exactly. It is straightforward to swap for native tool-use if
  a specific model/API requires it.
- `run_tests` targets pytest/npm/go/cargo detection heuristics; unusual project
  layouts may need a manually specified `target`.
- `search_files` is a pure-Python scanner (no ripgrep dependency), which is
  portable but slower than `rg` on very large repositories.
- The shell guardrails are pattern-based, not a full sandbox — they catch
  common catastrophic mistakes, not a maliciously adversarial actor.
