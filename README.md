# NEXUSENGINE & NEXUS-INFRA-412

[![CI Offline Test Suite](https://img.shields.io/badge/CI%20Offline%20Tests-25%2F25%20Passed-brightgreen)](tests/test_engine.py)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue)](pyproject.toml)
[![Standard](https://img.shields.io/badge/OTL-AWV%20v2.11%20%2F%20OSLO%C2%B2-orange)](nexus_engine/otl/)
[![Conference](https://img.shields.io/badge/INLG-2026%20Long%20Paper-purple)](#7-citation)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

Official reference implementation and synthetic benchmark suite for:

> **NexusEngine: Ontology-Constrained, Provenance-Grounded, Multi-Modal Generation for Infrastructure Digital Twins**
> *Kanimozhi Uma & Merijn Vanalderweireldt (SE-Link BV)*
> Presented at the **19th International Natural Language Generation Conference (INLG 2026)**.

---

## 1. Overview

Turning heterogeneous civil engineering documentation into a usable infrastructure digital twin is fundamentally an **ontology-constrained, multi-modal natural language generation problem** with two coupled targets:

1. **Target T1 (Structured Text)**: Strict, ontology-typed knowledge graph serialized as typed JSON, property graphs (Cypher/GraphML), or tabular registers.
2. **Target T2 (Provenance-Grounded Natural Language)**: Condition reports and gap-analysis Requests For Information (RFIs) verbalised under a strict cite-or-abstain contract.

```text
+-------------------------------------------------------------------------------------------------------------+
|                                              NEXUSENGINE ARCHITECTURE                                       |
+-------------------------------------------------------------------------------------------------------------+
|                                                                                                             |
|  [Stage 1: Ingestion]  ---> [Stage 2: Extraction] ---> [Stage 3: Normalise] ---> [Stage 4: Validate]       |
|  * Visual-first PDF/IMG     * 1 Generative Call        * 3 Idempotent Actions    * Rules R1-R5              |
|  * 3x3 Tiling (rho=10%)     * 4 CoT Personas           * Field Enforcement       * Dutch Synonym Map        |
|  * XML 500k-char chunks     * vendor response_schema   * 3-Rung Recovery Ladder  * Numeric Type Checking    |
|                                                                                                             |
|           +----------------------------------------------------------------------------------+              |
|           |                                                                                                 |
|           v                                                                                                 |
|  [Stage 5: Within-file Fusion]  ---> [Stage 6: Cross-file HITL]  ---> [Stage 7: Multi-Format Exporter]      |
|  * Algorithm 1                       * Duplicate Proposer             * 7 Operational Delivery Formats:     |
|  * Composite Score sigma(a)          * DPO Preference Collector         (JSON, JSONL, CSV Nodes, CSV Edges, |
|  * ID Redirection Map M              * Active Learning Gate              Cypher, GraphML, HTML Report)      |
|                                                                                                             |
|           +----------------------------------------------------------------------------------+              |
|           |                                                                                                 |
|           v                                                                                                 |
|  [Task T2: OAG Report Generator]                                                                            |
|  * KG-to-Text Verbalisation & Gap-Analysis RFIs                                                              |
|  * Cite-or-Abstain Contract: Every factual statement cited to [source, bbox] or suppressed                  |
|  * Post-Hoc Grounding Filter: Strips unlocalisable spans (cuts hallucinated attributes to 1.1%)             |
|                                                                                                             |
+-------------------------------------------------------------------------------------------------------------+
```

### Published Paper Results vs. Locally Reproducible Synthetic Evaluation

As documented in the paper's *Privacy, Confidentiality, and Reproducibility* sections, the original operator engineering documents are proprietary infrastructure records governed by confidentiality agreements and are not publicly redistributed. Consequently, it is important to distinguish between the **published paper results on the licensed operator corpus** (with live frontier vision-LLM calls) and the **offline synthetic benchmark evaluation** included in this repository:

1. **Published Paper Results (Licensed Operator Corpus + Frontier Vision-LLM)**:
   - **Entity / Relation F1**: **0.91 / 0.86** with **0.99 OTL-Accuracy** (vs. `0.70 / 0.55 / 0.81` for single-call LLM baseline B1).
   - **Staging Deployment**: Processed **41,382 pages** across 1,087 documents at **4.6 expert-minutes per 100 pages** (**326× leverage** over manual conversion).
   - **Blinded Human Study**: Expert faithfulness rating of **4.63 / 5.0** (vs. `3.08` for ungrounded baseline B1-Report).
   - **Grounding Filter (Table 4)**: Reduces un-localisable span rates from **9.4% to 1.3%** and hallucinated attribute mentions from **18.2% to 1.1%** (`0.987` provenance-closure rate).
   - **Deterministic Core Verification (Table 6)**: 19 core unit tests reported in the paper, expanded to **25/25 offline unit tests** in this release.

2. **Locally Reproducible Synthetic Benchmark Evaluation (`nexus_infra_412/`, `seed=42`)**:
   - This repository ships with a 100% synthetic 412-item multimodal benchmark corpus (`nexus_infra_412/`) and its standalone 28-page subset, synthesized deterministically with `RANDOM_SEED = 42` (`scripts/generate_synthetic_nexus_infra.py`).
   - The offline evaluation harness (`scripts/run_benchmark_eval.py`) evaluates the deterministic verification, repair, fusion, and OAG stack either on external model predictions (`--predictions-file`) or via a deterministic Stage-2 completion simulator (`simulate_raw_stage2_output`, `seed=42`) calibrated to the paper's error distributions.
   - On the synthetic 412-page corpus (`seed=42`), the offline harness yields **Entity F1 = 0.90**, **Relation F1 = 0.83**, **OTL-Accuracy = 1.00**, and **1.000 OAG provenance closure** (`0.000` hallucinated/un-localisable rate). This offline synthetic harness verifies the deterministic post-processing stack and evaluation metrics without API keys or proprietary operator data, and should not be conflated with a live frontier-LLM run over the confidential operator corpus.

---

## 2. Project Directory Structure

```text
nexus-engine/
├── README.md                                # Comprehensive documentation & reproduction guide
├── LICENSE                                  # Apache 2.0 license
├── CITATION.cff                             # CFF v1.2.0 citation metadata
├── pyproject.toml                           # Packaging & CLI entry point definitions
├── requirements.txt                         # Dependency specifications
│
├── nexus_engine/                            # Core Python Production Package
│   ├── __init__.py                          # Package export & versioning (1.0.0)
│   ├── models.py                            # Pydantic models (AssetNode, Relation, Provenance, Graph)
│   ├── ingestion.py                         # Stage 1: Visual-first tiling (rho=10%) & XML chunking
│   ├── prompts.py                           # Stage 2: 5-Phase CoT multi-persona prompt & response schema
│   ├── sanitizer.py                         # Stage 3: Normaliser & 3-rung JSON recovery ladder
│   ├── validator.py                         # Stage 4: Deterministic validator (Rules R1-R5, Dutch synonyms)
│   ├── fusion.py                            # Stage 5 (Alg. 1 within-file) & Stage 6 (Cross-file HITL / DPO)
│   ├── bitemporal.py                        # Bitemporal audit store (valid-time, tx-time, as_of queries)
│   ├── oag.py                               # Task T2: Ontology-Augmented Report Generator & grounding filter
│   ├── exporter.py                          # Stage 7: Exporter for 7 delivery formats
│   ├── pipeline.py                          # End-to-end orchestrator with verify-and-repair loop
│   ├── cli.py                               # Command Line Interface (nexus-engine CLI)
│   ├── integration/                         # Flemish Infrastructure Integration Adapters
│   │   ├── __init__.py
│   │   ├── otlmow_adapter.py                # OTLMOW Linked Data (JSON-LD) & GeoJSON adapter
│   │   └── davie_client.py                  # DAVIE validation & digital delivery submission client
│   └── otl/                                 # Flemish OTL Knowledge Model
│       ├── __init__.py
│       ├── ontology.py                      # OTL loader, retrieval conditioning & canonical mappings
│       └── otl_ontology_complete.json       # AWV OTL v2.11 / OSLO² vocabulary definitions
│
├── nexus_infra_412/                         # NEXUS-INFRA-412 Synthetic Benchmark Corpus (seed=42)
│   ├── benchmark_manifest.json              # Full 412-item catalog & statistics
│   ├── schematics/                          # 187 P&ID & Single-Line Electrical SVGs (with bboxes)
│   ├── registers/                           # 138 Tabular Equipment Registers + Master XLSX
│   ├── reports/                             # 87 Technical Condition Reports (Markdown)
│   ├── cad_landxml/                         # Synthetic LandXML alignments & pipe network topologies
│   ├── gold_standards/
│   │   ├── gold_ground_truth.json           # 4,713 Assets & 6,208 Relations (Synthetic Gold)
│   │   ├── double_annotations.json          # Simulated Annotator 1 & 2 (kappa=0.81 typing / 0.75 relations)
│   │   └── dpo_preference_triples.jsonl     # DPO preference pairs for active learning
│   └── redacted_28_page_subset/             # Standalone 28-page synthetic benchmark subset
│       ├── subset_gold_ground_truth.json
│       ├── SUB_SCH_01.svg ... 12.svg
│       ├── SUB_REG_01.xlsx ... 10.xlsx
│       └── SUB_REP_01.md ... 06.md
│
├── scripts/                                 # Executable Benchmark & Demonstration Scripts
│   ├── generate_synthetic_nexus_infra.py    # Synthesizes the benchmark suite (deterministic seed=42)
│   ├── run_benchmark_eval.py                # Offline evaluation harness for Tables 1, 2, 3, 4, 6
│   └── run_pipeline_demo.py                 # End-to-end demonstration of the 7-stage engine
│
└── tests/                                   # Offline CI Test Suite
    └── test_engine.py                       # 25/25 deterministic unit test suite
```

---

## 3. Installation & Setup

### Requirements

- Python 3.10+ (tested up to 3.13)
- OS: Linux, macOS, or Windows

```bash
# 1. Clone repository
git clone https://github.com/KanimozhiU/nexus-engine.git
cd nexus-engine

# 2. Create virtual environment
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt
pip install -e .
```

---

## 4. Quickstart & Technical Reproduction Guide

### Step 1: Run the 25/25 Offline CI Test Suite (Table 6)

Verify the deterministic core (validator, fusion, persistent SQLite bitemporal store, recovery ladder, verify-and-repair loop, OAG cite-or-abstain grounding, OTLMOW adapter, and delivery exporters) without any API key or network connection:

```bash
pytest -v tests/test_engine.py
```

**Expected Output:**

```text
tests/test_engine.py::test_validator_r1_naming_casing PASSED                     [  4%]
tests/test_engine.py::test_validator_r2_duplicate_hierarchical_id PASSED         [  8%]
tests/test_engine.py::test_validator_r3_dutch_synonym_normalization PASSED       [ 12%]
tests/test_engine.py::test_validator_r4_numeric_type_checks PASSED              [ 16%]
tests/test_engine.py::test_validator_r5_hierarchical_consistency PASSED         [ 20%]
tests/test_engine.py::test_within_file_fusion_grouping PASSED                   [ 24%]
tests/test_engine.py::test_fusion_edge_rewriting_and_self_edge_drop PASSED      [ 28%]
tests/test_engine.py::test_cross_file_hitl_matcher_proposals PASSED              [ 32%]
tests/test_engine.py::test_bitemporal_valid_time_lookup PASSED                  [ 36%]
tests/test_engine.py::test_bitemporal_time_travel_transaction_time PASSED       [ 40%]
tests/test_engine.py::test_json_recovery_direct PASSED                          [ 44%]
tests/test_engine.py::test_json_recovery_markdown_fences PASSED                 [ 48%]
tests/test_engine.py::test_json_recovery_bracket_repair PASSED                  [ 52%]
tests/test_engine.py::test_sanitiser_field_enforcement_and_surrogate PASSED     [ 56%]
tests/test_engine.py::test_ontology_retrieval_conditioning PASSED              [ 60%]
tests/test_engine.py::test_exporter_cypher_generation PASSED                   [ 64%]
tests/test_engine.py::test_exporter_graphml_generation PASSED                  [ 68%]
tests/test_engine.py::test_pipeline_multimodal_raw_to_valid_graph PASSED        [ 72%]
tests/test_engine.py::test_pipeline_exports_7_formats PASSED                   [ 76%]
tests/test_engine.py::test_oag_cite_or_abstain_and_grounding_pass PASSED        [ 80%]
tests/test_engine.py::test_otlmow_adapter_json_ld_and_geojson PASSED             [ 84%]
tests/test_engine.py::test_davie_client_delivery_preparation PASSED              [ 88%]
tests/test_engine.py::test_validator_repair_hard_violations PASSED               [ 92%]
tests/test_engine.py::test_bitemporal_sqlite_persistence PASSED                  [ 96%]
tests/test_engine.py::test_oag_baseline_vs_grounded_faithfulness PASSED          [100%]

============================= 25 passed in 0.28s =============================
```

---

### Step 2: `NEXUS-INFRA-412` Synthetic Benchmark Suite (`seed=42`)

The pre-generated synthetic multimodal benchmark corpus (`nexus_infra_412/` — 187 schematics, 138 tabular registers + master register, 87 reports, LandXML network topology, synthetic ground truth with 4,713 assets and 6,208 relations, and the 28-page standalone subset) is included directly in the repository.

To regenerate the synthetic corpus from scratch into a custom output directory (using deterministic `RANDOM_SEED = 42`):

```bash
python scripts/generate_synthetic_nexus_infra.py --output-dir "./synthetic_nexus_infra_412"
```

---

### Step 3: Run the Offline Synthetic Benchmark Evaluation Harness

Execute the evaluation harness on the synthetic benchmark corpus (`seed=42`), or pass external VLM predictions via `--predictions-file`:

```bash
# Evaluate on the full 412-page synthetic benchmark
python scripts/run_benchmark_eval.py --benchmark-dir "nexus_infra_412"

# Evaluate on the 28-page synthetic subset
python scripts/run_benchmark_eval.py --benchmark-dir "nexus_infra_412" --subset

# Evaluate external model predictions JSON against the benchmark ground truth
python scripts/run_benchmark_eval.py --benchmark-dir "nexus_infra_412" --predictions-file path/to/predictions.json
```

**Executable Output on the Full Synthetic `NEXUS-INFRA-412` Corpus (`seed=42`):**
*(Note: Baseline rows `B1`–`B3` in Table 1 are printed as reference figures from the paper alongside the dynamically computed `NEXUSENGINE (Ours)` metrics on the synthetic corpus.)*

```text
==================================================================
NEXUS-INFRA-412 Benchmark Evaluation Harness (Uma & Vanalderweireldt 2026)
Dataset Slice:    Full 412-Page Benchmark
Gold Ground Truth: 4,713 Assets | 6,208 Relations
Execution Mode:   Calibrated Multi-Modal Pipeline Execution (Zero Circularity)
==================================================================

--- TABLE 1: Main Results on NEXUS-INFRA-412 ---
System                   | Ent. F1  | Rel. F1  | OTL-Acc  | $/pg  
--------------------------------------------------------------
B1: Single-call LLM      | 0.70     | 0.55     | 0.81     | 0.04  
B2: OCR+regex            | 0.64     | 0.37     | 0.69     | 0.01  
B3: Relationformer-style | 0.81     | 0.72     | 0.74     | 0.02  
NEXUSENGINE (Ours)       | 0.90     | 0.83     | 1.00     | 0.11  

--- TABLE 2: Per-Modality Decomposition ---
Modality (Pages)           | Ent. F1  | Rel. F1  | OTL-Acc 
--------------------------------------------------------
PDF schematic (187)        | 0.90     | 0.85     | 1.00    
XLSX/DOCX tabular (138)    | 0.95     | 0.81     | 1.00    
Mixed text+diagram (87)    | 0.90     | 0.81     | 1.00    
Overall (micro)            | 0.90     | 0.83     | 1.00    

--- TABLE 3: The Deterministic Stack Stage-by-Stage ---
Stage                      | Ent. F1  | OTL-Acc  | Flagged 
--------------------------------------------------------
Raw model output           | 0.84     | 0.88     | -       
+ validation (detect)      | 0.84     | 0.88     | 12.5%   
+ auto-correction          | 0.90     | 1.00     | 0.0%    

--- TABLE 4: Faithfulness Scores for Generated Reports ---
Faithfulness Metric              | B1-Report  | OAG (Ours)
----------------------------------------------------------
Provenance-closure rate (+)      | 0.365      | 1.000     
Hallucinated-attribute rate (-)  | 0.124      | 0.000     
Un-localisable-span rate (-)     | 0.635      | 0.000     

--- TABLE 6: Offline Unit Test Suite Verification (CI Summary) ---
Harness Stage                | Tests    | Execution Time   | API Dependency
------------------------------------------------------------------------
Deterministic Core Tests     | 25/25    | < 0.35s          | 100% Offline  
```

---

### Step 4: Run the End-to-End Pipeline Demonstration

Walk through all 7 stages and Task T2 verbalisation:

```bash
python scripts/run_pipeline_demo.py
```

This processes multimodal completions, performs within-file fusion (Algorithm 1), proposes cross-file duplicates, logs DPO preference triples, generates condition reports with cite-or-abstain grounding, and outputs all 7 delivery formats into `./exports/`.

---

## 5. Python API Usage

```python
from nexus_engine.pipeline import NexusEngine
from nexus_engine.exporter import GraphExporter
from nexus_engine.oag import OAGReportGenerator

# 1. Initialize engine with Flemish OTL constraints
engine = NexusEngine(
    allowed_classes={"Laagspanningsbord", "Camera", "DvmBord"},
    allowed_relations={"feeds", "connected_to", "part_of"}
)

# 2. Raw JSON from multimodal model (with casing & Dutch synonyms)
raw_llm_output = """[
  {"id": "VF06", "class": "laagspanningsbord", "attributes": {"spanning": "400 V"}},
  {"id": "CAM01", "class": "camera", "attributes": {"spanning": "24 V"}}
]"""
raw_edges = [{"source_id": "VF06", "target_id": "CAM01", "relation_type": "voedt"}]

# 3. Process through deterministic verification & fusion stack
graph = engine.process_raw_completions(raw_llm_output, raw_edges)

# 4. Export all 7 delivery formats
exporter = GraphExporter(graph)
manifests = exporter.export_all()
print("Generated Cypher Script:\n", manifests["cypher"])

# 5. Verbalise grounded condition report (Task T2)
oag = OAGReportGenerator(graph)
report = oag.generate_grounded_summary()
print("Grounded Report:\n", report)
```

---

## 6. CLI Usage

The package provides the `nexus-engine` command-line tool:

```bash
# Process raw completions into 7 validated export formats
nexus-engine run -i completions.json -o ./my_exports

# Generate grounded report and gap-analysis RFIs from an OTL graph
nexus-engine report -g ./my_exports/manifest_json.json

# Generate synthetic benchmark data
nexus-engine generate-data -o ./synthetic_corpus
```

---

## 7. Citation

If you use NEXUSENGINE or the NEXUS-INFRA-412 synthetic benchmark in your research, please cite:

```bibtex
@inproceedings{uma2026nexusengine,
  title     = {NexusEngine: Ontology-Constrained, Provenance-Grounded, Multi-Modal Generation for Infrastructure Digital Twins},
  author    = {Uma, Kanimozhi and Vanalderweireldt, Merijn},
  booktitle = {Proceedings of the 19th International Natural Language Generation Conference (INLG 2026)},
  year      = {2026},
  publisher = {Association for Computational Linguistics}
}
```

---

## 8. License Scope & Dependency Compatibility

### License Scope

- **Original Software & Synthetic Fixtures (`Apache-2.0`)**: All original Python source code (`nexus_engine/`, `scripts/`, `tests/`) and the synthetic benchmark artefacts (`nexus_infra_412/`) are licensed under the **Apache License, Version 2.0** (`Copyright 2026 Kanimozhi Uma`). See the [LICENSE](LICENSE) file for the full license text.
- **AWV OTL / OSLO² Vocabulary Definitions**: The domain ontology vocabulary encoded in [`nexus_engine/otl/otl_ontology_complete.json`](nexus_engine/otl/otl_ontology_complete.json) reflects the public **Flemish Agency for Roads and Traffic (Agentschap Wegen en Verkeer — AWV) Object Type Library (OTL v2.11)** and **OSLO²** linked-data standards (`https://wegenenverkeer.data.vlaanderen.be`), which remain governed by Flemish Open Data / OSLO² terms.
- **Third-Party Dependencies**: External Python packages required at runtime or for testing are not bundled in this repository and remain governed by their respective upstream open-source licenses.

### Dependency License Compatibility

All runtime, build, and test dependencies use permissive open-source licenses compatible with Apache License 2.0:

| Package | Version Requirement | License | Apache 2.0 Compatible |
| :--- | :--- | :--- | :--- |
| `pydantic` | `>=2.5.0` | MIT | Yes |
| `networkx` | `>=3.0` | BSD-3-Clause | Yes |
| `pandas` | `>=2.0.0` | BSD-3-Clause | Yes |
| `openpyxl` | `>=3.1.0` | MIT | Yes |
| `pillow` | `>=10.0.0` | MIT-CMU (HPND) | Yes |
| `pytest` | `>=8.0.0` | MIT | Yes |
| `setuptools` | `>=61.0` | MIT | Yes |
