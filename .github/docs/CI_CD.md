# CI/CD Pipeline Documentation

This document provides comprehensive documentation of the GitHub Actions CI/CD pipeline for e621tagger. It covers workflow configuration, build process, and deployment triggers.

---

## Workflow Overview

The CI/CD pipeline is defined in `.github/workflows/docker-publish.yml`.

### Trigger Events

| Event | Branch | Description |
|-------|--------|-------------|
| Push | `latest` | Build and deploy production |
| Pull Request | `latest` | Build test image |

---

## Workflow File

**Location**: `.github/workflows/docker-publish.yml`

```yaml
name: Docker Build

on:
  push:
    branches: [ "latest" ]
  pull_request:
    branches: [ "latest" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
```

---

## Pipeline Stages

### Stage 1: Checkout

```yaml
- name: Checkout repository
  uses: actions/checkout@v6
  with:
    fetch-depth: 0
```

**Purpose**: Clone repository with full history for version detection.

---

### Stage 2: Version Determination

```yaml
- name: Determine app version
  id: version
  run: |
    if [[ "${{ github.event_name }}" == "pull_request" ]]; then
      # PR build: test-{commit_sha}
      APP_VERSION="test-${SHORT_SHA}"
    else
      # Merged: v{pr_number}
      PR_NUMBER=$(gh pr list --state merged --base latest --limit 1 --json number)
      APP_VERSION="v$PR_NUMBER"
    fi
```

**Version Logic**:

| Event | Version Format | Example |
|-------|----------------|---------|
| Pull Request | `test-{commit_sha}` | `test-a1b2c3d` |
| Push to latest | `v{pr_number}` | `v123` |
| Fallback | `{commit_sha}` | `a1b2c3d` |

---

### Stage 3: Model Cache

```yaml
- name: Cache ML model assets
  id: cache-model
  uses: actions/cache@v4
  with:
    path: |
      models/
      data/
    key: ml-models-${{ hashFiles('.github/workflows/docker-publish.yml') }}
    restore-keys: |
      ml-models-
```

**Purpose**: Cache ML model files (~500MB) to avoid re-downloading on subsequent builds.
- Cache key based on workflow file hash - invalidates only when download config changes
- Falls back to any `ml-models-*` cache if exact key not found

---

### Stage 4: Model Download

```yaml
- name: Download ML model assets
  if: steps.cache-model.outputs.cache-hit != 'true'
  run: |
    mkdir -p models data
    curl -L --retry 3 --fail -o models/jtp-3-hydra.safetensors \
      "https://huggingface.co/RedRocket/JTP-3/resolve/main/models/jtp-3-hydra.safetensors"
    curl -L --retry 3 --fail -o data/jtp-3-hydra-tags.csv \
      "https://huggingface.co/RedRocket/JTP-3/resolve/main/data/jtp-3-hydra-tags.csv"
```

**Purpose**: Download ML model files only on cache miss.
- Uses `curl` with retry logic instead of deprecated `ADD` with remote URLs
- Only runs when cache is cold, skipping on cache hit (~seconds vs ~2-3 minutes)

---

### Stage 5: Cosign Setup

```yaml
- name: Install cosign
  uses: sigstore/cosign-installer@v4
```

**Purpose**: Install cosign for container image signing.

---

### Stage 6: Docker Buildx Setup

```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v4
```

**Purpose**: Enable Docker BuildKit with buildx.

---

### Stage 7: Registry Login

```yaml
- name: Log into registry
  uses: docker/login-action@v4
  with:
    registry: ${{ env.REGISTRY }}
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

**Purpose**: Authenticate to GitHub Container Registry.

---

### Stage 8: Metadata Extraction

```yaml
- name: Extract Docker metadata
  id: meta
  uses: docker/metadata-action@v6
  with:
    images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
    tags: |
      type=ref,event=tag
      type=ref,event=branch
      type=raw,value=${{ github.head_ref }}
```

**Output Labels**:
- `tags`: Image tags
- `labels`: Labels from Dockerfile

---

### Stage 9: Build and Push

```yaml
- name: Build and push Docker image
  id: build-and-push
  uses: docker/build-push-action@v7
  with:
    context: .
    push: true
    tags: ${{ steps.meta.outputs.tags }}
    labels: ${{ steps.meta.outputs.labels }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
    build-args: |
      APP_VERSION=${{ steps.version.outputs.app_version }}
```

**Features**:
- Uses local model files from previous steps
- GitHub Actions cache for Docker layers
- Build argument for version
- Push to registry

---

### Stage 10: Image Signing

```yaml
- name: Sign the published Docker image
  env:
    TAGS: ${{ steps.meta.outputs.tags }}
    DIGEST: ${{ steps.build-and-push.outputs.digest }}
  run: echo "${TAGS}" | xargs -I {} cosign sign --yes {}@${DIGEST}
```

**Purpose**: Sign image with cosign for supply chain security.

---

### Stage 11: Image Cleanup

```yaml
- name: Clean up docker images
  uses: dataaxiom/ghcr-cleanup-action@v1
  with:
    keep-n-tagged: 4
    exclude-tags: latest,test
    delete-untagged: true
    delete-partial-images: true
    delete-orphaned-images: true
```

**Cleanup Rules**:
- Keep: 4 tagged images
- Exclude: `latest`, `test`
- Delete untagged: Yes
- Delete partial: Yes
- Delete orphaned: Yes

---

### Stage 12: Deployment Trigger (Production)

```yaml
- name: Trigger Dockhand deployment (latest)
  if: github.event_name == 'push' && github.ref_name == 'latest'
  env:
    WEBHOOK_URL: ${{ secrets.DOCKHAND_WEBHOOK_URL }}
    WEBHOOK_SECRET: ${{ secrets.DOCKHAND_WEBHOOK_SECRET }}
  run: |
    # ... validation checks ...
    if ! curl -sf --connect-timeout 30 --max-time 300 -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
      -d "$PAYLOAD"; then
      echo "❌ Deployment trigger failed" >> $GITHUB_STEP_SUMMARY
      exit 0
    fi
    echo "✅ Deployment triggered" >> $GITHUB_STEP_SUMMARY
```

**Trigger Condition**: Push to `latest` branch
**Note**: Failure does not fail the job - status is appended to build summary

---

### Stage 13: Deployment Trigger (Test)

```yaml
- name: Trigger Dockhand deployment (test)
  if: github.event_name == 'pull_request' && github.head_ref == 'test'
  env:
    WEBHOOK_URL: ${{ secrets.DOCKHAND_WEBHOOK_URL_TEST }}
    WEBHOOK_SECRET: ${{ secrets.DOCKHAND_WEBHOOK_SECRET_TEST }}
  run: |
    # ... validation checks ...
    if ! curl -sf --connect-timeout 30 --max-time 300 -X POST "$WEBHOOK_URL" \
      -H "Content-Type: application/json" \
      -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
      -d "$PAYLOAD"; then
      echo "❌ Test deployment trigger failed" >> $GITHUB_STEP_SUMMARY
      exit 0
    fi
    echo "✅ Test deployment triggered" >> $GITHUB_STEP_SUMMARY
```

**Trigger Condition**: PR to `test` branch
**Note**: Failure does not fail the job - status is appended to build summary

---

### Stage 14: Summary Output

```yaml
- name: Print published image info
  run: |
    echo "## 🐳 Docker Image Built" >> $GITHUB_STEP_SUMMARY
    echo "**Image:** \`${FIRST_TAG}\`" >> $GITHUB_STEP_SUMMARY
    echo "**Digest:** \`${DIGEST}\`" >> $GITHUB_STEP_SUMMARY
    echo "**Version:** \`$APP_VERSION\`" >> $GITHUB_STEP_SUMMARY
```

---

## GitHub Actions Secrets

### Required Secrets

| Secret | Description |
|--------|-------------|
| `GITHUB_TOKEN` |自动提供 |
| `DOCKHAND_WEBHOOK_URL` | Production deployment webhook |
| `DOCKHAND_WEBHOOK_SECRET` | Production webhook HMAC secret |
| `DOCKHAND_WEBHOOK_URL_TEST` | Test deployment webhook |
| `DOCKHAND_WEBHOOK_SECRET_TEST` | Test webhook HMAC secret |

---

## Image Tags

### Production Images

| Tag | Trigger | Example |
|-----|---------|----------|
| `latest` | Push to latest | `ghcr.io/fenrir784/e621tagger:latest` |
| `v123` | Merged PR #123 | `ghcr.io/fenrir784/e621tagger:v123` |

### Test Images

| Tag | Trigger | Example |
|-----|---------|----------|
| `test` | PR to latest | `ghcr.io/fenrir784/e621tagger:test` |
| `test-a1b2c3d` | PR commit | `ghcr.io/fenrir784/e621tagger:test-a1b2c3d` |

---

## Pipeline Flow

```
                    ┌─────────────────────┐
                    │  Push to latest     │
                    │  or PR to latest   │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────┐
│                  1. Checkout                        │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│              2. Version Detection                   │
│  - PR → test-{sha}                                  │
│  - Merge → v{pr_number}                            │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│              3. Model Cache                         │
│  - Check GHA cache for model files                 │
└──────────────────────┬───────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │ Cache hit?            │
           ▼                       ▼
    ┌─────────────┐        ┌─────────────┐
    │ Skip        │        │ Download    │
    │ (~5 sec)    │        │ (~2-3 min)  │
    └─────────────┘        └─────────────┘
           │                       │
           └───────────┬───────────┘
                       ▼
┌──────────────────────────────────────────────────────┐
│              4-8. Build & Push                       │
│  - Cosign, buildx, login, metadata, docker build   │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│              9. Sign Image                          │
│  - cosign sign                                     │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│              10. Cleanup                           │
│  - Keep 4 tagged, exclude latest/test              │
└──────────────────────┬───────────────────────────────┘
              ┌────────┴────────┐
              │                 │
              ▼                 ▼
┌─────────────────────┐  ┌─────────────────────┐
│  Production        │  │  Test Deployment   │
│  (push to latest) │  │  (PR from test)    │
└─────────────────────┘  └─────────────────────┘
```

---

## Concurrency Control

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

| Scenario | Before | After |
|----------|--------|-------|
| Push A → Push B (same branch) | Both build | B cancels A |
| PR update (force push) | Both build | New cancels old |
| Push to main while PR building | Both build | Main cancels PR |

**Benefits**:
- Saves CI minutes by canceling stale builds
- Prevents race conditions in deployment

---

## Docker Build Arguments

### APP_VERSION

The `APP_VERSION` build argument is passed to the Dockerfile:

```dockerfile
ARG APP_VERSION=test
ENV APP_VERSION=${APP_VERSION}
```

This sets:
- Application version string
- Service worker cache version
- Health check response version

---

## Caching Strategy

### Build Cache

```yaml
cache-from: type=gha
cache-to: type=gha,mode=max
```

| Option | Description |
|--------|-------------|
| `type=gha` | GitHub Actions cache |
| `mode=max` | Cache all layers |

### Model Cache

```yaml
- uses: actions/cache@v4
  with:
    path: |
      models/
      data/
    key: ml-models-${{ hashFiles('.github/workflows/docker-publish.yml') }}
    restore-keys: |
      ml-models-
```

| Aspect | Value |
|--------|-------|
| First run | Download ~500MB (2-3 min) |
| Subsequent (cache hit) | Restore from cache (< 5 sec) |
| Invalidation | Only when workflow file changes |

---

## Verification

### Check Build Status

```bash
# View workflow runs
gh run list --workflow=docker-publish.yml

# View specific run
gh run view <run-id>
```

### Check Published Image

```bash
# List images
gh cr list --owner=fenrir784

# View image details
gh cr view e621tagger
```

---

## Troubleshooting

### Build Fails

```bash
# Check workflow logs
gh run view <run-id> --log
```

### Push Fails

```bash
# Check registry permissions
gh auth status
```

### Deployment Not Triggered

```bash
# Check webhook secrets
# Verify DOCKHAND_WEBHOOK_URL is set
```

---

## GitHub Container Registry

### Access Control

```
ghcr.io/fenrir784/e621tagger
```

| Actor | Permission |
|-------|-------------|
| Owner (fenrir784) | Read/Write |
| Public | Read |

---

## Actions Used

| Action | Version | Purpose |
|--------|---------|---------|
| actions/checkout | v6 | Clone repository |
| actions/cache | v4 | Cache ML model files |
| sigstore/cosign-installer | v4 | Install cosign |
| docker/setup-buildx-action | v4 | Docker buildx |
| docker/login-action | v4 | GHCR login |
| docker/metadata-action | v6 | Image metadata |
| docker/build-push-action | v7 | Build & push |
| dataaxiom/ghcr-cleanup-action | v1 | Cleanup old images |

---

## Pipeline Artifacts

### Output Variables

| Variable | Description |
|----------|-------------|
| `app_version` | Detected version |
| `tags` | Image tags |
| `labels` | Image labels |
| `digest` | Image digest |

---

## Permissions

```yaml
permissions:
  contents: read
  packages: write
  id-token: write
```

| Permission | Needed For |
|------------|------------|
| contents: read | Checkout |
| packages: write | Push to GHCR |
| id-token: write | OIDC authentication |

---

## Complete Workflow YAML

```yaml
name: Docker Build

on:
  push:
    branches: [ "latest" ]
  pull_request:
    branches: [ "latest" ]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
      id-token: write

    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0

      - name: Determine app version
        id: version
        run: |
          # Version logic

      - name: Cache ML model assets
        id: cache-model
        uses: actions/cache@v4
        with:
          path: |
            models/
            data/
          key: ml-models-${{ hashFiles('.github/workflows/docker-publish.yml') }}
          restore-keys: |
            ml-models-

      - name: Download ML model assets
        if: steps.cache-model.outputs.cache-hit != 'true'
        run: |
          mkdir -p models data
          curl -L --retry 3 --fail -o models/jtp-3-hydra.safetensors \
            "https://huggingface.co/RedRocket/JTP-3/resolve/main/models/jtp-3-hydra.safetensors"
          curl -L --retry 3 --fail -o data/jtp-3-hydra-tags.csv \
            "https://huggingface.co/RedRocket/JTP-3/resolve/main/data/jtp-3-hydra-tags.csv"

      - uses: sigstore/cosign-installer@v4

      - uses: docker/setup-buildx-action@v4

      - uses: docker/login-action@v4
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/metadata-action@v6
        id: meta
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=tag
            type=ref,event=branch

      - uses: docker/build-push-action@v7
        id: build-and-push
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          build-args: |
            APP_VERSION=${{ steps.version.outputs.app_version }}

      - name: Sign the published Docker image
        env:
          TAGS: ${{ steps.meta.outputs.tags }}
          DIGEST: ${{ steps.build-and-push.outputs.digest }}
        run: echo "${TAGS}" | xargs -I {} cosign sign --yes {}@${DIGEST}

      - uses: dataaxiom/ghcr-cleanup-action@v1
        with:
          keep-n-tagged: 4
          exclude-tags: latest,test
          delete-untagged: true

      - name: Trigger Dockhand deployment
        if: github.event_name == 'push'
        run: |
          # ... validation and webhook logic ...
          if ! curl -sf --connect-timeout 30 --max-time 300 -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -H "X-Hub-Signature-256: sha256=$SIGNATURE" \
            -d "$PAYLOAD"; then
            echo "❌ Deployment trigger failed" >> $GITHUB_STEP_SUMMARY
            exit 0
          fi
          echo "✅ Deployment triggered" >> $GITHUB_STEP_SUMMARY
```