import {
  AccountAnalysisReport,
  AgentStatus,
  Citation,
  IndexedDocument,
  SampleFiling,
} from '../types';

export async function fetchStatus(): Promise<AgentStatus> {
  const res = await fetch('/api/status');
  if (!res.ok) throw new Error(`Status check failed (${res.status})`);
  return res.json();
}

export async function fetchAccounts(): Promise<AccountAnalysisReport[]> {
  const res = await fetch('/api/accounts');
  if (!res.ok) throw new Error(`Failed to load accounts (${res.status})`);
  const data = await res.json();
  return data.accounts || [];
}

export async function fetchDocuments(): Promise<IndexedDocument[]> {
  const res = await fetch('/api/documents');
  if (!res.ok) throw new Error(`Failed to load documents (${res.status})`);
  const data = await res.json();
  return data.documents || [];
}

export async function fetchSamples(): Promise<SampleFiling[]> {
  const res = await fetch('/api/samples');
  if (!res.ok) throw new Error(`Failed to load samples (${res.status})`);
  const data = await res.json();
  return data.samples || [];
}

export async function loadSample10K(sampleKey: string): Promise<{
  document: IndexedDocument;
  account_report: AccountAnalysisReport;
}> {
  const res = await fetch('/api/sample', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sample_key: sampleKey }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to load sample 10-K (${res.status})`);
  }
  return res.json();
}

export async function upload10KFile(params: {
  file: File;
  companyName?: string;
  ticker?: string;
  fiscalYear?: string;
  customFocus?: string;
}): Promise<{
  status: string;
  document: IndexedDocument;
  account_report: AccountAnalysisReport;
}> {
  const formData = new FormData();
  formData.append('file', params.file);
  if (params.companyName) formData.append('company_name', params.companyName);
  if (params.ticker) formData.append('ticker', params.ticker);
  if (params.fiscalYear) formData.append('fiscal_year', params.fiscalYear);
  if (params.customFocus) formData.append('custom_focus', params.customFocus);
  formData.append('auto_analyze', 'true');

  const res = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to upload 10-K report (${res.status})`);
  }
  return res.json();
}

export async function reanalyzeAccount(params: {
  document_name: string;
  company_name?: string;
  ticker?: string;
  fiscal_year?: string;
  custom_focus?: string;
}): Promise<AccountAnalysisReport> {
  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Analysis failed (${res.status})`);
  }
  return res.json();
}

export async function ingestGcs10K(params: {
  gcs_uris?: string[];
  folder_uri?: string;
  company_name?: string;
  ticker?: string;
  fiscal_year?: string;
}): Promise<{
  status: string;
  imported_files_count: number;
  message?: string;
  account_report?: AccountAnalysisReport;
}> {
  const res = await fetch('/api/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...params, auto_analyze: true }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `GCS ingestion failed (${res.status})`);
  }
  return res.json();
}

export async function sendAnalystQuestion(params: {
  message: string;
  account_id?: string;
  document_name?: string;
  session_id?: string;
}): Promise<{
  answer: string;
  citations: Citation[];
  session_id: string;
}> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to query 10-K agent (${res.status})`);
  }
  return res.json();
}

