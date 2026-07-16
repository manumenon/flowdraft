# FlowDraft E2E Test Suite Infrastructure (Milestone 1)

This document describes the End-to-End (E2E) testing infrastructure for the **Interactive Architecture Diagram Animator with Video Export** and maps the requirements from `ORIGINAL_REQUEST.md` to specific E2E test cases across four testing tiers.

---

## 1. Test Directory Layout
The proposed E2E test suite will be structured as follows:

```text
tests/e2e/
├── __init__.py                  # Package initialization
├── mock_services.py             # Mock services environment (HTTP servers, Worker thread)
└── test_e2e_suite.py            # Main E2E Test Suite containing all 50 tests
```

---

## 2. Test Environment Requirements & Dependencies
To run the full E2E test suite, the following must be installed and configured on the host/runner:
1. **Python 3.10+** (with packages specified in `requirements.txt`: FastAPI, pytest, playwright, sqlalchemy, psycopg2-binary, redis, boto3)
2. **Node.js 18+** & **npm** (for Frontend packages and Playwright browser binaries)
3. **Playwright** (`playwright install --with-deps chromium`)
4. **FFmpeg** (accessible in system PATH or worker container for video encoding)
5. **Docker & Docker Compose** (for multi-container orchestration tests)
6. **MinIO Client** or python SDK (for object storage verification)

---

## 3. Requirement Mapping & E2E Test Catalog

### Requirement R1. Frontend Interactive Canvas & Layout Engine
*Focuses on user interaction, XYFlow component rendering, ELKjs Web Worker layout calculation, GSAP telemetry animations, and the read-only `/render-box` viewer.*

#### Tier 1: Feature Coverage (R1)
1. **`test_r1_node_edge_creation`**: Verifies that custom React DOM nodes (cards, inputs, panels, diamonds) and SVG edges are dynamically added, positioned, and rendered in the editor viewport.
2. **`test_r1_elkjs_web_worker_layout`**: Verifies that triggering the layout engine offloads computation to a background Web Worker and resolves node coordinates without blocking the main DOM thread.
3. **`test_r1_gsap_telemetry_flow`**: Verifies that GSAP MotionPathPlugin animates packets smoothly along SVG curve paths.
4. **`test_r1_render_box_viewer_route`**: Verifies that the `/render-box` viewer route loads cleanly and displays only the pure animated architecture diagram, hiding gridlines, sidebars, and editing handles.
5. **`test_r1_dynamic_coordinate_sizing`**: Verifies that bounding boxes adjust layout offsets and sizes dynamically based on text changes in node components.

#### Tier 2: Edge & Boundary (R1)
6. **`test_r1_extreme_coordinates_scaling`**: Validates canvas behavior and ELKjs layout resolution when coordinates are extremely large, zero, or negative.
7. **`test_r1_text_overflow_wrapping_cjk`**: Validates that node components automatically wrap and scale long CJK and English titles without overlapping icons, borders, or exit ports.
8. **`test_r1_worker_failure_fallback`**: Verifies that if the Web Worker crashes or fails to respond, the frontend falls back to a basic grid layout gracefully and reports an error state without locking the UI.
9. **`test_r1_gsap_clock_control`**: Verifies that the global window exposed by the frontend allows programmatic pausing and stepping of the GSAP animation timeline (`window.step(16.67)`).
10. **`test_r1_high_density_graph_rendering`**: Evaluates frontend performance and layout collision resolution under stress with a high density of nodes (100+ nodes, 200+ connections).

---

### Requirement R2. Backend Orchestration & Message Broker
*Focuses on FastAPI endpoints, database persistence, authentication, rate limiting, and BullMQ Redis job queuing.*

#### Tier 1: Feature Coverage (R2)
11. **`test_r2_spec_db_storage`**: Verifies that diagram specs can be successfully saved to and retrieved from the PostgreSQL database using API gateway endpoints.
12. **`test_r2_gateway_auth`**: Verifies that authentication is enforced on API endpoints (e.g. JWT tokens required for editing/saving/exporting).
13. **`test_r2_export_job_creation`**: Verifies that POSTing to `/api/export` returns a `202 Accepted` status with a unique `job_id` and adds the job to the Redis queue.
14. **`test_r2_job_status_tracking`**: Verifies that database job records transition correctly through standard states: `queued` -> `processing` -> `completed` / `failed`.
15. **`test_r2_download_url_generation`**: Verifies that GET `/api/export/{job_id}` returns a status of `completed` along with a valid download link to the stored media asset in MinIO.

#### Tier 2: Edge & Boundary (R2)
16. **`test_r2_malformed_spec_schema_validation`**: Verifies that the API gateway runs schema checks and rejects invalid schemas with standard HTTP 422 errors and specific error details.
17. **`test_r2_broker_disconnect_recovery`**: Verifies backend resilience and API response states when the Redis message broker is temporarily offline.
18. **`test_r2_export_concurrency_stress`**: Verifies that the gateway handles 50+ concurrent export requests without dropping requests, database deadlocks, or duplicate job IDs.
19. **`test_r2_db_constraint_integrity`**: Verifies that foreign keys and constraints restrict operations that would cause inconsistent states (e.g., deleting a diagram while it has an active export job).
20. **`test_r2_rate_limiting`**: Verifies that flooding the export API gateway endpoints triggers a `429 Too Many Requests` response.

---

### Requirement R3. Headless Rendering & Encoding Worker
*Focuses on Playwright-based headless rendering, clock hooking, PNG frame capture, FFmpeg MP4/GIF compilation, and MinIO storage uploads.*

#### Tier 1: Feature Coverage (R3)
21. **`test_r3_playwright_page_loading`**: Verifies the worker successfully launches a headless Chromium instance and loads the `/render-box` viewer.
22. **`test_r3_deterministic_frame_capture`**: Verifies that Playwright correctly hooks the browser clock and captures frames sequentially in exact deterministic time increments (e.g. 16.67ms).
23. **`test_r3_ffmpeg_mp4_compilation`**: Verifies that FFmpeg compiles captured PNG frames into a valid, playable H.264 MP4 video.
24. **`test_r3_ffmpeg_optimized_gif`**: Verifies that FFmpeg compiles PNG frames into a 256-color optimized GIF using double-pass `palettegen` / `paletteuse` filters.
25. **`test_r3_minio_upload_completion`**: Verifies that the worker successfully uploads the compiled MP4/GIF file to MinIO and updates the job status to `completed`.

#### Tier 2: Edge & Boundary (R3)
26. **`test_r3_asset_loading_timeout`**: Verifies that the worker handles slow network assets (fonts/icons) or page loading timeouts by failing the job gracefully instead of hanging indefinitely.
27. **`test_r3_zero_duration_export`**: Verifies that rendering a diagram with zero-duration animation resolves to a single-frame static screenshot export or fails cleanly.
28. **`test_r3_minio_offline_recovery`**: Verifies that if MinIO is offline, the worker logs the upload failure, retries with backoff, and ultimately transitions the database job to `failed`.
29. **`test_r3_playwright_crash_recovery`**: Verifies that if the Playwright browser process crashes mid-capture, the worker terminates the process, marks the job `failed`, and frees system resources.
30. **`test_r3_worker_concurrency_limit`**: Verifies that the worker respects concurrency settings, processing only N jobs in parallel and keeping others in the queue.

---

### Requirement R4. Multi-Container Docker Architecture
*Focuses on docker-compose orchestration, cross-container networking, persistent volumes, and startup dependencies.*

#### Tier 1: Feature Coverage (R4)
31. **`test_r4_docker_compose_up`**: Verifies that all 6 services (frontend, api, db, redis, minio, worker) successfully start up using `docker compose up -d`.
32. **`test_r4_cross_container_dns`**: Verifies that containers resolve each other using their Docker DNS names (e.g., API gateway connects to database using host `db`).
33. **`test_r4_db_volume_persistence`**: Verifies that database records survive a complete container teardown (`docker compose down`) and spin-up cycle.
34. **`test_r4_minio_bucket_auto_init`**: Verifies that the `exports` bucket is created automatically upon MinIO container startup without requiring manual UI configuration.
35. **`test_r4_docker_log_aggregation`**: Verifies that standard output/error from all services is redirected to Docker logs for centralized troubleshooting.

#### Tier 2: Edge & Boundary (R4)
36. **`test_r4_dependency_startup_delay`**: Verifies that if the PostgreSQL database or Redis takes 10 seconds to start, the API and worker containers wait and retry instead of crashing.
37. **`test_r4_healthcheck_remediation`**: Verifies that container healthchecks flag containers as unhealthy when services are unresponsive (e.g., killing Redis process internally).
38. **`test_r4_minio_disk_full`**: Verifies how the worker and storage container handle a disk full condition during upload.
39. **`test_r4_abrupt_shutdown_recovery`**: Verifies that the system recovers cleanly from a sudden power-off/SIGKILL of containers, cleaning up active/stale locks upon restart.
40. **`test_r4_custom_port_mapping`**: Verifies that overriding default ports in the docker compose file (e.g. mapping API gateway to host port 8080 instead of 8000) does not break internal routing.

---

### Tier 3: Pairwise Combinations
*Verifies the interface contracts between two or more services. These ensure that integrated systems communicate correctly.*

41. **`test_comb_frontend_api_diagram_sync` (R1 + R2)**: Verifies that drawing a diagram on the frontend canvas and clicking "Save" calls the API gateway, persists the spec in PostgreSQL, and reloads it dynamically.
42. **`test_comb_gateway_queue_worker_flow` (R2 + R3)**: Verifies that requesting an export via `/api/export` creates a database record, queues a Redis job, and causes the Playwright worker to pull the job and transition the state.
43. **`test_comb_worker_s3_gateway_download` (R3 + R2)**: Verifies that when the worker uploads a completed animation to MinIO, the API gateway serves a valid, authenticated URL to download the asset.
44. **`test_comb_render_box_clock_hooking` (R1 + R3)**: Verifies that Playwright's clock mocking hooks correctly freeze the React/GSAP frontend clock in the browser window and allow stepwise rendering.
45. **`test_comb_docker_network_db_load` (R4 + R2)**: Verifies that the database container handles high-load operations sent from the API gateway over the docker internal bridge network.

---

### Tier 4: Real-world Application Scenarios
*End-to-end user journeys that mimic production workloads and verify that the output media is fully generated.*

46. **`test_scenario_ecommerce_order_processing`**:
   - *Workflow*: "Cart Checkout" -> "Payment Gateway" -> "Inventory System" -> "Shipping Provider". Includes a loop-back on payment failure via a decision diamond.
   - *Validation*: Verifies that the compiled GIF/MP4 animation shows the telemetry packet moving through the nodes, branching at the diamond, and looping back.
47. **`test_scenario_kubernetes_traffic_burst`**:
   - *Workflow*: "API Gateway" routing traffic to "User Service" and "Order Service" in parallel.
   - *Validation*: Verifies that parallel offset connections are correctly rendered without overlapping lines, and multiple GSAP packets animate concurrently.
48. **`test_scenario_kafka_data_pipeline`**:
   - *Workflow*: "IoT Sensors" -> "Kafka Broker" (custom orange style) -> "Spark Streaming" -> "PostgreSQL DB" (custom blue style).
   - *Validation*: Verifies that the generated video applies the correct theme and stroke styling, and the duration matches the configured timing.
49. **`test_scenario_ml_training_loop`**:
   - *Workflow*: "Data Collector" -> "Preprocessing" -> "Model Trainer" -> "Evaluation" (decision diamond) -> "Deploy" or loop back to "Model Trainer".
   - *Validation*: Verifies that long CJK labels on nodes and decision diamonds do not wrap awkwardly or overlap boundaries in the final exported GIF.
50. **`test_scenario_oauth2_auth_grant`**:
   - *Workflow*: Interactive flow between "User Browser", "Client App", "Auth Server", and "Resource Server" across 4 vertical swimlanes.
   - *Validation*: Verifies complex cross-lane connector paths, ensuring ELKjs computes coordinate layouts that avoid overlapping node panels.

---

## 4. Test Execution & Implementation Status

All 50 test cases listed in this catalog have been fully and genuinely implemented within `tests/e2e/test_e2e_suite.py` with zero facade stubs. All tests successfully run and pass.

### Run All Tests
```bash
python -m unittest tests.e2e.test_e2e_suite
```
