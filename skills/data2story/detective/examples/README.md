# Detective examples — dataset-specific, NOT general-purpose helpers

The scripts in this folder are **worked examples** kept for reference. They are
**dataset-specific, not general-purpose fetchers** — each one hardcodes the
domain it was built for, so **do not invoke them on unrelated datasets**.

Treat them as patterns to imitate when a new dataset needs a similar bespoke
augmentation step, not as tools to run as-is.

| Script | Hardcoded to | What it does |
|---|---|---|
| `fetch_venue_weather.py` | FIFA World Cup 2026 (16 named venues, Jun 11 – Jul 19 window) | Joins the 16 official FIFA venue names to real stadium coordinates and pulls historical Open-Meteo climate for the tournament window into a CSV the Analyst joins on `stadium`. |
| `fetch_hle_images.py` | the gated `cais/hle` HuggingFace dataset (Humanity's Last Exam) | Picks diverse image-bearing questions from a local `hle_questions.csv`, maps each row to the HF dataset offset, and decodes the inline base64 question images to disk. Requires an HF token with access to the gated dataset. |

## What to use instead (the general-purpose, dataset-agnostic fetchers)

For any normal run, use the reusable helpers, which take their subjects as
arguments and work on any topic:

- `../scripts/fetch_images.py` — Wikimedia Commons photos by Wikidata QID / CSV.
- `../scripts/fetch_flags.py` — national flags by country name.
- `../scripts/fetch_logos.py` — company / org logos by name.
- `../scripts/fetch_openverse.py` — keyword image search across the Openverse
  aggregator (Flickr-CC, museums, Wikimedia, …), license + attribution captured.
- `../../scout/scripts/fetch_music.py` — license-clean audio (BGM) candidates.
