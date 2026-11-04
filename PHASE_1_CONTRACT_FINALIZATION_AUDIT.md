# PHASE 1 — CONTRACT FINALIZATION AUDIT

**Document audited:** `PHASE_1_DATA_CONTRACT_v1.0.md` (Revision 5 → **Revision 5a**, amended in place)
**Audit date:** 2026-11-04
**Execution environment audited:** WSL development workstation, `/home/qili/projects/fx_monte_carlo`
**Nature:** Documentation-only finalization audit. No code, config, data, workflow, or schedule was changed.
**Status:** READY FOR HUMAN FREEZE (with one NOT VERIFIED item carried into Stage B as preflight)
**Stage B authorization:** **NOT GRANTED**

---

## 1. Files changed

| File | Change | Type |
|------|--------|------|
| `PHASE_1_DATA_CONTRACT_v1.0.md` | Revision 5 amended in place to Revision 5a | Documentation |
| `PHASE_1_CONTRACT_FINALIZATION_AUDIT.md` | This report (new) | Documentation |

Verified with `git status --short`: the **only** tracked modification is `PHASE_1_DATA_CONTRACT_v1.0.md`. All other listed entries are pre-existing untracked artifacts (`mc_results/*.json`, `api/2026/...`, `api/weekly/...`) that were **not** touched. No Git commit was made.

**No Revision 6 was created.** The document structure supported in-place amendment: a revision-log row was added and the revision marker in the title/version line was updated, leaving section numbering intact.

---

## 2. Sections amended

| § | Section | Amendment |
|---|---------|-----------|
| Title / header | — | Marked Revision 5a; added confirmed Stage B execution environment line |
| Revision Log | — | Added Rev 5a row describing the amendment |
| §0.1 | Verified workspace and evidence provenance | Re-verified `mc_results` as ordinary directory (2026-11-04, `test -L` false, `readlink -f` self, fs `ext2/ext3`); removed "execution machine not yet designated"; pointed Stage A root reference to new §0.2 |
| §0 (intro) | — | Added evidence-status legend (**CONFIRMED / VERIFIED / NOT VERIFIED**) |
| **§0.2 (new)** | **Execution environments and evidence boundaries** | E-1 WSL target designated; E-2 cloud Ubuntu explicitly separate; E-3 ordinary `mc_results`; E-4 Stage A is historical evidence only; no state transfer in either direction |
| §2 (example note) | Pair result schema | Market-timestamp example now flagged as contingent on PV-1 (NOT VERIFIED) |
| §5 (intro) | Timestamp semantics | Cross-reference to §5.1–§5.4 |
| §5.1 | Rules | Added **PV-1**: source-instant semantics **NOT VERIFIED** in E-1 (no project Python environment; `pandas`/`yfinance` absent) |
| **§5.2 (new)** | **Unified UTC policy for new system-generated time** | UTC mandatory for filenames, batch IDs, pair/batch timestamps, fetch timestamps, internal comparisons, ordering, audit timestamps, logs/metadata; timezone-aware; explicit `+00:00`; naive local prohibited |
| **§5.3 (new)** | **Legacy filename timezone interpretation (evidence-based)** | L-A (evidence-attributable) vs L-B (unknown provenance) classification table; UTC interpretation only for L-A; L-B = ordering key only |
| **§5.4 (new)** | **Market timestamps — no fabricated instants** | Session-date labels never converted to UTC instants; instant only where source semantics establish it |
| §8.3 | API ingestion | References §5.3 classification; L-A/L-B-aware ordering; `ordering_status: "incomparable"` must label L-B candidates as unverified; L-A and v1.0 share a UTC basis |
| §11 O-1 | Signed decisions | Removed stale "after resolving the `mc_results` symlink" obligation; replaced with E-1 actual-filesystem validation |
| §11.1 | Resolved findings | Added **R5a-1 … R5a-5** |
| **§11.4 (new)** | **Environment finalization** | ENV-1 … ENV-7 |
| **§11.5 (new)** | **Stage B boundary (NOT AUTHORIZED)** | SB-1 … SB-5 |
| §12 | Freeze checklist | Added Revision 5a checked items; human Freeze box remains **UNCHECKED**; Stage B authorization box remains **UNCHECKED** |

---

## 3. Decisions incorporated

1. **WSL is the Stage B target.** `/home/qili/projects/fx_monte_carlo` is designated (§0.2 E-1, §11.4 ENV-1). The prior "not yet designated" status is removed.
2. **Cloud Ubuntu is a separate environment.** `/home/ubuntu/projects/fx_monte_carlo` is explicitly **not** the same checkout (§0.2 E-2, ENV-2). Desktop-agent instructions that `mc_results` be treated as a symlink are rejected as cloud-only.
3. **Stage A is historical evidence.** Stage A findings do not prove WSL state and must be re-verified in E-1 before use (§0.2 E-4, ENV-3, §11.5 SB-2).
4. **Filesystem.** WSL `mc_results` is an ordinary directory — re-confirmed with a tool, not assumed (§0.1, §0.2 E-3, ENV-4, SB-3).
5. **Unified UTC policy.** All new timestamps and time-based operations use timezone-aware UTC with explicit `+00:00`; naive local values prohibited (§5.2, ENV-5).
6. **Evidence-based legacy timezone.** Legacy filenames are UTC only for L-A files. Re-confirmed from Git history that every committed `fx_monte_carlo.py` version generates the stamp with `datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")` (§5.3).
7. **No fabricated chronology.** L-B (unknown provenance) files are ordering keys only; no UTC-instant claim and no global chronological claim against v1.0 artifacts (§5.3, §8.3, ENV-6).
8. **No fabricated market instants.** Session-date labels are never converted to instants; otherwise the pair fails validation (§5.4, ENV-7).

---

## 4. Remaining contradictions

| # | Item | Resolution |
|---|------|-----------|
| C-1 | §11 O-1 required validating publication "after resolving the `mc_results` symlink", contradicting the confirmed ordinary directory. | **RESOLVED** — rewritten to require validation on the actual E-1 filesystem and to forbid introducing a symlink assumption. |
| C-2 | §0.1 said the Stage B machine "is not yet designated", contradicting the owner's confirmation. | **RESOLVED** — removed; target designated. |
| C-3 | §11 Stage B boundary notes contemplated a symlink checkout. | **RESOLVED** — now ordinary-directory only. |
| C-4 | §12 freeze condition required reconciling the `/home/ubuntu` root with `/home/qili`. | **RESOLVED** — reconciliation is now a stated fact (§0.2 E-2/E-4) rather than an open human task. |
| C-5 | Stage A report (`PHASE_1_STAGE_A_DISCOVERY.md`, `PHASE_1_STAGE_A_PROMPT.md`) still cites `/home/ubuntu/projects/fx_monte_carlo`. | **NOT A CONTRADICTION** — correct for its own environment; deliberately **not edited** (historical evidence; editing it would falsify provenance). §0.2 records its limited authority. |

**No unresolved contradictions remain in `PHASE_1_DATA_CONTRACT_v1.0.md`.**

---

## 5. Requirements still requiring human judgment

| # | Item | Why human judgment is needed | Status |
|---|------|------------------------------|--------|
| H-1 | **Human Freeze of the contract** | Only a human may freeze the contract. Box remains unchecked (§12). | OPEN — HUMAN |
| H-2 | **Stage B authorization** | Explicit authorization required after freeze (§12, §11.5 SB-5). | OPEN — HUMAN |
| H-3 | **Acceptance of NOT VERIFIED item PV-1 / SB-1** — whether the configured market-data source (`yfinance`, `yf_period` 1y/5y, `yf_interval` 1d/1wk) yields index values establishing real UTC instants. | Not verifiable in E-1 without the project's Python environment (`pandas`/`yfinance` not installed; installing packages is out of scope for a documentation task). If the source yields only session-date labels, §5.1/§7 require per-pair validation failure — a large behavioral consequence the owner must accept or resolve. **NOT VERIFIED.** | OPEN — HUMAN DECISION / Stage B PREFLIGHT |
| H-4 | **Acceptance of the L-A/L-B classification approach** for legacy artifacts | Requires confirming that attributing legacy files to committed generator versions is acceptable evidence practice. | OPEN — HUMAN |
| H-5 | **Legacy compatibility / API fallback behavior** acceptance | Carried from Revision 5; the human Freeze box requires it. | OPEN — HUMAN |

---

## 6. Consistency audit (Task C)

Confirmed **not weakened or removed**; all still present and self-consistent:

| Area | Section | Result |
|------|---------|--------|
| Batch/pair timestamp semantics (distinct capture points, pair ≤ batch) | §5.1, §7 V-7, §11.1 R5-1 | CONSISTENT |
| Count invariants (requested/unique/duplicate/successful/failed/not-attempted/executed/total) | §3.1, §11.1 P0-2, count edge rule | CONSISTENT |
| Configuration snapshot and fingerprint rules | §4.1–§4.3, P1-1, R4-2 | CONSISTENT |
| Schema and filename pairing | §8.1, §8.3, P0-3, R4-6 | CONSISTENT (now also provenance-aware) |
| Atomic no-replace publication | §11 O-1, P0-1, P1-2, R4-3, SB-3 | CONSISTENT (symlink clause corrected) |
| API ingestion eligibility (failed skipped, partial published, fallback) | §6, §8.3, §11 O-6, P1-5 | CONSISTENT |
| Legacy compatibility (`=X` keys, additive fields) | §2.2, §9.1, §9.6, §11 O-3 | CONSISTENT |
| Historical artifact preservation (no rewrite/migration) | §9.4, §10, §8.4 | CONSISTENT |
| Failed-batch handling (written but not ingested) | §6, §8.3, O-6 | CONSISTENT |
| Zero-pair preflight validation | §11 Stage B boundary notes (pre-existing) | CONSISTENT — untouched |

Additions are **additive and constraining** in direction (they add provenance and policy rules), except for the two stale symlink/designation clauses that were corrected to match the confirmed environment. No document item was relaxed.

---

## 7. Readiness assessment

**Contract status: READY FOR HUMAN FREEZE.**

All owner-confirmed decisions are incorporated, all internal contradictions are resolved, and existing requirements are unweakened. The single technical uncertainty (H-3 / PV-1) is explicitly marked **NOT VERIFIED** and converted into a mandatory Stage B preflight (SB-1) rather than being silently assumed — satisfying the instruction not to resolve open questions through assumption.

**Stage B authorization: NOT GRANTED.**

**No Stage B work of any kind was performed.** Documentation only.
