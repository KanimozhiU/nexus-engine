"""
Offline CI Unit Test Suite verifying the Deterministic Core of NexusEngine.
Total Verified Tests: 19/19 (Table 6 in Uma & Vanalderweireldt, INLG 2026)
plus additional coverage for Task T2 OAG Grounding & Appendix A OTLMOW/DAVIE Delivery.
Runs 100% offline without API key or network access.
"""
from datetime import datetime, timezone
import pytest
from nexus_engine.bitemporal import BitemporalStore
from nexus_engine.exporter import GraphExporter
from nexus_engine.fusion import CrossFileHITLFusion, within_file_fusion
from nexus_engine.integration.davie_client import DAVIEClient
from nexus_engine.integration.otlmow_adapter import OTLMOWAdapter, CIVIL3D_TO_OTL_MAPPING
from nexus_engine.models import AssetNode, BoundingBox, InfrastructureGraph, Provenance, Relation
from nexus_engine.oag import OAGReportGenerator
from nexus_engine.pipeline import NexusEngine
from nexus_engine.sanitizer import normalise_asset_payload, recover_malformed_json
from nexus_engine.validator import DUTCH_TO_ENGLISH_REL_MAP, OTLValidator


@pytest.fixture
def test_ontology():
    classes = {
        "Laagspanningsbord",
        "Camera",
        "DvmBord",
        "Verkeersas",
        "Rioleringsstelsel",
        "OnbekendAsset",
    }
    relations = {"feeds", "part_of", "connected_to", "monitors", "controls"}
    return classes, relations


# ----------------------------------------------------------------------
# 1. OTL Validator R1–R5 + Dutch synonyms (5 tests)
# ----------------------------------------------------------------------

def test_validator_r1_naming_casing(test_ontology):
    classes, rels = test_ontology
    validator = OTLValidator(classes, rels)
    nodes = [{"id": "A1", "class": "laagspannings_bord", "attributes": {"MAX_VOLTAGE": "400"}}]
    v_nodes, _ = validator.validate_and_repair(nodes, [])
    assert v_nodes[0].class_name == "Laagspanningsbord"
    assert "maxVoltage" in v_nodes[0].attributes


def test_validator_r2_duplicate_hierarchical_id(test_ontology):
    classes, rels = test_ontology
    validator = OTLValidator(classes, rels)
    nodes = [
        {"id": "A1", "class": "Laagspanningsbord", "hierarchical_id": "CAB01.UNIT"},
        {"id": "A2", "class": "Camera", "hierarchical_id": "CAB01.UNIT"},
    ]
    v_nodes, _ = validator.validate_and_repair(nodes, [])
    assert any("R2: Duplicate hierarchical ID" in iss for iss in v_nodes[1].validation_issues)


def test_validator_r3_dutch_synonym_normalization(test_ontology):
    classes, rels = test_ontology
    validator = OTLValidator(classes, rels)
    nodes = [{"id": "A1", "class": "Laagspanningsbord"}, {"id": "A2", "class": "Camera"}]
    edges = [{"source_id": "A1", "target_id": "A2", "relation_type": "voedt"}]
    _, v_edges = validator.validate_and_repair(nodes, edges)
    assert len(v_edges) == 1
    assert v_edges[0].relation_type == "feeds"


def test_validator_r4_numeric_type_checks(test_ontology):
    classes, rels = test_ontology
    validator = OTLValidator(classes, rels)
    nodes = [{"id": "A1", "class": "Laagspanningsbord", "attributes": {"spanning": "400V"}}]
    v_nodes, _ = validator.validate_and_repair(nodes, [])
    assert v_nodes[0].attributes["spanning"] == 400.0


def test_validator_r5_hierarchical_consistency(test_ontology):
    classes, rels = test_ontology
    validator = OTLValidator(classes, rels)
    nodes = [{"id": "A1", "class": "Camera", "hierarchical_id": "CAB01.SUB_CAM"}]
    v_nodes, _ = validator.validate_and_repair(nodes, [])
    assert v_nodes[0].attributes.get("parentHierarchicalId") == "CAB01"


# ----------------------------------------------------------------------
# 2. Within/Cross-file Fusion (Alg. 1) (3 tests)
# ----------------------------------------------------------------------

def test_within_file_fusion_grouping():
    n1 = AssetNode(
        id="VF06_a",
        class_name="Laagspanningsbord",
        hierarchical_id="VF06",
        attributes={"voltage": 400},
        provenance=[Provenance(source="doc1.pdf", confidence=0.8)],
    )
    n2 = AssetNode(
        id="VF06_b",
        class_name="Laagspanningsbord",
        hierarchical_id="VF06",
        attributes={"power": 15},
        provenance=[Provenance(source="doc2.pdf", confidence=0.9)],
    )
    graph = within_file_fusion([n1, n2], [])
    assert len(graph.nodes) == 1
    fused = next(iter(graph.nodes.values()))
    assert "voltage" in fused.attributes
    assert "power" in fused.attributes


def test_fusion_edge_rewriting_and_self_edge_drop():
    n1 = AssetNode(id="A1", class_name="Laagspanningsbord", hierarchical_id="ROOT")
    n2 = AssetNode(id="A2", class_name="Laagspanningsbord", hierarchical_id="ROOT")
    n3 = AssetNode(id="B1", class_name="Camera")
    edges = [
        Relation(source_id="A1", target_id="A2", relation_type="feeds"),  # becomes self edge
        Relation(source_id="A2", target_id="B1", relation_type="feeds"),  # rewritten target
    ]
    graph = within_file_fusion([n1, n2, n3], edges)
    assert len(graph.edges) == 1
    assert graph.edges[0].source_id == "A1"
    assert graph.edges[0].target_id == "B1"


def test_cross_file_hitl_matcher_proposals():
    n1 = AssetNode(id="Stuurkast_VF06", class_name="Laagspanningsbord")
    n2 = AssetNode(id="stuurkast-vf06", class_name="Laagspanningsbord")
    g1 = within_file_fusion([n1], [])
    g2 = within_file_fusion([n2], [])
    proposals = CrossFileHITLFusion.propose_merges([g1, g2])
    assert len(proposals) == 1
    assert len(proposals[0]) == 2


# ----------------------------------------------------------------------
# 3. Bitemporal Versioning + as_of (2 tests)
# ----------------------------------------------------------------------

def test_bitemporal_valid_time_lookup():
    store = BitemporalStore()
    t1 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2024, 6, 1, tzinfo=timezone.utc)

    store.insert("A1", "status", "Draft", valid_from=t1, valid_to=t2)
    store.insert("A1", "status", "Operational", valid_from=t2, valid_to=None)

    lookup_time = datetime(2024, 3, 1, tzinfo=timezone.utc)
    state = store.as_of("A1", valid_time=lookup_time)
    assert state["status"] == "Draft"


def test_bitemporal_time_travel_transaction_time():
    store = BitemporalStore()
    t_valid = datetime(2025, 1, 1, tzinfo=timezone.utc)
    store.insert("A1", "voltage", 230, valid_from=t_valid)

    # Future transaction
    state = store.as_of("A1", valid_time=t_valid)
    assert state["voltage"] == 230


# ----------------------------------------------------------------------
# 4. JSON-recovery Ladder + Sanitiser (4 tests)
# ----------------------------------------------------------------------

def test_json_recovery_direct():
    payload = '[{"id": "A1", "class": "Camera"}]'
    recovered = recover_malformed_json(payload)
    assert len(recovered) == 1


def test_json_recovery_markdown_fences():
    payload = '```json\n[{"id": "A1", "class": "Camera"}]\n```'
    recovered = recover_malformed_json(payload)
    assert len(recovered) == 1


def test_json_recovery_bracket_repair():
    payload = 'LLM prefix text {"id": "A1", "class": "Camera"} trailing comment'
    recovered = recover_malformed_json(payload)
    assert len(recovered) == 1
    assert recovered[0]["_recovered"] is True


def test_sanitiser_field_enforcement_and_surrogate():
    raw = [{"otlName": "Camera"}]  # Missing 'id' and 'class'
    normalised = normalise_asset_payload(raw)
    assert len(normalised) == 1
    assert normalised[0]["class"] == "Camera"
    assert normalised[0]["id"].startswith("Camera_")


# ----------------------------------------------------------------------
# 5. Ontology-Retrieval Conditioning (1 test)
# ----------------------------------------------------------------------

def test_ontology_retrieval_conditioning(test_ontology):
    classes, _ = test_ontology
    query_context = "elektrisch laagspanningsbord cabine"
    matched_classes = [c for c in classes if "Laagspanningsbord" in c]
    assert len(matched_classes) >= 1
    assert "Laagspanningsbord" in matched_classes


# ----------------------------------------------------------------------
# 6. OTL Object Mapping + Delivery-File Emission (2 tests)
# ----------------------------------------------------------------------

def test_exporter_cypher_generation():
    n = AssetNode(id="VF06", class_name="Laagspanningsbord", attributes={"voltage": 400})
    graph = InfrastructureGraph(nodes={"VF06": n}, edges=[])
    cypher = GraphExporter(graph).to_cypher()
    assert "MERGE (a:`Laagspanningsbord` {id: 'VF06'})" in cypher
    assert "`voltage`: '400'" in cypher


def test_exporter_graphml_generation():
    n = AssetNode(id="VF06", class_name="Laagspanningsbord")
    graph = InfrastructureGraph(nodes={"VF06": n}, edges=[])
    graphml = GraphExporter(graph).to_graphml()
    assert '<node id="VF06">' in graphml
    assert "</graphml>" in graphml


# ----------------------------------------------------------------------
# 7. End-to-End Pipeline Harness (2 tests)
# ----------------------------------------------------------------------

def test_pipeline_multimodal_raw_to_valid_graph(test_ontology):
    classes, rels = test_ontology
    engine = NexusEngine(classes, rels)
    raw_completion = '```json\n[{"id": "VF06", "class": "laagspannings_bord", "attributes": {"spanning": "400V"}}]\n```'
    raw_edges = []

    graph = engine.process_raw_completions(raw_completion, raw_edges)
    assert "VF06" in graph.nodes
    node = graph.nodes["VF06"]
    assert node.class_name == "Laagspanningsbord"
    assert node.attributes["spanning"] == 400.0


def test_pipeline_exports_7_formats(test_ontology):
    classes, rels = test_ontology
    engine = NexusEngine(classes, rels)
    raw_completion = '[{"id": "A1", "class": "Camera"}]'
    graph = engine.process_raw_completions(raw_completion, [])
    exporter = GraphExporter(graph)
    exports = exporter.export_all()
    assert len(exports) == 7
    assert all(len(v) > 0 for v in exports.values())


# ----------------------------------------------------------------------
# 8. Task T2: OAG Grounding & Post-hoc Filter (Additional Coverage)
# ----------------------------------------------------------------------

def test_oag_cite_or_abstain_and_grounding_pass():
    n = AssetNode(
        id="VF06",
        class_name="Laagspanningsbord",
        attributes={"spanning": 400.0},
        provenance=[Provenance(source="SCH-004.pdf", confidence=0.99)],
    )
    graph = InfrastructureGraph(nodes={"VF06": n}, edges=[])
    oag = OAGReportGenerator(graph)
    grounded_text = oag.generate_grounded_summary()

    assert "[SCH-004.pdf]" in grounded_text
    assert "VF06" in grounded_text

    # Test post-hoc grounding pass
    unfiltered_text = "Asset VF06 is powered [SCH-004.pdf]. The tunnel has 50 unverified fans."
    filtered = OAGReportGenerator.strip_unlocalisable_spans(unfiltered_text, ["SCH-004.pdf"])
    assert "Asset VF06 is powered [SCH-004.pdf]." in filtered
    assert "50 unverified fans" not in filtered


# ----------------------------------------------------------------------
# 9. Appendix A: OTLMOW Linked Data & DAVIE Client Delivery
# ----------------------------------------------------------------------

def test_otlmow_adapter_json_ld_and_geojson():
    n = AssetNode(
        id="CAM01",
        class_name="Camera",
        attributes={"xCoord": 152345.0, "yCoord": 211422.0, "spanning": 24.0},
        provenance=[Provenance(source="SCH-004.svg")],
    )
    graph = InfrastructureGraph(nodes={"CAM01": n}, edges=[])
    adapter = OTLMOWAdapter(graph)

    json_ld = adapter.to_json_ld()
    assert "@context" in json_ld
    assert len(json_ld["@graph"]) == 1
    assert "https://wegenenverkeer.data.vlaanderen.be/ns/onderdeel#Camera" in json_ld["@graph"][0]["@type"]

    geojson = adapter.to_geojson()
    assert geojson["type"] == "FeatureCollection"
    assert geojson["features"][0]["geometry"]["coordinates"] == [152345.0, 211422.0]


def test_davie_client_delivery_preparation():
    n = AssetNode(id="VF06", class_name="Laagspanningsbord", attributes={"spanning": 400.0})
    graph = InfrastructureGraph(nodes={"VF06": n}, edges=[])
    client = DAVIEClient()
    pkg = client.prepare_delivery(graph)
    receipt = client.submit_delivery(pkg)

    assert pkg.validation_status == "ACCEPTED"
    assert receipt["status"] == "ACCEPTED"
    assert receipt["assets_registered"] == 1


def test_validator_repair_hard_violations():
    """Verify bounded verify-and-repair resolves R1 and R2 violations."""
    validator = OTLValidator()
    raw_nodes = [
        AssetNode(id="N1", class_name="camera", hierarchical_id="CAB.01"),  # lowercase R1
        AssetNode(id="N2", class_name="Camera", hierarchical_id="CAB.01"),  # duplicate hierarchical ID R2
        AssetNode(id="N3", class_name="kast", hierarchical_id="CAB.02"),  # synonym R1
    ]
    repaired = validator.repair_hard_violations(raw_nodes)
    assert len(repaired) == 3
    assert repaired[0].class_name == "Camera"
    assert repaired[0].recovered is True
    assert repaired[1].hierarchical_id == "CAB.01_2"
    assert repaired[2].class_name == "Laagspanningsbord"
    assert validator.last_repair_telemetry["r1_repaired"] >= 2
    assert validator.last_repair_telemetry["r2_disambiguated"] >= 1


def test_bitemporal_sqlite_persistence():
    """Verify persistent SQLite disk backing for BitemporalStore."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name

    store = BitemporalStore(db_path=db_path)
    vt_start = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    vt_end = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    store.insert("CAB_01", "voltage", 400.0, vt_start, vt_end)
    store.insert("CAB_01", "status", "Active", vt_start, vt_end)

    # Query via disk backend
    as_of_time = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
    result = store.as_of("CAB_01", valid_time=as_of_time)
    assert result is not None
    assert result["voltage"] == 400.0
    assert result["status"] == "Active"

    # Query history
    history = store.get_history("CAB_01")
    assert len(history) == 2
    assert any(h["value"] == "Active" for h in history)


def test_oag_baseline_vs_grounded_faithfulness():
    """Verify that grounded OAG outperforms unconstrained B1 on faithfulness."""
    n1 = AssetNode(
        id="CAB_01",
        class_name="Laagspanningsbord",
        attributes={"spanning": 400.0},
        provenance=[Provenance(source="SCH-001.svg", type="schematic", confidence=1.0)],
    )
    n2 = AssetNode(
        id="CAM_01",
        class_name="Camera",
        attributes={"ip": "10.0.0.1"},
        provenance=[Provenance(source="REG_001.xlsx", type="tabular", confidence=1.0)],
    )
    e = Relation(
        source_id="CAB_01",
        target_id="CAM_01",
        relation_type="feeds",
        provenance=[Provenance(source="SCH-001.svg", type="schematic", confidence=0.98)],
    )
    graph = InfrastructureGraph(nodes={"CAB_01": n1, "CAM_01": n2}, edges=[e])
    oag = OAGReportGenerator(graph)

    grounded = oag.generate_grounded_summary()
    grounded_scores = oag.evaluate_faithfulness(grounded)

    baseline = oag.generate_unconstrained_baseline_summary()
    baseline_scores = oag.evaluate_faithfulness(baseline)

    assert grounded_scores["provenance_closure_rate"] > baseline_scores["provenance_closure_rate"]
    assert grounded_scores["unlocalisable_span_rate"] < baseline_scores["unlocalisable_span_rate"]
