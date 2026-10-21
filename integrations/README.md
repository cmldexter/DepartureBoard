# Integrations

The board has an API; the integrations are yours. This folder is what we ship so you can build
one in minutes:

| What | Where | For |
|---|---|---|
| Runnable `curl` examples | [`curl/examples.sh`](curl/examples.sh) | A shell, a cron line, copy-paste into anything |
| An **Agent Skill** | [`skills/departureboard/SKILL.md`](skills/departureboard/SKILL.md) | Claude Code, Hermes Agent and any agent that reads `SKILL.md` |
| A Hermes Agent walkthrough | [`hermes/README.md`](hermes/README.md) | Installing the skill into Hermes and asking it to post and schedule |
| `llms.txt` | [`/llms.txt`](../llms.txt) in the repo root, served at `http://<board>/llms.txt` | Anything that reads the web before acting |

Your own board also serves `/integrate` — the same calls pre-filled with **your** host and
token — and `/docs`, the complete reference generated from the code.

Built something? Share it in
[Discussions → Show and tell](https://github.com/cmldexter/DepartureBoard/discussions/categories/show-and-tell).
We will not add per-service panels to the UI; that is the point.
