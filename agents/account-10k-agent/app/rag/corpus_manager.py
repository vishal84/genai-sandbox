"""Vertex AI RAG Corpus Manager and SEC Form 10-K Document Parser.

Manages:
1. Direct 10-K file uploads (.pdf, .html, .txt, .md) with page-level text extraction
   and automatic SEC Form 10-K Item section tagging (Item 1, Item 1A, Item 7, Item 8).
2. Google Cloud Storage upload (gs://<bucket>/10k-filings/...) with local file fallback.
3. Vertex AI RAG Corpus lookup/creation (text-embedding-005) and layout-aware chunk import.
4. Hybrid retrieval across Vertex AI RAG and parsed 10-K chunks for zero-latency analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import html
import io
import logging
import os
from pathlib import Path
import re
from typing import Any

from app.rag.signed_urls import generate_gcs_signed_url

logger = logging.getLogger(__name__)

LOCAL_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / ".local_uploads"


@dataclass
class RagChunk:
    """Represents a retrieved 10-K chunk with section metadata and source citation info."""

    text: str
    score: float
    source_uri: str
    document_name: str
    section: str | None = None
    page_number: int | None = None
    page_range: str | None = None
    signed_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "score": self.score,
            "source_uri": self.source_uri,
            "document_name": self.document_name,
            "section": self.section,
            "page_number": self.page_number,
            "page_range": self.page_range,
            "signed_url": self.signed_url,
        }


STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "in", "on", "of", "and", "or", "for", "to",
    "with", "about", "can", "you", "tell", "me", "how", "why", "which", "do", "does",
    "did", "from", "at", "by", "this", "that", "these", "those", "it", "its", "be",
    "been", "being", "have", "has", "had", "as", "their", "there", "were", "was",
}


def detect_10k_section(text: str) -> str:
    """Detects the primary SEC Form 10-K Item section from a page or chunk of text."""
    t_lower = text.lower()
    if re.search(r"item\s*1a\b|risk\s+factors", t_lower):
        return "Item 1A. Risk Factors"
    if re.search(r"item\s*1c\b|cybersecurity", t_lower):
        return "Item 1C. Cybersecurity"
    if re.search(r"item\s*7a\b|quantitative\s+and\s+qualitative\s+disclosures\s+about\s+market\s+risk", t_lower):
        return "Item 7A. Market Risk"
    if re.search(r"item\s*7\b|management['’]?s\s+discussion\s+and\s+analysis|md&a", t_lower):
        return "Item 7. MD&A"
    if re.search(r"item\s*8\b|financial\s+statements\s+and\s+supplementary|consolidated\s+statements\s+of\s+operations|balance\s+sheets", t_lower):
        return "Item 8. Financial Statements"
    if re.search(r"item\s*1\b|business\s+overview|our\s+business", t_lower):
        return "Item 1. Business"
    return "Form 10-K Disclosure"


def extract_company_metadata_from_text(text: str, filename: str) -> dict[str, str]:
    """Heuristically infers company_name, ticker, and fiscal_year from 10-K header text or filename."""
    company_name = ""
    ticker = ""
    fiscal_year = "FY2025"

    # Look for explicit patterns in text
    comp_match = re.search(
        r"(?:exact\s+name\s+of\s+registrant|company\s+name|registrant)\s*[:\-]\s*([A-Z][A-Za-z0-9\s,\.&\-]{2,60})",
        text,
        re.IGNORECASE,
    )
    if comp_match:
        company_name = comp_match.group(1).splitlines()[0].strip(" .,-")

    ticker_match = re.search(
        r"(?:trading\s+symbol(?:\(s\))?|ticker\s+symbol|ticker|nasdaq|nyse)\s*[:\-]\s*([A-Z]{2,5})\b",
        text,
        re.IGNORECASE,
    )
    if ticker_match:
        ticker = ticker_match.group(1).upper()

    fy_match = re.search(r"\b(FY\s*20\d{2}|202[3-7])\b", text, re.IGNORECASE)
    if fy_match:
        raw_fy = fy_match.group(1).upper().replace(" ", "")
        fiscal_year = raw_fy if raw_fy.startswith("FY") else f"FY{raw_fy}"

    # Fallback to filename parsing (e.g. "AAPL_FY2025_10K.pdf" or "apex-cloud-2025-10k.pdf")
    stem = Path(filename).stem
    if not ticker:
        stem_ticker = re.match(r"^([A-Z]{2,5})[_\-\s]", stem)
        if stem_ticker:
            ticker = stem_ticker.group(1).upper()

    if not company_name:
        cleaned_stem = re.sub(r"(?:10[\-_]?k|fy\d{4}|20\d{2})", "", stem, flags=re.IGNORECASE)
        cleaned_stem = re.sub(r"[_\-]+", " ", cleaned_stem).strip()
        company_name = cleaned_stem.title() if cleaned_stem else "Enterprise Account Corp."

    if not ticker:
        words = [w for w in re.findall(r"[A-Za-z]+", company_name) if w.lower() not in {"inc", "corp", "corporation", "holdings", "group", "the", "and"}]
        if len(words) >= 2:
            ticker = "".join(w[0] for w in words[:4]).upper()
        elif words:
            ticker = words[0][:4].upper()
        else:
            ticker = "ACCT"

    return {
        "company_name": company_name,
        "ticker": ticker,
        "fiscal_year": fiscal_year,
    }


def extract_pages_from_bytes(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Extracts page-numbered text blocks from PDF, HTML, or TXT/MD 10-K files."""
    lower_name = filename.lower()
    pages: list[dict[str, Any]] = []

    if lower_name.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(file_bytes))
            for idx, page in enumerate(reader.pages):
                txt = (page.extract_text() or "").strip()
                if txt:
                    pages.append(
                        {
                            "page_number": idx + 1,
                            "text": txt,
                            "section": detect_10k_section(txt),
                        }
                    )
        except Exception as e:
            logger.warning("pypdf extraction fallback for %s: %s", filename, e)

    if not pages:
        raw_text = file_bytes.decode("utf-8", errors="ignore")
        if lower_name.endswith((".html", ".htm")):
            raw_text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", raw_text, flags=re.IGNORECASE)
            raw_text = re.sub(r"<[^>]+>", "\n", raw_text)
            raw_text = html.unescape(raw_text)

        # Check if explicit page markers exist (e.g. "--- PAGE 1 ---" or form feed)
        explicit_pages = re.split(r"(?:\f|---\s*PAGE\s+\d+\s*---)", raw_text, flags=re.IGNORECASE)
        explicit_pages = [p.strip() for p in explicit_pages if p.strip()]

        if len(explicit_pages) > 1:
            for idx, p_text in enumerate(explicit_pages):
                pages.append(
                    {
                        "page_number": idx + 1,
                        "text": p_text,
                        "section": detect_10k_section(p_text),
                    }
                )
        else:
            # Split by ~1800 character blocks along paragraph boundaries
            paragraphs = [p.strip() for p in re.split(r"\n{2,}", raw_text) if p.strip()]
            current_buf: list[str] = []
            current_len = 0
            page_num = 1
            for para in paragraphs:
                if current_len + len(para) > 1800 and current_buf:
                    combined = "\n\n".join(current_buf)
                    pages.append(
                        {
                            "page_number": page_num,
                            "text": combined,
                            "section": detect_10k_section(combined),
                        }
                    )
                    page_num += 1
                    current_buf = [para]
                    current_len = len(para)
                else:
                    current_buf.append(para)
                    current_len += len(para)
            if current_buf:
                combined = "\n\n".join(current_buf)
                pages.append(
                    {
                        "page_number": page_num,
                        "text": combined,
                        "section": detect_10k_section(combined),
                    }
                )

    return pages


def extract_relevant_excerpt(query: str, text: str, max_chars: int = 350) -> str:
    """Extracts a focused textual excerpt from chunk text that is directly relevant to query."""
    cleaned = re.sub(r"\r\n|\r", "\n", text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    query_words = [
        w.lower()
        for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", query)
        if len(w) >= 3 and w.lower() not in STOP_WORDS
    ]
    if not query_words:
        query_words = [
            w.lower()
            for w in re.findall(r"\b[a-zA-Z0-9_\-]+\b", query)
            if w.lower() not in STOP_WORDS
        ]

    raw_sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        if s.strip()
    ]
    if not raw_sentences:
        clean_prefix = cleaned[:max_chars]
        if " " in clean_prefix:
            return clean_prefix.rsplit(" ", 1)[0] + "..."
        return clean_prefix + "..."

    scored_sentences = []
    for i, s in enumerate(raw_sentences):
        s_lower = s.lower()
        score = sum(2 if w in s_lower else 0 for w in query_words)
        for j in range(len(query_words) - 1):
            if f"{query_words[j]} {query_words[j+1]}" in s_lower:
                score += 5
        scored_sentences.append((score, i, s))

    scored_sentences.sort(key=lambda x: (x[0], -x[1]), reverse=True)
    best_score, best_idx, _ = scored_sentences[0]

    if best_score <= 0:
        best_idx = 0

    selected_indices = [best_idx]
    current_len = len(raw_sentences[best_idx])

    if best_idx + 1 < len(raw_sentences) and current_len + len(raw_sentences[best_idx + 1]) + 1 <= max_chars:
        selected_indices.append(best_idx + 1)
        current_len += len(raw_sentences[best_idx + 1]) + 1

    if best_idx - 1 >= 0 and current_len + len(raw_sentences[best_idx - 1]) + 1 <= max_chars:
        selected_indices.insert(0, best_idx - 1)
        current_len += len(raw_sentences[best_idx - 1]) + 1

    excerpt = " ".join(raw_sentences[i] for i in selected_indices)
    if selected_indices[0] > 0:
        excerpt = "..." + excerpt
    if selected_indices[-1] < len(raw_sentences) - 1:
        excerpt = excerpt + "..."

    return excerpt


# ---------------------------------------------------------------------------
# Built-in Sample SEC Form 10-K Filings for Instant Testing & Evaluation
# ---------------------------------------------------------------------------

SAMPLE_10K_FILINGS: dict[str, dict[str, Any]] = {
    "apex_cloud_retail_2025_10k.txt": {
        "company_name": "Apex OmniRetail & Cloud Holdings Inc.",
        "ticker": "APXC",
        "fiscal_year": "FY2025",
        "filename": "apex_cloud_retail_2025_10k.txt",
        "content": """--- PAGE 1 ---
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
Washington, D.C. 20549
FORM 10-K
ANNUAL REPORT PURSUANT TO SECTION 13 OR 15(d) OF THE SECURITIES EXCHANGE ACT OF 1934
For the Fiscal Year Ended December 31, 2025
Exact Name of Registrant: Apex OmniRetail & Cloud Holdings Inc.
Trading Symbol: APXC (NASDAQ)

ITEM 1. BUSINESS OVERVIEW & STRATEGIC PRIORITIES
Apex OmniRetail & Cloud Holdings Inc. ("Apex", "we", or "the Company") operates 1,420 omnichannel fulfillment centers and a rapidly growing B2B commerce marketplace across North America and Europe.
In FY2025, management launched "Project Horizon", a three-year $420 million digital & AI modernization program focused on:
1. Consolidating four legacy on-premises data centers onto managed cloud infrastructure by Q4 2026 to eliminate $65M in annual hardware maintenance overhead.
2. Deploying generative AI customer service agents and automated demand-forecasting models across 1,420 fulfillment nodes to reduce inventory stockouts by 22%.
3. Unifying fragmented ERP and warehouse telemetry silos into a real-time cloud data lakehouse capable of sub-second personalization.

--- PAGE 2 ---
ITEM 1A. RISK FACTORS
Investing in Apex involves significant operational, technological, and financial risks:
1. Legacy Data Center & Cloud Migration Risk (High Severity): Over 58% of our core order-management workloads still run on end-of-life on-premises database clusters. Unplanned outages during the Q3 2025 peak shopping week resulted in $18.4 million in lost gross merchandise value (GMV) and SLA penalties.
2. Cybersecurity, Ransomware & PCI-DSS Compliance Exposure (High Severity): In May 2025, a third-party logistics vendor experienced a credential-stuffing breach that exposed 1.2 million customer shipping records. Regulatory audits under GDPR and CCPA could result in fines up to $35 million if zero-trust identity controls and automated threat detection are not implemented across hybrid workloads.
3. Supply Chain & Gross Margin Compression (Medium Severity): Freight cost volatility and manual warehouse routing inefficiencies compressed gross margins by 110 basis points in H1 2025. Failure to automate fulfillment forecasting could materially impact operating cash flow.

--- PAGE 3 ---
ITEM 1C. CYBERSECURITY GOVERNANCE
Our Chief Information Security Officer (CISO) reports quarterly to the Audit Committee. Following the May 2025 vendor incident, the Board authorized an incremental $28 million cybersecurity transformation budget for FY2026 prioritizing SIEM modernization, cloud posture management, and AI-driven anomaly detection.

--- PAGE 4 ---
ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS (MD&A)
Executive Financial Highlights (FY2025 vs. FY2024):
- Total Consolidated Revenue: $14.85 billion in FY2025, an increase of 16.4% YoY compared to $12.76 billion in FY2024, driven by 29% growth in B2B digital marketplace subscriptions.
- Operating Income: $1.62 billion in FY2025, up 21.8% YoY from $1.33 billion in FY2024. Operating margin expanded to 10.9%.
- Free Cash Flow: $1.18 billion in FY2025 (+18.0% YoY), providing strong liquidity to self-fund cloud and AI transformation initiatives.
- Capital Expenditures (CapEx) & Technology R&D: Technology and infrastructure spend reached $610 million (4.1% of revenue), with management guiding to $740 million in FY2026 specifically earmarked for cloud migration, AI inference infrastructure, and real-time analytics.

--- PAGE 5 ---
ITEM 8. CONSOLIDATED FINANCIAL STATEMENTS & SUPPLEMENTARY DATA
Consolidated Balance Sheet & Liquidity Summary (as of December 31, 2025):
- Cash, Cash Equivalents, and Marketable Securities: $2.45 billion.
- Total Long-Term Debt: $1.90 billion (Net cash positive by $550 million; debt-to-EBITDA ratio of 0.9x).
- Remaining Performance Obligations (RPO) in Enterprise Commerce: $3.12 billion (+24% YoY).
Note 14 - Commitments and Contingencies: The Company has committed $145 million over the next 36 months for cloud compute, enterprise data platform modernization, and managed security services, with $85 million of vendor contracts currently under active RFP evaluation for Q1-Q2 2026.""",
    },
    "vanguard_industrial_fintech_2025_10k.txt": {
        "company_name": "Vanguard Industrial & FinTech Corp.",
        "ticker": "VIFC",
        "fiscal_year": "FY2025",
        "filename": "vanguard_industrial_fintech_2025_10k.txt",
        "content": """--- PAGE 1 ---
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
FORM 10-K — ANNUAL REPORT FOR THE FISCAL YEAR ENDED DECEMBER 31, 2025
Exact Name of Registrant: Vanguard Industrial & FinTech Corp.
Trading Symbol: VIFC (NYSE)

ITEM 1. BUSINESS
Vanguard Industrial & FinTech Corp. ("Vanguard") provides embedded equipment financing, treasury payment rails, and IoT predictive maintenance software to 48,000 commercial manufacturing clients.
Strategic Priorities for FY2026:
- AI Underwriting & Fraud Prevention: Modernizing credit risk scoring and real-time wire fraud detection using machine learning on Vertex cloud infrastructure.
- Post-Merger ERP & Database Consolidation: Following three acquisitions in 2024-2025, Vanguard operates 7 disparate SQL/mainframe ledgers causing $42M in duplicate licensing and manual reconciliation delays.

--- PAGE 2 ---
ITEM 1A. RISK FACTORS
- High Cloud & Mainframe Cost Escalation (High Severity): Third-party mainframe and legacy database licensing renewals increased 34% in FY2025, reducing net operating margin by 180 bps.
- Real-Time Payment Fraud & Regulatory Compliance Risk (High Severity): Synthetic identity fraud in commercial equipment leasing rose 41% YoY, resulting in $29.5 million in credit charge-offs.
- Delayed Financial Close & Audit Remediation (Medium Severity): Siloed data warehouses across acquired subsidiaries delayed quarterly close cycles by 6 business days.

--- PAGE 3 ---
ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS (MD&A) & ITEM 8. FINANCIAL STATEMENTS
- Total Revenue: $6.42 billion in FY2025 (+9.2% YoY vs. $5.88 billion in FY2024).
- Operating Income: $712 million (-3.5% YoY due to $42M duplicate IT/mainframe costs and $29.5M fraud provisions).
- Free Cash Flow: $540 million (+4.1% YoY); Cash & Equivalents of $1.15 billion.
- IT & Cloud Modernization Budget: CFO announced a $190 million cost-takeout and database consolidation initiative ("OneVanguard Platform") targeting $55 million in annualized run-rate savings by FY2027.""",
    },
}


class VertexRagManager:
    """Interface to Vertex AI RAG Engine, Cloud Storage, and local 10-K document cache."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
        corpus_id: str | None = None,
        display_name: str | None = None,
    ) -> None:
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = (
            location
            or os.getenv("RAG_LOCATION")
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or "us-east5"
        )
        self.corpus_id = corpus_id or os.getenv("RAG_CORPUS_ID")
        self.display_name = (
            display_name
            or os.getenv("RAG_CORPUS_DISPLAY_NAME")
            or "account-10k-corpus"
        )
        self._corpus_resource_name: str | None = None
        self._initialized = False

        # In-memory parsed 10-K store for zero-latency structured analysis & local fallback
        self._local_documents: dict[str, dict[str, Any]] = {}
        self._local_chunks: dict[str, list[RagChunk]] = {}
        self._account_reports: dict[str, Any] = {}

    def _ensure_initialized(self) -> None:
        """Initializes Vertex AI SDK if not already done."""
        if self._initialized:
            return

        import vertexai

        if self.project_id:
            vertexai.init(project=self.project_id, location=self.location)
            self._initialized = True
        else:
            logger.warning("GOOGLE_CLOUD_PROJECT is not set; running in local/uninitialized mode.")

    def get_or_create_corpus(
        self,
        display_name: str | None = None,
        embedding_model: str = "publishers/google/models/text-embedding-005",
    ) -> str:
        """Looks up or auto-creates the Vertex AI RAG corpus."""
        if self._corpus_resource_name:
            return self._corpus_resource_name

        if self.corpus_id:
            if "/" in self.corpus_id:
                self._corpus_resource_name = self.corpus_id
            else:
                self._corpus_resource_name = (
                    f"projects/{self.project_id}/locations/{self.location}/ragCorpora/{self.corpus_id}"
                )
            return self._corpus_resource_name

        self._ensure_initialized()
        from vertexai.preview import rag

        target_name = display_name or self.display_name

        try:
            existing_corpora = list(rag.list_corpora())
            for corpus in existing_corpora:
                if getattr(corpus, "display_name", "") == target_name:
                    self._corpus_resource_name = corpus.name
                    return corpus.name

            embedding_model_config = rag.EmbeddingModelConfig(
                publisher_model=embedding_model
            )
            corpus = rag.create_corpus(
                display_name=target_name,
                embedding_model_config=embedding_model_config,
            )
            self._corpus_resource_name = corpus.name
            return corpus.name

        except Exception as e:
            logger.warning("Vertex AI RAG corpus lookup/creation fallback: %s", e)
            fallback_name = (
                f"projects/{self.project_id or 'default'}/locations/{self.location}/ragCorpora/{target_name}"
            )
            self._corpus_resource_name = fallback_name
            return fallback_name

    def upload_and_ingest_file(
        self,
        file_bytes: bytes,
        filename: str,
        company_name: str | None = None,
        ticker: str | None = None,
        fiscal_year: str | None = None,
    ) -> dict[str, Any]:
        """Uploads a 10-K file from browser, parses its pages/sections, uploads to GCS if configured, and indexes into Vertex AI RAG."""
        safe_filename = re.sub(r"[^a-zA-Z0-9._\-]", "_", Path(filename).name)
        pages = extract_pages_from_bytes(file_bytes, safe_filename)
        full_text = "\n\n".join(p["text"] for p in pages)

        inferred = extract_company_metadata_from_text(full_text, safe_filename)
        resolved_company = (company_name or "").strip() or inferred["company_name"]
        resolved_ticker = (ticker or "").strip().upper() or inferred["ticker"]
        resolved_fy = (fiscal_year or "").strip() or inferred["fiscal_year"]

        # Persist locally so citations can always be downloaded/viewed
        try:
            LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            (LOCAL_UPLOAD_DIR / safe_filename).write_bytes(file_bytes)
        except Exception as e:
            logger.debug("Could not write local upload copy: %s", e)

        bucket_name = (os.getenv("GCS_DOCUMENTS_BUCKET") or "").strip()
        source_uri = f"local://10k-filings/{safe_filename}"
        signed_url = f"/api/files/{safe_filename}"
        rag_import_status = "cached_locally"

        # Upload to GCS & import to Vertex AI RAG if bucket is configured
        if bucket_name and bucket_name not in {"your-10k-bucket-name", "your-doc-bucket-name"}:
            try:
                from google.cloud import storage

                storage_client = storage.Client(project=self.project_id)
                bucket = storage_client.bucket(bucket_name)
                blob_path = f"10k-filings/{resolved_ticker.lower()}/{safe_filename}"
                blob = bucket.blob(blob_path)
                content_type = "application/pdf" if safe_filename.lower().endswith(".pdf") else "text/plain"
                blob.upload_from_string(file_bytes, content_type=content_type)
                source_uri = f"gs://{bucket_name}/{blob_path}"
                signed_url = generate_gcs_signed_url(source_uri)

                rag_res = self.import_gcs_documents([source_uri])
                rag_import_status = rag_res.get("status", "submitted")
            except Exception as e:
                logger.warning(
                    "GCS/Vertex RAG upload skipped or fell back to local store for %s: %s",
                    safe_filename,
                    e,
                )

        # Build local page/section chunks for immediate analysis & hybrid retrieval
        doc_chunks: list[RagChunk] = []
        for page in pages:
            p_num = page["page_number"]
            p_text = page["text"]
            section = page["section"]
            doc_chunks.append(
                RagChunk(
                    text=p_text,
                    score=0.1,
                    source_uri=source_uri,
                    document_name=safe_filename,
                    section=section,
                    page_number=p_num,
                    page_range=str(p_num),
                    signed_url=signed_url,
                )
            )

        self._local_chunks[safe_filename] = doc_chunks
        doc_meta = {
            "display_name": safe_filename,
            "name": source_uri,
            "source_uri": source_uri,
            "signed_url": signed_url,
            "company_name": resolved_company,
            "ticker": resolved_ticker,
            "fiscal_year": resolved_fy,
            "pages_count": len(pages),
            "rag_status": rag_import_status,
            "create_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._local_documents[safe_filename] = doc_meta
        return doc_meta

    def load_sample_10k(self, sample_key: str | None = None) -> dict[str, Any]:
        """Loads one of the built-in sample SEC Form 10-K filings for instant analysis."""
        key = sample_key if sample_key in SAMPLE_10K_FILINGS else "apex_cloud_retail_2025_10k.txt"
        sample = SAMPLE_10K_FILINGS[key]
        return self.upload_and_ingest_file(
            file_bytes=sample["content"].encode("utf-8"),
            filename=sample["filename"],
            company_name=sample["company_name"],
            ticker=sample["ticker"],
            fiscal_year=sample["fiscal_year"],
        )

    def import_gcs_documents(
        self,
        gcs_uris: list[str],
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        corpus_name: str | None = None,
    ) -> dict[str, Any]:
        """Imports PDF/HTML/TXT 10-K documents from GCS into the Vertex AI RAG corpus."""
        self._ensure_initialized()
        from vertexai.preview import rag

        corpus = corpus_name or self.get_or_create_corpus()
        transformation_config = rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

        # Also attempt to fetch and parse GCS files locally so structured analysis has immediate access
        for uri in gcs_uris:
            if uri.startswith("gs://"):
                doc_name = uri.rstrip("/").split("/")[-1]
                if doc_name not in self._local_documents:
                    try:
                        from google.cloud import storage
                        from app.rag.signed_urls import parse_gcs_uri

                        b_name, blob_path = parse_gcs_uri(uri)
                        client = storage.Client(project=self.project_id)
                        data = client.bucket(b_name).blob(blob_path).download_as_bytes()
                        pages = extract_pages_from_bytes(data, doc_name)
                        full_text = "\n\n".join(p["text"] for p in pages)
                        inferred = extract_company_metadata_from_text(full_text, doc_name)
                        s_url = generate_gcs_signed_url(uri)
                        self._local_chunks[doc_name] = [
                            RagChunk(
                                text=p["text"],
                                score=0.1,
                                source_uri=uri,
                                document_name=doc_name,
                                section=p["section"],
                                page_number=p["page_number"],
                                page_range=str(p["page_number"]),
                                signed_url=s_url,
                            )
                            for p in pages
                        ]
                        self._local_documents[doc_name] = {
                            "display_name": doc_name,
                            "name": uri,
                            "source_uri": uri,
                            "signed_url": s_url,
                            "company_name": inferred["company_name"],
                            "ticker": inferred["ticker"],
                            "fiscal_year": inferred["fiscal_year"],
                            "pages_count": len(pages),
                            "rag_status": "imported",
                            "create_time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }
                    except Exception as e:
                        logger.debug("Could not pre-cache GCS file %s locally: %s", uri, e)

        batch_size = 25
        total_imported = 0
        errors: list[str] = []

        for i in range(0, len(gcs_uris), batch_size):
            batch_uris = gcs_uris[i : i + batch_size]
            try:
                response = rag.import_files(
                    corpus_name=corpus,
                    paths=batch_uris,
                    transformation_config=transformation_config,
                    max_embedding_requests_per_min=900,
                )
                imported = getattr(response, "imported_rag_files_count", len(batch_uris))
                total_imported += imported
            except Exception as e:
                logger.error("Failed to import batch into RAG corpus %s: %s", corpus, e)
                errors.append(str(e))

        if errors and total_imported == 0:
            return {
                "status": "error",
                "error": "; ".join(errors),
                "corpus": corpus,
                "paths": gcs_uris,
                "imported_files_count": 0,
            }

        return {
            "status": "success" if not errors else "partial_success",
            "imported_files_count": total_imported,
            "corpus": corpus,
            "paths": gcs_uris,
        }

    def import_gcs_folder(
        self,
        folder_uri: str,
        chunk_size: int = 512,
        chunk_overlap: int = 100,
        corpus_name: str | None = None,
    ) -> dict[str, Any]:
        """Imports all 10-K documents from a GCS folder path into Vertex AI RAG."""
        if not folder_uri or not folder_uri.strip().startswith("gs://"):
            return {
                "status": "error",
                "error": f"Invalid GCS folder URI '{folder_uri}'. Must start with 'gs://'.",
                "imported_files_count": 0,
            }

        norm_uri = folder_uri.strip()
        path_without_scheme = norm_uri[5:].strip("/")
        parts = path_without_scheme.split("/", 1)
        if len(parts) < 2 or not parts[1].strip("/"):
            return {
                "status": "error",
                "error": "A folder path inside the bucket must be provided (e.g., gs://bucket-name/10k-filings/).",
                "imported_files_count": 0,
            }

        clean_folder_uri = f"gs://{parts[0]}/{parts[1].strip('/')}/"
        result = self.import_gcs_documents(
            gcs_uris=[clean_folder_uri],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            corpus_name=corpus_name,
        )
        result["folder_uri"] = clean_folder_uri
        return result

    def get_document_chunks(self, document_name: str | None = None) -> list[RagChunk]:
        """Returns all parsed chunks for a specific 10-K document (or the most recent one)."""
        if document_name and document_name in self._local_chunks:
            return self._local_chunks[document_name]

        # Match by partial filename or URI
        if document_name:
            target_base = document_name.rstrip("/").split("/")[-1]
            if target_base in self._local_chunks:
                return self._local_chunks[target_base]

        if self._local_chunks:
            latest_key = list(self._local_chunks.keys())[-1]
            return self._local_chunks[latest_key]

        # If no local chunks exist, query the Vertex AI RAG corpus for key 10-K sections
        return self.query_corpus(
            "Item 1 Business Overview Item 1A Risk Factors Item 7 MD&A Revenue Operating Income Cash Flow CapEx",
            top_k=8,
            document_name=document_name,
        )

    def get_document_metadata(self, document_name: str | None = None) -> dict[str, Any] | None:
        """Returns stored metadata for a specific document or the most recently uploaded document."""
        if document_name:
            if document_name in self._local_documents:
                return self._local_documents[document_name]
            base = document_name.rstrip("/").split("/")[-1]
            if base in self._local_documents:
                return self._local_documents[base]
        if self._local_documents:
            latest_key = list(self._local_documents.keys())[-1]
            return self._local_documents[latest_key]
        return None

    def save_account_report(self, report: Any) -> None:
        """Stores a generated AccountAnalysisReport in memory."""
        account_id = getattr(report, "account_id", None) or report.get("account_id")
        if account_id:
            self._account_reports[account_id] = report

    def list_account_reports(self) -> list[Any]:
        """Returns all analyzed AccountAnalysisReport objects (newest first)."""
        return list(reversed(list(self._account_reports.values())))

    def get_account_report(self, account_id: str) -> Any | None:
        """Looks up an AccountAnalysisReport by account_id, ticker, or document_name."""
        if account_id in self._account_reports:
            return self._account_reports[account_id]
        for rep in self._account_reports.values():
            ticker = getattr(rep, "ticker", "") if not isinstance(rep, dict) else rep.get("ticker", "")
            doc_name = getattr(rep, "document_name", "") if not isinstance(rep, dict) else rep.get("document_name", "")
            if account_id.lower() in {ticker.lower(), doc_name.lower()}:
                return rep
        return None

    def query_corpus(
        self,
        query_text: str,
        top_k: int = 5,
        vector_distance_threshold: float = 0.85,
        document_name: str | None = None,
    ) -> list[RagChunk]:
        """Queries both local parsed 10-K chunks and Vertex AI RAG corpus, returning ranked RagChunks."""
        results: list[RagChunk] = []
        seen_snippets: set[str] = set()

        # 1. Score local parsed 10-K chunks first (fast, page-accurate, section-tagged)
        q_words = [
            w.lower()
            for w in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", query_text)
            if w.lower() not in STOP_WORDS
        ]

        candidate_docs = (
            {document_name: self._local_chunks[document_name]}
            if (document_name and document_name in self._local_chunks)
            else self._local_chunks
        )

        scored_local: list[tuple[float, RagChunk]] = []
        for d_name, chunks in candidate_docs.items():
            for ch in chunks:
                text_lower = ch.text.lower()
                sec_lower = (ch.section or "").lower()
                matches = sum(1 for w in q_words if w in text_lower or w in sec_lower)
                if matches > 0 or not q_words:
                    # Convert keyword overlap into a distance-like score (smaller = closer, 0.05..0.65)
                    ratio = matches / max(len(q_words), 1)
                    dist_score = round(max(0.05, 0.70 - (ratio * 0.60)), 4)
                    scored_local.append(
                        (
                            dist_score,
                            RagChunk(
                                text=ch.text,
                                score=dist_score,
                                source_uri=ch.source_uri,
                                document_name=d_name,
                                section=ch.section,
                                page_number=ch.page_number,
                                page_range=ch.page_range,
                                signed_url=ch.signed_url,
                            ),
                        )
                    )

        scored_local.sort(key=lambda item: (item[0], item[1].page_number or 0))
        for _, chunk in scored_local[:top_k]:
            sig = chunk.text[:120]
            if sig not in seen_snippets:
                seen_snippets.add(sig)
                results.append(chunk)

        # 2. Query Vertex AI RAG Corpus if configured and additional chunks needed
        if len(results) < top_k and self.project_id:
            try:
                self._ensure_initialized()
                from vertexai.preview import rag

                corpus = self.get_or_create_corpus()
                rag_resource = rag.RagResource(rag_corpus=corpus)
                try:
                    rag_retrieval_config = rag.RagRetrievalConfig(
                        top_k=top_k,
                        filter=rag.Filter(vector_distance_threshold=vector_distance_threshold),
                    )
                    response = rag.retrieval_query(
                        rag_resources=[rag_resource],
                        text=query_text,
                        rag_retrieval_config=rag_retrieval_config,
                    )
                except (AttributeError, TypeError):
                    response = rag.retrieval_query(
                        rag_resources=[rag_resource],
                        text=query_text,
                        similarity_top_k=top_k,
                        vector_distance_threshold=vector_distance_threshold,
                    )

                contexts = getattr(response, "contexts", None)
                context_list = getattr(contexts, "contexts", []) if contexts else []

                for ctx in context_list:
                    text = getattr(ctx, "text", "") or ""
                    sig = text[:120]
                    if not text or sig in seen_snippets:
                        continue
                    source_uri = getattr(ctx, "source_uri", "") or ""
                    doc_display = (
                        getattr(ctx, "source_display_name", "")
                        or (source_uri.split("/")[-1] if source_uri else "Form-10K.pdf")
                    )
                    if document_name and document_name.lower() not in doc_display.lower():
                        continue
                    distance = float(getattr(ctx, "distance", 0.25) or 0.25)
                    signed_url = generate_gcs_signed_url(source_uri) if source_uri.startswith("gs://") else None
                    results.append(
                        RagChunk(
                            text=text,
                            score=distance,
                            source_uri=source_uri,
                            document_name=doc_display,
                            section=detect_10k_section(text),
                            page_number=1,
                            page_range="1",
                            signed_url=signed_url,
                        )
                    )
                    seen_snippets.add(sig)
                    if len(results) >= top_k:
                        break
            except Exception as e:
                logger.debug("Vertex AI RAG query skipped/fallback: %s", e)

        return results[:top_k]

    def list_imported_files(self) -> list[dict[str, Any]]:
        """Lists all 10-K documents available in local cache and Vertex AI RAG corpus."""
        docs_by_name: dict[str, dict[str, Any]] = {}

        for name, meta in self._local_documents.items():
            docs_by_name[name] = dict(meta)

        if self.project_id and self.corpus_id:
            try:
                self._ensure_initialized()
                from vertexai.preview import rag

                corpus = self.get_or_create_corpus()
                files = list(rag.list_files(corpus_name=corpus))
                for f in files:
                    d_name = getattr(f, "display_name", "") or getattr(f, "name", "")
                    if d_name and d_name not in docs_by_name:
                        docs_by_name[d_name] = {
                            "name": getattr(f, "name", ""),
                            "display_name": d_name,
                            "source_uri": getattr(f, "name", ""),
                            "create_time": str(getattr(f, "create_time", "")),
                            "rag_status": "indexed_in_vertex_rag",
                        }
            except Exception as e:
                logger.debug("Failed to list files from Vertex AI RAG: %s", e)

        return list(docs_by_name.values())

