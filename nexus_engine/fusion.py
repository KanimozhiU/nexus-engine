"""
Stage 5: Within-file Fusion (Algorithm 1)
Stage 6: Cross-file Human-in-the-Loop (HITL) Matcher & DPO Preference Collector
"""
import re
from typing import Any, Dict, List, Set, Tuple
from nexus_engine.models import AssetNode, DPOPreferenceTriple, InfrastructureGraph, Relation


def normalize_label(label: str) -> str:
    """Lower-cases and strips whitespace, hyphens, and underscores."""
    if not label:
        return ""
    return re.sub(r"[\s\-_]+", "", str(label).lower())


def within_file_fusion(nodes: List[AssetNode], edges: List[Relation]) -> InfrastructureGraph:
    """
    Implements Algorithm 1 from the paper (Section 4, Page 13):
    1: G <- GROUPBY(A, h or norm(l))
    4: a* <- argmax |a.attrs| * mean_confidence(a)
    6: a*.attrs <- a*.attrs U a.attrs
    7: a*.prov <- a*.prov U a.prov
    8: M[a.id] <- a*.id
    12: Rewrite all e.source and e.target via M; drop self-edges.
    """
    groups: Dict[str, List[AssetNode]] = {}
    for node in nodes:
        key = node.hierarchical_id if node.hierarchical_id else normalize_label(node.id)
        groups.setdefault(key, []).append(node)

    fused_nodes: Dict[str, AssetNode] = {}
    id_redirect_map: Dict[str, str] = {}

    for _, group in groups.items():
        # Select primary candidate a*
        primary = max(group, key=lambda a: (len(a.attributes) + 1) * a.mean_confidence)
        id_redirect_map[primary.id] = primary.id

        # Merge subordinates
        for sub in group:
            if sub.id == primary.id:
                continue
            id_redirect_map[sub.id] = primary.id

            # Merge attributes (primary takes precedence for conflicts)
            for k, v in sub.attributes.items():
                if k not in primary.attributes:
                    primary.attributes[k] = v

            # Merge evidence provenance
            for p in sub.provenance:
                if p not in primary.provenance:
                    primary.provenance.append(p)

            # Propagate validation issues
            for iss in sub.validation_issues:
                if iss not in primary.validation_issues:
                    primary.validation_issues.append(iss)

        fused_nodes[primary.id] = primary

    # Step 12: rewrite relations and drop self-edges
    fused_edges: List[Relation] = []
    seen_triples: Set[Tuple[str, str, str]] = set()

    for edge in edges:
        new_src = id_redirect_map.get(edge.source_id, edge.source_id)
        new_tgt = id_redirect_map.get(edge.target_id, edge.target_id)
        if new_src == new_tgt:
            continue  # Drop self-edges created by fusion

        triple = (new_src, edge.relation_type, new_tgt)
        if triple not in seen_triples:
            seen_triples.add(triple)
            fused_edges.append(
                Relation(
                    source_id=new_src,
                    target_id=new_tgt,
                    relation_type=edge.relation_type,
                    confidence=edge.confidence,
                    provenance=edge.provenance,
                )
            )

    return InfrastructureGraph(nodes=fused_nodes, edges=fused_edges)


class CrossFileHITLFusion:
    """Proposes cross-file candidate duplicates and records DPO preference triples."""

    @staticmethod
    def propose_merges(graphs: List[InfrastructureGraph]) -> List[List[AssetNode]]:
        """
        Groups assets across multiple documents by normalized label.
        Returns clusters of size >= 2 for human review in FusionView.
        """
        clusters: Dict[str, List[AssetNode]] = {}
        for g in graphs:
            for node in g.nodes.values():
                key = normalize_label(node.id)
                clusters.setdefault(key, []).append(node)

        return [cluster for cluster in clusters.values() if len(cluster) >= 2]

    @staticmethod
    def record_dpo_preference(
        context: str,
        accepted_merge: Dict[str, Any],
        rejected_merge: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Emits a DPO-ready JSONL training record (Section 4.5)."""
        triple = DPOPreferenceTriple(
            context=context,
            accepted=accepted_merge,
            rejected=rejected_merge,
        )
        return triple.model_dump()

