import React, { useEffect, useState } from 'react';
import {
  FileUp,
  Loader2,
  Sparkles,
} from 'lucide-react';
import {
  fetchAccounts,
  fetchSamples,
  fetchStatus,
  loadSample10K,
  reanalyzeAccount,
} from './api/client';
import { AccountIntelligenceDashboard } from './components/AccountIntelligenceDashboard';
import { AccountSidebar } from './components/AccountSidebar';
import { AnalystChatDrawer } from './components/AnalystChatDrawer';
import { CitationDrawer } from './components/CitationDrawer';
import { Upload10KModal } from './components/Upload10KModal';
import {
  AccountAnalysisReport,
  AgentStatus,
  Citation,
  SampleFiling,
} from './types';

export const App: React.FC = () => {
  const [accounts, setAccounts] = useState<AccountAnalysisReport[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState<string | null>(null);
  const [samples, setSamples] = useState<SampleFiling[]>([]);
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [isLoadingInitial, setIsLoadingInitial] = useState(true);
  const [isLoadingSample, setIsLoadingSample] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(true);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);

  useEffect(() => {
    async function init() {
      setIsLoadingInitial(true);
      try {
        const [st, accts, smpls] = await Promise.all([
          fetchStatus().catch(() => null),
          fetchAccounts().catch(() => []),
          fetchSamples().catch(() => []),
        ]);
        if (st) setStatus(st);
        setSamples(smpls);
        if (accts.length > 0) {
          setAccounts(accts);
          setSelectedAccountId(accts[0].account_id);
        } else if (smpls.length > 0) {
          const seeded = await loadSample10K(smpls[0].sample_key);
          if (seeded.account_report) {
            setAccounts([seeded.account_report]);
            setSelectedAccountId(seeded.account_report.account_id);
          }
        }
      } finally {
        setIsLoadingInitial(false);
      }
    }
    init();
  }, []);

  const activeAccount =
    accounts.find((a) => a.account_id === selectedAccountId) || accounts[0] || null;

  const upsertAccountReport = (report: AccountAnalysisReport) => {
    setAccounts((prev) => {
      const exists = prev.some((p) => p.account_id === report.account_id);
      if (exists) {
        return prev.map((p) => (p.account_id === report.account_id ? report : p));
      }
      return [report, ...prev];
    });
    setSelectedAccountId(report.account_id);
  };

  const handleLoadSample = async (sampleKey: string) => {
    setIsLoadingSample(true);
    try {
      const res = await loadSample10K(sampleKey);
      if (res.account_report) {
        upsertAccountReport(res.account_report);
      }
    } finally {
      setIsLoadingSample(false);
    }
  };

  const handleReanalyze = async (customFocus: string) => {
    if (!activeAccount) return;
    setIsReanalyzing(true);
    try {
      const updated = await reanalyzeAccount({
        document_name: activeAccount.document_name,
        company_name: activeAccount.company_name,
        ticker: activeAccount.ticker,
        fiscal_year: activeAccount.fiscal_year,
        custom_focus: customFocus || undefined,
      });
      upsertAccountReport(updated);
    } finally {
      setIsReanalyzing(false);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      {/* Left Account & 10-K Sidebar */}
      <AccountSidebar
        accounts={accounts}
        selectedAccountId={activeAccount?.account_id || null}
        onSelectAccount={(id) => setSelectedAccountId(id)}
        onOpenUploadModal={() => setIsUploadModalOpen(true)}
        samples={samples}
        onLoadSample={handleLoadSample}
        isLoadingSample={isLoadingSample}
        status={status}
      />

      {/* Center Account Intelligence Workspace */}
      {isLoadingInitial ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
          <p className="text-sm font-medium text-slate-300">
            Initializing Vertex AI 10-K Account Intelligence Workspace...
          </p>
        </div>
      ) : activeAccount ? (
        <AccountIntelligenceDashboard
          report={activeAccount}
          onSelectCitation={(cit) => setActiveCitation(cit)}
          onReanalyze={handleReanalyze}
          isReanalyzing={isReanalyzing}
          onToggleChat={() => setIsChatOpen((prev) => !prev)}
          isChatOpen={isChatOpen}
        />
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
          <div className="max-w-md space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-sky-500/15 border border-sky-500/30 flex items-center justify-center text-sky-400 mx-auto">
              <FileUp className="w-6 h-6" />
            </div>
            <h2 className="text-lg font-bold text-slate-100">
              Upload an SEC Form 10-K Report to Begin
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Upload any company&apos;s 10-K filing (.PDF, .HTML, or .TXT) or load a sample filing from the sidebar to extract financial health metrics, Item 1A risks, and C-level account recommendations.
            </p>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsUploadModalOpen(true)}
                className="px-4 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-semibold text-xs cursor-pointer"
              >
                Upload 10-K Report
              </button>
              {samples[0] && (
                <button
                  type="button"
                  onClick={() => handleLoadSample(samples[0].sample_key)}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs border border-slate-700 flex items-center gap-1.5 cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Load Sample 10-K</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Right Grounded Analyst Chat Drawer */}
      <AnalystChatDrawer
        isOpen={isChatOpen}
        onClose={() => setIsChatOpen(false)}
        activeAccount={activeAccount}
        onSelectCitation={(cit) => setActiveCitation(cit)}
      />

      {/* Slide-over Citation Evidence Drawer */}
      <CitationDrawer
        citation={activeCitation}
        allCitations={activeAccount?.citations || []}
        onSelectCitation={(cit) => setActiveCitation(cit)}
        onClose={() => setActiveCitation(null)}
      />

      {/* Upload 10-K Modal */}
      <Upload10KModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onAnalysisComplete={(report) => upsertAccountReport(report)}
      />
    </div>
  );
};

export default App;

