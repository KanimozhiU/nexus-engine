"""
End-to-End Orchestrator Pipeline (NexusEngine).
Ties together Stage 1 (Ingestion) through Stage 7 (Exporters)
with bounded verify-and-repair loop and ontology-retrieval conditioning.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
from nexus_engine.bitemporal import BitemporalStore
from nexus_engine.exporter import GraphExporter
from nexus_engine.fusion import CrossFileHITLFusion, within_file_fusion
from nexus_engine.models import AssetNode, InfrastructureGraph, Relation
from nexus_engine.oag import OAGReportGenerator
from nexus_engine.otl.ontology import (
    DEFAULT_OTL_CLASSES,
    CANONICAL_RELATIONS,
    OTLDefinition,
    get_default_otl,
)
from nexus_engine.prompts import build_chunk_prompt
from nexus_engine.sanitizer import normalise_asset_payload, recover_malformed_json
from nexus_engine.validator import OTLValidator


class NexusEngine:
    """
    Production orchestrator for ontology-constrained, provenance-grounded digital twins.
    """

    def __init__(
        self,
        allowed_classes: Optional[Set[str]] = None,
        allowed_relations: Optional[Set[str]] = None,
        otl_def: Optional[OTLDefinition] = None,
    ):
        self.otl = otl_def or get_default_otl()
        self.classes = allowed_classes if allowed_classes is not None else self.otl.classes
        self.relations = allowed_relations if allowed_relations is not None else self.otl.relations
        self.validator = OTLValidator(self.classes, self.relations)
        self.bitemporal_store = BitemporalStore()

    def retrieve_ontology_classes(self, context_text: str, k: int = 40) -> List[str]:
        """Injects k most relevant OTL classes into prompt (Section 4.6)."""
        return self.otl.retrieve_relevant_classes(context_text, k=k)

    def process_raw_completions(
        self,
        raw_completion: str,
        raw_edges: Optional[List[Dict[str, Any]]] = None,
        max_repair_iterations: int = 2,
    ) -> InfrastructureGraph:
        """
        Executes Stages 2 -> 3 -> 4 -> 5:
        - Rung 1-3 JSON recovery ladder
        - Idempotent normalisation (field enforcement, surrogate IDs)
        - Deterministic OTL validation & auto-correction (R1-R5)
        - Bounded verify-and-repair loop (k <= 2)
        - Within-file fusion (Algorithm 1)
        """
        if raw_edges is None:
            raw_edges = []

        # Step 2 -> 3: Recovery ladder & normalisation
        parsed_nodes = recover_malformed_json(raw_completion)
        sanitised_nodes = normalise_asset_payload(parsed_nodes)

        # Step 4: Deterministic validation & repair
        valid_nodes, valid_edges = self.validator.validate_and_repair(
            sanitised_nodes, raw_edges
        )

        # Bounded verify-and-repair loop on hard violations (Section 4.3, k <= 2)
        iterations = 0
        repair_telemetry = {
            "initial_hard_violations": 0,
            "repaired_count": 0,
            "iterations": 0
        }

        while iterations < max_repair_iterations:
            hard_violations = [
                n for n in valid_nodes
                if any(iss.startswith("R1:") or iss.startswith("R2:") for iss in n.validation_issues)
            ]
            if iterations == 0:
                repair_telemetry["initial_hard_violations"] = len(hard_violations)

            if not hard_violations:
                break

            # Execute active deterministic repair on hard violations
            valid_nodes = self.validator.repair_hard_violations(valid_nodes)
            repair_telemetry["repaired_count"] += len(hard_violations)
            iterations += 1

        repair_telemetry["iterations"] = iterations
        self.last_repair_telemetry = repair_telemetry

        # Step 5: Within-file fusion (Algorithm 1)
        graph = within_file_fusion(valid_nodes, valid_edges)
        return graph

    def process_multiple_documents(
        self,
        document_completions: List[Tuple[str, List[Dict[str, Any]]]],
    ) -> Tuple[InfrastructureGraph, List[List[AssetNode]]]:
        """
        Processes chunks in parallel, fuses within-file, and proposes cross-file merges (Stage 6).
        """
        per_doc_graphs: List[InfrastructureGraph] = []
        for raw_nodes_str, raw_edges in document_completions:
            g = self.process_raw_completions(raw_nodes_str, raw_edges)
            per_doc_graphs.append(g)

        # Propose cross-file duplicate candidates for HITL review
        merge_proposals = CrossFileHITLFusion.propose_merges(per_doc_graphs)

        # Aggregate nodes and edges
        all_nodes = [node for g in per_doc_graphs for node in g.nodes.values()]
        all_edges = [edge for g in per_doc_graphs for edge in g.edges]

        # Final unified fusion
        unified_graph = within_file_fusion(all_nodes, all_edges)
        return unified_graph, merge_proposals

    def export_graph(self, graph: InfrastructureGraph) -> Dict[str, str]:
        """Emits all 7 operational delivery formats (Stage 7)."""
        exporter = GraphExporter(graph)
        return exporter.export_all()

    def generate_report(self, graph: InfrastructureGraph) -> str:
        """Verbalises grounded report under cite-or-abstain contract (Task T2)."""
        oag = OAGReportGenerator(graph)
        return oag.generate_grounded_summary()

