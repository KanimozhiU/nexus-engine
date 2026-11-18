"""
Multi-persona Prompt Specification & Response Schemas.
Instantiates 4 specialist personas in a single CoT/ReAct call (Stage 2):
1. TOPOLOGY: Visual hierarchy & spatial containment
2. TABULAR: Equipment register & attribute-value binding
3. CIRCUIT: Single-line schematics & distribution boards
4. CIVIL3D/BIM: CAD-to-OTL geometry & LandXML networks
"""
from typing import Any, Dict, List, Optional


RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "array",
    "description": "Synthesized OTL-compliant knowledge graph fragment.",
    "items": {
        "type": "object",
        "required": ["id", "class", "attributes", "relationships", "provenance"],
        "properties": {
            "id": {
                "type": "string",
                "description": "Primary external identifier (e.g. 'VF06', 'VF06.CAM01').",
            },
            "class": {
                "type": "string",
                "description": "Authoritative OTL class name in PascalCase (e.g. 'Laagspanningsbord', 'Camera').",
            },
            "hierarchical_id": {
                "type": "string",
                "description": "Fully qualified dot-extended containment ID (e.g. 'CAB01.SUB02.DEV03').",
            },
            "attributes": {
                "type": "object",
                "description": "Key-value map of properties in camelCase (e.g. 'spanning', 'vermogen', 'lengte').",
            },
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["source_id", "target_id", "relation_type"],
                    "properties": {
                        "source_id": {"type": "string"},
                        "target_id": {"type": "string"},
                        "relation_type": {
                            "type": "string",
                            "description": "Typed relationship (e.g. 'feeds', 'part_of', 'connected_to').",
                        },
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                },
            },
            "provenance": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["source", "confidence"],
                    "properties": {
                        "source": {"type": "string", "description": "Document name or tile reference."},
                        "type": {"type": "string", "enum": ["visual", "tabular", "xml", "schematic"]},
                        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "bbox": {
                            "type": "object",
                            "properties": {
                                "ymin": {"type": "number"},
                                "xmin": {"type": "number"},
                                "ymax": {"type": "number"},
                                "xmax": {"type": "number"},
                            },
                        },
                    },
                },
            },
        },
    },
}


MULTI_PERSONA_SYSTEM_PROMPT = """You are NEXUSENGINE, an autonomous multi-modal agent translating heterogeneous engineering deliverables into a formal Object Type Library (OTL) digital twin.

You execute a 5-phase Chain-of-Thought / ReAct protocol instantiating 4 sequential expert personas in a single forward pass:

1. PERSONA [TOPOLOGY]:
   - Inspects spatial layouts, plans, and bounding boxes.
   - Extracts physical enclosures, parent-child containment chains, and assigns dot-extended hierarchical IDs (e.g., CAB01.SUB02).
   - Generates 'part_of' relationships.

2. PERSONA [TABULAR]:
   - Extracts rows and attribute-value bindings from registers (IP_componenten, Excel tables).
   - Resolves device UUIDs, voltages (spanning), power ratings (vermogen), and geolocations (X/Y Lambert 72).
   - Normalises attribute keys to camelCase.

3. PERSONA [CIRCUIT]:
   - Traces electrical single-line schematics and P&ID diagrams (SCH-004).
   - Follows power distribution lines from feeding cabinets (Laagspanningsbord / Stuurkast) to field loads (Camera, DvmBord).
   - Generates 'feeds' and 'connected_to' relationships.

4. PERSONA [CIVIL3D/BIM]:
   - Maps CAD layers (DWG/DXF) and LandXML networks (alignments, pipe networks, riolering) into OTL objects.
   - Converts alignments to Verkeersas, pipes to Rioleringsbuis, manholes to Inspectieput/Kolk.

EXECUTION PROTOCOL:
- Enforce strict PascalCase for class names and camelCase for attribute keys.
- Enforce canonical relationship types: 'part_of', 'feeds', 'connected_to', 'monitors', 'controls'.
- Ensure every asset and relationship attaches provenance pointing to source document and location.
- Output ONLY valid JSON satisfying the requested response schema.
"""


def build_chunk_prompt(
    filename: str,
    retrieved_classes: Optional[List[str]] = None,
    guidance: Optional[str] = None,
) -> str:
    """Constructs prompt conditioned with retrieved top-k OTL classes."""
    classes_str = ", ".join(retrieved_classes) if retrieved_classes else "Standard Flemish AWV OTL classes"
    prompt = f"""Process the attached engineering document chunk from '{filename}'.

AUTHORITATIVE CANDIDATE OTL CLASSES:
[{classes_str}]

Execute the 5-phase protocol (TOPOLOGY -> TABULAR -> CIRCUIT -> CIVIL3D/BIM -> FUSION) and return an array of OTL assets conforming to the response schema.
"""
    if guidance:
        prompt += f"\nADDITIONAL VERIFICATION GUIDANCE:\n{guidance}\n"
    return prompt


CITE_OR_ABSTAIN_REPORT_PROMPT = """You are the NEXUSENGINE Ontology-Augmented Report Generator (OAG).
Task: Verbalise an authoritative engineering report or RFI from the provided digital twin sub-graph.

STRICT CITE-OR-ABSTAIN CONTRACT:
1. Every factual statement MUST cite its source node/document in square brackets, e.g. [SCH-004.pdf] or [VF06].
2. Do NOT invent or infer unmentioned voltages, connections, or components.
3. If an asset has missing required specifications (e.g., a distribution board without voltage, or an unpowered camera), emit an actionable RFI (Request For Information).
4. Any claim that cannot be cited to the graph MUST be suppressed.
"""

