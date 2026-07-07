from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class KYCCheck(BaseModel):
    full_name: str = Field(..., description="Subject's legal full name")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    document_type: str = Field(..., description="Type of identity document (passport, national_id, driver_license)")
    document_number: str = Field(..., description="Identity document number")
    address: str | None = Field(default=None, description="Residential address for verification")
    nationality: str | None = Field(default=None, description="Subject nationality ISO code")


class AMLScreening(BaseModel):
    entity_name: str = Field(..., description="Entity or individual name to screen")
    entity_type: Literal["individual", "organization"] = Field(..., description="Type of entity being screened")
    country: str | None = Field(default=None, description="Country ISO code of entity")
    id_number: str | None = Field(default=None, description="Optional ID number for disambiguation")


class SanctionsHit(BaseModel):
    list_name: str = Field(..., description="Sanctions list name (OFAC SDN, UN, EU, HMT, DFAT)")
    matched_name: str = Field(..., description="Name that matched on sanctions list")
    match_confidence: float = Field(..., ge=0.0, le=1.0, description="Fuzzy match confidence score")
    match_type: Literal["exact", "fuzzy", "alias"] = Field(..., description="Type of name match")
    list_reference: str | None = Field(default=None, description="Reference ID on sanctions list")
    notes: str | None = Field(default=None, description="Additional match details")


class RegulatoryReport(BaseModel):
    case_id: str = Field(..., description="Unique compliance case identifier")
    report_type: Literal["SAR", "CTR", "KYC_REVIEW", "AML_ESCALATION"] = Field(..., description="Type of regulatory report")
    subject_name: str = Field(..., description="Subject of the report")
    findings: str = Field(..., description="Detailed compliance findings")
    risk_level: Literal["low", "medium", "high"] = Field(..., description="Overall risk classification")
    recommended_action: str = Field(..., description="Recommended compliance action")
    regulatory_basis: list[str] = Field(default_factory=list, description="Applicable regulations (SOC2, PCI-DSS, GDPR, etc.)")
    timestamp: str = Field(..., description="ISO 8601 timestamp of report generation")


class ComplianceVerifyRequest(BaseModel):
    case_id: str = Field(..., description="Unique compliance case identifier")
    query: str = Field(..., min_length=1, max_length=16000, description="Compliance verification query")
    workflow_type: Literal["sequential", "concurrent", "handoff"] = Field(
        default="sequential",
        description="Type of compliance workflow to use",
    )


class ComplianceVerifyResponse(BaseModel):
    case_id: str | None = None
    result: str | None = None
    status: str = "PENDING"
    trace: list[dict[str, Any]] = Field(default_factory=list)
    sanctions_hits: list[str] | None = None
    guardrail_violations: list[str] | None = None


class ComplianceScreenRequest(BaseModel):
    entity_name: str = Field(..., description="Name of entity or individual to screen")
    entity_query: str = Field(..., min_length=1, max_length=16000, description="Full screening query with entity details")
    screen_types: list[Literal["kyc", "aml", "fraud", "sanctions"]] = Field(
        default=["kyc", "aml", "fraud", "sanctions"],
        description="Which screening checks to run",
    )


class ComplianceScreenResponse(BaseModel):
    entity_name: str
    result: str | None = None
    status: str = "PENDING"
    screening_results: list[dict[str, Any]] = Field(default_factory=list)
    guardrail_violations: list[str] | None = None


class AuditTrailResponse(BaseModel):
    case_id: str | None = None
    entity_name: str | None = None
    timestamp: str | None = None
    workflow: str | None = None
    sub_workflow: str | None = None
    status: str | None = None
    duration_ms: float | None = None
    token_usage: dict[str, int] | None = None
    trace_length: int | None = None
    violations: list[str] | None = None
