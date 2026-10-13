import React from 'react';
import {
  Building2,
  Database,
  FileSpreadsheet,
  FolderUp,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import {
  AccountAnalysisReport,
  AgentStatus,
  SampleFiling,
} from '../types';

interface AccountSidebarProps {
  accounts: AccountAnalysisReport[];
  selectedAccountId: string | null;
  onSelectAccount: (accountId: string) => void;
  onOpenUploadModal: () => void;
  samples: SampleFiling[];
  onLoadSample: (sampleKey: string) => void;
  isLoadingSample: boolean;
  status: AgentStatus | null;
}

export const AccountSidebar: React.FC<AccountSidebarProps> = ({
  accounts,
  selectedAccountId,
  onSelectAccount,
  onOpenUploadModal,
  samples,
  onLoadSample,
  isLoadingSample,
  status,
}) => {
  return (
    <aside
      aria-label="Account Intelligence Navigation"
      className="w-72 shrink-0 bg-slate-900/90 border-r border-slate-800 flex flex-col h-full select-none"
    >
      {/* Brand Header */}
      <div className="p-4 border-b border-slate-800 flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-sky-500/15 border border-sky-500/40 flex items-center justify-center text-sky-400 shrink-0">
          <TrendingUp className="w-5 h-5" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <h1 className="text-sm font-bold tracking-tight text-slate-100 truncate">
              10-K Account Intel
            </h1>
            <span className="px-1.5 py-0.5 text-[10px] font-mono font-semibold uppercase rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              ADK 2.0
            </span>
          </div>
          <p className="text-[11px] text-slate-400 truncate">
            Vertex AI RAG &bull; Account Strategy
          </p>
        </div>
      </div>

      {/* Primary Action: Upload 10-K Report */}
      <div className="p-3.5 border-b border-slate-800/80">
        <button
          type="button"
          onClick={onOpenUploadModal}
          className="w-full py-2.5 px-3.5 rounded-lg bg-sky-500 hover:bg-sky-400 active:bg-sky-600 text-slate-950 font-semibold text-xs flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer"
        >
          <FolderUp className="w-4 h-4 stroke-[2.2]" />
          <span>Upload 10-K Report</span>
        </button>
      </div>

      {/* Analyzed Accounts List */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-5">
        <div>
          <div className="px-2 mb-2 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Analyzed Accounts ({accounts.length})
            </span>
          </div>
          <div className="space-y-1.5">
            {accounts.map((acct) => {
              const isSelected = acct.account_id === selectedAccountId;
              const scoreColor =
                acct.account_health_score >= 80
                  ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
                  : acct.account_health_score >= 65
                  ? 'text-amber-400 bg-amber-500/10 border-amber-500/30'
                  : 'text-rose-400 bg-rose-500/10 border-rose-500/30';

              return (
                <button
                  key={acct.account_id}
                  type="button"
                  onClick={() => onSelectAccount(acct.account_id)}
                  className={`w-full text-left p-2.5 rounded-xl border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-slate-800/95 border-sky-500/50 shadow-sm'
                      : 'bg-slate-900/40 border-slate-800/70 hover:bg-slate-800/50 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <Building2
                        className={`w-4 h-4 shrink-0 ${
                          isSelected ? 'text-sky-400' : 'text-slate-400'
                        }`}
                      />
                      <span className="text-xs font-semibold text-slate-100 truncate">
                        {acct.company_name}
                      </span>
                    </div>
                    <span
                      className={`px-1.5 py-0.5 text-[10px] font-mono font-bold rounded border tabular-nums shrink-0 ${scoreColor}`}
                      title="Account Health & Opportunity Score"
                    >
                      {acct.account_health_score}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-400 pl-6">
                    <span className="font-mono font-medium text-slate-300">
                      {acct.ticker} &bull; {acct.fiscal_year}
                    </span>
                    <span>{acct.recommendations.length} plays</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Sample 10-K Filings for Instant Testing */}
        {samples.length > 0 && (
          <div className="pt-2 border-t border-slate-800/80">
            <div className="px-2 mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Sample SEC 10-K Filings
              </span>
            </div>
            <div className="space-y-1.5">
              {samples.map((s) => (
                <button
                  key={s.sample_key}
                  type="button"
                  disabled={isLoadingSample}
                  onClick={() => onLoadSample(s.sample_key)}
                  className="w-full text-left px-2.5 py-2 rounded-lg bg-slate-950/60 hover:bg-slate-800/70 border border-slate-800/80 hover:border-slate-700 transition-colors flex items-center justify-between gap-2 disabled:opacity-50 cursor-pointer"
                >
                  <div className="min-w-0">
                    <div className="text-xs font-medium text-slate-200 truncate">
                      {s.company_name}
                    </div>
                    <div className="text-[10px] font-mono text-slate-400">
                      {s.ticker} &bull; {s.fiscal_year} Form 10-K
                    </div>
                  </div>
                  <FileSpreadsheet className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Vertex AI Platform Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/60 text-[11px] text-slate-400 space-y-1">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-slate-300 font-medium">
            <Database className="w-3.5 h-3.5 text-emerald-400" />
            Vertex AI RAG Engine
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] font-mono text-emerald-400">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Active
          </span>
        </div>
        <div className="font-mono text-[10px] text-slate-400 truncate">
          Model: {status?.model || 'gemini-3.8-flash'} ({status?.location || 'global'})
        </div>
      </div>
    </aside>
  );
};

