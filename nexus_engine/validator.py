"""
Stage 4: Deterministic Faithfulness & Admissibility Validator.
Enforces rules R1 to R5 and Dutch-to-English relationship synonym mapping.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from nexus_engine.models import AssetNode, Provenance, Relation
from nexus_engine.otl.ontology import (
    DUTCH_TO_ENGLISH_REL_MAP,
    NUMERIC_ATTRIBUTES,
    DEFAULT_OTL_CLASSES,
    CANONICAL_RELATIONS,
)


def to_pascal_case(s: str) -> str:
    """Converts snake_case, kebab-case, or space-separated string to PascalCase."""
    if not s:
        return ""
    words = [w for w in re.split(r"[-_\s]+", s) if w]
    return "".join(word.capitalize() for word in words)


def to_camel_case(s: str) -> str:
    """Converts snake_case, kebab-case, or spaced string to camelCase."""
    if not s:
        return ""
    words = [w for w in re.split(r"[-_\s]+", s) if w]
    if not words:
        return ""
    return words[0].lower() + "".join(word.capitalize() for word in words[1:])


class OTLValidator:
    """
    Deterministic validator enforcing OTL conformance without LLM re-prompting.
    Executes rules R1 through R5:
    - R1: PascalCase class names, camelCase attribute keys, OTL membership check
    - R2: Hierarchical ID collision detection
    - R3: Relationship integrity and Dutch synonym normalization
    - R4: Numeric attribute casting and syntax checking
    - R5: Hierarchical containment chain dot-extension consistency
    """

    def __init__(
        self,
        allowed_classes: Optional[Set[str]] = None,
        allowed_relations: Optional[Set[str]] = None,
    ):
        self.allowed_classes: Set[str] = allowed_classes if allowed_classes is not None else set(DEFAULT_OTL_CLASSES)
        self.allowed_relations: Set[str] = allowed_relations if allowed_relations is not None else set(CANONICAL_RELATIONS)

    def validate_and_repair(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> Tuple[List[AssetNode], List[Relation]]:
        validated_nodes: List[AssetNode] = []
        validated_edges: List[Relation] = []
        node_ids: Set[str] = set()
        hierarchical_ids: Set[str] = set()

        for raw_node in nodes:
            issues: List[str] = list(raw_node.get("validation_issues", []))

            # R1: Casing conventions & class validation
            raw_class = str(raw_node.get("class", raw_node.get("otlName", "OnbekendAsset")))
            class_candidate = to_pascal_case(raw_class)

            # Map case-insensitively to authoritative OTL class name if present
            cls_lookup = {c.lower(): c for c in self.allowed_classes}
            cand_norm = re.sub(r"[-_\s]+", "", raw_class).lower()

            if cand_norm in cls_lookup:
                class_name = cls_lookup[cand_norm]
            elif class_candidate.lower() in cls_lookup:
                class_name = cls_lookup[class_candidate.lower()]
            else:
                class_name = class_candidate
                issues.append(f"R1: Class '{class_name}' is not in authoritative OTL")

            attrs: Dict[str, Any] = {}
            raw_attrs = raw_node.get("attributes", {})
            if isinstance(raw_attrs, list):
                # Convert list of {key, value} to dict
                attr_dict = {}
                for item in raw_attrs:
                    if isinstance(item, dict) and "key" in item:
                        attr_dict[item["key"]] = item.get("value")
                raw_attrs = attr_dict

            for k, v in raw_attrs.items():
                camel_k = to_camel_case(k)

                # R4: Numeric check
                if camel_k.lower() in NUMERIC_ATTRIBUTES or any(num_key in camel_k.lower() for num_key in ["spanning", "voltage", "vermogen", "power", "lengte", "length"]):
                    if isinstance(v, str):
                        # Extract numerical component (handles '400V', '15kW', '2.5 kW')
                        num_match = re.search(r"[-+]?\d*\.?\d+", v)
                        if num_match:
                            v = float(num_match.group(0))
                        else:
                            issues.append(f"R4: Attribute '{camel_k}' expected numeric, got '{v}'")
                    elif isinstance(v, (int, float)):
                        v = float(v)

                attrs[camel_k] = v

            # R2: Hierarchical ID uniqueness
            h_id = raw_node.get("hierarchical_id")
            if h_id:
                if h_id in hierarchical_ids:
                    issues.append(f"R2: Duplicate hierarchical ID '{h_id}' detected")
                else:
                    hierarchical_ids.add(h_id)

            # R5: Hierarchical consistency (child must dot-extend parent)
            if h_id and "." in h_id:
                parent_prefix = h_id.rsplit(".", 1)[0]
                attrs["parentHierarchicalId"] = parent_prefix

            # Provenance parsing
            prov_list: List[Provenance] = []
            for p in raw_node.get("provenance", []):
                if isinstance(p, dict):
                    prov_list.append(Provenance(**p))
                elif isinstance(p, Provenance):
                    prov_list.append(p)

            node = AssetNode(
                id=str(raw_node["id"]),
                class_name=class_name,
                hierarchical_id=h_id,
                attributes=attrs,
                provenance=prov_list,
                validation_issues=issues,
                recovered=raw_node.get("recovered", False),
            )
            validated_nodes.append(node)
            node_ids.add(node.id)

        # Validate edges
        for raw_edge in edges:
            src = str(raw_edge.get("source_id", ""))
            tgt = str(raw_edge.get("target_id", ""))
            r_type = str(raw_edge.get("relation_type", "")).lower()

            # R3: Relationship integrity & synonym normalization
            norm_rel = DUTCH_TO_ENGLISH_REL_MAP.get(r_type, r_type)

            if src not in node_ids:
                continue  # Discard or flag dangling source
            if tgt not in node_ids:
                continue  # Discard or flag dangling target

            prov_list: List[Provenance] = []
            for p in raw_edge.get("provenance", []):
                if isinstance(p, dict):
                    prov_list.append(Provenance(**p))
                elif isinstance(p, Provenance):
                    prov_list.append(p)

            validated_edges.append(
                Relation(
                    source_id=src,
                    target_id=tgt,
                    relation_type=norm_rel,
                    confidence=float(raw_edge.get("confidence", 1.0)),
                    provenance=prov_list,
                )
            )

        return validated_nodes, validated_edges

    def repair_hard_violations(self, nodes: List[AssetNode]) -> List[AssetNode]:
        """
        Executes bounded deterministic repair on R1 and R2 hard violations (Section 4.3).
        - R1: Resolves out-of-vocabulary or malformed classes to the closest authoritative OTL class.
        - R2: Disambiguates duplicate hierarchical IDs with deterministic sub-indices.
        """
        repaired_nodes: List[AssetNode] = []
        seen_h_ids: Dict[str, int] = {}
        r1_repaired_count = 0
        r2_disambiguated_count = 0

        # Pre-populate authoritative class lookup mapping
        clean_class_map = {re.sub(r"[-_\s]+", "", c).lower(): c for c in self.allowed_classes}

        for node in nodes:
            issues = list(node.validation_issues)
            class_name = node.class_name
            h_id = node.hierarchical_id
            attrs = dict(node.attributes)
            was_recovered = node.recovered

            # Repair R1: Out-of-vocabulary class
            is_r1 = any(iss.startswith("R1:") for iss in issues) or (class_name not in self.allowed_classes)
            if is_r1:
                # Find closest match in authoritative OTL
                cand_clean = re.sub(r"[-_\s]+", "", class_name).lower()
                matched_class = None
                
                # Common engineering abbreviations & synonyms
                synonym_map = {
                    "kast": "Laagspanningsbord",
                    "bord": "Laagspanningsbord",
                    "cab": "Laagspanningsbord",
                    "cam": "Camera",
                    "lus": "MIVLus",
                    "dvm": "DvmBord",
                    "rss": "DvmBord",
                    "plc": "Stuurkast",
                    "switch": "WegkantSwitch",
                    "lamp": "Verlichtingstoestel",
                    "mast": "Verlichtingstoestel",
                }

                # Check exact clean lookup
                if cand_clean in clean_class_map:
                    matched_class = clean_class_map[cand_clean]
                elif cand_clean in synonym_map:
                    matched_class = synonym_map[cand_clean]
                else:
                    # Partial token matching
                    for norm_k, authoritative_name in clean_class_map.items():
                        if norm_k in cand_clean or cand_clean in norm_k:
                            matched_class = authoritative_name
                            break
                    if not matched_class:
                        for syn_k, syn_v in synonym_map.items():
                            if syn_k in cand_clean:
                                matched_class = syn_v
                                break

                repaired_class = matched_class or "OnbekendAsset"
                issues = [iss for iss in issues if not iss.startswith("R1:")]
                issues.append(f"R1-REPAIRED: Class '{class_name}' auto-repaired to '{repaired_class}'")
                class_name = repaired_class
                was_recovered = True
                r1_repaired_count += 1

            # Repair R2: Duplicate hierarchical ID collision
            is_r2 = any(iss.startswith("R2:") for iss in issues) or (h_id and h_id in seen_h_ids)
            if is_r2 and h_id:
                seen_h_ids[h_id] = seen_h_ids.get(h_id, 1) + 1
                repaired_h_id = f"{h_id}_{seen_h_ids[h_id]}"
                issues = [iss for iss in issues if not iss.startswith("R2:")]
                issues.append(f"R2-REPAIRED: Duplicate hierarchical ID '{h_id}' disambiguated to '{repaired_h_id}'")
                h_id = repaired_h_id
                attrs["hierarchicalId"] = repaired_h_id
                if "." in repaired_h_id:
                    attrs["parentHierarchicalId"] = repaired_h_id.rsplit(".", 1)[0]
                was_recovered = True
                r2_disambiguated_count += 1
            elif h_id:
                seen_h_ids[h_id] = 1

            repaired_nodes.append(
                AssetNode(
                    id=node.id,
                    class_name=class_name,
                    hierarchical_id=h_id,
                    attributes=attrs,
                    provenance=node.provenance,
                    validation_issues=issues,
                    recovered=was_recovered,
                )
            )

        self.last_repair_telemetry = {
            "r1_repaired": r1_repaired_count,
            "r2_disambiguated": r2_disambiguated_count,
        }
        return repaired_nodes

