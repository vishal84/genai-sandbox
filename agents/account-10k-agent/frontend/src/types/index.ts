export interface Citation {
  citation_index: number;
  document_name: string;
  source_uri: string;
  section?: string | null;
  page_number?: number | null;
  page_range?: string | null;
  snippet: string;
  signed_url?: string | null;
}

export interface FinancialMetric {
  label: string;
  value: string;
  yoy_change?: string | null;
  trend: 'up' | 'down' | 'neutral';
  insight: string;
  citation_index?: number | null;
}

export interface StrategicInitiative {
  title: string;
  category: string;
  description: string;
  investment_signal: string;
  citation_index?: number | null;
}

export interface RiskFactorItem {
  category: string;
  title: string;
  severity: 'high' | 'medium' | 'low';
  description: string;
  account_opportunity: string;
  citation_index?: number | null;
}

export type RecommendationCategory =
  | 'Cloud & AI Modernization'
  | 'Data & Analytics'
  | 'Security & Compliance'
  | 'Cost & Operational Efficiency'
  | 'Revenue & GTM Expansion';

export interface AccountRecommendation {
  id: string;
  title: string;
  category: RecommendationCategory;
  priority: 'High' | 'Medium' | 'Low';
  confidence_score: number;
  target_stakeholder: string;
  rationale: string;
  recommended_actions: string[];
  talking_points: string[];
  citation_indices: number[];
}

export interface AccountAnalysisReport {
  account_id: string;
  company_name: string;
  ticker: string;
  fiscal_year: string;
  document_name: string;
  source_uri: string;
  analyzed_at: string;
  account_health_score: number;
  health_verdict: string;
  executive_summary: string;
  financial_metrics: FinancialMetric[];
  strategic_initiatives: StrategicInitiative[];
  risk_factors: RiskFactorItem[];
  recommendations: AccountRecommendation[];
  citations: Citation[];
}

export interface IndexedDocument {
  name: string;
  display_name: string;
  source_uri?: string;
  signed_url?: string;
  company_name?: string;
  ticker?: string;
  fiscal_year?: string;
  pages_count?: number;
  rag_status?: string;
  create_time?: string;
}

export interface SampleFiling {
  sample_key: string;
  filename: string;
  company_name: string;
  ticker: string;
  fiscal_year: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: string;
}

export interface AgentStatus {
  status: string;
  agent: string;
  model: string;
  project: string;
  location: string;
  rag_location: string;
  rag_corpus_id: string;
  gcs_bucket: string;
  accounts_count: number;
  documents_count: number;
}

