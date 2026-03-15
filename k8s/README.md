# TPCP Kubernetes Infrastructure

Production Kubernetes manifests for deploying the TPCP A-DNS relay at scale.

## Prerequisites

- Kubernetes 1.26+
- [nginx ingress controller](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager](https://cert-manager.io/) with a `letsencrypt-prod` ClusterIssuer
- kubectl configured for your cluster

## Deploy

```bash
# 1. Create namespace
kubectl apply -f k8s/namespace.yaml

# 2. Deploy Redis
kubectl apply -f k8s/redis/

# 3. Deploy relay
kubectl apply -f k8s/relay/

# 4. Deploy ingress + TLS
kubectl apply -f k8s/ingress/

# Or deploy everything at once:
kubectl apply -f k8s/namespace.yaml && kubectl apply -f k8s/
```

## Architecture

```
Internet
  │
  ▼
nginx Ingress (relay.tpcp.io:443 → ws upgrade)
  │
  ▼
tpcp-relay Service (ClusterIP :8765)
  │
  ├── tpcp-relay Pod 1  ─┐
  ├── tpcp-relay Pod 2  ─┤── Redis StatefulSet (peer registry)
  └── tpcp-relay Pod 3  ─┘
```

## Scaling

The HPA (`relay/hpa.yaml`) scales between 3–20 replicas based on CPU (70%) and memory (400Mi).

## Build Container

```bash
docker build -f k8s/Dockerfile.relay -t ghcr.io/tpcp-protocol/tpcp-relay:0.4.0 .
docker push ghcr.io/tpcp-protocol/tpcp-relay:0.4.0
```
