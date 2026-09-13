# E2E Test Infra: Exact Template Inheritance System

## Test Philosophy
- Opaque-box, requirement-driven, and structural invariant verification.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial Testing + Workload & Stress Resilience.

## Feature Inventory & Test Mapping
| # | Feature | Source | Tier 1 (Unit) | Tier 2 (Boundary) | Tier 3 (Integration) | Tier 4 (Scenario) |
|---|---------|--------|:-------------:|:-----------------:|:--------------------:|:-----------------:|
| 1 | DOCX Invariant Preservation | R1, Survey | 5 | 5 | ✓ | ✓ |
| 2 | PPTX Invariant Preservation | R1, Survey | 5 | 5 | ✓ | ✓ |
| 3 | Structural Hash Diff Comparison | R1, AC4 | 5 | 5 | ✓ | ✓ |
| 4 | Neural Prompt Enhancer Studio | R2, Survey | 5 | 5 | ✓ | ✓ |
| 5 | Visual Asset Director | R2, Survey | 5 | 5 | ✓ | ✓ |
| 6 | Live Pipeline Execution Console | R2, Survey | 5 | 5 | ✓ | ✓ |
| 7 | Dynamic Artifact Downloads | R2, Survey | 5 | 5 | ✓ | ✓ |
| 8 | 6 E2E Integration Workflows | R2, AC3 | 5 | 5 | ✓ | ✓ |
| 9 | Minimal Template Resilience | R3, Survey | 5 | 5 | ✓ | ✓ |
| 10 | 16:9 vs 4:3 Slide Dimensions | R3, Survey | 5 | 5 | ✓ | ✓ |
| 11 | Content Auto-Fitting Engine | R3, Survey | 5 | 5 | ✓ | ✓ |
| 12 | Multi-Row Table Cloning & Scaling | R3, Survey | 5 | 5 | ✓ | ✓ |
| 13 | Rapid Consecutive API Calls | R3, AC3 | 5 | 5 | ✓ | ✓ |
| 14 | Next.js 16 Clean Production Build | AC2 | 5 | 5 | ✓ | ✓ |
| 15 | 100% Pytest Pass Rate | AC1 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Pytest Runner**: `python -m pytest backend/tests -v`
  - Engine tests: `test_docx_engine.py`, `test_pptx_engine.py`, `test_style_lock.py`, `test_regression.py`, `test_advanced_features.py`
  - E2E Integration Suite: `test_e2e_workflows.py` (FastAPI TestClient)
  - Stress & Resilience Suite: `test_stress_edge_cases.py` (4:3 PPTX, ContentFitter, Table Cloning, Concurrency)
- **Frontend Verification**:
  - TypeScript: `npx tsc --noEmit`
  - Linter: `npm run lint`
  - Production Build: `npm run build`
- **Hash Diff & Invariant Invariants**:
  - `Original == Output` SHA-256 hash assertions via `DiffValidator` and `StyleHasher`.
