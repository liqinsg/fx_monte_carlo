# PHASE 1 — HUMAN DECISION RECORD

**Project:** FX Monte Carlo / Fibonacci Shadow Observation System  
**Workspace:** `/home/qili/projects/fx_monte_carlo` (WSL)  
**Contract:** `PHASE_1_DATA_CONTRACT_v1.0.md`  
**Decision record:** H-4 / H-5  
**Recorded:** 2026-11-04 07:09 UTC  
**Execution mode:** Documentation-only

## 1. Decision context

H-4 and H-5 were the remaining policy decisions requested for the Phase 1 contract. This record captures their acceptance and integration into Revision 5b. It does not grant Contract Freeze, PV-1 acceptance, or Stage B authorization.

## 2. H-4 — Historical legacy artifact timestamp classification

**Status: DECIDED — ACCEPTED.** Accept the L-A/L-B dual classification in §5.3.

- **L-A:** A specific historical artifact may use its `YYYYMMDD_HHMM` filename value as a UTC generation-time label only when reliable provenance ties that artifact to an exact generator version whose UTC filename behavior is established. The existence of a similar committed code version alone is not sufficient.
- **L-B:** If artifact-specific provenance is unknown or insufficient, the filename value is only a deterministic discovery-order/tie-breaking key. It is not a verified UTC instant and cannot support an unsupported global chronology claim against v1.0 or L-A artifacts.

**Rationale:** Tracked historical generator code can establish how that code formed filenames, but it cannot by itself prove which code generated an individual artifact. This policy preserves usable evidence without overstating timestamp certainty.

**Operational consequences:** Stage B must classify each legacy artifact before making recency claims, preserve the evidence basis for L-A attribution in logs/metadata already required by the contract, treat unclassified artifacts as L-B, and never rewrite historical artifacts. Section §8.3 exposes incomparable time bases under its existing ordering contract.

## 3. H-5 — Legacy eligibility and API fallback

**Status: DECIDED — ACCEPTED.** Accept strict Legacy/v1.0 separation and the contract's transparent eligibility and fallback policy.

- Legacy filename plus absent `schema_version` is evaluated only under Legacy rules: strict filename, parseable JSON, matching timeframe identity, and usable `results`.
- v1.0 filename plus supported explicit schema version is evaluated under v1.0 rules. Filename/schema mismatches and unsupported explicit schema versions are rejected and logged.
- Legacy artifacts do not receive fabricated v1.0 metadata or v1.0 validation status. Original legacy `=X` result keys are preserved; `_fib` artifacts remain excluded and only the authorized `mc_results/` directory is scanned.
- Malformed, unsupported, or failed artifacts do not silently become eligible. A valid older eligible artifact may remain published after a newer candidate is rejected, provided the existing `latest_seen`, `latest_eligible`, and published identity/fallback-reason distinctions remain visible.

**Rationale:** Preserve usable historical data while making eligibility, rejection, and fallback reviewable. Do not disguise older fallback data as the newest generated result.

**Operational consequences:** Apply existing §8 rules and metadata/logging contract. H-5 adds no API response fields, runtime behavior, historical migration, or cleanup authorization.

## 4. Explicit non-decisions

- **H-1: OPEN — HUMAN FREEZE NOT GRANTED.** This record does not freeze the contract.
- **H-2: OPEN — STAGE B AUTHORIZATION NOT GRANTED.** No implementation or production execution is authorized.
- **H-3: OPEN — PV-1 ACCEPTANCE NOT GRANTED.** Source timestamp semantics and the stated PV-1 limitations remain unresolved for decision purposes.
- No algorithm, configuration, data, API, scheduler, workflow, or historical artifact change is approved.
- No new API response field or runtime behavior is introduced by this record.

## 5. Contract integration

Revision 5b updates:

- §5.3 — L-A/L-B classification now requires artifact-specific provenance for L-A.
- §8.3 — Legacy eligibility, schema/filename matching, logged rejection, and transparent fallback explicitly reference H-4/H-5.
- §11.6 — formal H-4/H-5 decision entries and operational consequences.
- §12 — records H-4/H-5 as accepted while leaving Freeze and Stage B authorization unchecked.

The existing Revision 5a PV-1 boundary remains in §5.1 and §11.5 SB-1. Supporting evidence: `PHASE_1_PV1_EVIDENCE_REPORT.md` and `PHASE_1_PV1_WEEKLY_SEMANTICS_ADDENDUM.md`. These documents retain their NOT VERIFIED limitations, including source-version/reproducibility gaps, timezone stripping in the sampled `yf.download` path, weekly boundary/OHLC interpretation limits, and lack of proof for all historical index behavior.

## 6. Final status

- H-4: **DECIDED — ACCEPTED**
- H-5: **DECIDED — ACCEPTED**
- H-1: **OPEN — HUMAN FREEZE NOT GRANTED**
- H-2: **OPEN — STAGE B AUTHORIZATION NOT GRANTED**
- H-3: **OPEN — PV-1 ACCEPTANCE NOT GRANTED**

**H-4/H-5 DECISION RECORDING COMPLETE — CONTRACT FREEZE PENDING HUMAN REVIEW.**

No Git-mutating operation was performed. No production code, configuration, data, API artifact, workflow, scheduler, or PV-1 evidence document was modified. No production entrypoint or data-generation process was executed.
