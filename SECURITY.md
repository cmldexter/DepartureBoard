# Security

## Reporting a vulnerability

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/cmldexter/DepartureBoard/security/advisories/new),
not as a public issue. You will get an acknowledgement within a week.

## Supported versions

The latest minor release. Older releases are not patched.

## What the app assumes

- It is meant to run on a home or office network. Nothing in the container terminates TLS; if you
  expose it beyond the LAN, put a reverse proxy with HTTPS in front of it.
- Every write needs the bearer token. The token is generated on first boot, stored in the data
  volume, and printed once in the server log. Treat the log and the settings page as secrets.
- The board endpoint (`GET /api/board/current`) and the board page are public by design, so a TV
  never holds a secret. Anything you put on the board is visible to anyone who can reach the port.
- There are no user accounts. One token, one board.
