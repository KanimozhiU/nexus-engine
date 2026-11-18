"""
Stage 1: Visual-First Conditioning.
Handles multi-modal inputs, tile splitting with spatial overlap (rho = 10%),
and character-based chunking for XML/LandXML representations.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from PIL import Image
from nexus_engine.models import BoundingBox


def tile_image(
    image: Image.Image,
    tile_size_ratio: float = 0.40,
    step_ratio: float = 0.30,
    max_edge_threshold: int = 2048,
) -> List[Tuple[Image.Image, BoundingBox]]:
    """
    Tiles an image exceeding max_edge_threshold into a 3x3 grid with
    a 40% size window stepped by 30% of dimension (providing ~10% spatial overlap rho=0.10).
    A component straddling a tile boundary stays visible in an adjacent tile.
    """
    width, height = image.size
    if max(width, height) <= max_edge_threshold:
        return [(image, BoundingBox(ymin=0.0, xmin=0.0, ymax=1.0, xmax=1.0))]

    tiles: List[Tuple[Image.Image, BoundingBox]] = []
    tile_w = int(width * tile_size_ratio)
    tile_h = int(height * tile_size_ratio)
    step_x = int(width * step_ratio)
    step_y = int(height * step_ratio)

    for row in range(3):
        for col in range(3):
            x0 = min(col * step_x, max(0, width - tile_w))
            y0 = min(row * step_y, max(0, height - tile_h))
            x1 = min(x0 + tile_w, width)
            y1 = min(y0 + tile_h, height)

            cropped = image.crop((x0, y0, x1, y1))
            norm_bbox = BoundingBox(
                ymin=round(y0 / height, 4),
                xmin=round(x0 / width, 4),
                ymax=round(y1 / height, 4),
                xmax=round(x1 / width, 4),
            )
            tiles.append((cropped, norm_bbox))
    return tiles


def chunk_structured_xml(text: str, chunk_size: int = 500_000) -> List[str]:
    """
    Chunks LandXML / IFC / XML representations at newline boundaries near chunk_size (500k characters).
    Preserves structural line tags without arbitrary mid-tag cuts.
    """
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for line in text.splitlines(keepends=True):
        current_chunk.append(line)
        current_length += len(line)
        if current_length >= chunk_size:
            chunks.append("".join(current_chunk))
            current_chunk = []
            current_length = 0

    if current_chunk:
        chunks.append("".join(current_chunk))
    return chunks


def load_file_content(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Modality-aware loader for heterogeneous engineering deliverables.
    Distinguishes visual PDFs, tabular XLSX/CSV, and structured XML.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        img = Image.open(path)
        tiles = tile_image(img)
        return {
            "type": "image",
            "path": str(path),
            "tiles": tiles,
            "dimensions": img.size,
        }

    elif suffix in [".xml", ".landxml", ".ifc"]:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        chunks = chunk_structured_xml(text)
        return {
            "type": "xml",
            "path": str(path),
            "chunks": chunks,
            "char_count": len(text),
        }

    elif suffix in [".csv", ".tsv"]:
        import pandas as pd
        sep = ";" if suffix == ".csv" and ";" in open(path, "r", encoding="utf-8", errors="ignore").readline() else ","
        df = pd.read_csv(path, sep=sep, encoding="utf-8", on_bad_lines="skip")
        return {
            "type": "tabular",
            "path": str(path),
            "rows": len(df),
            "dataframe": df,
        }

    elif suffix in [".xlsx", ".xls"]:
        import pandas as pd
        xl = pd.ExcelFile(path)
        sheets = {sheet: pd.read_excel(xl, sheet) for sheet in xl.sheet_names}
        return {
            "type": "excel",
            "path": str(path),
            "sheets": sheets,
        }

    elif suffix == ".pdf":
        return {
            "type": "pdf",
            "path": str(path),
            "is_vector_plan": True,
        }

    else:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {
            "type": "text",
            "path": str(path),
            "content": content,
        }

