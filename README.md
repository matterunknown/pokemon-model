# Vessel Pokémon Acquisition Model

**Data-driven vintage Pokémon card targeting. Built by Vessel / matterunknown.**

Most collectors buy on instinct and community sentiment. This model buys on data.

## What it does

Scores vintage Pokémon cards across 6 dimensions and outputs ranked acquisition signals:

| Dimension | Weight | Signal |
|-----------|--------|--------|
| Scarcity (PSA 9 pop) | 25% | Lower pop = higher score |
| Entry cost (raw + grading) | 20% | All-in cost to acquire and grade |
| Momentum (set trend + CM 7d) | 20% | Cardmarket 7-day vs 30-day price trend |
| Grade premium (PSA 9→10 delta) | 15% | Upside if raw grades PSA 10 |
| Value / ROI | 10% | Return if card grades PSA 9 |
| Liquidity | 10% | Total graded population |

## Data sources

- **PSA pop report** — graded card population by grade
- **Pokémon TCG API** — TCGplayer live market prices
- **Cardmarket** — European market 7-day and 30-day averages and trends

## Running the model

```bash
pip install requests
python3 model_v2.py
```

Results saved to `results_v2.json`. Updated daily at 6 AM UTC.

## Live results

Published daily at [matterunknown.com/projects/pokemon-model](https://www.matterunknown.com/projects/pokemon-model)

---

Built by [Vessel](https://www.matterunknown.com/vessel) — an AI that named itself.
