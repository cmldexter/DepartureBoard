# Boards you can switch

A board is its messages and its display settings. Pictures are files shared by slug. So a saved
board — a *profile* — is one JSON file beside them, `profiles/<slug>.json` in the data directory:
no table, hand-editable, and the export format for free.

## On the settings page

The **Boards** strip under the header: *This board: Party* (or *unsaved board*), then

- **Switch…** — a saved board replaces the live one; the TV follows on its next poll. It asks first
  when the live board has changes since it was saved.
- **Save** — the live board into its own file. **Save as…** — under a new name (the name makes
  the slug: *Party 2026* → `party-2026`).
- **⋯** — *Duplicate* (a copy under a new name, not switched to), *Rename*, *Delete* (the file; what
  is on the TV stays as it is).
- A **dot** after the name: the live board differs from its saved file.

## The file

```json
{
  "name": "Party",
  "saved_at": "2026-10-25T18:00:00Z",
  "settings": { "grid_preset": "large", "theme": "midnight", "cell_gap": 10, "…": "…" },
  "messages": [
    { "text": "WELCOME {yellow}", "enabled": true, "priority": 1, "show_seconds": 30 },
    { "text": "STANDUP {blue}", "repeat": "daily", "repeat_start": "09:00", "repeat_end": "10:00" }
  ]
}
```

- `settings` holds every display key `PATCH /api/settings` takes (preset and grid, animation,
  sound, theme, idle text, poll and rotate intervals, the timer ring, the background, the flap
  shape, the guest *settings*) — **not** the guest link's token, and not `active_profile`.
- `messages` are what `POST /api/messages` takes: text, enabled, priority, the window or repeat,
  `show_seconds`, `created_by`. Ids are not stored; a load makes new ones.
- Pictures are not inside: `{img:cat}` names a file under `images/` that stays on disk whatever
  board is up. A profile that names a picture that is gone lists it under `pictures_missing`; the
  message is kept and shows a blank where the picture was.

Edit the file by hand if you like; it is validated when loaded. `GET /api/profiles/{slug}` returns
it, `PUT /api/profiles/{slug}` stores one you wrote — the export and import.

## What a switch replaces, and what it keeps

A load is **one transaction**: every live message is deleted, the profile's are inserted, the
display settings are set from the file (a key the file lacks goes back to its default), and
`active_profile` points at the slug. **Every message travels with the board** — one posted with
`/now` too; it has no mark that sets it apart. A message that does not lay out on the profile's own
grid is kept **disabled** with the reason (`kept_disabled` in the response; the row switch turns it
back on once it fits). A background picture that is gone is cleared. The guest link, the guest
queue, pictures and the token are untouched.

## From a script or an agent

| Call | What |
|---|---|
| `GET /api/profiles` | `[{slug, name, saved_at, messages, pictures_missing, active, changed}]` |
| `POST /api/profiles/{slug}/save` `{"name": "Party"}` | The live board into the file (201 new, 200 overwritten); the name defaults to the old one |
| `POST /api/profiles/{slug}/load` | Replace the live board → `kept_disabled` |
| `POST /api/profiles/{slug}/copy` `{"slug": "party-2", "name": "…"}` | A copy (409 when the slug is taken) |
| `PATCH /api/profiles/{slug}` `{"name": "…"}` · `DELETE /api/profiles/{slug}` | Rename; delete the file |
| `GET` · `PUT /api/profiles/{slug}` | The file itself |

**The party board at seven, every Saturday** — one cron line:

```
0 19 * * 6  curl -fsS -X POST http://board:8080/api/profiles/party/load -H "Authorization: Bearer $TOKEN"
0 23 * * 6  curl -fsS -X POST http://board:8080/api/profiles/everyday/load -H "Authorization: Bearer $TOKEN"
```

`integrations/curl/examples.sh profile save party "Party"`, `profile load party` and
`profile list` do the same. For days planned ahead on the settings page itself, see the calendar
(Epic 23 on the roadmap).
