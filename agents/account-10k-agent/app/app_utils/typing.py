"""Data schemas and typing definitions for account-10k-agent."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class Citation(BaseModel):
    """Citation reference for grounded 10-K statements and recommendations."""

    citation_index: int = Field(..., description="1-indexed citation number, e.g. 1 for [1]")
    document_name: str = Field(..., description="Filename or title of the cited 10-K filing")
    source_uri: str = Field(..., description="Original gs:// or local URI of the 10-K filing")
    section: str | None = Field(None, description="SEC Form 10-K Item/section (e.g. 'Item 1A. Risk Factors')")
    page_number: int | None = Field(None, description="Page number where content appears")
    page_range: str | None = Field(None, description="Formatted page or page span (e.g. '12' or '12-13')")
    snippet: str = Field(..., description="Exact textual excerpt from the 10-K filing")
    signed_url: str | None = Field(None, description="Direct signed download/view link")


class FinancialMetric(BaseModel):
    """Key financial metric extracted from Item 7 (MD&A) or Item 8 (Financial Statements)."""

    label: str = Field(..., description="Metric name, e.g. 'Total Revenue', 'Operating Income', 'Free Cash Flow'")
    value: str = Field(..., description="Reported figure, e.g. '$48.2B'")
    yoy_change: str | None = Field(None, description="Year-over-year delta, e.g. '+14.2% YoY'")
    trend: Literal["up", "down", "neutral"] = Field("neutral", description="Directional performance indicator")
    insight: str = Field(..., description="Concise explanation of what drives this metric")
    citation_index: int | None = Field(None, description="1-indexed citation reference")


class StrategicInitiative(BaseModel):
    """Strategic business or technology priority extracted from Item 1 or Item 7."""

    title: str = Field(..., description="Title of the strategic initiative")
    category: str = Field(..., description="Area such as 'AI & Cloud Infrastructure', 'Digital Transformation', 'Global Expansion'")
    description: str = Field(..., description="Grounded description of the initiative from the 10-K")
    investment_signal: str = Field(..., description="CapEx, R&D, or budget signal stated in the 10-K")
    citation_index: int | None = Field(None, description="1-indexed citation reference")


class RiskFactorItem(BaseModel):
    """Material risk extracted from SEC Item 1A (Risk Factors) paired with account opportunity."""

    category: str = Field(..., description="Risk domain, e.g. 'Cybersecurity & Data Privacy', 'Supply Chain', 'Macro / Margin Pressure'")
    title: str = Field(..., description="Short summary title of the risk")
    severity: Literal["high", "medium", "low"] = Field("high", description="Materiality/severity level")
    description: str = Field(..., description="Explanation of the risk stated in Item 1A")
    account_opportunity: str = Field(..., description="How our account team can help the customer mitigate this risk")
    citation_index: int | None = Field(None, description="1-indexed citation reference")


class AccountRecommendation(BaseModel):
    """Actionable account recommendation grounded in the company's 10-K filing."""

    id: str = Field(..., description="Unique identifier for the recommendation")
    title: str = Field(..., description="Action-oriented recommendation title")
    category: Literal[
        "Cloud & AI Modernization",
        "Data & Analytics",
        "Security & Compliance",
        "Cost & Operational Efficiency",
        "Revenue & GTM Expansion",
    ] = Field(..., description="Strategic category of the recommendation")
    priority: Literal["High", "Medium", "Low"] = Field("High", description="Execution priority")
    confidence_score: int = Field(90, ge=1, le=100, description="Confidence score (1-100) based on 10-K evidence")
    target_stakeholder: str = Field(..., description="Target executive persona, e.g. 'CIO / VP Infrastructure', 'CFO', 'CISO'")
    rationale: str = Field(..., description="Why this matters now based on specific 10-K disclosures (with [n] citations)")
    recommended_actions: list[str] = Field(default_factory=list, description="Concrete next steps for the account team")
    talking_points: list[str] = Field(default_factory=list, description="Ready-to-use executive outreach talking points")
    citation_indices: list[int] = Field(default_factory=list, description="List of 1-indexed citations supporting this play")


class AccountAnalysisReport(BaseModel):
    """Complete structured 10-K account analysis and recommendation report."""

    account_id: str = Field(..., description="Unique slug/ID for the account")
    company_name: str = Field(..., description="Official company name")
    ticker: str = Field(..., description="Stock ticker symbol, e.g. 'ACME'")
    fiscal_year: str = Field(..., description="Fiscal year covered by the 10-K, e.g. 'FY2025'")
    document_name: str = Field(..., description="Source 10-K filename")
    source_uri: str = Field(..., description="GCS or local URI of the 10-K filing")
    analyzed_at: str = Field(..., description="ISO timestamp of the analysis")
    account_health_score: int = Field(..., ge=0, le=100, description="Composite 0-100 account health & opportunity score")
    health_verdict: str = Field(..., description="Short verdict label, e.g. 'Strong Expansion Account'")
    executive_summary: str = Field(..., description="2-4 sentence executive synthesis with [n] citations")
    financial_metrics: list[FinancialMetric] = Field(default_factory=list)
    strategic_initiatives: list[StrategicInitiative] = Field(default_factory=list)
    risk_factors: list[RiskFactorItem] = Field(default_factory=list)
    recommendations: list[AccountRecommendation] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    """Request to run or re-run 10-K account analysis on an indexed document."""

    document_name: str = Field(..., description="Name of the uploaded/indexed 10-K document")
    company_name: str | None = Field(None, description="Optional override for company name")
    ticker: str | None = Field(None, description="Optional override for stock ticker")
    fiscal_year: str | None = Field(None, description="Optional override for fiscal year")
    custom_focus: str | None = Field(None, description="Optional strategic focus area for recommendations")


class ChatRequest(BaseModel):
    """Analyst question request."""

    message: str = Field(..., description="Question or research prompt from the analyst")
    account_id: str | None = Field(None, description="Optional account ID to scope retrieval")
    document_name: str | None = Field(None, description="Optional document name to scope retrieval")
    session_id: str | None = Field(None, description="Session ID for multi-turn history")


class ChatResponse(BaseModel):
    """Response returned to the analyst with grounded answer and citations."""

    answer: str = Field(..., description="Grounded analyst response")
    citations: list[Citation] = Field(default_factory=list, description="Ordered citations")
    session_id: str | None = Field(None, description="Active session ID")
    raw_chunks: list[dict[str, Any]] = Field(default_factory=list, description="Retrieved raw context chunks")


class IngestRequest(BaseModel):
    """Document ingestion request via GCS URIs."""

    gcs_uris: list[str] = Field(default_factory=list, description="List of gs:// paths to 10-K PDF/HTML/TXT documents")
    folder_uri: str | None = Field(default=None, description="GCS folder path to ingest all 10-K documents from")
    company_name: str | None = Field(default=None, description="Optional company name for auto-analysis")
    ticker: str | None = Field(default=None, description="Optional ticker symbol")
    fiscal_year: str | None = Field(default=None, description="Optional fiscal year")
    auto_analyze: bool = Field(default=True, description="Whether to automatically generate an account report")


class IngestResponse(BaseModel):
    """Result of document ingestion."""

    status: str
    imported_files_count: int
    corpus: str | None = None
    paths: list[str] = Field(default_factory=list)
    folder_uri: str | None = Field(default=None)
    message: str | None = None
    account_report: AccountAnalysisReport | None = None


class Feedback(BaseModel):
    """Feedback submitted by users or analysts."""

    score: int = Field(..., ge=1, le=5, description="Satisfaction score 1-5")
    comment: str | None = None
    session_id: str | None = None
    query: str | None = None

