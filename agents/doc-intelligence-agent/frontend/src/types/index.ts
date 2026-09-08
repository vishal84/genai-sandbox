export interface Citation {
  citation_index: number;
  document_name: string;
  source_uri: string;
  page_number?: number | null;
  snippet: string;
  signed_url?: string | null;
}

export interface Message {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: string;
  citations?: Citation[];
  raw_chunks?: any[];
}

export interface DocumentMetadata {
  name: string;
  display_name: string;
  source_uri: string;
  create_time?: string;
}

export interface IngestResult {
  status: string;
  imported_files_count: number;
  message?: string;
}

