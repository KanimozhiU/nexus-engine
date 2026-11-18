"""
Command Line Interface (CLI) for NexusEngine.
Provides end-to-end execution, evaluation, and data generation subcommands.
"""
import argparse
import json
import sys
from pathlib import Path
from nexus_engine.exporter import GraphExporter
from nexus_engine.oag import OAGReportGenerator
from nexus_engine.pipeline import NexusEngine


def main():
    parser = argparse.ArgumentParser(
        prog="nexus-engine",
        description="NexusEngine: Multi-Modal Ontology-Constrained Generation for Infrastructure Digital Twins (INLG 2026)",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Process raw completions into validated digital twin graph")
    run_parser.add_argument("--input", "-i", type=str, required=True, help="Path to input JSON completion file")
    run_parser.add_argument("--output-dir", "-o", type=str, default="./exports", help="Directory to save 7 export formats")

    # Command: report
    report_parser = subparsers.add_parser("report", help="Generate grounded report and RFIs from a digital twin graph")
    report_parser.add_argument("--graph", "-g", type=str, required=True, help="Path to input InfrastructureGraph JSON")

    # Command: generate-data
    data_parser = subparsers.add_parser("generate-data", help="Synthesize NEXUS-INFRA-412 benchmark corpus")
    data_parser.add_argument("--base-data", "-b", type=str, default="data-for-nexus-infra-412", help="Path to raw base data")
    data_parser.add_argument("--output-dir", "-o", type=str, default="./synthetic_nexus_infra", help="Output directory")

    args = parser.parse_args()

    if args.subcommand == "run":
        engine = NexusEngine()
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"Error: input file {input_path} not found.", file=sys.stderr)
            sys.exit(1)

        raw_text = input_path.read_text(encoding="utf-8")
        graph = engine.process_raw_completions(raw_text)

        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        exporter = GraphExporter(graph)
        exports = exporter.export_all()

        for fmt, content in exports.items():
            ext = {
                "json": "json",
                "jsonl": "jsonl",
                "csv_assets": "assets.csv",
                "csv_relations": "relations.csv",
                "cypher": "cql",
                "graphml": "graphml",
                "html": "html",
            }[fmt]
            out_file = out_dir / f"manifest_{fmt}.{ext}"
            out_file.write_text(content, encoding="utf-8")
            print(f"  [x] Wrote {out_file}")

        print(f"Successfully processed {len(graph.nodes)} assets and {len(graph.edges)} relations.")

    elif args.subcommand == "report":
        graph_path = Path(args.graph)
        if not graph_path.exists():
            print(f"Error: graph file {graph_path} not found.", file=sys.stderr)
            sys.exit(1)

        from nexus_engine.models import InfrastructureGraph
        with open(graph_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
        graph = InfrastructureGraph(**graph_data)
        oag = OAGReportGenerator(graph)

        print("\n--- GROUNDED SUMMARY (Task T2) ---")
        summary = oag.generate_grounded_summary()
        print(summary)

        print("\n--- GAP ANALYSIS RFIs ---")
        rfis = oag.generate_gap_analysis_rfis()
        for rfi in rfis:
            print(" -", rfi)

    elif args.subcommand == "generate-data":
        from scripts.generate_synthetic_nexus_infra import create_synthetic_corpus
        create_synthetic_corpus(base_dir=args.base_data, output_dir=args.output_dir)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

