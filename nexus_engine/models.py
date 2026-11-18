from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """Normalized page coordinates [0.0, 1.0]."""
    ymin: float = Field(default=0.0, ge=0.0, le=1.0)
    xmin: float = Field(default=0.0, ge=0.0, le=1.0)
    ymax: float = Field(default=1.0, ge=0.0, le=1.0)
    xmax: float = Field(default=1.0, ge=0.0, le=1.0)


class Provenance(BaseModel):
    """Evidence trace linking an extracted element to its original document and bounding box."""
    source: str
    type: str = "visual"  # visual, tabular, xml, schematic
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    bbox: Optional[BoundingBox] = None


class Relation(BaseModel):
    """Ontology-typed directed edge between two physical assets."""
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: List[Provenance] = Field(default_factory=list)


class AssetNode(BaseModel):
    """Ontology-typed asset entity in the infrastructure knowledge graph."""
    id: str
    class_name: str
    hierarchical_id: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    provenance: List[Provenance] = Field(default_factory=list)
    validation_issues: List[str] = Field(default_factory=list)
    recovered: bool = False

    @property
    def mean_confidence(self) -> float:
        if not self.provenance:
            return 0.5
        return sum(p.confidence for p in self.provenance) / len(self.provenance)


class InfrastructureGraph(BaseModel):
    """Complete digital twin knowledge graph with typed nodes and edges."""
    nodes: Dict[str, AssetNode] = Field(default_factory=dict)
    edges: List[Relation] = Field(default_factory=list)


class TemporalRecord(BaseModel):
    """Bitemporal audit entry tracking valid-time and transaction-time."""
    entity_id: str
    attribute_key: str
    value: Any
    valid_from: datetime
    valid_to: Optional[datetime] = None
    tx_from: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tx_to: Optional[datetime] = None


class DPOPreferenceTriple(BaseModel):
    """Preference pair for direct preference optimization (DPO) refinement."""
    context: str
    accepted: Dict[str, Any]
    rejected: Dict[str, Any]


class GroundingEvaluation(BaseModel):
    """Automatic evaluation metrics for generation faithfulness and grounding."""
    provenance_closure_rate: float
    hallucinated_attribute_rate: float
    unlocalisable_span_rate: float
    entity_f1: float
    relation_f1: float
    otl_accuracy: float

