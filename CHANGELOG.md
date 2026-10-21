# Changelog

All notable changes to DepartureBoard are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). Each release is a tag `vX.Y.Z`, a GitHub release
and a container image `ghcr.io/cmldexter/departureboard:X.Y.Z`.

## [Unreleased]

## [0.1.0] — 2026-10-21

The first release: a board anyone can run tonight. It exists because
[@feltbykraft](https://www.instagram.com/feltbykraft/) asked for a split-flap board people
can afford — *"come find me when that exists."*

### Added

- **The board** (`/`): a split-flap display that flips, cascades left to right and clicks.
  Two presets, Compact (6 × 22, for a 42–48" TV) and Large (8 × 28, for 55–77"), or a custom
  grid; an animation setting from instant to the full mechanical pace; four themes (Classic
  black, Walnut, Arctic white, Midnight) with bundled fonts; a synthesized click with volume
  and mute; a fullscreen button that keeps the TV awake (Screen Wake Lock where the browser
  allows it, a silent video otherwise); colour chips, emoji and uploaded pictures as flaps.
- **The settings page** (`/settings`): write messages, preview them, schedule them (a window,
  a daily or weekly repeat), set the preset, theme, animation, sound and idle text, upload
  pictures. Behind a bearer token generated on first boot.
- **The API**: everything the settings page does. `POST /api/messages/now` takes a JSON or a
  plain-text body for one-line integrations; `GET /api/board/current` is public and cheap to
  poll with ETag. Swagger at `/docs`, written to be read.
- **The integrate page** (`/integrate`): copy-paste `curl` lines pre-filled with your own host
  and token, one per task, with the expected response under each.
- **The agent bundle** under `integrations/`: runnable `curl` examples, an Agent Skill
  (`SKILL.md`, read by Claude Code, Hermes Agent and others), `llms.txt` (served at
  `/llms.txt`) and a Hermes walkthrough.
- **One command**: `docker compose up -d` pulls `ghcr.io/cmldexter/departureboard` (amd64 and
  arm64, so a Raspberry Pi can host the board) and serves on port 8080; SQLite in a named
  volume; a non-root container built from a digest-pinned base.
- **Docs**: a TV setup guide (`docs/tv-setup.md`) covering laptops, Raspberry Pi kiosks, Fire
  TV, Google TV, built-in TV browsers and Apple TV, with the keep-awake matrix.

### Security

- `main` is protected: every change is a reviewed PR; CI is required.
- Dependencies are locked (`uv.lock`), the base image and `uv` are pinned by digest, GitHub
  Actions are pinned by commit, Dependabot proposes bumps.
- The release image carries a build provenance attestation:
  `gh attestation verify oci://ghcr.io/cmldexter/departureboard:0.1.0 --owner cmldexter`.
- The board endpoint and the pictures are public so the TV never holds a secret; everything
  else needs the token. CORS is off unless origins are listed.

[Unreleased]: https://github.com/cmldexter/DepartureBoard/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cmldexter/DepartureBoard/releases/tag/v0.1.0
