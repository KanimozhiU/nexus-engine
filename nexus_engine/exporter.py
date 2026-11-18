"""
Stage 7: Multi-Format Exporter.
Emits the generated digital twin graph into all 7 supported formats:
1. JSON
2. JSONL
3. CSV (Assets)
4. CSV (Relations)
5. Cypher (Graph Database / Neo4j)
6. GraphML (Standard interchange XML)
7. HTML (Self-contained interactive summary)
"""
import csv
import json
from io import StringIO
from typing import Dict
from nexus_engine.models import InfrastructureGraph


class GraphExporter:
    """Exports an InfrastructureGraph into 7 operational formats."""

    def __init__(self, graph: InfrastructureGraph):
        self.graph = graph

    def to_json(self) -> str:
        """Standard indented JSON representation."""
        return self.graph.model_dump_json(indent=2)

    def to_jsonl(self) -> str:
        """Line-delimited JSON for streaming ingestion."""
        lines = []
        for node in self.graph.nodes.values():
            lines.append(json.dumps({"type": "node", **node.model_dump()}))
        for edge in self.graph.edges:
            lines.append(json.dumps({"type": "edge", **edge.model_dump()}))
        return "\n".join(lines)

    def to_csv_assets(self) -> str:
        """Tabular CSV dump of all validated physical assets."""
        out = StringIO()
        writer = csv.writer(out)
        writer.writerow(["id", "class_name", "hierarchical_id", "attributes", "issues"])
        for n in self.graph.nodes.values():
            writer.writerow([
                n.id,
                n.class_name,
                n.hierarchical_id or "",
                json.dumps(n.attributes),
                ";".join(n.validation_issues),
            ])
        return out.getvalue()

    def to_csv_relations(self) -> str:
        """Tabular CSV dump of all typed relationships."""
        out = StringIO()
        writer = csv.writer(out)
        writer.writerow(["source_id", "relation_type", "target_id", "confidence"])
        for e in self.graph.edges:
            writer.writerow([e.source_id, e.relation_type, e.target_id, e.confidence])
        return out.getvalue()

    def to_cypher(self) -> str:
        """Cypher script for Neo4j / property graph import."""
        lines = []
        for n in self.graph.nodes.values():
            props = ", ".join(
                f"`{k}`: '{v}'"
                for k, v in n.attributes.items()
                if isinstance(v, (str, int, float))
            )
            props_str = f" {{{props}}}" if props else ""
            lines.append(f"MERGE (a:`{n.class_name}` {{id: '{n.id}'}}){props_str};")

        for e in self.graph.edges:
            clean_rel = e.relation_type.upper().replace("-", "_").replace(" ", "_")
            lines.append(
                f"MATCH (s {{id: '{e.source_id}'}}), (t {{id: '{e.target_id}'}}) "
                f"MERGE (s)-[:`{clean_rel}`]->(t);"
            )
        return "\n".join(lines)

    def to_graphml(self) -> str:
        """Standard GraphML interchange format for NetworkX, Gephi, Cytoscape."""
        xml = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
            '  <key id="class" for="node" attr.name="class" attr.type="string"/>',
            '  <key id="type" for="edge" attr.name="type" attr.type="string"/>',
            '  <graph id="G" edgedefault="directed">',
        ]
        for n in self.graph.nodes.values():
            xml.append(f'    <node id="{n.id}"><data key="class">{n.class_name}</data></node>')
        for idx, e in enumerate(self.graph.edges):
            xml.append(
                f'    <edge id="e{idx}" source="{e.source_id}" target="{e.target_id}">'
                f'<data key="type">{e.relation_type}</data></edge>'
            )
        xml.append('  </graph>')
        xml.append('</graphml>')
        return "\n".join(xml)

    def to_html_report(self) -> str:
        """Self-contained interactive HTML summary report."""
        nodes_html = "".join(
            f"<tr><td><b>{n.id}</b></td><td><span class='badge'>{n.class_name}</span></td>"
            f"<td>{n.hierarchical_id or '-'}</td><td><code>{json.dumps(n.attributes)}</code></td>"
            f"<td>{len(n.provenance)} source(s)</td></tr>"
            for n in self.graph.nodes.values()
        )
        edges_html = "".join(
            f"<tr><td>{e.source_id}</td><td><b>&rarr; {e.relation_type} &rarr;</b></td>"
            f"<td>{e.target_id}</td><td>{e.confidence:.2f}</td></tr>"
            for e in self.graph.edges
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>NexusEngine Digital Twin Manifest</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; background: #fafafa; color: #222; }}
    h1 {{ color: #003366; }}
    .badge {{ background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 30px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #e5e7eb; }}
    th {{ background: #f3f4f6; color: #374151; }}
    code {{ background: #f9fafb; padding: 2px 4px; border: 1px solid #e5e7eb; border-radius: 3px; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>NexusEngine: Infrastructure Digital Twin</h1>
  <p><b>Summary:</b> {len(self.graph.nodes)} Validated Physical Assets | {len(self.graph.edges)} Relationships</p>
  
  <h2>Validated Assets (Nodes)</h2>
  <table>
    <thead><tr><th>ID</th><th>OTL Class</th><th>Hierarchical ID</th><th>Attributes</th><th>Evidence</th></tr></thead>
    <tbody>{nodes_html}</tbody>
  </table>

  <h2>Verified Relationships (Edges)</h2>
  <table>
    <thead><tr><th>Source</th><th>Relationship</th><th>Target</th><th>Confidence</th></tr></thead>
    <tbody>{edges_html}</tbody>
  </table>
</body>
</html>"""

    def export_all(self) -> Dict[str, str]:
        """Emits all seven delivery representations."""
        return {
            "json": self.to_json(),
            "jsonl": self.to_jsonl(),
            "csv_assets": self.to_csv_assets(),
            "csv_relations": self.to_csv_relations(),
            "cypher": self.to_cypher(),
            "graphml": self.to_graphml(),
            "html": self.to_html_report(),
        }

