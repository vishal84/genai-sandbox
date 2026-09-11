import React, { useState } from 'react';
import { Database, Plus, RefreshCw, FileText, CheckCircle, AlertCircle, FolderDown } from 'lucide-react';
import { DocumentMetadata } from '../types';
import { ingestDocuments, ingestFolder } from '../api/client';

interface DocumentExplorerProps {
  documents: DocumentMetadata[];
  onRefresh: () => void;
  isLoading: boolean;
}

type IngestMode = 'folder' | 'files';

export const DocumentExplorer: React.FC<DocumentExplorerProps> = ({
  documents,
  onRefresh,
  isLoading,
}) => {
  const [showIngestInput, setShowIngestInput] = useState(false);
  const [ingestMode, setIngestMode] = useState<IngestMode>('folder');
  const [folderUriInput, setFolderUriInput] = useState('');
  const [gcsUriInput, setGcsUriInput] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [ingestStatus, setIngestStatus] = useState<{ success?: boolean; message?: string } | null>(null);

  const handleIngestFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setIngestStatus(null);

    const trimmed = folderUriInput.trim();
    if (!trimmed) {
      setValidationError('When ingesting all, a folder path must be provided.');
      return;
    }

    if (!trimmed.startsWith('gs://')) {
      setValidationError('Folder path must start with gs:// (e.g., gs://bucket-name/folder/).');
      return;
    }

    const pathPart = trimmed.slice(5).replace(/^\/+|\/+$/g, '');
    const parts = pathPart.split('/');

    if (parts.length < 2 || !parts[1]) {
      setValidationError(
        'When ingesting all, a folder path must be provided (e.g., gs://bucket-name/folder/). A bucket root alone is not permitted.'
      );
      return;
    }

    const lastPart = parts[parts.length - 1].toLowerCase();
    const docExtensions = ['.pdf', '.txt', '.docx', '.html', '.md'];
    if (docExtensions.some(ext => lastPart.endsWith(ext))) {
      setValidationError(
        'A folder path must be provided when ingesting all, not a single file URI. For single files, use Ingest Files.'
      );
      return;
    }

    setIsIngesting(true);

    try {
      const normFolder = `gs://${parts[0]}/${parts.slice(1).join('/')}/`;
      const result = await ingestFolder(normFolder);
      setIngestStatus({
        success: result.status !== 'error',
        message: result.message || `Successfully submitted folder '${normFolder}' for ingestion.`,
      });
      if (result.status !== 'error') {
        setFolderUriInput('');
        setShowIngestInput(false);
        onRefresh();
      }
    } catch (err: any) {
      setIngestStatus({
        success: false,
        message: err.message || 'Folder ingestion failed.',
      });
    } finally {
      setIsIngesting(false);
    }
  };

  const handleIngestFiles = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    setIngestStatus(null);

    if (!gcsUriInput.trim()) {
      setValidationError('Must enter at least one valid gs:// URI.');
      return;
    }

    const uris = gcsUriInput
      .split('\n')
      .map(u => u.trim())
      .filter(u => u.startsWith('gs://'));

    if (uris.length === 0) {
      setValidationError('Must enter at least one valid gs:// URI.');
      return;
    }

    setIsIngesting(true);

    try {
      const result = await ingestDocuments(uris);
      setIngestStatus({
        success: result.status !== 'error',
        message: result.message || `Ingestion submitted for ${uris.length} file(s).`,
      });
      if (result.status !== 'error') {
        setGcsUriInput('');
        setShowIngestInput(false);
        onRefresh();
      }
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
        {/* Ingestion Action Buttons */}
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => {
              if (showIngestInput && ingestMode === 'folder') {
                setShowIngestInput(false);
              } else {
                setIngestMode('folder');
                setShowIngestInput(true);
                setValidationError(null);
              }
            }}
            className={`flex items-center justify-center space-x-1.5 py-2 px-2.5 rounded-lg text-xs font-medium border transition-colors ${
              showIngestInput && ingestMode === 'folder'
                ? 'bg-blue-600 text-white border-blue-500 shadow-sm'
                : 'bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border-blue-500/30'
            }`}
            title="Ingest all documents within a GCS bucket folder"
          >
            <FolderDown className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">Ingest All</span>
          </button>

          <button
            onClick={() => {
              if (showIngestInput && ingestMode === 'files') {
                setShowIngestInput(false);
              } else {
                setIngestMode('files');
                setShowIngestInput(true);
                setValidationError(null);
              }
            }}
            className={`flex items-center justify-center space-x-1.5 py-2 px-2.5 rounded-lg text-xs font-medium border transition-colors ${
              showIngestInput && ingestMode === 'files'
                ? 'bg-slate-700 text-white border-slate-600 shadow-sm'
                : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border-slate-700/60'
            }`}
            title="Ingest specific PDF file URIs"
          >
            <Plus className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">Ingest Files</span>
          </button>
        </div>

        {showIngestInput && (
          <div className="mt-3 p-3 bg-slate-800/80 rounded-lg border border-slate-700/60 space-y-2.5">
            {/* Mode Switcher Tabs */}
            <div className="flex border-b border-slate-700/60 pb-1.5">
              <button
                type="button"
                onClick={() => {
                  setIngestMode('folder');
                  setValidationError(null);
                }}
                className={`text-[11px] font-medium pb-1 mr-3 border-b-2 transition-colors ${
                  ingestMode === 'folder'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-400 hover:text-slate-300'
                }`}
              >
                Ingest All (Folder)
              </button>
              <button
                type="button"
                onClick={() => {
                  setIngestMode('files');
                  setValidationError(null);
                }}
                className={`text-[11px] font-medium pb-1 border-b-2 transition-colors ${
                  ingestMode === 'files'
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-400 hover:text-slate-300'
                }`}
              >
                Single Files
              </button>
            </div>

            {ingestMode === 'folder' ? (
              <form onSubmit={handleIngestFolder} className="space-y-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-300 block mb-0.5">
                    GCS Bucket Folder Path
                  </label>
                  <p className="text-[10px] text-slate-400 mb-1 leading-tight">
                    A folder path must be provided. All supported documents in this folder will be ingested.
                  </p>
                  <input
                    type="text"
                    value={folderUriInput}
                    onChange={(e) => {
                      setFolderUriInput(e.target.value);
                      if (validationError) setValidationError(null);
                    }}
                    placeholder="gs://my-bucket/contracts/"
                    className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>

                {validationError && (
                  <div className="p-2 rounded text-[11px] bg-red-950/70 border border-red-800 text-red-300 flex items-start space-x-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                    <span>{validationError}</span>
                  </div>
                )}

                <div className="flex justify-end space-x-2 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setShowIngestInput(false);
                      setValidationError(null);
                    }}
                    className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isIngesting}
                    className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium transition-colors disabled:opacity-50 flex items-center space-x-1"
                  >
                    <FolderDown className="w-3.5 h-3.5" />
                    <span>{isIngesting ? 'Ingesting All...' : 'Ingest All'}</span>
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleIngestFiles} className="space-y-2">
                <div>
                  <label className="text-[11px] font-medium text-slate-300 block mb-0.5">
                    GCS Bucket URIs (one per line)
                  </label>
                  <textarea
                    value={gcsUriInput}
                    onChange={(e) => {
                      setGcsUriInput(e.target.value);
                      if (validationError) setValidationError(null);
                    }}
                    placeholder="gs://my-bucket/documents/quarterly_report.pdf"
                    rows={3}
                    className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-blue-500"
                  />
                </div>

                {validationError && (
                  <div className="p-2 rounded text-[11px] bg-red-950/70 border border-red-800 text-red-300 flex items-start space-x-1.5">
                    <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
                    <span>{validationError}</span>
                  </div>
                )}

                <div className="flex justify-end space-x-2 pt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setShowIngestInput(false);
                      setValidationError(null);
                    }}
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
          </div>
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

