# GUI walkthrough

FAIRGAME ships with a Streamlit web app that wraps every engine feature in
a guided form. It's intended for non-technical users — researchers,
analysts, students — who want to design experiments without reading the
JSON schema.

## Running it

```bash
pip install -e '.[server,test]'   # ensures streamlit + plotly are present
streamlit run gui/app.py
```

The app binds to port `8501` by default (override with
`--server.port 9000`). It opens in your browser automatically; otherwise
visit <http://localhost:8501>.

## Demo mode

The sidebar has a **Demo mode** toggle that defaults to **on**. While it's
on, every LLM call is answered by a fast, deterministic in-process fake
— no API keys are needed and no provider charges accrue. Switch the
toggle off when you're ready to use real models; you'll see a green
"Live mode" banner and provider APIs will be billed on every agent
action.

The toggle hot-swaps the connector registry, so it takes effect
immediately without restarting the app.

## Pages

### 🎯 Home

Landing page with cards pointing to each workflow, a gallery of every
shipped scenario, and a list of recent runs that live on this machine.

### 🚀 Quick start

Pick one of the five shipped scenarios:

* **Prisoner's Dilemma — classic** — 2-player one-shot, multilingual.
* **Prisoner's Dilemma — Theory of Mind** — belief elicitation, second-order
  ToM, private types.
* **Prisoner's Dilemma — mixed strategies + discount** — sampled actions,
  δ=0.9, equilibrium + welfare metrics.
* **Round-robin tournament** — AlwaysCooperate vs AlwaysDefect vs
  TitForTat.
* **Volunteer's Dilemma — multi-agent** — three agents, permutation engine.

Optionally tweak the run label, master seed, and seed count, then click
**Run scenario**. The DataFrame of results renders inline; deeper
inspection is available on the Results page.

### 🛠️ Scenario builder

Six tabs for fully custom scenarios:

| Tab | Purpose |
|---|---|
| Basics | Name, rounds, languages, communication, permutation flag. |
| Agents | Per-agent name, personality, opponent prior, model / baseline. |
| Theory of Mind | Belief elicitation, ToM order (0/1/2), private types. |
| Game theory | Mixed strategies, discount factor, continuation probability, utility transform (CRRA / Fehr-Schmidt), declared equilibria, Pareto-optimal sum. |
| Reproducibility | Master seed + seed count for confidence intervals. |
| Run | Live config preview, JSON download, **Run scenario** button. |

The sidebar lets you pre-fill the form from a shipped preset or upload
an existing config JSON.

### 🏆 Tournament

Stage a round-robin between any combination of LLM models and the
canonical baseline strategies. Adjust the rounds-per-match, discount
factor, payoff weights, and seed count. The page builds the config under
the hood, calls the engine in tournament mode (NC2 pair games), and
shows the per-pair results.

### 🧪 Experiment manifest

Build a multi-config, multi-seed experiment in one shot. Pick configs
from the shipped catalog or upload your own; choose a seed count and an
output directory; optionally override `nRounds` for the whole batch. The
runner writes one CSV per config (raw and seed-aggregated) plus a
`manifest_summary.json`.

### 📊 Results explorer

Browse every run on this machine in newest-first order. Each run shows:

* a metadata card with feature pills (ToM, Tournament, Mixed strategies, …);
* **Charts** tab — Plotly interactive figures: cooperation rate per
  round, score per round, welfare summary, equilibrium-rate
  distribution, Brier score per round (when beliefs were elicited),
  multi-seed mean ± 95% CI;
* **DataFrame** tab — the per-game DataFrame with a CSV download button;
* **Raw history** tab — collapsible per-game JSON;
* **Config** tab — the exact config that was run, downloadable as JSON.

## What's stored where

```
results/gui/
  YYYYMMDD_HHMMSS_<slug>/
    config.json          # exact config that ran
    raw_results.json     # engine output (factory.create_and_run_games)
    results.csv          # ResultsProcessor DataFrame
    results_aggregated.csv  # only when seedCount > 1

results/gui/experiments/<experiment_name>/
  <config_stem>_per_seed.csv
  <config_stem>_aggregated.csv
  manifest_summary.json
```

## Theming

Colours, fonts and the Streamlit chrome are tuned in
[`.streamlit/config.toml`](../.streamlit/config.toml) and
[`gui/static/style.css`](../gui/static/style.css). Drop a logo into
`gui/static/` and reference it from `app.py` if you want to brand the
hero card.

## Limits and roadmap

* The GUI calls the engine in-process. For long multi-seed tournaments,
  prefer the experiment-manifest CLI runner (`python -m src.experiment
  manifest.json`) and watch progress in the Results page.
* Streaming logs are buffered into `st.status` — they appear at the end
  of each run rather than line-by-line.
* No authentication / multi-tenancy. The GUI is built for local research
  use; if you need to expose it remotely, deploy behind an SSO proxy.
