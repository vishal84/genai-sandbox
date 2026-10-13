import React from 'react';
import {
  BookOpen,
  ExternalLink,
  FileText,
  Layers,
  X,
} from 'lucide-react';
import { Citation } from '../types';

interface CitationDrawerProps {
  citation: Citation | null;
  allCitations: Citation[];
  onSelectCitation: (citation: Citation) => void;
  onClose: () => void;
}

export function renderTextWithCitations(
  text: string,
  citations: Citation[],
  onSelectCitation: (c: Citation) => void
): React.ReactNode {
  if (!text) return null;
  const parts = text.split(/(\[\d+(?:,\s*\d+)*\])/g);
  return parts.map((part, idx) => {
    const match = part.match(/^\[(\d+(?:,\s*\d+)*)\]$/);
    if (!match) return <React.Fragment key={idx}>{part}</React.Fragment>;

    const nums = match[1].split(',').map((s) => parseInt(s.trim(), 10));
    return (
      <span key={idx} className="inline-flex items-center gap-1 mx-0.5 align-baseline">
        {nums.map((n) => {
          const found = citations.find((c) => c.citation_index === n);
          return (
            <button
              key={n}
              type="button"
              onClick={() => found && onSelectCitation(found)}
              title={
                found
                  ? `${found.document_name} — ${found.section || 'Page ' + (found.page_number || 1)}`
                  : `Source [${n}]`
              }
              className="inline-flex items-center px-1.5 py-0.5 text-[11px] font-mono font-semibold rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 hover:border-sky-400 transition-colors cursor-pointer"
            >
              [{n}]
            </button>
          );
        })}
      </span>
    );
  });
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({
  citation,
  allCitations,
  onSelectCitation,
  onClose,
}) => {
  if (!citation) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm animate-fadeIn"
      role="dialog"
      aria-modal="true"
      aria-label="10-K Source Evidence Drawer"
    >
      <div className="w-full max-w-xl bg-slate-900 border-l border-slate-800 h-full flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/90">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-mono font-bold bg-sky-500/20 text-sky-300 border border-sky-500/40">
              [{citation.citation_index}]
            </span>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">
                SEC Form 10-K Grounded Evidence
              </h3>
              <p className="text-xs text-slate-400 truncate max-w-sm">
                {citation.document_name}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close citation drawer"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Citation Switcher Pills */}
        {allCitations.length > 1 && (
          <div className="px-6 py-3 bg-slate-950/60 border-b border-slate-800/80 flex items-center gap-1.5 overflow-x-auto">
            <span className="text-[11px] font-medium text-slate-400 mr-1 shrink-0">
              Filing Sources:
            </span>
            {allCitations.map((c) => {
              const active = c.citation_index === citation.citation_index;
              return (
                <button
                  key={c.citation_index}
                  type="button"
                  onClick={() => onSelectCitation(c)}
                  className={`px-2 py-1 rounded text-xs font-mono transition-colors shrink-0 ${
                    active
                      ? 'bg-sky-500 text-slate-950 font-bold'
                      : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700'
                  }`}
                >
                  [{c.citation_index}] p.{c.page_range || c.page_number || 1}
                </button>
              );
            })}
          </div>
        )}

        {/* Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-5">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 bg-slate-950/70 p-4 rounded-xl border border-slate-800/90">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Layers className="w-3.5 h-3.5 text-sky-400" />
                SEC 10-K Section
              </div>
              <div className="mt-1 text-xs font-semibold text-slate-200">
                {citation.section || 'General 10-K Disclosure'}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                Filing Page
              </div>
              <div className="mt-1 text-xs font-mono font-semibold text-slate-200">
                Page {citation.page_range || citation.page_number || '1'}
              </div>
            </div>
            <div className="col-span-2 pt-2 border-t border-slate-800/70">
              <div className="text-[11px] uppercase tracking-wider text-slate-400">
                Storage URI
              </div>
              <div className="mt-0.5 text-xs font-mono text-slate-300 break-all">
                {citation.source_uri}
              </div>
            </div>
          </div>

          {/* Verbatim Excerpt */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-sky-400" />
                Verbatim 10-K Filing Excerpt
              </span>
            </div>
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-slate-200 text-sm leading-relaxed font-sans whitespace-pre-wrap">
              {citation.snippet}
            </div>
          </div>
        </div>

        {/* Footer with Direct Filing Link */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/90 flex items-center justify-between">
          <span className="text-xs text-slate-400">
            Grounded via Vertex AI RAG Engine
          </span>
          {citation.signed_url && (
            <a
              href={citation.signed_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold bg-sky-500 hover:bg-sky-400 text-slate-950 transition-colors"
            >
              <span>Open Full 10-K Filing</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
};

