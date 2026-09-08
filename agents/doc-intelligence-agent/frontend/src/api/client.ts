import { Citation, DocumentMetadata, IngestResult } from '../types';

const API_BASE = '/api';

export async function askAgent(message: string, sessionId?: string): Promise<{
  answer: string;
  citations: Citation[];
  raw_chunks: any[];
  session_id?: string;
}> {
  const response = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(err.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}

export async function ingestDocuments(gcsUris: string[]): Promise<IngestResult> {
  const response = await fetch(`${API_BASE}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gcs_uris: gcsUris }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Ingestion failed' }));
    throw new Error(err.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}

export async function fetchIndexedDocuments(): Promise<DocumentMetadata[]> {
  try {
    const response = await fetch(`${API_BASE}/documents`);
    if (!response.ok) return [];
    const data = await response.json();
    return data.documents || [];
  } catch (err) {
    console.error('Failed to load documents:', err);
    return [];
  }
}

export async function sendFeedback(score: number, comment?: string, query?: string): Promise<void> {
  await fetch('/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ score, comment, query }),
  }).catch(() => {});
}

