# 0002. Build local-first; choose a cloud in Phase 4

Status: accepted · 2026-09-25

**Context.** The plan defers cloud deployment to Phase 4. The app must not quietly depend on one provider in the meantime.

**Decision.** Everything runs with `make dev` on the compose stack. Every stateful dependency is either an open-source component that every cloud offers as a managed service, or sits behind an adapter in `firstlook_core.adapters`: object storage, event bus, KMS, OCR, mail. Each adapter has a local implementation and contract tests (`packages/pycore/tests/test_adapter_contracts.py`) that future cloud implementations must also pass. Services are 12-factor: config from the environment, logs to stdout, a container image each (`infra/docker/`).

**Consequences.** Phase 4 adds cloud adapter implementations and infrastructure code, not application changes. Real design-partner data can't be processed until then (plan §2).
