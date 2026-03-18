"""
Pydantic models for Aura-App <-> Paperclip TPCP communication.
Matches the JSON schema in ../shared/schemas.json
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class ServiceType(str, Enum):
    WEBSITE_LANDING = "website_landing"
    WEBSITE_ECOMMERCE = "website_ecommerce"
    WEBSITE_PORTFOLIO = "website_portfolio"
    WEBAPP_SAAS = "webapp_saas"
    WEBAPP_INTERNAL_TOOL = "webapp_internal_tool"
    WEBAPP_DASHBOARD = "webapp_dashboard"
    AUTOMATION_EMAIL = "automation_email"
    AUTOMATION_CRM = "automation_crm"
    AUTOMATION_DATA_PIPELINE = "automation_data_pipeline"
    AUTOMATION_SCRAPER = "automation_scraper"
    AUTOMATION_REPORTING = "automation_reporting"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ProjectStatus(str, Enum):
    RECEIVED = "received"
    SCOPING = "scoping"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DELIVERED = "delivered"
    REVISION_REQUESTED = "revision_requested"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CompanySize(str, Enum):
    SOLO = "solo"
    SMALL = "2-10"
    MEDIUM = "11-50"
    LARGE = "51-200"
    ENTERPRISE = "200+"


class ProjectRequest(BaseModel):
    """Sent by Aura-App to Paperclip when a lead qualifies for service delivery."""

    request_id: UUID = Field(default_factory=uuid4)
    lead_id: str = Field(..., description="Aura internal lead ID")
    company_name: str = Field(..., max_length=255)
    contact_email: str = Field(..., description="Primary contact email")
    contact_name: str | None = None
    contact_phone: str | None = None
    service_type: ServiceType
    requirements: str = Field(..., description="What the client needs")
    budget_usd: float = Field(..., ge=0, description="Client budget in USD")
    priority: Priority = Priority.NORMAL
    deadline_iso: datetime | None = None
    research_notes: str | None = Field(
        None, description="Aura's research: pain points, tech stack, opportunities"
    )
    existing_website: str | None = None
    industry: str | None = None
    company_size: CompanySize | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectStatusUpdate(BaseModel):
    """Received from Paperclip as the project progresses."""

    request_id: UUID
    lead_id: str
    paperclip_ticket_id: str | None = None
    status: ProjectStatus
    message: str | None = None
    progress_pct: int = Field(0, ge=0, le=100)
    deliverable_url: str | None = None
    deliverable_type: str | None = None
    agent_notes: str | None = None
    cost_usd: float | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)
