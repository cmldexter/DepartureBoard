# DepartureBoard with Hermes Agent

[Hermes Agent](https://hermes-agent.nousresearch.com/) reads the same `SKILL.md` format as other
agents, so there is nothing Hermes-specific to maintain: install the skill, give the agent the two
values it needs, and ask.

Written against Hermes Agent's skills CLI as documented in October 2026; if the commands differ in
your version, `hermes skills --help` is the source of truth.

## 1. Install the skill

From a URL (the raw file on `main`):

```bash
hermes skills install https://raw.githubusercontent.com/cmldexter/DepartureBoard/main/integrations/skills/departureboard/SKILL.md
hermes skills list | grep departureboard
```

Or copy [`../skills/departureboard/`](../skills/departureboard/) into your Hermes skills directory.

## 2. Give the agent the board

In the profile's `.env` (never in a prompt or a shared file):

```
DB_URL=http://192.168.1.20:8080
DB_TOKEN=…            # docker compose logs departureboard, or /settings → Show token
```

The skill tells the agent to read both from the environment and never print the token.

## 3. Ask

> Put "HAPPY BIRTHDAY NICK" on the board tomorrow from 7am to 11pm, make it stand out.

The agent reads the board's size, composes `HAPPY BIRTHDAY NICK {yellow}`, posts it with a window
and a priority, and answers with the message's state and id. Other things it can do from the same
skill:

> Show "DINNER AT 7" now.
> Every weekday at 9, say "STANDUP 09:30".
> What is on the board right now? Clear it.
> Put this picture on the board next to WELCOME HOME.   *(attach a PNG; it uploads it and uses `{img:…}`)*
> Switch the board to the large preset and the walnut theme.

## Without the skill: one tool

If you would rather define a single tool than install a skill, the shortest call is the whole
tool — `POST $DB_URL/api/messages/now` with a `text/plain` body and the bearer header. The
complete reference is `http://<board>/docs`; the page `http://<board>/integrate` writes every
call out with your host and token filled in.
