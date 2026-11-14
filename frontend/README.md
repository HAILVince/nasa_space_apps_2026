# Workspace 1 — Frontend

The whole page is `index.html`: plain HTML with scenario research dashboards and the design chat. **No CSS, no styles, no
images** (that is a project decision; `tests/frontend` enforces it).

- Enter sends the message, Shift+Enter makes a new line.
- `.hu` hostname -> asks the agent for Hungarian answers, anything else -> English.
- It only calls the endpoints in `docs/API.md`. Need a new one? Agree it with the backend
  workspace and add it to `docs/API.md` in the same pull request.
- Show user text and snapshots with `textContent`; only `message.html` (already escaped by
  the server) may go into `innerHTML`.

Test: `pytest tests/frontend`. Try it: run the backend (see CONTRIBUTING.md) and open http://127.0.0.1:8000.
