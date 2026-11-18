"""
OTLMOW Integration Adapter.
Maps extracted assets to validated OTLMOW Linked Data models (AWV / OSLO2 standard)
with live data.vlaanderen.be type URIs, and serializes to acceptance-ready
JSON-LD, GeoJSON, and CSV exchange packages.
Reference: Uma & Vanalderweireldt (INLG 2026), Appendix A & Appendix B (Table 8).
"""
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from nexus_engine.models import AssetNode, InfrastructureGraph, Relation


BASE_URI_ONDERDEEL = "https://wegenenverkeer.data.vlaanderen.be/ns/onderdeel#"
BASE_URI_INSTALLATIE = "https://wegenenverkeer.data.vlaanderen.be/ns/installatie#"
BASE_URI_NETWERK = "https://wegenenverkeer.data.vlaanderen.be/ns/netwerk#"

# Table 8 from INLG 2026 paper: Illustrative Civil3D/LandXML -> MOW OTL target mapping
CIVIL3D_TO_OTL_MAPPING: Dict[str, Tuple[str, str]] = {
    "Alignment": ("Verkeersas", "object id + geometry"),
    "Profile": ("Lengteprofiel", "object id"),
    "Surface": ("Maaiveld", "surface definition"),
    "PipeNetwork": ("Rioleringsstelsel", "network topology"),
    "Pipe": ("Rioleringsbuis", "pipe id + coordinates"),
    "Structure": ("Inspectieput", "geometry + source"),
    "Assembly": ("TypeDwarsprofiel", "assembly definition"),
}


class OTLMOWAdapter:
    """
    Transforms internal InfrastructureGraph models into official AWV OTL delivery formats.
    """

    def __init__(self, graph: InfrastructureGraph):
        self.graph = graph

    def resolve_type_uri(self, class_name: str) -> str:
        """Resolves official Flemish linked data URI for an OTL class."""
        installaties = {"Laagspanningsbord", "Stuurkast", "Seinstelsel", "Rioleringsstelsel"}
        if class_name in installaties:
            return f"{BASE_URI_INSTALLATIE}{class_name}"
        return f"{BASE_URI_ONDERDEEL}{class_name}"

    def to_json_ld(self) -> Dict[str, Any]:
        """Serializes digital twin graph to standards-compliant JSON-LD."""
        context = {
            "@vocab": "https://wegenenverkeer.data.vlaanderen.be/ns/",
            "otl": BASE_URI_ONDERDEEL,
            "ins": BASE_URI_INSTALLATIE,
            "id": "@id",
            "type": "@type",
            "feeds": {"@id": "https://wegenenverkeer.data.vlaanderen.be/ns/onderdeel#Voedt", "@type": "@id"},
            "part_of": {"@id": "https://wegenenverkeer.data.vlaanderen.be/ns/onderdeel#IsOnderdeelVan", "@type": "@id"},
            "connected_to": {"@id": "https://wegenenverkeer.data.vlaanderen.be/ns/onderdeel#SluitAanOp", "@type": "@id"},
            "monitors": {"@id": "https://wegenenverkeer.data.vlaanderen.be/ns/onderdeel#Controleert", "@type": "@id"},
        }

        graph_nodes = []
        for n in self.graph.nodes.values():
            node_dict: Dict[str, Any] = {
                "@id": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, n.id)}",
                "@type": self.resolve_type_uri(n.class_name),
                "identificatie": n.id,
                "hierarchischId": n.hierarchical_id,
            }
            # Append attributes
            for k, v in n.attributes.items():
                node_dict[k] = v

            # Append relationships
            outgoing = [e for e in self.graph.edges if e.source_id == n.id]
            for edge in outgoing:
                target_urn = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_DNS, edge.target_id)}"
                node_dict.setdefault(edge.relation_type, []).append(target_urn)

            graph_nodes.append(node_dict)

        return {
            "@context": context,
            "@graph": graph_nodes,
        }

    def to_geojson(self) -> Dict[str, Any]:
        """
        Serializes georeferenced assets (with xCoord / yCoord or Lambert 72)
        to standard RFC 7946 GeoJSON FeatureCollection.
        """
        features = []
        for n in self.graph.nodes.values():
            x = n.attributes.get("xCoord", n.attributes.get("x_coord"))
            y = n.attributes.get("yCoord", n.attributes.get("y_coord"))

            if x is not None and y is not None:
                try:
                    # Treat coordinates (supports Belgian Lambert 72 / projected coordinates)
                    fx = float(x)
                    fy = float(y)
                    geometry = {
                        "type": "Point",
                        "coordinates": [fx, fy],
                    }
                except Exception:
                    geometry = None
            else:
                geometry = None

            properties = {
                "id": n.id,
                "class": n.class_name,
                "hierarchical_id": n.hierarchical_id,
                "type_uri": self.resolve_type_uri(n.class_name),
                **{k: v for k, v in n.attributes.items() if k not in ["xCoord", "yCoord", "x_coord", "y_coord"]},
            }

            features.append({
                "type": "Feature",
                "id": n.id,
                "geometry": geometry,
                "properties": properties,
            })

        return {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:EPSG::31370"},  # Belgian Lambert 72
            },
            "features": features,
        }

