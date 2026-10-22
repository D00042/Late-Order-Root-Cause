# KPI Claim Checker

Does an LLM's written commentary agree with the numbers it was given?

I built an AI commentary feature for a finance reporting platform. Reviewing its saved outputs, I saw the model quote the same KPI differently across runs (a cash ratio of 0.30, 0.32 and 0.27 for one period). This project is the check I wish that platform had had: it recomputes each KPI from source inputs, finds the figures quoted in the text, and flags every mismatch.

## Run it

```bash
python validate.py        # prints a verdict per sentence, writes index.html and results.json
```

Exit code is 1 when a figure is contradicted, so it can gate a CI job. No dependencies beyond Python 3.8+.

## How it works

1. `data/inputs.json` holds source inputs (revenue, cash, equity…). KPIs are computed from them with documented formulas in `SPEC`.
2. `data/commentary.txt` is the model output to audit.
3. Each sentence is matched to a KPI by keyword, then the first number in the right unit (ratio, %, EUR) is compared with the computed value using a per-unit tolerance.
4. Verdicts: **verified**, **contradicted**, or **unverifiable** (no KPI defined, or no figure quoted).

## Data

All figures are invented. No real company data is included.

## Known limits and next steps

- Keyword matching misses paraphrases. Next: use a model to extract claims, then verify them with the same deterministic code.
- Add `pytest` cases for tolerance edges and sign handling.
- Run over repeated generations to measure how often each KPI is misquoted.

## Design tokens (shared across my portfolio projects)

| Token | Value |
| --- | --- |
| Deep blue (ink) | `#0B2C5F` |
| Cream (background) | `#F5EFDF` |
| Paper | `#FBF8EF` |
| Mid blue | `#1F4A8C` |
| Muted blue-grey | `#5A6A86` |
| Flag red | `#A8261C` |
| Fonts | Newsreader (text), Public Sans (labels and tables) |
