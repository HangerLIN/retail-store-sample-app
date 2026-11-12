# Continuous delivery to Kubernetes

This repository now includes three delivery entry points:

- `.github/workflows/deploy-kubernetes.yml` for GitHub Actions and GitHub
  Container Registry.
- `Jenkinsfile.delivery` for a Jenkins multibranch pipeline.
- `.gitlab-ci.yml` for a GitLab project or mirror.

Both paths use the existing service Dockerfiles and the umbrella Helm chart in
`src/app/chart`. Each commit is tested, published as five images tagged with
its immutable short Git SHA, then deployed with Helm. Helm waits for the
Kubernetes API to report each application Deployment ready, and the pipeline
ends by listing the Pods in the target namespace.

## Required CI configuration

Set `IMAGE_REPOSITORY_PREFIX` to a registry path such as
`registry.example.com/platform`. The pipeline publishes:

```
<prefix>/retail-store-sample-cart:<git-sha>
<prefix>/retail-store-sample-catalog:<git-sha>
<prefix>/retail-store-sample-checkout:<git-sha>
<prefix>/retail-store-sample-orders:<git-sha>
<prefix>/retail-store-sample-ui:<git-sha>
```

For local Kubernetes delivery, register a self-hosted Windows runner on the
Docker Desktop machine with the labels `self-hosted`, `Windows`, and `X64`.
The workflow uses that runner's `docker-desktop` kubeconfig to deploy locally;
no kubeconfig is stored in GitHub. The built-in `GITHUB_TOKEN` publishes images
to GitHub Container Registry under `ghcr.io/<repository-owner>`. Every commit
pushed to `main` tests all five services, publishes all five images, deploys
the Helm release, and waits for the resulting Pods.

For Jenkins, create these credentials and set their IDs in the build
parameters:

- a username/password registry credential (`retail-registry` by default);
- a secret-file kubeconfig credential (`retail-kubeconfig` by default).

For GitLab, enable the Container Registry and add a protected, masked
`KUBECONFIG_B64` variable containing the base64-encoded kubeconfig. The built-in
`CI_REGISTRY_*` variables provide registry authentication.

The CI runner or Jenkins agent needs Docker, Helm 3, kubectl, and access to the
registry and Kubernetes API. Configure the Git push webhook in Jenkins or use
GitLab's normal push pipeline trigger. Keep deployment credentials protected so
only the default branch can reach the production environment.

## Deployment behavior

`ci/deploy-helm.sh` runs `helm upgrade --install` against the existing
umbrella chart, pins every application image to the commit tag, waits up to ten
minutes, verifies the five Deployments (`catalog`, `carts`, `checkout`,
`orders`, and `ui`), and prints the final Pod state. No cluster, registry, or
credential is embedded in the repository.

