#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
# Re-run after recreating kind; only configures this lab's node and registry.
node=retail-lab-control-plane
docker network inspect kind --format '{{json .Containers}}' | grep -q retail-registry || docker network connect kind retail-registry
docker exec "$node" mkdir -p /etc/containerd/certs.d/localhost:5001
docker exec -i "$node" sh -c 'cat > /etc/containerd/certs.d/localhost:5001/hosts.toml' <<'CONFIG'
[host."http://retail-registry:5000"]
  capabilities = ["pull", "resolve"]
CONFIG
docker exec "$node" mkdir -p /etc/systemd/system/containerd.service.d
docker exec -i "$node" sh -c 'cat > /etc/systemd/system/containerd.service.d/retail-proxy.conf' <<'PROXY'
[Service]
Environment="NO_PROXY=127.0.0.1,localhost,retail-registry,retail-lab-control-plane,172.23.0.0/16,10.96.0.0/16,10.244.0.0/16,.svc,.svc.cluster.local"
Environment="no_proxy=127.0.0.1,localhost,retail-registry,retail-lab-control-plane,172.23.0.0/16,10.96.0.0/16,10.244.0.0/16,.svc,.svc.cluster.local"
PROXY
docker exec "$node" systemctl daemon-reload
docker exec "$node" systemctl restart containerd
docker cp "$node:/var/lib/kubelet/config.yaml" env/kubelet.yaml
env/python/bin/python - <<'PY'
import yaml
p='env/kubelet.yaml';o=yaml.safe_load(open(p));o['kubeReserved']={'memory':'2Gi'};o['evictionHard']={'memory.available':'500Mi','nodefs.available':'10%','imagefs.available':'15%','nodefs.inodesFree':'5%'};open(p,'w').write(yaml.safe_dump(o))
PY
docker cp env/kubelet.yaml "$node:/var/lib/kubelet/config.yaml"
docker exec "$node" systemctl restart kubelet
