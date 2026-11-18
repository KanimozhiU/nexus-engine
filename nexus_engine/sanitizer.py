"""
Stage 3: Normalisation & 3-Rung JSON Recovery Ladder.
Applies field enforcement, surrogate IDs, and recovery notices for malformed completions.
"""
import json
import re
import uuid
from typing import Any, Dict, List


def generate_session_id() -> str:
    """Emits random base-36 / hex surrogate identifier."""
    return uuid.uuid4().hex[:8]


def recover_malformed_json(raw_text: str) -> List[Dict[str, Any]]:
    """
    Three-rung recovery ladder for malformed completions (Section 4.2 / Section 4.3):
    Rung 1: Direct JSON parsing
    Rung 2: Markdown code block extraction (```json ... ```)
    Rung 3: Greedy regex block matching for { ... } objects
    """
    cleaned = raw_text.strip()

    # Rung 1: Direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Check if assets wrapped in an object
            if "assets" in data and isinstance(data["assets"], list):
                return data["assets"]
            return [data]
    except Exception:
        pass

    # Rung 2: Markdown code block parse
    block_match = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", cleaned, re.DOTALL)
    if block_match:
        try:
            data = json.loads(block_match.group(1))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "assets" in data and isinstance(data["assets"], list):
                    return data["assets"]
                return [data]
        except Exception:
            pass

    # Rung 3: Greedy regex bracket repair
    results: List[Dict[str, Any]] = []
    # Match any balanced or bracketed JSON object
    for match in re.finditer(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL):
        snippet = match.group(0)
        try:
            item = json.loads(snippet)
            if isinstance(item, dict) and ("class" in item or "id" in item or "otlName" in item):
                item["_recovered"] = True
                results.append(item)
        except Exception:
            continue

    if results:
        return results

    raise ValueError("Unrecoverable malformed JSON payload.")


def normalise_asset_payload(raw_assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Stage 3: Deterministic normaliser applies 3 idempotent actions:
    1. Field enforcement (mapping otlName -> class, assigning 'OnbekendAsset')
    2. Surrogate ID generation (random base-36 suffix)
    3. Warning propagation (_recovered -> recovered with review note)
    """
    normalised: List[Dict[str, Any]] = []
    for item in raw_assets:
        clean = dict(item)
        issues = list(clean.get("validation_issues", []))

        # 1. Field enforcement
        if "class" not in clean and "otlName" in clean:
            clean["class"] = clean.pop("otlName")
        if "class" not in clean or not clean["class"]:
            clean["class"] = "OnbekendAsset"
            issues.append("Missing class: surrogate assigned")

        # 2. Surrogate ID generation
        if "id" not in clean or not clean["id"]:
            clean["id"] = f"{clean['class']}_{generate_session_id()}"
            issues.append("Missing ID: random base-36 surrogate assigned")

        # 3. Warning propagation
        if clean.get("_recovered") or clean.get("recovered"):
            clean["recovered"] = True
            issues.append("Data recovered from a partial or malformed response")

        clean["validation_issues"] = issues
        clean.setdefault("attributes", {})
        clean.setdefault("provenance", [])
        normalised.append(clean)

    return normalised

