import React, { useState } from 'react';
import { Database, Plus, RefreshCw, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { DocumentMetadata } from '../types';
import { ingestDocuments } from '../api/client';

interface DocumentExplorerProps {
  documents: DocumentMetadata[];
  onRefresh: () => void;
  isLoading: boolean;
}

export const DocumentExplorer: React.FC<DocumentExplorerProps> = ({
  documents,
  onRefresh,
  isLoading,
}) => {
  const [showIngestInput, setShowIngestInput] = useState(false);
  const [gcsUriInput, setGcsUriInput] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<{ success?: boolean; message?: string } | null>(null);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gcsUriInput.trim()) return;

    const uris = gcsUriInput
      .split('\n')
      .map(u => u.trim())
      .filter(u => u.startsWith('gs://'));

    if (uris.length === 0) {
      setIngestStatus({
        success: false,
        message: 'Must enter at least one valid gs:// URI',
      });
      return;
    }

    setIsIngesting(true);
    setIngestStatus(null);

    try {
      const result = await ingestDocuments(uris);
      setIngestStatus({
        success: true,
        message: result.message || `Ingestion submitted for ${uris.length} file(s).`,
      });
      setGcsUriInput('');
      setShowIngestInput(false);
      onRefresh();
    } catch (err: any) {
      setIngestStatus({
        success: false,
        message: err.message || 'Ingestion failed.',
      });
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col h-full select-none">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Database className="w-5 h-5 text-blue-400" />
          <h2 className="font-semibold text-sm text-slate-100">RAG Document Store</h2>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          title="Refresh indexed files"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="p-3">
        <button
          onClick={() => setShowIngestInput(!showIngestInput)}
          className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/30 rounded-lg text-xs font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Ingest GCS PDF</span>
        </button>

        {showIngestInput && (
          <form onSubmit={handleIngest} className="mt-3 p-3 bg-slate-800/80 rounded-lg border border-slate-700/60 space-y-2">
            <label className="text-[11px] font-medium text-slate-300 block">
              GCS Bucket URIs (one per line)
            </label>
            <textarea
              value={gcsUriInput}
              onChange={(e) => setGcsUriInput(e.target.value)}
              placeholder="gs://my-bucket/documents/quarterly_report.pdf"
              rows={3}
              className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500"
            />
            <div className="flex justify-end space-x-2 pt-1">
              <button
                type="button"
                onClick={() => setShowIngestInput(false)}
                className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isIngesting}
                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium transition-colors disabled:opacity-50"
              >
                {isIngesting ? 'Ingesting...' : 'Submit'}
              </button>
            </div>
          </form>
        )}

        {ingestStatus && (
          <div className={`mt-2 p-2 rounded text-xs flex items-start space-x-2 ${
            ingestStatus.success ? 'bg-emerald-950/60 text-emerald-300 border border-emerald-800' : 'bg-red-950/60 text-red-300 border border-red-800'
          }`}>
            {ingestStatus.success ? (
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            )}
            <span className="text-[11px] leading-tight">{ingestStatus.message}</span>
          </div>
        )}
      </div>

      <div className="px-4 py-2 flex items-center justify-between text-xs text-slate-400 border-b border-slate-800/60">
        <span>Indexed Corpus ({documents.length})</span>
        <span className="text-[10px] uppercase tracking-wider text-slate-400">Vertex AI RAG</span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {documents.length === 0 ? (
          <div className="text-center py-8 px-4 text-slate-400 text-xs">
            <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p>No documents imported yet.</p>
            <p className="mt-1 text-[11px] text-slate-400">
              Provide a GCS bucket URI above to index PDFs into Vertex AI RAG.
            </p>
          </div>
        ) : (
          documents.map((doc, idx) => (
            <div
              key={idx}
              className="p-2.5 rounded-lg bg-slate-800/40 hover:bg-slate-800/80 border border-slate-700/40 transition-colors"
            >
              <div className="flex items-start space-x-2">
                <FileText className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-slate-200 truncate" title={doc.display_name || doc.name}>
                    {doc.display_name || doc.name.split('/').pop()}
                  </p>
                  <p className="text-[10px] text-slate-400 font-mono truncate mt-0.5" title={doc.source_uri}>
                    {doc.source_uri || 'Internal corpus'}
                  </p>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </aside>
  );
};

