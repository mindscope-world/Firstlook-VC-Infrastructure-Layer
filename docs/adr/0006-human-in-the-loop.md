# 0006. AI output is proposed; people decide

Status: accepted · 2026-09-25

Extraction output is stored as `proposed` with a verbatim citation (message id plus character offsets). Items whose quote can't be found in the source text are dropped. Accepting an item is what writes to the graph or CRM: `introduced` edges for intros, a deal for a deal mention, an open task for a next step. The logic lives in SQL (`decide_extraction`, `er_decide`), so every service applies it the same way and it is audited.

Entity resolution auto-merges only on deterministic identifiers or on high similarity within the same organisation. Anything in between creates a provisional entity plus a review-queue item, so ingestion never waits on a human.
