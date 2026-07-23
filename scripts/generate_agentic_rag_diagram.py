#!/usr/bin/env python3
import json
import asyncio
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
backend_dir = os.path.join(project_root, "backend")
if project_root not in sys.path:
    sys.path.insert(0, project_root)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from scripts.flowdraft.schema import validate_spec
from scripts.flowdraft.compiler import compile_spec
from scripts.flowdraft.layout_engine import layout
from app.api.v1.mcp import trigger_export, get_export_status
from app.services.storage import MinioStorage

def build_agentic_rag_spec() -> dict:
    return {
        "version": "2.0",
        "theme": "dark",
        "title": {
            "prefix": "An End-to-End Architecture for",
            "highlight": "Enhanced Agentic RAG Systems"
        },
        "signature": "Insights & Updates on GenAI @FlowDraft",
        "canvas": {
            "width": 2200,
            "height": 1350,
            "layoutDirection": "LR",
            "fps": 30,
            "duration": 2.0
        },
        "elements": [
            # --- ROW 1 LEFT: INGESTION PIPELINE ---
            {
                "id": "panel_doc_proc",
                "type": "panel",
                "title": "Enriched Document Ingestion Pipeline",
                "badge": "Ingestion Pipeline",
                "children": [
                    { "id": "gdocs_src", "type": "input", "title": "Knowledge Docs (GDocs)", "icon": "folder", "variant": "amber" },
                    { "id": "doc_extract", "type": "input", "title": "Content Extraction", "body": "GDoc API reader", "icon": "file", "variant": "coral" },
                    { "id": "table_enrich", "type": "card", "title": "Table Enrichment", "body": "LLM metadata annotation", "icon": "scan", "variant": "sky" },
                    { "id": "aware_chunk", "type": "card", "title": "Table-Aware Chunking", "body": "Semantic boundary split", "icon": "scan", "variant": "peach" },
                    { "id": "embed_gen", "type": "card", "title": "Embedding Generation", "body": "Dense vector encoder", "icon": "package", "status": "active", "variant": "coral" }
                ]
            },

            # --- ROW 1 RIGHT: OFFLINE STORAGE ---
            {
                "id": "panel_offline_store",
                "type": "panel",
                "title": "Offline Vector & Feature Storage",
                "badge": "Storage Layer",
                "children": [
                    { "id": "vector_store", "type": "cylinder", "title": "Vector Store", "body": "Indexed document embeddings", "icon": "db", "variant": "purple" },
                    { "id": "feature_store", "type": "cylinder", "title": "Feature Store", "body": "Custom metadata attributes", "icon": "db", "variant": "amber" }
                ]
            },

            # --- ROW 2 LEFT: CORE QUERY & RETRIEVAL ENGINE ---
            {
                "id": "panel_core_agent",
                "type": "panel",
                "title": "Agentic Query & Answer Generation Engine",
                "badge": "Core Engine",
                "children": [
                    { "id": "user", "type": "input", "title": "User Prompt", "icon": "file", "variant": "sky" },
                    { "id": "query_node", "type": "card", "title": "Query Gateway", "body": "User input prompt & metadata", "status": "active", "variant": "sky" },
                    { "id": "llm_optimizer", "type": "card", "title": "LLM Query Optimizer", "body": "Rewrites & enriches user query", "icon": "scan", "status": "streaming", "variant": "sky" },
                    { "id": "llm_src_id", "type": "card", "title": "Source Identifier", "body": "Selects metadata filters & routes", "icon": "scan", "variant": "sky" },
                    { "id": "vec_search", "type": "card", "title": "Dense Vector Search", "body": "Embedding similarity retrieval", "icon": "scan", "variant": "coral" },
                    { "id": "bm25_search", "type": "card", "title": "BM25 Retriever", "body": "Sparse keyword BM25 search", "icon": "scan", "variant": "sky" },
                    { "id": "llm_postproc", "type": "card", "title": "LLM Post-Processor", "body": "Reranks & filters retrieved chunks", "icon": "scan", "variant": "sky" },
                    { "id": "llm_generator", "type": "card", "title": "LLM Answer Generator", "body": "Generates grounded final answer", "icon": "package", "status": "healthy", "variant": "purple" }
                ]
            },

            # --- ROW 2 RIGHT: OUTPUT & TELEMETRY GATEWAY ---
            {
                "id": "panel_output",
                "type": "panel",
                "title": "Delivery Gateway & Telemetry",
                "badge": "Output Gateway",
                "children": [
                    { "id": "slack_iface", "type": "card", "title": "Slack / Chat Gateway", "body": "Bi-directional chat interface", "icon": "hash", "status": "streaming", "variant": "purple" },
                    { "id": "answer_node", "type": "card", "title": "Final Answer", "body": "Grounded RAG response", "status": "healthy", "variant": "mint" },
                    { "id": "pre_prod_metrics", "type": "card", "title": "Pre-prod Metrics", "body": "Batch eval & LLM-as-Judge", "status": "healthy", "variant": "mint" },
                    { "id": "post_prod_metrics", "type": "card", "title": "Post-prod Telemetry", "body": "Online monitoring & feedback", "status": "active", "variant": "mint" }
                ]
            }
        ],
        "connections": [
            # User & Gateway Flow inside Panel 2
            { "from": "user", "to": "query_node", "label": "User Query", "style": "solid", "flowing": True },
            { "from": "query_node", "to": "llm_optimizer", "label": "Dispatch", "style": "solid", "flowing": True },

            # Core Agent Query Engine Flow
            { "from": "llm_optimizer", "to": "llm_src_id", "style": "solid" },
            { "from": "llm_src_id", "to": "vec_search", "label": "Dense Query", "style": "solid" },
            { "from": "llm_src_id", "to": "bm25_search", "label": "Sparse Query", "style": "solid" },
            { "from": "vec_search", "to": "llm_postproc", "label": "Vector Chunks", "style": "solid" },
            { "from": "bm25_search", "to": "llm_postproc", "label": "BM25 Matches", "style": "solid" },
            { "from": "llm_postproc", "to": "llm_generator", "label": "Context", "style": "solid", "flowing": True },

            # Ingestion Flow inside Panel 1
            { "from": "gdocs_src", "to": "doc_extract", "label": "Raw Docs", "style": "solid" },
            { "from": "doc_extract", "to": "table_enrich", "style": "solid" },
            { "from": "table_enrich", "to": "aware_chunk", "style": "solid" },
            { "from": "aware_chunk", "to": "embed_gen", "style": "solid" },

            # Ingestion -> Storage (Row 1 Left -> Row 1 Right)
            { "from": "embed_gen", "to": "vector_store", "label": "Embeddings", "style": "solid", "flowing": True },
            { "from": "embed_gen", "to": "feature_store", "label": "Attributes", "style": "solid" },

            # Storage -> Retrieval Links (Row 1 Right -> Row 2 Left)
            { "from": "vec_search", "to": "vector_store", "label": "KNN Lookup", "style": "dashed" },
            { "from": "bm25_search", "to": "feature_store", "label": "Index Lookup", "style": "dashed" },

            # Core Generator -> Delivery Panel (Row 2 Left -> Row 2 Right)
            { "from": "llm_generator", "to": "slack_iface", "label": "Response", "style": "solid", "flowing": True },
            { "from": "slack_iface", "to": "answer_node", "label": "Deliver Answer", "style": "solid" },

            # Telemetry
            { "from": "slack_iface", "to": "post_prod_metrics", "label": "Telemetry", "style": "dashed" },
            { "from": "pre_prod_metrics", "to": "llm_generator", "label": "Eval Feedback", "style": "dashed" }
        ],
        "annotations": [
            { "text": "Prompt Config & LLM System Templates", "attachTo": "llm_generator" }
        ]
    }

async def generate_and_export_rag_diagram():
    print("=================================================================")
    print(" GENERATING PERFECT 2200x1350 ZERO-WASTE AGENTIC RAG DIAGRAM (GIF + PNG)")
    print("=================================================================")
    
    spec = build_agentic_rag_spec()
    validated = validate_spec(spec)
    ir = compile_spec(validated)
    layout(ir)

    print("Spec compiled cleanly. Submitting GIF and PNG export jobs...")
    gif_res = await trigger_export(spec, format="gif")
    png_res = await trigger_export(spec, format="png")
    
    gif_job_id = json.loads(gif_res).get("job_id")
    png_job_id = json.loads(png_res).get("job_id")
    print(f"GIF Export Job: {gif_job_id}")
    print(f"PNG Export Job: {png_job_id}")

    # Wait for completion
    completed = {"gif": False, "png": False}
    for _ in range(45):
        await asyncio.sleep(1.0)
        if not completed["gif"]:
            st = json.loads(await get_export_status(gif_job_id))
            if st.get("status") == "completed":
                print(f"SUCCESS! GIF exported. Download URL: {st.get('download_url')}")
                completed["gif"] = True
        if not completed["png"]:
            st = json.loads(await get_export_status(png_job_id))
            if st.get("status") == "completed":
                print(f"SUCCESS! PNG exported. Download URL: {st.get('download_url')}")
                completed["png"] = True
        if completed["gif"] and completed["png"]:
            break

    # Fetch artifacts locally into brain artifacts folder
    storage = MinioStorage()
    artifacts_dir = r"C:\Users\Administrator\.gemini\antigravity\brain\1cf9cb3b-5bd2-4c9f-9283-ce35d98320c4"
    
    if completed["gif"]:
        gif_path = os.path.join(artifacts_dir, "agentic_rag_animated.gif")
        resp = storage.client.get_object(storage.bucket_name, f"{gif_job_id}.gif")
        with open(gif_path, "wb") as f:
            f.write(resp.read())
        resp.close()
        resp.release_conn()
        print(f"Saved local GIF artifact: {gif_path}")

    if completed["png"]:
        png_path = os.path.join(artifacts_dir, "agentic_rag_aligned_perfect.png")
        resp = storage.client.get_object(storage.bucket_name, f"{png_job_id}.png")
        with open(png_path, "wb") as f:
            f.write(resp.read())
        resp.close()
        resp.release_conn()
        print(f"Saved local PNG artifact: {png_path}")

if __name__ == "__main__":
    asyncio.run(generate_and_export_rag_diagram())
