# Autonomous Coding Agent Harness

A text-only autonomous coding agent for the AI Harness Hackathon 2026. It accepts a natural-language issue, inspects a repository, chooses focused tools dynamically, edits code, runs verification, recovers from failures, and reports the result in a terminal UI.

## Quick start

```sh
export AI_API_KEY="your-key"
make setup
make run REPO=/path/to/repository TASK="Fix the login API when email is missing"
make test
```

`AI_API_KEY` is never printed or stored. `AI_MODEL` and `AI_API_URL` can select any compatible text-only chat API. The default client uses only Python's standard library.

## Architecture

- `harness/tools.py`: workspace-rooted filesystem, search, shell, test, and Git tools.
- `harness/repository.py`: lightweight language, package, test, configuration, and entry-point map.
- `harness/model.py`: OpenAI-compatible text API client and strict JSON action parser.
- `harness/context.py` and `harness/state.py`: bounded history, truncation, cache space, and compact task state.
- `harness/agent.py`: inspect, decide, execute, observe, recover, test, and verify loop.
- `harness/ui.py` and `harness/cli.py`: concise activity stream and command-line entry point.

The model must return an action object such as `{"action":"search_files","arguments":{"query":"login"},"summary":"Locating login routes."}`. It can inspect, edit, run tests, inspect the diff, or finish only after verification. Model failures and tool failures are fed back into the bounded loop; `AI_MAX_RETRIES` and `AI_MAX_STEPS` prevent infinite work.

## Safety and efficiency

All relative paths resolve beneath the selected repository. Traversal, root deletion, and several destructive shell patterns are blocked. File edits require one exact match. Environment secrets are not included in prompts or command output. Directory listings skip generated/vendor directories, files and command output are truncated, and context history is bounded.

## Commands

- `make setup`: create a local virtual environment; no runtime package downloads are required.
- `make run`: run the agent. Set `REPO` and `TASK`; the evaluator can also provide its own environment.
- `make test`: run the unit and fake-repository end-to-end tests.
- `make clean`: remove generated Python and test caches.

## Verification output

The final screen distinguishes completed versus unverified work, reports test status, changed files, and the latest error. The harness also checks exit codes and can inspect `git diff`; it does not claim success merely because a model proposed a change.

## Known limitations

The initial test runner supports common pytest, unittest, and npm layouts and selects the first detected runner. The API client expects an OpenAI-compatible chat-completions response. A human should review changes before merging, especially when a task requires domain-specific judgment or a repository uses an unsupported build system.# AI-Harness
