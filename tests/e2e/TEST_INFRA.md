# FlowDraft E2E Test Suite Infrastructure

This document describes the End-to-End (E2E) testing infrastructure for the FlowDraft rendering engine.

## Test Directory Layout
The E2E tests are located in `tests/e2e` and structured into four tiers.

- `tests/e2e/__init__.py` - Package initialization.
- `tests/e2e/test_e2e_suite.py` - Complete test suite containing Tiers 1-4.
- `tests/e2e/TEST_INFRA.md` - Infrastructure documentation.
- `tests/e2e/TEST_READY.md` - Test readiness and validation report.

## Verification Tiers
The E2E test suite validates the system across four tiers:

### Tier 1: Feature Coverage
Verifies the four primary requirements (R1, R2, R3, R4) with at least 5 test cases per feature:
- **Feature R1: Rebrand and Remove Old Branding** (CLI/spec rebrand flags, customized signatures, no old branding references).
- **Feature R2: Auto-scaling Grid Layout & Collision Prevention** (Coordinate validation, non-overlapping bounding boxes, scaling ratios).
- **Feature R3: High-Resolution SVG and Vector Output** (SVG file creation, XML parsing validation, vector shape/text mapping).
- **Feature R4: Exhaustive Regression Testing** (PNG/GIF canvas dimension checks, FPS validation, motion detection, contract validations).

### Tier 2: Boundary & Corner Cases
Verifies the rendering engine under extreme or edge conditions (at least 5 cases per feature):
- **Feature R1 Boundary Cases**: Empty signatures, partial signature matches, multilingual rebranding, special characters.
- **Feature R2 Boundary Cases**: Tiny/Huge canvas sizes, skewed aspect ratios (very wide/tall), missing canvas block.
- **Feature R3 Boundary Cases**: CJK characters in SVG, empty labels, dense shapes, custom themes, SVG overrides.
- **Feature R4 Boundary Cases**: Single-frame GIFs, zero-frame fallbacks, extreme FPS, empty inputs or core cards.

### Tier 3: Cross-feature Combinations
Verifies pairwise combinations of features, ensuring they interact correctly:
- Rebranding + Auto-scaling.
- Rebranding + SVG Output.
- Auto-scaling + SVG Output.
- Rebranding + Auto-scaling + SVG Output + 1 Frame.
- Text Fitting + Auto-scaling.

### Tier 4: Real-World Application Scenarios
Executes the rendering engine against complex, realistic workloads:
1. `test_scenario_1_microservices_auth_flow`
2. `test_scenario_2_data_ingestion_pipeline`
3. `test_scenario_3_ml_training_pipeline`
4. `test_scenario_4_e_commerce_order_processing`
5. `test_scenario_5_devops_ci_cd_pipeline`

## Execution Command
To execute the E2E test suite, run the following command in the workspace root:

```bash
python -m unittest discover -s tests/e2e
```
