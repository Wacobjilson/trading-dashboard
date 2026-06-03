# Raw Kubernetes manifests

These mirror the Helm chart defaults for users who prefer plain `kubectl`/Kustomize.
They deploy into the `quanta` namespace and assume images at
`ghcr.io/your-org/quanta-backend:0.1.0` and `quanta-frontend:0.1.0` — edit the
image references to match your registry.

```bash
# 1. Edit 01-secret.yaml with real values (or apply your own Secret named "quanta-secrets").
# 2. Apply everything:
kubectl apply -k .
# or, without kustomize:
kubectl apply -f 00-namespace.yaml -f 01-secret.yaml -f 02-postgres.yaml \
              -f 03-redis.yaml -f 04-backend.yaml -f 05-frontend.yaml -f 06-ingress.yaml
```

Edit `06-ingress.yaml` host + `ingressClassName` (`traefik` or `nginx`) for your
cluster, and rebuild the frontend image with `NEXT_PUBLIC_*` build-args matching
that host (see ../helm/README.md).
