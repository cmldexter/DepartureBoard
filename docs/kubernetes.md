# DepartureBoard on Kubernetes

Kubernetes is the board's second way to run — a peer of Compose, not an add-on. Same image
(`ghcr.io/cmldexter/departureboard`, amd64 and arm64), same `/data` layout (the SQLite database, the
token, pictures, saved boards, the calendar), same environment variables, same release: the Helm
chart is published with every version as OCI at `oci://ghcr.io/cmldexter/charts/departureboard`.

## The one-minute version

```bash
helm install board oci://ghcr.io/cmldexter/charts/departureboard --version 0.5.0 \
  --namespace departureboard --create-namespace
kubectl -n departureboard port-forward svc/board-departureboard 8080:80
```

Open `http://localhost:8080/settings`. The token it asks for:

```bash
kubectl -n departureboard exec deploy/board-departureboard -- cat /data/api_token
```

That is a board with a Service, a 2 GiB volume on the cluster's default StorageClass and no Ingress.
The TV needs a name, so read on.

## What you need

- A cluster, 1.25 or newer, and `helm` 3.8 or newer (OCI charts).
- A default StorageClass, or one you name in `persistence.storageClass`. Any `ReadWriteOnce` class
  works; the board is one pod.
- For a TV on the network: an Ingress controller, a DNS name that reaches it, and (recommended) a
  certificate — cert-manager or whatever issues them in your cluster. A TV browser takes the
  native wake lock only on `https://` or a `*.localhost` name, so a certificate is worth having.

## The values that matter

Put them in a file and pass `-f board.yaml`:

```yaml
# board.yaml
env:
  TZ: America/New_York                 # schedules are evaluated in this timezone
  DEPARTUREBOARD_HOST: board.example.com   # the name the settings page shows and the integrate page pre-fills
persistence:
  size: 5Gi                            # pictures add up
  # storageClass: longhorn
ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: board.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: board-tls
      hosts: [board.example.com]
```

```bash
helm upgrade --install board oci://ghcr.io/cmldexter/charts/departureboard --version 0.5.0 \
  --namespace departureboard --create-namespace -f board.yaml
```

The TV opens `https://board.example.com/`, your laptop `https://board.example.com/settings`, and the
first-run walkthrough takes it from there — the same as Compose.

| Value | What it is for |
|---|---|
| `env.TZ` | The timezone daily and weekly schedules use. `UTC` by default |
| `env.DEPARTUREBOARD_HOST` | A bare name (no scheme, port or path). Shown on the settings page, pre-filled on the integrate page. The app does not make it resolve; your DNS and Ingress do |
| `env.DEPARTUREBOARD_CORS_ORIGINS` | Off by default. Comma-separated origins that may call the API from a browser app elsewhere |
| `env.DEPARTUREBOARD_CALENDAR_TICK_SECONDS` | How often the calendar of boards checks whether today's board changed. `"30"`; `"0"` turns the tick off |
| `existingSecret` / `secretKey` | Bring your own token (below) |
| `persistence.size`, `persistence.storageClass`, `persistence.existingClaim` | The volume behind `/data` |
| `ingress.*` | Class, annotations, host, TLS secret |
| `resources` | 50m CPU / 128Mi requested, 512Mi limit. The board is small; raise the limit only if pictures are many and large |
| `image.tag` | Empty = the chart's `appVersion`. A chart version pins its image |

The chart's [README](../deploy/helm/departureboard/README.md) lists every value.

## The token

Every write needs the bearer token; the board page and `GET /api/board/current` are public, so a
TV never holds a secret.

- **Minted (default).** The app makes a token on first boot, prints it once in the pod's log and keeps
  it in `/data/api_token` on the volume. Read it with `kubectl exec … -- cat /data/api_token`. It
  survives restarts and upgrades because the volume does.
- **Yours.** Make a Secret and name it:

  ```bash
  kubectl -n departureboard create secret generic departureboard-token \
    --from-literal=DEPARTUREBOARD_API_TOKEN="$(openssl rand -hex 24)"
  helm upgrade board … --set existingSecret=departureboard-token
  ```

  The key is `DEPARTUREBOARD_API_TOKEN` unless you set `secretKey`. A secret store (External
  Secrets, Sealed Secrets, the Vault injector) fits here: the chart only needs the Secret to exist.
  Changing the token restarts the pod; sessions on the settings page sign in again.

## Upgrading

```bash
helm upgrade board oci://ghcr.io/cmldexter/charts/departureboard --version 0.6.0 -f board.yaml
```

The new pod runs the database migrations on start, before `/api/health` answers; the old pod is gone
first (`strategy: Recreate`), so the board is dark for the seconds in between. Pin the chart version
in your values or your GitOps tool rather than following `latest` — a board on a wall should change
when you say so. Each release's notes are in [CHANGELOG.md](../CHANGELOG.md).

## Backup

Everything the board knows is on the PVC: `departureboard.db` (SQLite), `api_token`, `images/`,
`profiles/` and `calendar.json`. Back the volume up the way your cluster backs volumes up
(a snapshot class, Longhorn or Velero recurring backups, or a CronJob that copies `/data`). A copy of
`/data` from a Compose install restores into the PVC, and the other way round — the layout is the
same. The PVC is kept on `helm uninstall` for the same reason.

## Why one replica

The database is SQLite, a file on one volume. One pod owns it; a second pod would corrupt it or
wait on its lock. The Deployment therefore runs one replica with `strategy: Recreate`, the PVC is
`ReadWriteOnce`, and the chart has no `replicaCount`. The board is a small app — one pod serves a
house full of TVs — so this costs nothing but the few seconds of an upgrade.

## Plain manifests instead of Helm

`deploy/kubernetes.yaml` is the chart rendered with its defaults (namespace `departureboard`, no
Ingress, a 2 GiB PVC on the default class):

```bash
kubectl create namespace departureboard
kubectl apply -f https://raw.githubusercontent.com/cmldexter/DepartureBoard/v0.5.0/deploy/kubernetes.yaml
```

Edit it for an Ingress or a name, or render your own: `helm template board deploy/helm/departureboard -f board.yaml`.

## What is the same as Compose, and what is not

| | Compose | Kubernetes |
|---|---|---|
| Image | `ghcr.io/cmldexter/departureboard:X.Y.Z` | the same |
| Data | the `departureboard_data` volume | the PVC |
| Port | `8080` on the machine | the Service (80) and the Ingress |
| TLS | `DEPARTUREBOARD_TLS=self-signed` in the container | the Ingress and its certificate; the pod stays http |
| Token | `docker compose exec departureboard cat /data/api_token` | `kubectl exec deploy/… -- cat /data/api_token`, or your Secret |
| Upgrade | `docker compose pull && up -d` | `helm upgrade … --version` |

Anything the API does in one mode it does in the other; [llms.txt](../llms.txt) is the API in one page.
