# Deploying Quanta to a self-hosted k3s cluster

Your images are published by CI to GHCR:

- `ghcr.io/wacobjilson/quanta-backend:latest`
- `ghcr.io/wacobjilson/quanta-frontend:latest`

> **Prerequisite:** make both packages **public** (one-time) so k3s can pull them
> without a secret:
> - https://github.com/users/Wacobjilson/packages/container/quanta-backend/settings → Danger Zone → Change visibility → Public
> - https://github.com/users/Wacobjilson/packages/container/quanta-frontend/settings → same
>
> (If you'd rather keep them private, see "Private images" at the bottom.)

k3s already gives you everything else:
- **Traefik** ingress controller (the chart targets `traefik` by default)
- **local-path** default StorageClass (the PVCs use the cluster default)

---

## Step 1 — Get a shell with cluster access

Run these on the **k3s server node** (it has `kubectl` built in), or from any machine
that has your kubeconfig. On the node:

```bash
# k3s writes its kubeconfig here; export it for kubectl/helm
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get nodes        # confirm the cluster responds
```

> To drive it from your Windows machine instead, copy `/etc/rancher/k3s/k3s.yaml`
> to `~/.kube/config` and replace `127.0.0.1` in it with the node's LAN IP.

## Step 2 — Install Helm (if not present)

```bash
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

## Step 3 — Get the chart onto that machine

```bash
git clone https://github.com/Wacobjilson/trading-dashboard.git
cd trading-dashboard
```

## Step 4 — Pick a hostname

For a homelab with no DNS, use a wildcard-DNS trick so the name resolves to your
node automatically. If your k3s node IP is e.g. `192.168.1.50`, use:

```
quanta.192.168.1.50.nip.io
```

(`nip.io` resolves `anything.<IP>.nip.io` → `<IP>`.) Or add a line to your client's
`/etc/hosts` / `C:\Windows\System32\drivers\etc\hosts`:

```
192.168.1.50   quanta.local
```

## Step 5 — Install with Helm

Replace `HOST` with your chosen hostname. Start in **mock mode** (no API keys) to
verify the deploy, then add keys later (Step 7).

```bash
HOST=quanta.192.168.1.50.nip.io

helm upgrade --install quanta ./deploy/helm/trading-dashboard \
  --namespace quanta --create-namespace \
  --set image.registry=ghcr.io \
  --set image.repository=wacobjilson/quanta \
  --set backend.tag=latest \
  --set frontend.tag=latest \
  --set ingress.className=traefik \
  --set ingress.host=$HOST \
  --set ingress.corsAllowedOrigins=http://$HOST \
  --set secret.values.JWT_SECRET="$(openssl rand -base64 48)"
```

Watch it come up:

```bash
kubectl -n quanta get pods -w
```

You should see `quanta-postgres-0`, `quanta-redis-0`, and the backend/frontend pods
go `Running`. The backend auto-migrates the database on first start.

## Step 6 — Open it

Browse to `http://quanta.192.168.1.50.nip.io` (your HOST). Register a user, log in,
and the dashboard streams quotes. With no API key set it serves **synthetic mock
data** — proof the whole pipeline (ingress → frontend → backend → WS → Postgres/Redis)
works end to end.

## Step 7 — Add real market data (and AI)

Re-run the same `helm upgrade --install` command with extra `--set` flags (Helm keeps
your other values):

```bash
  --set secret.values.FINNHUB_API_KEY="<your-finnhub-key>" \
  --set secret.values.POLYGON_API_KEY="<your-polygon-key>" \
  --set secret.values.ANTHROPIC_API_KEY="<your-anthropic-key>"
```

The backend picks the first configured provider automatically (or pin one with
`--set backend.marketDataProvider=polygon`). Restart picks up the new secret:

```bash
kubectl -n quanta rollout restart deploy/quanta-backend
```

---

## Alternative: raw manifests (no Helm)

```bash
cd deploy/k8s
# edit 01-secret.yaml (JWT_SECRET + keys) and 06-ingress.yaml (host)
kubectl apply -k .
```

The image references already point at `ghcr.io/wacobjilson/quanta-*:latest`.

## Enabling HTTPS (optional)

Install cert-manager and add a ClusterIssuer, then:

```bash
  --set ingress.tls.enabled=true \
  --set ingress.tls.secretName=quanta-tls \
  --set ingress.corsAllowedOrigins=https://$HOST
```

(and add the cert-manager issuer annotation to the ingress).

## Private images (if you skipped making packages public)

Create a pull secret and reference it:

```bash
kubectl -n quanta create secret docker-registry ghcr-creds \
  --docker-server=ghcr.io \
  --docker-username=Wacobjilson \
  --docker-password=<a-GHCR-PAT-with-read:packages>

# then add to the helm install:
#   --set imagePullSecrets[0].name=ghcr-creds
```

(Requires adding `imagePullSecrets` to the deployment templates — ask and I'll wire it in.)

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Pods `ImagePullBackOff` | Packages still private → make them public (top of this doc) |
| Pod `Pending` on PVC | `kubectl get sc` — ensure a default StorageClass exists |
| 404 / can't reach host | `kubectl -n quanta get ingress`; confirm HOST resolves to the node IP |
| WebSocket won't connect | Traefik handles WS natively; confirm you browse the same HOST as `corsAllowedOrigins` |
| Backend `CrashLoopBackOff` | `kubectl -n quanta logs deploy/quanta-backend` — usually DB not ready yet; it retries |
