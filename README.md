# TensorGrid

Market Intelligence for Bittensor Subnets.

- **Terminal live** — [/terminal](https://many77290-star.github.io/tensorgrid/terminal.html)
- **API JSON** — [/feeds/subnets.json](https://many77290-star.github.io/tensorgrid/feeds/subnets.json)
- **Docs** — [/docs](https://many77290-star.github.io/tensorgrid/docs.html)
- **Pricing** — [/pricing](https://many77290-star.github.io/tensorgrid/pricing.html)
- **Request Access** — [issues label `access`](https://github.com/many77290-star/tensorgrid/issues/new?labels=access)

## Data pipeline

- Source : CoinGecko `category=bittensor-subnets` (public, without API key).
- Refresh : every 15 minutes via GitHub Actions (`.github/workflows/refresh.yml`).
- Output : `feeds/subnets.json` (normalised universe), `feeds/meta.json` (API metadata), `feeds/history/snapshot-YYYYMMDD.json` (daily snapshot, retention 400 days).
- Signal : `beats_tao_30d` — true when `var30d > TAO.var30d`.

## Repository layout

```
index.html         Marketing page
terminal.html      Live terminal (reads feeds/ client-side)
docs.html          API documentation
pricing.html       Pricing tiers
contact.html       Access request (GitHub issue generator)
css/style.css      Design system
feeds/             Live JSON data (public API)
refresh_feed.py    Generator (no secrets, only public endpoints)
.github/workflows/refresh.yml  15-min auto-refresh
```

## Legal / disclaimers

- Market intelligence only, never financial advice.
- Data © CoinGecko, re-served under their public policy.
- TensorGrid Data License v1.0 applies to `feeds/*.json`. See `docs.html` for the exact terms.

## Contact

- Issues (`access` label) : access requests
- Issues (`support` label) : API questions
- Issues (`pro` label) : priority

GitHub : [many77290-star/tensorgrid](https://github.com/many77290-star/tensorgrid).
