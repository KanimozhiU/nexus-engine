"""
Flemish Object Type Library (OTL) domain model and ontology loader.
Based on AWV OTL v2.11+ / OSLO2 standard for Flemish infrastructure (Agentschap Wegen en Verkeer).
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


DUTCH_TO_ENGLISH_REL_MAP: Dict[str, str] = {
    # Containment / Hierarchical
    "onderdeel_van": "part_of",
    "is_onderdeel_van": "part_of",
    "hoort_bij": "part_of",
    "bestaat_uit": "part_of",
    "contains": "part_of",
    "is_part_of": "part_of",
    # Power / Supply
    "voedt": "feeds",
    "voedt_aangestuurd": "feeds",
    "wordt_gevoed_door": "feeds",
    "powers": "feeds",
    "powered_by": "feeds",
    # Connectivity / Network
    "verbonden_met": "connected_to",
    "sluit_aan_op": "connected_to",
    "verbindt": "connected_to",
    "connects": "connected_to",
    "connects_to": "connected_to",
    # Monitoring / Surveillance
    "bewaakt": "monitors",
    "monitored_by": "monitors",
    "observeert": "monitors",
    # Control / Steering
    "stuurt": "controls",
    "sturing": "controls",
    "controleert": "controls",
    # Data flow
    "zendt_data_naar": "sends_data_to",
    "sends_data_to": "sends_data_to",
    # Location / Mounting
    "bevindt_zich_in": "located_in",
    "ligt_op": "located_in",
    "bevestiging": "attached_to",
}

CANONICAL_RELATIONS: Set[str] = {
    "part_of",
    "feeds",
    "connected_to",
    "monitors",
    "controls",
    "sends_data_to",
    "located_in",
    "attached_to",
}

NUMERIC_ATTRIBUTES: Set[str] = {
    "vermogen",
    "spanning",
    "lengte",
    "voltage",
    "power",
    "length",
    "stroom",
    "current",
    "frequentie",
    "frequency",
    "diameter",
    "hoogte",
    "height",
    "breedte",
    "width",
    "x_coord",
    "y_coord",
    "z_coord",
    "position_x",
    "position_y",
    "position_z",
}

DEFAULT_OTL_CLASSES: Set[str] = {
    "Laagspanningsbord",
    "Stuurkast",
    "Camera",
    "DvmBord",
    "Verkeersas",
    "Rioleringsstelsel",
    "Rioleringsbuis",
    "Put",
    "Inspectieput",
    "Kolk",
    "Seinbrug",
    "Seinstelsel",
    "MIVLus",
    "Glasvezelkabel",
    "Netwerkcomponent",
    "Wegkantkast",
    "WegkantSwitch",
    "Verlichtingstoestel",
    "Lichtmast",
    "Dienstgebouw",
    "Tunnelwand",
    "Wegtunnel",
    "Kabeltrace",
    "Wachtbuis",
    "OnbekendAsset",
}


class OTLDefinition:
    """Encapsulates the authoritative OTL schema and retrieval capabilities."""

    def __init__(
        self,
        classes: Optional[Set[str]] = None,
        relations: Optional[Set[str]] = None,
        json_path: Optional[str] = None,
    ):
        self.classes: Set[str] = set(classes) if classes else set(DEFAULT_OTL_CLASSES)
        self.relations: Set[str] = set(relations) if relations else set(CANONICAL_RELATIONS)
        self.raw_ontology: Dict[str, Any] = {}

        # Attempt to load rich JSON ontology if present
        if json_path and os.path.exists(json_path):
            self.load_from_json(json_path)
        else:
            default_json = Path(__file__).parent / "otl_ontology_complete.json"
            if default_json.exists():
                self.load_from_json(str(default_json))

    def load_from_json(self, json_path: str) -> None:
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                self.raw_ontology = json.load(f)

            # Extract asset classes
            categories = self.raw_ontology.get("asset_categories", {})
            for cat_data in categories.values():
                for cls_name in cat_data.get("classes", []):
                    # Clean PascalCase class names
                    clean_name = re.sub(r"[-_\s]+", "", cls_name).capitalize()
                    self.classes.add(clean_name)
                    self.classes.add(cls_name)

            # Extract relationships
            for rel in self.raw_ontology.get("relationships", []):
                rel_name = rel.get("name", "") if isinstance(rel, dict) else str(rel)
                canon = DUTCH_TO_ENGLISH_REL_MAP.get(rel_name.lower(), rel_name.lower())
                self.relations.add(canon)
        except Exception:
            pass

    def retrieve_relevant_classes(self, context_text: str, k: int = 40) -> List[str]:
        """
        Ontology-retrieval conditioning (Section 4.6).
        Injects the k live OTL classes most similar to a query chunk context.
        """
        context_lower = context_text.lower()
        scored: List[Tuple[float, str]] = []

        tokens = re.findall(r"\w+", context_lower)
        token_set = set(tokens)

        for cls in sorted(self.classes):
            cls_lower = cls.lower()
            score = 0.0

            # Substring match in context
            if cls_lower in context_lower:
                score += 5.0

            # Token overlap
            cls_tokens = re.findall(r"[A-Z]?[a-z]+", cls)
            for ct in cls_tokens:
                ct_l = ct.lower()
                if ct_l in token_set:
                    score += 2.0
                elif any(ct_l in t or t in ct_l for t in token_set if len(t) >= 4):
                    score += 1.0

            scored.append((score, cls))

        # Sort by score descending, then alphabetically
        scored.sort(key=lambda x: (-x[0], x[1]))
        top_k = [cls for _, cls in scored[:k]]
        return top_k


_GLOBAL_OTL: Optional[OTLDefinition] = None


def get_default_otl() -> OTLDefinition:
    global _GLOBAL_OTL
    if _GLOBAL_OTL is None:
        _GLOBAL_OTL = OTLDefinition()
    return _GLOBAL_OTL

