import type { FlowSpec } from '../types/spec';

// Deliberately much bigger than defaultSpec.ts (27 elements / 23 connections /
// 1 level of panel nesting): ~67 elements, 62 connections, 3 levels of panel
// nesting, mixing row/column/flow/grid panel layouts (including flow/grid at
// a nested depth, not just top-level), panels with badges/subtitles/footers,
// dense cross-panel connections, and multiple feedback/cyclic edges. Extends
// defaultSpec's "Cognitive Memory Mesh" architecture-diagram vocabulary
// (same element types: panel/card/diamond/input, same realistic
// infra-component content) at a scale meant to stress-test layoutCore.ts and
// the quality-check suite — see frontend/src/quality/checkLayoutQuality.test.ts.
export const stressSpec: FlowSpec = {
  "canvas": {
    "width": 2400,
    "height": 1800,
    "fps": 30,
    "frames": 90
  },
  "hand": false,
  "theme": "dark",
  "signature": "@FlowDraft",
  "title": {
    "prefix": "Architecture of the",
    "highlight": "Federated Cognitive Memory Mesh",
    "subtitle": "Multi-Region Agent Platform at Scale"
  },
  "elements": [
    {
      "id": "ingest_panel",
      "type": "panel",
      "title": "Federated Telemetry & Knowledge Ingest",
      "badge": "streaming",
      "subtitle": "(Real-time multi-source capture)",
      "layout": { "direction": "column", "gap": 18, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#22c86f", "strokeWidth": 2, "cornerRadius": 16 },
      "children": [
        { "id": "ing_vec", "type": "input", "title": "Vector Streams", "icon": "database", "style": { "color": "#3b82f6", "strokeWidth": 2.5, "cornerRadius": 8 } },
        { "id": "ing_ctx", "type": "input", "title": "LLM Context Caches", "icon": "cpu", "style": { "color": "#a855f7", "strokeWidth": 2.5, "cornerRadius": 8 } },
        { "id": "ing_git", "type": "input", "title": "GitOps State", "icon": "git-branch", "style": { "color": "#10b981", "strokeWidth": 2.5, "cornerRadius": 8 } },
        { "id": "ing_usr", "type": "input", "title": "User Sessions", "icon": "users", "style": { "color": "#f59e0b", "strokeWidth": 2.5, "cornerRadius": 8 } },
        { "id": "ing_graph", "type": "input", "title": "Graph DB Nodes", "icon": "share-2", "style": { "color": "#ec4899", "strokeWidth": 2.5, "cornerRadius": 8 } },
        { "id": "ing_audio", "type": "input", "title": "Audio Transcripts", "icon": "radio", "style": { "color": "#06b6d4", "strokeWidth": 2.5, "cornerRadius": 8 } }
      ]
    },
    {
      "id": "edge_gateway_panel",
      "type": "panel",
      "title": "Multi-Region Edge Gateway",
      "subtitle": "(Regional ingress & routing)",
      "layout": { "direction": "row", "gap": 24, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#06b6d4", "strokeWidth": 2, "cornerRadius": 16 },
      "children": [
        { "id": "gw_authn", "type": "card", "title": "Auth & Rate Limit", "body": "Token verification\nSliding window limiter\nDenylist enforcement", "icon": "shield", "style": { "color": "#06b6d4", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "gw_normalize", "type": "card", "title": "Payload Normalizer", "body": "Schema coercion\nUnit conversion\nEnvelope unwrapping", "icon": "wrench", "style": { "color": "#06b6d4", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        {
          "id": "geo_router_subpanel",
          "type": "panel",
          "title": "Geo-Aware Router Mesh",
          "badge": "4 regions",
          "layout": { "direction": "grid", "gap": 16, "grid_cols": 2, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
          "style": { "strokeColor": "#0891b2", "strokeWidth": 2, "cornerRadius": 14 },
          "children": [
            { "id": "region_us", "type": "card", "title": "US-East Router", "icon": "globe", "style": { "color": "#0891b2", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "region_eu", "type": "card", "title": "EU-West Router", "icon": "globe", "style": { "color": "#0891b2", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "region_apac", "type": "card", "title": "APAC Router", "icon": "globe", "style": { "color": "#0891b2", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "region_sa", "type": "card", "title": "SA-East Router", "icon": "globe", "style": { "color": "#0891b2", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
          ]
        }
      ]
    },
    {
      "id": "core_panel",
      "type": "panel",
      "title": "Orchestration & Synchronization Core",
      "badge": "hot path",
      "subtitle": "(Asynchronous distributed pipeline)",
      "layout": { "direction": "row", "gap": 20, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#1d8be8", "strokeWidth": 3, "cornerRadius": 20, "colorPreset": "core" },
      "children": [
        { "id": "core_ingest", "type": "card", "title": "Ingest & Decouple", "body": "Poll memory queues\nParse raw markdown\nResolve sequence IDs", "icon": "activity", "style": { "color": "#3b82f6", "strokeWidth": 2, "cornerRadius": 12, "bold": true, "borderless": true, "transparent": false } },
        { "id": "core_guard", "type": "card", "title": "Privacy & Ingress Guardrail", "body": "Regex & NER scrubbing\nToken redactor\nZero PII verified", "icon": "shield-check", "style": { "color": "#10b981", "strokeWidth": 2, "cornerRadius": 12, "bold": true, "borderless": true, "transparent": false } },
        { "id": "core_embed", "type": "card", "title": "Vector Embedding", "body": "Chunk long forms\nGenerate embeddings\nValidate dimensions", "icon": "layers", "style": { "color": "#a855f7", "strokeWidth": 2, "cornerRadius": 12, "bold": true, "borderless": true, "transparent": false } },
        { "id": "core_stitch", "type": "card", "title": "Graph Stitching", "body": "Extract entities\nMap dependencies\nUpdate entity relations", "icon": "git-commit", "style": { "color": "#ec4899", "strokeWidth": 2, "cornerRadius": 12, "bold": true, "borderless": true, "transparent": false } },
        {
          "id": "consensus_subpanel",
          "type": "panel",
          "title": "Consensus & Commit Detail",
          "badge": "quorum",
          "layout": { "direction": "column", "gap": 16, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
          "style": { "strokeColor": "#f59e0b", "strokeWidth": 2, "cornerRadius": 14 },
          "children": [
            { "id": "cons_lock", "type": "card", "title": "Async Lock Registry", "body": "Distributed mutex\nLease renewal", "icon": "lock", "style": { "color": "#f59e0b", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "cons_drift", "type": "card", "title": "Delta Drift Resolver", "body": "Vector clock merge\nConflict resolution", "icon": "activity", "style": { "color": "#f59e0b", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            {
              "id": "quorum_detail_subpanel",
              "type": "panel",
              "title": "Raft Quorum Internals",
              "subtitle": "(Vote & commit detail)",
              "layout": { "direction": "row", "gap": 16, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
              "style": { "strokeColor": "#eab308", "strokeWidth": 2, "cornerRadius": 12 },
              "children": [
                { "id": "quorum_vote", "type": "card", "title": "Raft Vote Tally", "body": "Majority check\nTerm comparison", "icon": "bar-chart", "style": { "color": "#eab308", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
                { "id": "quorum_commit", "type": "card", "title": "Commit Log Writer", "body": "Append-only log\nSnapshot compaction", "icon": "file-text", "style": { "color": "#eab308", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
              ]
            }
          ]
        }
      ]
    },
    {
      "id": "decision",
      "type": "diamond",
      "title": "State Validated?",
      "body": "Consensus achieved\nSchema matched\nConflict free",
      "style": { "color": "#ef4444", "strokeWidth": 3 }
    },
    {
      "id": "output",
      "type": "card",
      "title": "Dispatched Context",
      "icon": "zap",
      "style": { "color": "#10b981", "strokeWidth": 2.5, "cornerRadius": 12, "borderless": true, "transparent": false }
    },
    {
      "id": "storage_panel",
      "type": "panel",
      "title": "Persistent State Mesh",
      "badge": "durable tier",
      "subtitle": "(Encrypted persistence & WAL journal tier)",
      "layout": { "direction": "row", "gap": 28, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#bd54d3", "strokeWidth": 2, "cornerRadius": 16, "colorPreset": "purple" },
      "children": [
        { "id": "store_wal", "type": "card", "title": "System WAL Storage", "body": "Distributed Raft WAL\nTransactional Raft log\nCommit snapshot journal", "icon": "database", "style": { "color": "#bd54d3", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "store_blob", "type": "card", "title": "Blob Engine", "body": "Immutable cold backups\nRaw system snap dumps\nLZ4 compression", "icon": "archive", "style": { "color": "#bd54d3", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        {
          "id": "replica_subpanel",
          "type": "panel",
          "title": "Cross-Region Replica Set",
          "badge": "4x replicated",
          "layout": { "direction": "grid", "gap": 16, "grid_cols": 2, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
          "style": { "strokeColor": "#a855f7", "strokeWidth": 2, "cornerRadius": 14 },
          "children": [
            { "id": "replica_us", "type": "card", "title": "US Replica Set", "icon": "disc", "style": { "color": "#a855f7", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "replica_eu", "type": "card", "title": "EU Replica Set", "icon": "disc", "style": { "color": "#a855f7", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "replica_apac", "type": "card", "title": "APAC Replica Set", "icon": "disc", "style": { "color": "#a855f7", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "replica_cold", "type": "card", "title": "Cold Archive Replica", "icon": "disc", "style": { "color": "#a855f7", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
          ]
        }
      ],
      "footer": {
        "id": "storage_footer",
        "type": "card",
        "title": "Hybrid Search Engine (HNSW Index + BM25 Lexical + Cypher Traversal)",
        "style": { "color": "#bd54d3", "strokeWidth": 2, "cornerRadius": 8, "borderless": true, "transparent": false }
      }
    },
    {
      "id": "left_ingestion_panel",
      "type": "panel",
      "title": "Distributed Ingestion Layer",
      "badge": "event driven",
      "layout": { "direction": "column", "gap": 17, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#22c86f", "strokeWidth": 2, "cornerRadius": 16, "colorPreset": "green" },
      "children": [
        { "id": "left_buffers", "type": "card", "title": "Ephemeral Buffers", "body": "Redis Stream queues\nKafka transaction logs\nIn-memory hot keys", "icon": "zap", "style": { "color": "#10b981", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "left_parsers", "type": "card", "title": "Model-Agnostic Parsers", "body": "Claude XML tags\nOpenAI JSON schemas\nMarkdown execution blocks", "icon": "code", "style": { "color": "#10b981", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "left_aggregators", "type": "card", "title": "Stream Aggregators", "body": "Agent token usage logs\nException trace states\nTool execution histories", "icon": "terminal", "style": { "color": "#10b981", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "left_dlq", "type": "card", "title": "Dead Letter Queue", "body": "Poison message capture\nRetry backoff ledger", "icon": "alert-triangle", "style": { "color": "#10b981", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
      ]
    },
    {
      "id": "right_agent_panel",
      "type": "panel",
      "title": "Agent Execution Fabric",
      "badge": "agent fabric",
      "layout": { "direction": "column", "gap": 14, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#f4b64e", "strokeWidth": 2, "cornerRadius": 16, "colorPreset": "amber" },
      "children": [
        { "id": "right_planner", "type": "card", "title": "Dynamic Planner", "body": "Injects real-time context\nAdapts runbook goals\nCalculates token budget", "icon": "sliders", "style": { "color": "#f4b64e", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "right_persona", "type": "card", "title": "Persona Registry", "body": "Cross-agent alignment\nHistorical user biases\nGlobal system behaviors", "icon": "user-check", "style": { "color": "#f4b64e", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        {
          "id": "tool_grid_subpanel",
          "type": "panel",
          "title": "Ephemeral Tool Sandbox",
          "badge": "6 tools",
          "layout": { "direction": "flow", "gap": 16, "max_cols": 3, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
          "style": { "strokeColor": "#fbbf24", "strokeWidth": 2, "cornerRadius": 14 },
          "children": [
            { "id": "tool_search", "type": "card", "title": "Web Search", "icon": "box", "style": { "color": "#fbbf24", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "tool_code", "type": "card", "title": "Code Interpreter", "icon": "box", "style": { "color": "#fbbf24", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "tool_file", "type": "card", "title": "File Ops", "icon": "box", "style": { "color": "#fbbf24", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "tool_sql", "type": "card", "title": "SQL Executor", "icon": "box", "style": { "color": "#fbbf24", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "tool_http", "type": "card", "title": "HTTP Client", "icon": "box", "style": { "color": "#fbbf24", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
            { "id": "tool_shell", "type": "card", "title": "Sandboxed Shell", "icon": "box", "style": { "color": "#fbbf24", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
          ]
        }
      ]
    },
    {
      "id": "observability_panel",
      "type": "panel",
      "title": "Observability & Telemetry Plane",
      "badge": "telemetry",
      "subtitle": "(Metrics, traces & logs)",
      "layout": { "direction": "flow", "gap": 18, "max_cols": 3, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 16 },
      "children": [
        { "id": "obs_metrics", "type": "card", "title": "Metrics Aggregator", "icon": "activity", "style": { "color": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "obs_traces", "type": "card", "title": "Distributed Tracing", "icon": "radio", "style": { "color": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "obs_logs", "type": "card", "title": "Structured Log Sink", "icon": "file-text", "style": { "color": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "obs_alerts", "type": "card", "title": "Alert Router", "icon": "bell", "style": { "color": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "obs_dash", "type": "card", "title": "Live Dashboards", "icon": "eye", "style": { "color": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "obs_cost", "type": "card", "title": "Cost Attribution", "icon": "dollar-sign", "style": { "color": "#7ee3d6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
      ]
    },
    {
      "id": "governance_panel",
      "type": "panel",
      "title": "Governance & Policy Control",
      "subtitle": "(Policy, cost & access control)",
      "layout": { "direction": "grid", "gap": 18, "grid_cols": 2, "padding": { "left": 12, "right": 12, "top": 36, "bottom": 12 } },
      "style": { "strokeColor": "#ff7ab6", "strokeWidth": 2, "cornerRadius": 16 },
      "children": [
        { "id": "gov_policy", "type": "card", "title": "Policy Engine", "icon": "shield", "style": { "color": "#ff7ab6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "gov_cost", "type": "card", "title": "Cost Governor", "icon": "dollar-sign", "style": { "color": "#ff7ab6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "gov_access", "type": "card", "title": "Access Control", "icon": "key", "style": { "color": "#ff7ab6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "gov_audit", "type": "card", "title": "Audit Trail", "icon": "eye", "style": { "color": "#ff7ab6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } },
        { "id": "gov_secrets", "type": "card", "title": "Secrets Rotation", "icon": "lock", "style": { "color": "#ff7ab6", "strokeWidth": 2, "cornerRadius": 10, "borderless": true, "transparent": false } }
      ]
    },
    {
      "id": "quality_gate",
      "type": "diamond",
      "title": "Compliance Gate Passed?",
      "body": "Policy checks green\nAudit trail complete\nNo open violations",
      "style": { "color": "#f97316", "strokeWidth": 3 }
    },
    {
      "id": "archive_output",
      "type": "card",
      "title": "Compliance Archive",
      "icon": "archive",
      "style": { "color": "#10b981", "strokeWidth": 2.5, "cornerRadius": 12, "borderless": true, "transparent": false }
    }
  ],
  "connections": [
    { "from": "ing_vec", "to": "gw_normalize", "exitPort": "right", "entryPort": "left" },
    { "from": "ing_ctx", "to": "gw_normalize", "exitPort": "right", "entryPort": "left" },
    { "from": "ing_git", "to": "gw_authn", "exitPort": "right", "entryPort": "left" },
    { "from": "ing_usr", "to": "gw_authn", "exitPort": "right", "entryPort": "left" },
    { "from": "ing_graph", "to": "gw_normalize", "exitPort": "right", "entryPort": "left" },
    { "from": "ing_audio", "to": "gw_normalize", "exitPort": "right", "entryPort": "left" },

    { "from": "gw_authn", "to": "gw_normalize", "exitPort": "right", "entryPort": "left" },
    { "from": "gw_normalize", "to": "region_us", "exitPort": "right", "entryPort": "left" },
    { "from": "gw_normalize", "to": "region_eu", "exitPort": "right", "entryPort": "left" },
    { "from": "gw_normalize", "to": "region_apac", "exitPort": "right", "entryPort": "left" },
    { "from": "gw_normalize", "to": "region_sa", "exitPort": "right", "entryPort": "left" },

    { "from": "region_us", "to": "core_ingest", "exitPort": "right", "entryPort": "left" },
    { "from": "region_eu", "to": "core_ingest", "exitPort": "right", "entryPort": "left" },
    { "from": "region_apac", "to": "core_ingest", "exitPort": "right", "entryPort": "left" },
    { "from": "region_sa", "to": "core_ingest", "exitPort": "right", "entryPort": "left" },

    { "from": "core_ingest", "to": "core_guard", "exitPort": "right", "entryPort": "left" },
    { "from": "core_guard", "to": "core_embed", "exitPort": "right", "entryPort": "left" },
    { "from": "core_embed", "to": "core_stitch", "exitPort": "right", "entryPort": "left" },
    { "from": "core_stitch", "to": "cons_lock", "exitPort": "right", "entryPort": "left" },
    { "from": "cons_lock", "to": "cons_drift", "exitPort": "bottom", "entryPort": "top" },
    { "from": "cons_drift", "to": "quorum_vote", "exitPort": "bottom", "entryPort": "top" },
    { "from": "quorum_vote", "to": "quorum_commit", "exitPort": "right", "entryPort": "left" },
    { "from": "quorum_commit", "to": "decision", "exitPort": "right", "entryPort": "left" },

    { "from": "decision", "to": "output", "exitPort": "right", "entryPort": "left", "label": "Yes" },
    { "from": "decision", "to": "core_guard", "exitPort": "left", "entryPort": "bottom", "label": "No" },

    { "from": "output", "to": "store_wal", "exitPort": "right", "entryPort": "left" },
    { "from": "output", "to": "right_planner", "exitPort": "right", "entryPort": "left" },

    { "from": "store_wal", "to": "store_blob", "exitPort": "bottom", "entryPort": "top" },
    { "from": "store_blob", "to": "replica_us", "exitPort": "right", "entryPort": "left" },
    { "from": "store_blob", "to": "replica_eu", "exitPort": "right", "entryPort": "left" },
    { "from": "store_blob", "to": "replica_apac", "exitPort": "right", "entryPort": "left" },
    { "from": "store_blob", "to": "replica_cold", "exitPort": "right", "entryPort": "left" },

    { "from": "core_embed", "to": "store_wal", "exitPort": "bottom", "entryPort": "top" },
    { "from": "core_stitch", "to": "store_blob", "exitPort": "bottom", "entryPort": "top" },

    { "from": "store_blob", "to": "storage_footer", "exitPort": "bottom", "entryPort": "top" },

    { "from": "right_planner", "to": "right_persona", "exitPort": "bottom", "entryPort": "top" },
    { "from": "right_persona", "to": "tool_search", "exitPort": "right", "entryPort": "left" },
    { "from": "right_persona", "to": "tool_code", "exitPort": "right", "entryPort": "left" },
    { "from": "right_persona", "to": "tool_file", "exitPort": "right", "entryPort": "left" },
    { "from": "right_persona", "to": "tool_sql", "exitPort": "right", "entryPort": "left" },
    { "from": "right_persona", "to": "tool_http", "exitPort": "right", "entryPort": "left" },
    { "from": "right_persona", "to": "tool_shell", "exitPort": "right", "entryPort": "left" },

    { "from": "right_planner", "to": "decision", "exitPort": "left", "entryPort": "bottom", "label": "Re-evaluate (If Drift > 2%)" },

    { "from": "left_buffers", "to": "left_parsers", "exitPort": "bottom", "entryPort": "top" },
    { "from": "left_parsers", "to": "left_aggregators", "exitPort": "bottom", "entryPort": "top" },
    { "from": "left_aggregators", "to": "left_dlq", "exitPort": "bottom", "entryPort": "top" },
    { "from": "left_buffers", "to": "core_guard", "exitPort": "right", "entryPort": "bottom" },

    { "from": "core_stitch", "to": "obs_metrics", "exitPort": "bottom", "entryPort": "top" },
    { "from": "core_embed", "to": "obs_traces", "exitPort": "bottom", "entryPort": "top" },
    { "from": "right_planner", "to": "obs_logs", "exitPort": "left", "entryPort": "top" },
    { "from": "store_wal", "to": "obs_alerts", "exitPort": "bottom", "entryPort": "top" },

    { "from": "obs_metrics", "to": "obs_dash", "exitPort": "right", "entryPort": "left" },
    { "from": "obs_metrics", "to": "obs_cost", "exitPort": "right", "entryPort": "left" },

    { "from": "obs_alerts", "to": "gov_audit", "exitPort": "right", "entryPort": "left" },

    { "from": "gov_policy", "to": "gov_cost", "exitPort": "right", "entryPort": "left" },
    { "from": "gov_cost", "to": "gov_access", "exitPort": "right", "entryPort": "left" },
    { "from": "gov_access", "to": "gov_audit", "exitPort": "right", "entryPort": "left" },
    { "from": "gov_access", "to": "gov_secrets", "exitPort": "right", "entryPort": "left" },

    { "from": "gov_audit", "to": "core_guard", "exitPort": "left", "entryPort": "bottom", "label": "Escalate Compliance Violation" },
    { "from": "gov_audit", "to": "quality_gate", "exitPort": "right", "entryPort": "left" },

    { "from": "quality_gate", "to": "archive_output", "exitPort": "right", "entryPort": "left", "label": "Yes" },
    { "from": "quality_gate", "to": "gov_policy", "exitPort": "left", "entryPort": "bottom", "label": "No / Remediate" }
  ],
  "annotations": [
    {
      "text": "Iterate state sync until vector drift < 2% and WAL entries commit to storage blocks",
      "attachTo": "core_panel",
      "position": "top",
      "style": { "fontSize": 14 }
    },
    {
      "text": "Federated ingest across 4 geo regions",
      "attachTo": "ingest_panel",
      "position": "top-label"
    },
    {
      "text": "Compliance loop",
      "attachTo": "governance_panel",
      "position": "top-right",
      "style": { "fontSize": 14 }
    }
  ]
};
