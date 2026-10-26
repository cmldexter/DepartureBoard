# departureboard (Helm chart)

The same board Compose runs, on a Kubernetes cluster: one Deployment (one replica — SQLite on one
volume), a Service, a PersistentVolumeClaim for `/data`, an optional Ingress, a non-root pod.
The chart ships with every release as OCI:

```bash
helm install board oci://ghcr.io/cmldexter/charts/departureboard --version 0.5.0 \
  --namespace departureboard --create-namespace
```

`image.tag` defaults to the chart's `appVersion`, so a chart version pins its image. The longer
walk-through (hostname, TLS, the token, upgrades, backups) is
[docs/kubernetes.md](../../../docs/kubernetes.md).

## Values

| Key | Default | What it does |
|---|---|---|
| `image.repository` | `ghcr.io/cmldexter/departureboard` | The image (amd64 and arm64) |
| `image.tag` | `""` | Empty = the chart's `appVersion` |
| `image.pullPolicy` | `IfNotPresent` | |
| `imagePullSecrets` | `[]` | For a private mirror |
| `env.TZ` | `UTC` | Timezone schedules are evaluated in (IANA name) |
| `env.DEPARTUREBOARD_HOST` | `""` | The board's name, shown on the settings page; put the Ingress host here |
| `env.DEPARTUREBOARD_CORS_ORIGINS` | `""` | Comma-separated origins allowed to call the API from a browser |
| `env.DEPARTUREBOARD_CALENDAR_TICK_SECONDS` | `"30"` | How often the calendar of boards checks the day (`"0"` = off) |
| `extraEnv` | `[]` | More `env` entries, verbatim |
| `existingSecret` | `""` | A Secret you manage whose `secretKey` becomes `DEPARTUREBOARD_API_TOKEN`; empty = the app mints a token into `/data/api_token` |
| `secretKey` | `DEPARTUREBOARD_API_TOKEN` | The key in that Secret |
| `persistence.enabled` | `true` | `false` = an `emptyDir` (the board forgets everything on restart) |
| `persistence.existingClaim` | `""` | Use a claim you made |
| `persistence.storageClass` | `""` | The cluster's default class when empty |
| `persistence.accessModes` | `[ReadWriteOnce]` | |
| `persistence.size` | `2Gi` | Database, pictures, saved boards, the calendar |
| `persistence.annotations` | `{}` | |
| `service.type` / `service.port` | `ClusterIP` / `80` | The pod listens on 8000 |
| `ingress.enabled` | `false` | |
| `ingress.className` | `""` | |
| `ingress.annotations` | `{}` | e.g. `cert-manager.io/cluster-issuer` |
| `ingress.hosts` | one host, `/` Prefix | |
| `ingress.tls` | `[]` | |
| `resources` | 50m / 128Mi requests, 512Mi limit | |
| `podSecurityContext` | uid/gid/fsGroup 10001, non-root, RuntimeDefault | The image's user is `board` (10001) |
| `securityContext` | no escalation, read-only root, drop ALL | `/tmp` is an `emptyDir` |
| `livenessProbe` / `readinessProbe` / `startupProbe` | `GET /api/health` | Full probe objects; override whole |
| `podAnnotations`, `podLabels`, `priorityClassName`, `nodeSelector`, `tolerations`, `affinity` | empty | Passed through |

## Notes

- **One replica, always.** The database is SQLite on the volume; the Deployment uses
  `strategy: Recreate` so two pods never hold it at once. Scale the TV count, not the pod count.
- **The PVC is kept** on `helm uninstall` (`helm.sh/resource-policy: keep`). Delete it yourself if you
  mean it.
- **The token.** With no `existingSecret`, the app mints one on first boot, prints it once in the log
  and keeps it in `/data/api_token`:
  `kubectl -n departureboard exec deploy/board-departureboard -- cat /data/api_token`.
- **TLS** ends at the Ingress. `DEPARTUREBOARD_TLS` is not a chart value: the probes speak plain http
  to the pod.
- **Upgrades:** `helm upgrade board oci://ghcr.io/cmldexter/charts/departureboard --version X.Y.Z`;
  the app migrates its database on start.
- **Plain manifests:** `deploy/kubernetes.yaml` at the repo root is this chart rendered with the
  defaults for `kubectl apply`.

## Developing the chart

```bash
helm lint deploy/helm/departureboard
helm lint deploy/helm/departureboard -f deploy/helm/departureboard/ci/full-values.yaml
helm template departureboard deploy/helm/departureboard --namespace departureboard > deploy/kubernetes.yaml
```

CI lints both, checks the rendered file is current, and installs the chart on a kind cluster with the
PR's image (`.github/workflows/ci.yml`). `release.yml` pushes the chart to `oci://ghcr.io/cmldexter/charts`
with the release tag.
