---
description: Fetch YouTube transcripts (or search / download) with anansi
argument-hint: <links> | search <query> | download <links> [--audio] | web
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/anansi/scripts/anansi.py:*), Read
---

Use the anansi skill to handle this request: $ARGUMENTS

The CLI is `python3 "${CLAUDE_PLUGIN_ROOT}/skills/anansi/scripts/anansi.py"`.

- If the arguments start with `search`, `download`, `web` or `doctor`, run that subcommand with the rest of the arguments.
- If they are links (or text containing links), run `fetch` on them, read each transcript document it reports, and give a short summary per video: what it covers, the key points with `[m:ss]` timestamps, and anything notable from the description or chapters. Then offer next steps (deeper summary, quotes, comparison, notes file).
- If there are no arguments, ask which videos to fetch, or offer `search`.
