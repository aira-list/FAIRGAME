# Deployment

This page covers running FAIRGAME locally for development, in Docker for
production, and in Kubernetes via the bundled Helm chart.

## Local development

```bash
python -m venv fairenv
source fairenv/bin/activate
pip install -e '.[server,test]'
cp .env.example .env       # fill in OPENAI_API_KEY / etc.
```

Run the web app (FastAPI + SPA):

```bash
uvicorn web_api.main:app --reload --port 4263       # dev server on :4263
uvicorn web_api.main:app --host 0.0.0.0 --port 4263 --workers 2  # production
```

Or invoke the engine directly:

```bash
python main.py local       # runs the configured prisoner_dilemma scenario
```

## Tests

```bash
pytest                          # default suite, no live LLM required
FAIRGAME_LIVE_LLM=1 pytest      # also run translation tests against real provider
pytest --cov=src --cov-report=term-missing  # with coverage
```

The default suite uses a deterministic fake connector registered by
`unit_tests/conftest.py`; no API keys are needed.

## Docker

The shipped Dockerfile produces a slim Python 3.12 image, runs as an
unprivileged `fairgame` user, and starts uvicorn (`web_api.main:app`) on
port 4263 with a built-in `HEALTHCHECK`.

```bash
docker build -t fairgame:dev .
docker run --rm -p 4263:4263 \
  -e OPENAI_API_KEY=sk-... \
  -e ANTHROPIC_API_KEY=sk-... \
  fairgame:dev
```

Health probe:

```bash
curl http://localhost:4263/api/health
```

## Helm

A Helm chart is bundled under `.deploy/helm/`. The most important values:

| Value | Purpose |
|---|---|
| `image.repository`, `image.tag` | Container image to deploy. |
| `service.port` | Cluster-internal port (matches `PORT` in the container). |
| `env` | Override env vars (set `FAIRGAME_LOG_LEVEL`, retry tuning). |
| `secrets` | API keys mounted as env vars. |
| `resources` | CPU / memory requests and limits. Recommended: 0.5 CPU + 512Mi RAM minimum (no local ML model is loaded — translation is delegated to a remote LLM). |

Install:

```bash
helm install fairgame .deploy/helm \
  --set image.repository=ghcr.io/your-org/fairgame \
  --set image.tag=v0.1.0 \
  --set-string secrets.OPENAI_API_KEY=sk-...
```

## Security

**The FastAPI service ships with no built-in authentication or rate limiting.**
The run endpoints (`POST /api/runs`, `POST /api/configurations/{id}/run`, and
the batch variants) invoke real, *paid* LLM providers using the API keys
configured on the server. Anyone who can reach the service can therefore spend
your provider budget.

Treat the app as **local / trusted-network by default**. Before exposing it:

* Put it behind a reverse proxy or gateway that enforces authentication
  (Basic auth, OAuth2 proxy, mTLS, an API gateway, …) and rate limiting.
* Restrict network exposure (bind to `127.0.0.1` for local use; use a private
  network / ingress allow-list otherwise).
* Keep provider API keys in secrets (Docker/Helm secrets or your platform's
  secret manager), never in the image or in committed files. Only `.env`
  (gitignored) or the environment should carry real keys; `.env.example`
  holds placeholders only.

There is no application-level tenant isolation: every caller shares one run
history and one library.

## Production checklist

* [ ] Set `FAIRGAME_LOG_LEVEL=INFO` (or `WARNING`).
* [ ] Provision API keys for whichever providers you actually use; do not set
      keys for unused providers (the lazy connector loader keeps them inert).
* [ ] Persist `results/web/` (run results are written there) on a durable
      volume if you need runs to survive container restarts.
* [ ] Tune `FAIRGAME_LLM_MAX_ATTEMPTS` and the backoff window to match your
      provider rate limits.
* [ ] Front the service with a reverse proxy that enforces a generous
      request timeout (the LLM phase can take minutes for large permutation
      runs) **and authentication / rate limiting** (see [Security](#security)).
* [ ] Pin the image tag in production (`v0.1.0`, not `latest`).

## Observability

The default log format is:

```
2026-04-29 09:14:07 [INFO] src.fairgame_factory: Running 6 game(s)
```

Pipe stdout to your aggregator (Loki, Cloud Logging, …). For metrics, add an
ASGI instrumentation layer (e.g. `prometheus-fastapi-instrumentator`) to the
`web_api.main:app` application — the `/api/health` endpoint is already wired
and returns `{"status": "OK"}` on a `200`.
