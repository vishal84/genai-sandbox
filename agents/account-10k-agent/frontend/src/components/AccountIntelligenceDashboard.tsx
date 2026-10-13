import React, { useState } from 'react';
import {
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  ExternalLink,
  FileText,
  MessageSquare,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Target,
} from 'lucide-react';
import {
  AccountAnalysisReport,
  Citation,
} from '../types';
import { renderTextWithCitations } from './CitationDrawer';
import { RecommendationsPanel } from './RecommendationsPanel';
import { RiskAndStrategyPanel } from './RiskAndStrategyPanel';

interface AccountIntelligenceDashboardProps {
  report: AccountAnalysisReport;
  onSelectCitation: (citation: Citation) => void;
  onReanalyze: (customFocus: string) => Promise<void>;
  isReanalyzing: boolean;
  onToggleChat: () => void;
  isChatOpen: boolean;
}

export const AccountIntelligenceDashboard: React.FC<
  AccountIntelligenceDashboardProps
> = ({
  report,
  onSelectCitation,
  onReanalyze,
  isReanalyzing,
  onToggleChat,
  isChatOpen,
}) => {
  const [activeTab, setActiveTab] = useState<'recommendations' | 'strategy' | 'sources'>(
    'recommendations'
  );
  const [customFocusInput, setCustomFocusInput] = useState('');

  const handleFocusSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onReanalyze(customFocusInput.trim());
  };

  const healthBadgeColor =
    report.account_health_score >= 80
      ? 'text-emerald-300 bg-emerald-500/15 border-emerald-500/40'
      : report.account_health_score >= 65
      ? 'text-amber-300 bg-amber-500/15 border-amber-500/40'
      : 'text-rose-300 bg-rose-500/15 border-rose-500/40';

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
      {/* Top Account Header Bar */}
      <header className="px-6 py-4 bg-slate-900/80 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4 shrink-0">
        <div className="flex items-center gap-3.5">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-lg font-bold text-slate-100 tracking-tight">
                {report.company_name}
              </h2>
              <span className="px-2 py-0.5 rounded-md text-xs font-mono font-bold bg-slate-800 text-sky-300 border border-slate-700">
                {report.ticker}
              </span>
              <span className="px-2 py-0.5 rounded-md text-xs font-mono text-slate-300 bg-slate-900 border border-slate-800">
                {report.fiscal_year} Form 10-K
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5 flex items-center gap-2">
              <FileText className="w-3.5 h-3.5 text-slate-400" />
              <span>Source: {report.document_name}</span>
              <span>&bull;</span>
              <span>{report.citations.length} Grounded 10-K Sections</span>
            </p>
          </div>
        </div>

        {/* Right Controls: Health Score + Analyst Copilot Toggle */}
        <div className="flex items-center gap-3">
          <div
            className={`px-3.5 py-1.5 rounded-xl border flex items-center gap-2.5 ${healthBadgeColor}`}
          >
            <div>
              <div className="text-[10px] uppercase tracking-wider font-semibold opacity-80">
                Account Score
              </div>
              <div className="text-xs font-semibold">{report.health_verdict}</div>
            </div>
            <span className="text-xl font-mono font-extrabold tabular-nums">
              {report.account_health_score}
            </span>
          </div>

          <button
            type="button"
            onClick={onToggleChat}
            className={`px-3.5 py-2.5 rounded-xl text-xs font-semibold border flex items-center gap-2 transition-colors cursor-pointer ${
              isChatOpen
                ? 'bg-sky-500 text-slate-950 border-sky-400'
                : 'bg-slate-800/90 hover:bg-slate-800 text-slate-100 border-slate-700'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Ask 10-K Analyst</span>
          </button>
        </div>
      </header>

      {/* Main Scrollable Dashboard Content */}
      <main className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Executive Synthesis Card + Custom Focus Bar */}
        <section className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-sky-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
                Executive 10-K Account Synthesis
              </h3>
            </div>
            <form onSubmit={handleFocusSubmit} className="flex items-center gap-2">
              <input
                type="text"
                value={customFocusInput}
                onChange={(e) => setCustomFocusInput(e.target.value)}
                placeholder="Refocus plays (e.g. Security, FinOps, GenAI)..."
                aria-label="Custom strategic focus for re-analysis"
                className="w-64 px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
              <button
                type="submit"
                disabled={isReanalyzing}
                className="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-medium flex items-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw
                  className={`w-3.5 h-3.5 ${isReanalyzing ? 'animate-spin text-sky-400' : ''}`}
                />
                <span>{isReanalyzing ? 'Analyzing...' : 'Re-Run'}</span>
              </button>
            </form>
          </div>

          <p className="text-sm text-slate-200 leading-relaxed">
            {renderTextWithCitations(
              report.executive_summary,
              report.citations,
              onSelectCitation
            )}
          </p>
        </section>

        {/* Financial KPI Strip (Tabular-Nums) */}
        <section
          aria-label="Key Financial Metrics from Item 7 and Item 8"
          className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
        >
          {report.financial_metrics.map((metric, idx) => {
            const cit = report.citations.find(
              (c) => c.citation_index === metric.citation_index
            );
            return (
              <div
                key={idx}
                className="rounded-2xl bg-slate-900/90 border border-slate-800 p-4 flex flex-col justify-between space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-medium text-slate-400">
                    {metric.label}
                  </span>
                  {metric.citation_index && (
                    <button
                      type="button"
                      onClick={() => cit && onSelectCitation(cit)}
                      className="px-1.5 py-0.5 text-[10px] font-mono font-semibold rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 cursor-pointer"
                    >
                      [{metric.citation_index}]
                    </button>
                  )}
                </div>

                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-2xl font-mono font-bold text-slate-100 tabular-nums">
                    {metric.value}
                  </span>
                  {metric.yoy_change && (
                    <span
                      className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-xs font-mono font-semibold tabular-nums ${
                        metric.trend === 'down'
                          ? 'bg-rose-500/15 text-rose-300'
                          : 'bg-emerald-500/15 text-emerald-300'
                      }`}
                    >
                      {metric.trend === 'down' ? (
                        <ArrowDownRight className="w-3.5 h-3.5" />
                      ) : (
                        <ArrowUpRight className="w-3.5 h-3.5" />
                      )}
                      {metric.yoy_change}
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-slate-400 leading-snug">
                  {renderTextWithCitations(
                    metric.insight,
                    report.citations,
                    onSelectCitation
                  )}
                </p>
              </div>
            );
          })}
        </section>

        {/* Workspace Section Tabs */}
        <div className="border-b border-slate-800 flex items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveTab('recommendations')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'recommendations'
                ? 'border-sky-400 text-sky-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Target className="w-4 h-4" />
            <span>Account Recommendations ({report.recommendations.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('strategy')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'strategy'
                ? 'border-sky-400 text-sky-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>
              Strategic Initiatives &amp; Item 1A Risks (
              {report.strategic_initiatives.length + report.risk_factors.length})
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('sources')}
            className={`px-4 py-2.5 text-xs font-semibold border-b-2 flex items-center gap-2 transition-colors cursor-pointer ${
              activeTab === 'sources'
                ? 'border-sky-400 text-sky-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <BookOpen className="w-4 h-4" />
            <span>10-K Filing Evidence ({report.citations.length})</span>
          </button>
        </div>

        {/* Active Tab Content */}
        {activeTab === 'recommendations' && (
          <RecommendationsPanel
            recommendations={report.recommendations}
            citations={report.citations}
            onSelectCitation={onSelectCitation}
          />
        )}

        {activeTab === 'strategy' && (
          <RiskAndStrategyPanel
            strategicInitiatives={report.strategic_initiatives}
            riskFactors={report.risk_factors}
            citations={report.citations}
            onSelectCitation={onSelectCitation}
          />
        )}

        {activeTab === 'sources' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {report.citations.map((cit) => (
              <div
                key={cit.citation_index}
                onClick={() => onSelectCitation(cit)}
                className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 hover:border-sky-500/40 transition-colors cursor-pointer space-y-2.5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40">
                      [{cit.citation_index}]
                    </span>
                    <span className="text-xs font-semibold text-slate-200">
                      {cit.section || '10-K Filing Excerpt'}
                    </span>
                  </div>
                  <span className="text-xs font-mono text-slate-400">
                    Page {cit.page_range || cit.page_number || 1}
                  </span>
                </div>
                <p className="text-xs text-slate-300 line-clamp-4 leading-relaxed">
                  {cit.snippet}
                </p>
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                  <span className="truncate">{cit.document_name}</span>
                  {cit.signed_url && (
                    <a
                      href={cit.signed_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-sky-400 hover:underline inline-flex items-center gap-1"
                    >
                      <span>Open Filing</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

