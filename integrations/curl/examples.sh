#!/usr/bin/env bash
# DepartureBoard — runnable curl examples, one function per task.
#
#   export DB_URL=http://192.168.1.20:8080      # where the board is
#   export DB_TOKEN=…                           # from `docker compose logs departureboard`, or /settings
#   ./examples.sh now "DINNER AT 7"
#   ./examples.sh now "DINNER AT 7" 10                           # holds the board 10 s when taking turns (show_seconds)
#   ./examples.sh window "HAPPY BIRTHDAY NICK {yellow}" 2026-10-21T07:00:00-04:00 2026-10-21T23:00:00-04:00
#   ./examples.sh daily "STANDUP 09:30 {blue}" 09:00 10:00
#   ./examples.sh weekly "BINS OUT TONIGHT" 4 18:00 23:00      # repeat_days: Mon 1 Tue 2 Wed 4 Thu 8 Fri 16 Sat 32 Sun 64
#   ./examples.sh image ./cat.png cat                            # then "HELLO {img:cat}"
#   ./examples.sh qr menu "https://example.com/menu"            # a QR code, drawn whole — then "SCAN ME {img:menu}"
#   ./examples.sh profile save party "Party" | load party | list   # the live board as a saved file; load puts it on the TV
#   ./examples.sh calendar add xmas 2026-12-20 2026-12-26 | list | delete 2   # a saved board on dates; the board switches at midnight
#   ./examples.sh list [live|scheduled|expired|disabled]
#   ./examples.sh delete 12
#   ./examples.sh preset large|compact|custom [rows cols]
#   ./examples.sh board                                          # what the TV sees (no token)
#   ./examples.sh --demo                                         # only checks the host answers
set -euo pipefail

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; }

need() {
  if [ -z "${DB_URL:-}" ]; then echo "DB_URL is not set (e.g. http://192.168.1.20:8080)" >&2; exit 2; fi
  if [ "${1:-}" != "public" ] && [ -z "${DB_TOKEN:-}" ]; then echo "DB_TOKEN is not set" >&2; exit 2; fi
  DB_URL="${DB_URL%/}"
}

auth() { printf 'Authorization: Bearer %s' "$DB_TOKEN"; }
json() { curl -fsS "$@" -H "$(auth)" -H "Content-Type: application/json"; echo; }

db_health()  { need public; curl -fsS "$DB_URL/api/health"; echo; }
db_board()   { need public; curl -fsS "$DB_URL/api/board/current"; echo; }
db_now()     { need; if [ -n "${2:-}" ]; then json -X POST "$DB_URL/api/messages/now" -d "$(jq -cn --arg t "$1" --argjson s "$2" '{text:$t, show_seconds:$s}')"; else curl -fsS -X POST "$DB_URL/api/messages/now" -H "$(auth)" -H "Content-Type: text/plain" --data "$1"; echo; fi; }
db_window()  { need; json -X POST "$DB_URL/api/messages" -d "$(jq -cn --arg t "$1" --arg s "$2" --arg e "$3" '{text:$t, starts_at:$s, ends_at:$e}')"; }
db_daily()   { need; json -X POST "$DB_URL/api/messages" -d "$(jq -cn --arg t "$1" --arg s "$2" --arg e "$3" '{text:$t, repeat:"daily", repeat_start:$s, repeat_end:$e}')"; }
db_weekly()  { need; json -X POST "$DB_URL/api/messages" -d "$(jq -cn --arg t "$1" --argjson d "$2" --arg s "$3" --arg e "$4" '{text:$t, repeat:"weekly", repeat_days:$d, repeat_start:$s, repeat_end:$e}')"; }
db_image()   { need; curl -fsS -X POST "$DB_URL/api/images" -H "$(auth)" -F "file=@$1" ${2:+-F "slug=$2"}; echo; }
db_qr()      { need; json -X POST "$DB_URL/api/images/qr" -d "$(jq -cn --arg s "$1" --arg d "$2" '{slug:$s, data:$d}')"; }
db_list()    { need; curl -fsS "$DB_URL/api/messages${1:+?state=$1}" -H "$(auth)"; echo; }
db_calendar() { need; case "${1:-}" in
  list) curl -fsS "$DB_URL/api/calendar" -H "$(auth)"; echo ;;
  add) json -X POST "$DB_URL/api/calendar" -d "$(jq -cn --arg p "$2" --arg s "$3" --arg e "${4:-}" '{profile:$p, start:$s, end:(if $e == "" then null else $e end)}')" ;;
  delete) curl -fsS -X DELETE "$DB_URL/api/calendar/$2" -H "$(auth)" -o /dev/null -w 'deleted %{http_code}\n' ;;
  *) usage; exit 2 ;;
esac; }
db_profile() { need; case "${1:-}" in
  list) curl -fsS "$DB_URL/api/profiles" -H "$(auth)"; echo ;;
  save) json -X POST "$DB_URL/api/profiles/$2/save" -d "$(jq -cn --arg n "${3:-$2}" '{name:$n}')" ;;
  load) curl -fsS -X POST "$DB_URL/api/profiles/$2/load" -H "$(auth)"; echo ;;
  *) usage; exit 2 ;;
esac; }
db_delete()  { need; curl -fsS -X DELETE "$DB_URL/api/messages/$1" -H "$(auth)" -o /dev/null -w 'deleted %{http_code}\n'; }
db_preset()  { need; if [ "$1" = custom ]; then json -X PATCH "$DB_URL/api/settings" -d "{\"grid_preset\":\"custom\",\"rows\":$2,\"cols\":$3}"; else json -X PATCH "$DB_URL/api/settings" -d "{\"grid_preset\":\"$1\"}"; fi; }

case "${1:-}" in
  --demo)  db_health ;;
  now)     db_now "$2" "${3:-}" ;;
  window)  db_window "$2" "$3" "$4" ;;
  daily)   db_daily "$2" "$3" "$4" ;;
  weekly)  db_weekly "$2" "$3" "$4" "$5" ;;
  image)   db_image "$2" "${3:-}" ;;
  qr)      db_qr "$2" "$3" ;;
  profile) db_profile "${2:-}" "${3:-}" "${4:-}" ;;
  calendar) db_calendar "${2:-}" "${3:-}" "${4:-}" "${5:-}" ;;
  list)    db_list "${2:-}" ;;
  delete)  db_delete "$2" ;;
  preset)  db_preset "$2" "${3:-}" "${4:-}" ;;
  board)   db_board ;;
  health)  db_health ;;
  *)       usage; exit 1 ;;
esac
