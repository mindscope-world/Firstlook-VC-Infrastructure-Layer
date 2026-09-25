# 0007. Deal sourcing: sources, two-stage ranking, learning from votes

Status: accepted · 2026-09-25

**Context.** Phase 1b ranks companies against each fund's thesis before competitors see them. The first licensed data vendor is not chosen yet (plan §12, question 3).

**Decision.**
- **Theses are versioned.** Editing a thesis creates a new version. Scores and votes point at the version they were made against, so history stays interpretable.
- **Sources** (`services/sourcing/sources`):
  - Licensed vendor: a `VendorSource` interface (`search`, `lookup`). A sandbox implementation reads a JSON export shaped like a typical vendor's; the real vendor is one new class.
  - GitHub organisation activity.
  - Greenhouse and Lever public job boards: open roles, and hiring velocity from their history.
  - News RSS: mentions of tracked companies, plus funding-announcement headlines as a discovery source.
  - Company-registry extracts, starting with Kenya BRS. It has no open bulk API, so data arrives as CSV.
- **Profiles go through entity resolution.** A startup the team already emails is enriched in place, not duplicated. Licensed vendors may overwrite profile fields. Registries may overwrite legal facts only (country, incorporation year). Other sources only fill blanks.
- **Signals** are daily observations in Postgres (`signal_observations`), idempotent per company, signal, source, day and URL. They are mirrored to ClickHouse (`company_signals`) for analytics when `CLICKHOUSE_URL` is set. A ClickHouse outage delays analytics, not ranking.
- **Stage 1** has hard filters: stage two or more steps away, or a country outside the thesis geographies. It then scores seven explainable features in [0, 1]: sector, stage, geo, cheque, text, momentum and warm. Cold start uses fixed weights (`rules-v1`). Once a thesis has 30 or more votes covering both directions, a logistic model is fitted on the same features. The plan's XGBoost ranker takes over at about 500 labels; the `Ranker` protocol is the seam, and XGBoost isn't a dependency until then.
- **Stage 2** is an LLM re-rank of the top N (default 20) over numbered facts, each tied to its source. The model must cite fact ids, and citations that don't match a presented fact are dropped. Third-party text is passed as data. Final score = 0.4 × stage 1 + 0.6 × stage 2 for re-ranked companies, and stage 1 for the rest.
- **Scheduling.** Temporal runs sourcing daily at 04:00 UTC (collect, then score) and the digest on Mondays. The API triggers re-ranks and retraining through the outbox (`sourcing.requested`, `sourcing.feedback`).

**Consequences.** Until the vendor contract is signed, discovery depends on news and registries plus the sandbox data. The ranker learns only from votes cast in the feed. Evals for ranking quality (NDCG against partner judgements) are Phase 1d.
