# Deployment

This page covers running FAIRGAME locally for development, in Docker for
production, and in Kubernetes via the bundled Helm chart.

## Local development

```bash
python -m venv fairenv
source fairenv/bin/activate
pip install -e '.[server,test]'
cp .env.example .env       # fill in API_KEY_OPENAI / etc.
```

Run the API:

```bash
python api.py              # dev server on :5003
gunicorn api:app --bind 0.0.0.0:5003 --workers 2 --threads 4 --timeout 300
```

Or invoke the engine directly:

```bash
python main.py local       # runs the configured prisoner_dilemma scenario
```

## Tests

```bash
pytest                          # default: 54 tests, no live LLM required
FAIRGAME_LIVE_LLM=1 pytest      # also run translation tests against real provider
pytest --cov=src --cov-report=term-missing  # with coverage
```

The default suite uses a deterministic fake connector registered by
`unit_tests/conftest.py`; no API keys are needed.

## Docker

The shipped Dockerfile produces a slim Python 3.12 image, runs as an
unprivileged `fairgame` user, and ships gunicorn as the default entry point
with a built-in `HEALTHCHECK`.

```bash
docker build -t fairgame:dev .
docker run --rm -p 5003:5003 \
  -e API_KEY_OPENAI=sk-... \
  -e API_KEY_ANTHROPIC=sk-... \
  fairgame:dev
```

Health probe:

```bash
curl http://localhost:5003/health
```

## Helm

A Helm chart is bundled under `.deploy/helm/`. The most important values:

| Value | Purpose |
|---|---|
| `image.repository`, `image.tag` | Container image to deploy. |
| `service.port` | Cluster-internal port (matches `PORT` in the container). |
| `env` | Override env vars (set `FAIRGAME_LOG_LEVEL`, retry tuning, S3). |
| `secrets` | API keys mounted as env vars. |
| `resources` | CPU / memory requests and limits. Recommended: 1 CPU + 1Gi RAM minimum because of `sentence-transformers` startup cost. |

Install:

```bash
helm install fairgame .deploy/helm \
  --set image.repository=ghcr.io/your-org/fairgame \
  --set image.tag=v0.1.0 \
  --set-string secrets.API_KEY_OPENAI=sk-...
```

## Production checklist

* [ ] Set `FAIRGAME_LOG_LEVEL=INFO` (or `WARNING`).
* [ ] Provision API keys for whichever providers you actually use; do not set
      keys for unused providers (the lazy connector loader keeps them inert).
* [ ] Configure S3 credentials (`S3_ENDPOINT`, `BUCKET_NAME`, `S3_KEY`,
      `S3_SECRET`, optional `S3_PREFIX`). When omitted, the API still returns
      results in the response body but does not persist them.
* [ ] Tune `FAIRGAME_LLM_MAX_ATTEMPTS` and the backoff window to match your
      provider rate limits.
* [ ] Front the service with a reverse proxy that enforces a generous
      request timeout (the LLM phase can take minutes for large permutation
      runs).
* [ ] Pin the image tag in production (`v0.1.0`, not `latest`).

## Observability

The default log format is:

```
2026-04-29 09:14:07 [INFO] src.fairgame_factory: Running 6 game(s)
```

Pipe stdout to your aggregator (Loki, Cloud Logging, …). For metrics, plug a
`prometheus_flask_exporter` into `create_app()` — the `/health` endpoint is
already wired and returns `{"status": "OK"}` on a `200`.
