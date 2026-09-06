"""Shared immutable, JSON-serializable contracts."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CourseCode = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]

class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class KnowledgeVersion(SchemaModel):
    student_version: Identifier
    curriculum_version: Identifier
    ontology_version: Identifier
    rule_version: Identifier
    offering_version: Identifier
