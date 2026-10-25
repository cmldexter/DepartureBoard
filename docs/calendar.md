# A calendar of boards

Saved boards ([docs/profiles.md](profiles.md)) assigned to dates, so the week, the month or the
holidays are planned once and the board changes by itself.

## On the settings page

The **Calendar** section: this month and the next as grids, each planned day tinted by its board
and today outlined; a legend; the plan as a list (*Oct 31 · Halloween*, *Dec 20 – 26 · Christmas ·
"family"*) with Edit and Delete; a form — board, from, until (blank = until further notice), a
note; and the **everyday board**, what shows between planned days. Click a day in a grid to start a
plan there. *Today: Halloween — today only* says what the calendar decided for today.

Every change is applied at once: if it changes today's board, the Boards strip and the live card
follow within a moment, and the status line says which board was saved where.

## The rules

1. **At midnight, the board's time** (`TZ` in `.env`), the switch finds the entry covering the new
   day. It runs every 30 seconds (`DEPARTUREBOARD_CALENDAR_TICK_SECONDS`; `0` turns it off, and
   `POST /api/calendar/apply` still works), so a change made at 19:00 for today is on the TV
   within half a minute.
2. **Nothing is lost.** Before it loads the planned board, the switch **saves the live board back
   into its own profile** — the one the Boards strip names. A board that was never saved and holds
   messages is saved as `unsaved-<date>` first. Then the planned board is loaded like *Switch…*
   would: every message replaced, the display settings set, `active_profile` pointing at it.
3. **The later start wins** when two entries cover a day — a one-day party inside the Christmas
   week shows that day, and the week comes back the day after.
4. **Between planned days** the everyday board is loaded, if one is set; otherwise the board stays
   on the last planned one until the next entry.
5. **A deleted board** leaves its entries in place, marked *board deleted — skipped*; the everyday
   board, if any, applies instead. Save a board under that slug again and the entries work again.
6. The calendar never touches pictures, the guest link or the token. The calendar's own two
   settings are not part of a profile.

A manual *Switch…* on a planned day stands: the switch only acts when the plan for the day
changes, not every tick.

## The file

`calendar.json` in the data directory, beside `profiles/`:

```json
{
  "entries": [
    { "id": 1, "profile": "halloween", "start": "2026-10-31", "end": "2026-10-31", "note": "" },
    { "id": 2, "profile": "xmas", "start": "2026-12-20", "end": "2026-12-26", "note": "family" }
  ]
}
```

`end` is inclusive; `null` means until further notice. Hand-editable; the server reads it on every
tick.

## From a script or an agent

| Call | What |
|---|---|
| `GET /api/calendar` | `{everyday, entries: [{id, profile, name, start, end, note, missing}], today: {date, profile, entry_id, until}, applied}` |
| `POST /api/calendar` `{"profile": "xmas", "start": "2026-12-20", "end": "2026-12-26", "note": "family"}` | Plan a board (422 for an unknown board or `end` before `start`) |
| `PATCH /api/calendar/{id}` · `DELETE /api/calendar/{id}` | Change or remove an entry |
| `PATCH /api/settings {"calendar_everyday": "everyday"}` | The board between planned days (`""` = stay) |
| `POST /api/calendar/apply` | Run the switch now → `{changed, applied, loaded, saved_back, kept_disabled}` |

`integrations/curl/examples.sh calendar add xmas 2026-12-20 2026-12-26`, `calendar list` and
`calendar delete 2` do the same.
