import React from 'react';
import { X, ExternalLink, FileText, CheckCircle2 } from 'lucide-react';
import { Citation } from '../types';

interface CitationDrawerProps {
  citation: Citation | null;
  onClose: () => void;
}

export const CitationDrawer: React.FC<CitationDrawerProps> = ({ citation, onClose }) => {
  if (!citation) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-slate-800 border-l border-slate-700 shadow-2xl z-50 flex flex-col p-6 animate-in slide-in-from-right duration-200">
      <div className="flex items-center justify-between pb-4 border-b border-slate-700">
        <div className="flex items-center space-x-2">
          <span className="flex items-center justify-center w-7 h-7 rounded-full bg-blue-600/30 text-blue-400 font-semibold text-xs border border-blue-500/40">
            [{citation.citation_index}]
          </span>
          <h3 className="font-semibold text-slate-100 text-sm truncate max-w-[200px]" title={citation.document_name}>
            {citation.document_name}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-slate-400 hover:text-slate-200 hover:bg-slate-700/50 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-4 space-y-5">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">
              Grounded Evidence Excerpt
            </label>
            <span className="text-[10px] text-blue-400 font-medium">
              Evidence from {citation.page_range ? `Page ${citation.page_range}` : (citation.page_number ? `Page ${citation.page_number}` : 'Source')}
            </span>
          </div>
          <div className="bg-slate-900/90 p-4 rounded-xl border border-blue-500/30 text-slate-100 text-xs leading-relaxed font-sans shadow-inner relative">
            <p className="italic font-normal">"{citation.snippet}"</p>
          </div>
        </div>

        <div className="space-y-2 text-xs">
          <div className="flex justify-between py-1.5 border-b border-slate-700/40">
            <span className="text-slate-400">Document Name</span>
            <span className="text-slate-200 font-medium truncate max-w-[180px]">{citation.document_name}</span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-slate-700/40">
            <span className="text-slate-400">Page Reference</span>
            <span className="text-amber-300 font-medium bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
              {citation.page_range ? `Page ${citation.page_range}` : (citation.page_number ? `Page ${citation.page_number}` : 'Indexed Section')}
            </span>
          </div>

          <div className="flex justify-between py-1.5 border-b border-slate-700/40">
            <span className="text-slate-400">Verification</span>
            <span className="flex items-center text-emerald-400 space-x-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>RAG Verified</span>
            </span>
          </div>

          <div className="pt-2">
            <span className="text-slate-400 block mb-1">Cloud Storage Source</span>
            <p className="font-mono text-[11px] text-slate-300 bg-slate-900/50 p-2 rounded break-all border border-slate-800">
              {citation.source_uri}
            </p>
          </div>
        </div>
      </div>

      <div className="pt-4 border-t border-slate-700">
        {citation.signed_url ? (
          <a
            href={citation.signed_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center space-x-2 w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium text-xs transition-colors shadow-lg shadow-blue-600/20"
          >
            <FileText className="w-4 h-4" />
            <span>Download / Open Source PDF</span>
            <ExternalLink className="w-3.5 h-3.5 ml-1" />
          </a>
        ) : (
          <div className="text-center text-xs text-slate-400 py-2">
            Direct download link not generated.
          </div>
        )}
      </div>
    </div>
  );
};

