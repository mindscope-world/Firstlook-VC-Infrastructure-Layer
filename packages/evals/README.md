# Evals

Golden sets and scoring for the AI and matching components. The suites run the production code paths: the same parser, prompt and validation as the services.

```bash
make evals                 # golden answers, no model calls (CI runs this on every PR)
make evals-live            # live model through the gateway (needs `make dev` + ANTHROPIC_API_KEY)
make evals SUITES="er -v"  # one suite, per-case detail
```

| Suite | What it scores | Golden set |
|---|---|---|
| `er` | Entity resolution: pairwise precision/recall of people and companies, how much of the remaining recall the review queue recovers | `golden/er.yaml`: about 80 mentions, with traps (relatives and colleagues sharing a surname and domain, namesakes at other companies, swapped name order) |
| `extraction` | Intros, next steps and deal mentions: P/R/F1 per kind, field accuracy, citation validity, prompt-injection resistance | Synthetic fund emails (`packages/fixtures/fund.py`) plus `golden/extraction_redteam.yaml` |
| `ranking` | Sourcing: NDCG@5/10 of stage 1 (rules) and of the final order after the LLM re-rank; relevant companies never hard-filtered | `golden/ranking.yaml`: one thesis, 15 companies graded 0–3 |
| `factsheet` | Deck/model → fact sheet: field accuracy and recall, hallucinated fields, metric and team P/R, numbers readable from their quote, injection resistance | `packages/fixtures/documents.py`: PDF deck, PPTX deck with an injection attempt, XLSX model |

**Modes.** In golden mode the LLM is replaced by the golden answers. Entity resolution and stage-1 ranking involve no model, so they are scored for real. For the model suites, golden mode checks that the harness and golden sets agree; a model is scored only in `--llm gateway` mode. Gateway mode refuses to report if the gateway answers with its offline stand-in.

**Gates.** `thresholds.yaml` holds the minimums: `always` gates apply in every mode, `live` gates only to live runs. A failure exits 1. `.github/workflows/evals-live.yml` runs the live suites on PRs that touch prompts, schemas, model routing or golden sets. Reports go to `packages/evals/reports/` (gitignored).

**Not yet covered.** Memo citation coverage (memo drafting is not built). Design-partner samples join the golden sets only with consent and once Phase 4 provides somewhere secure to keep them.
