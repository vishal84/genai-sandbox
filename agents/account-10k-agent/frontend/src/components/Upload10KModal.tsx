import React, { useState } from 'react';
import {
  AlertCircle,
  CloudUpload,
  Database,
  FileText,
  Loader2,
  X,
} from 'lucide-react';
import { ingestGcs10K, upload10KFile } from '../api/client';
import { AccountAnalysisReport } from '../types';

interface Upload10KModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAnalysisComplete: (report: AccountAnalysisReport) => void;
}

export const Upload10KModal: React.FC<Upload10KModalProps> = ({
  isOpen,
  onClose,
  onAnalysisComplete,
}) => {
  const [mode, setMode] = useState<'file' | 'gcs'>('file');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [companyName, setCompanyName] = useState('');
  const [ticker, setTicker] = useState('');
  const [fiscalYear, setFiscalYear] = useState('FY2025');
  const [customFocus, setCustomFocus] = useState('');
  const [gcsUriInput, setGcsUriInput] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setErrorMsg(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setIsSubmitting(true);

    try {
      if (mode === 'file') {
        if (!selectedFile) {
          throw new Error('Please select a 10-K report file (.pdf, .html, .txt, or .md).');
        }
        const res = await upload10KFile({
          file: selectedFile,
          companyName: companyName.trim() || undefined,
          ticker: ticker.trim() || undefined,
          fiscalYear: fiscalYear.trim() || undefined,
          customFocus: customFocus.trim() || undefined,
        });
        if (res.account_report) {
          onAnalysisComplete(res.account_report);
        }
        onClose();
      } else {
        const cleanUri = gcsUriInput.trim();
        if (!cleanUri.startsWith('gs://')) {
          throw new Error('Please enter a valid Google Cloud Storage URI starting with gs://');
        }
        const isFolder = cleanUri.endsWith('/');
        const res = await ingestGcs10K({
          gcs_uris: isFolder ? [] : [cleanUri],
          folder_uri: isFolder ? cleanUri : undefined,
          company_name: companyName.trim() || undefined,
          ticker: ticker.trim() || undefined,
          fiscal_year: fiscalYear.trim() || undefined,
        });
        if (res.account_report) {
          onAnalysisComplete(res.account_report);
        }
        onClose();
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to ingest and analyze 10-K filing.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/75 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="upload-10k-title"
    >
      <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div>
            <h2 id="upload-10k-title" className="text-base font-bold text-slate-100">
              Upload &amp; Analyze SEC Form 10-K Filing
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Indexes into Vertex AI RAG Engine and extracts account recommendations
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close modal"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Mode Switcher */}
        <div className="px-6 pt-4 flex gap-2">
          <button
            type="button"
            onClick={() => setMode('file')}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 border transition-colors cursor-pointer ${
              mode === 'file'
                ? 'bg-sky-500/15 border-sky-500/50 text-sky-300'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <CloudUpload className="w-4 h-4" />
            <span>Direct File Upload (.PDF / .HTML / .TXT)</span>
          </button>
          <button
            type="button"
            onClick={() => setMode('gcs')}
            className={`flex-1 py-2 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 border transition-colors cursor-pointer ${
              mode === 'gcs'
                ? 'bg-sky-500/15 border-sky-500/50 text-sky-300'
                : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-4 h-4" />
            <span>Google Cloud Storage (gs://)</span>
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {mode === 'file' ? (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleFileDrop}
              className="border-2 border-dashed border-slate-700 hover:border-sky-500/60 rounded-xl p-6 text-center bg-slate-950/50 transition-colors"
            >
              <input
                id="file-upload-input"
                type="file"
                accept=".pdf,.html,.htm,.txt,.md"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setSelectedFile(e.target.files[0]);
                    setErrorMsg(null);
                  }
                }}
                className="hidden"
              />
              <label
                htmlFor="file-upload-input"
                className="cursor-pointer flex flex-col items-center gap-2"
              >
                <div className="w-11 h-11 rounded-full bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
                  <FileText className="w-5 h-5" />
                </div>
                {selectedFile ? (
                  <div>
                    <p className="text-sm font-semibold text-emerald-300">
                      {selectedFile.name}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {(selectedFile.size / 1024).toFixed(1)} KB &bull; Click to change file
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-xs font-semibold text-slate-200">
                      Drag &amp; drop a 10-K filing here, or <span className="text-sky-400 underline">browse</span>
                    </p>
                    <p className="text-[11px] text-slate-400 mt-1">
                      Supports SEC Form 10-K in PDF, HTML, TXT, or Markdown
                    </p>
                  </div>
                )}
              </label>
            </div>
          ) : (
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                GCS 10-K Document or Folder URI
              </label>
              <input
                type="text"
                value={gcsUriInput}
                onChange={(e) => setGcsUriInput(e.target.value)}
                placeholder="gs://your-10k-bucket/filings/company-2025-10k.pdf"
                className="w-full px-3.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
              />
            </div>
          )}

          {/* Optional Account Metadata */}
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-1">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Company Name (optional)
              </label>
              <input
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Auto-detected"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Ticker Symbol
              </label>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                placeholder="e.g. ACME"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono uppercase text-slate-100 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">
                Fiscal Year
              </label>
              <input
                type="text"
                value={fiscalYear}
                onChange={(e) => setFiscalYear(e.target.value)}
                placeholder="FY2025"
                className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-slate-100 focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-medium text-slate-400 mb-1">
              Strategic Account Focus (optional)
            </label>
            <input
              type="text"
              value={customFocus}
              onChange={(e) => setCustomFocus(e.target.value)}
              placeholder="e.g. Cloud Migration, GenAI Copilot, Mainframe Exit, Cybersecurity"
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
            />
          </div>

          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="pt-2 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 rounded-lg text-xs font-semibold bg-sky-500 hover:bg-sky-400 text-slate-950 flex items-center gap-2 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Indexing &amp; Analyzing 10-K...</span>
                </>
              ) : (
                <span>Ingest &amp; Generate Recommendations</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

