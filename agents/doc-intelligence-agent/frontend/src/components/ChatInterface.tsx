import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, BookOpen, ExternalLink, ThumbsUp } from 'lucide-react';
import { Message, Citation } from '../types';

interface ChatInterfaceProps {
  messages: Message[];
  onSendMessage: (query: string) => void;
  isLoading: boolean;
  onSelectCitation: (citation: Citation) => void;
  onSendFeedback?: (score: number, query?: string) => void;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  messages,
  onSendMessage,
  isLoading,
  onSelectCitation,
  onSendFeedback,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  const renderMessageContent = (text: string, citations?: Citation[]) => {
    if (!citations || citations.length === 0) {
      return <span>{text}</span>;
    }

    // Split text by citation brackets like [1], [2]
    const parts = text.split(/(\[\d+\])/g);
    return (
      <span>
        {parts.map((part, index) => {
          const match = part.match(/^\[(\d+)\]$/);
          if (match) {
            const citeIdx = parseInt(match[1], 10);
            const foundCitation = citations.find((c) => c.citation_index === citeIdx);
            return (
              <button
                key={index}
                onClick={() => foundCitation && onSelectCitation(foundCitation)}
                title={foundCitation ? `${foundCitation.document_name} (${foundCitation.source_uri})` : 'View Citation'}
                className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 rounded text-[11px] font-bold bg-blue-500/20 text-blue-300 hover:bg-blue-500/40 hover:text-white border border-blue-400/30 transition-all cursor-pointer"
              >
                {part}
              </button>
            );
          }
          return <span key={index}>{part}</span>;
        })}
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 overflow-hidden">
      {/* Header */}
      <header className="px-6 py-3.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100">Analyst Research Workspace</h1>
            <p className="text-[11px] text-slate-400">Grounded ADK 2.0 Graph Agent • Vertex AI RAG</p>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="px-2.5 py-1 rounded-full bg-emerald-950/60 text-emerald-400 border border-emerald-800/60 font-medium text-[11px]">
            ● RAG Grounded
          </span>
        </div>
      </header>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4 text-slate-400">
            <div className="w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <h3 className="text-base font-medium text-slate-200">Ask the Document Intelligence Agent</h3>
              <p className="text-xs text-slate-400 mt-1">
                Answers are grounded strictly in your Vertex AI RAG corpus with short, concise explanations and direct PDF download links.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-2 w-full pt-2">
              {[
                'What are the key financial highlights and revenue figures?',
                'Summarize the compliance and risk obligations mentioned.',
                'Find references to regulatory audit deadlines and deliverables.',
              ].map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => onSendMessage(sample)}
                  className="text-left p-3 rounded-lg bg-slate-900/60 hover:bg-slate-850 hover:border-slate-700 text-xs text-slate-300 border border-slate-800/80 transition-all"
                >
                  "{sample}"
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.sender === 'agent' && (
                <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-4 h-4 text-blue-400" />
                </div>
              )}

              <div
                className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-sm shadow-md shadow-blue-600/10'
                    : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-sm'
                }`}
              >
                <div className="text-sm font-normal">
                  {renderMessageContent(msg.text, msg.citations)}
                </div>

                {/* Citations List on Agent Message */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-800/80 space-y-1.5">
                    <span className="text-[10px] uppercase font-semibold text-slate-400 tracking-wider block">
                      Grounded Sources ({msg.citations.length})
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.citations.map((cite) => (
                        <button
                          key={cite.citation_index}
                          onClick={() => onSelectCitation(cite)}
                          className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800/90 hover:bg-slate-750 border border-slate-700/80 text-[11px] text-slate-300 transition-colors"
                        >
                          <span className="text-blue-400 font-bold">[{cite.citation_index}]</span>
                          <span className="truncate max-w-[140px]">{cite.document_name}</span>
                          {cite.page_number && <span className="text-slate-400">p.{cite.page_number}</span>}
                          {cite.signed_url && <ExternalLink className="w-2.5 h-2.5 text-slate-400 ml-0.5" />}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {msg.sender === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-slate-300" />
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex items-start space-x-3 justify-start">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center shrink-0 animate-pulse">
              <Bot className="w-4 h-4 text-blue-400" />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-2xl rounded-tl-sm p-4 text-xs text-slate-400 flex items-center space-x-2">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce" />
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.2s]" />
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-bounce [animation-delay:0.4s]" />
              <span className="ml-2 font-mono text-[11px]">Traversing RAG Graph Workflow...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Bar */}
      <div className="p-4 bg-slate-900 border-t border-slate-800">
        <form onSubmit={handleSubmit} className="flex items-center space-x-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question about the corpus (e.g. 'What are the termination clauses in Section 4?')..."
            disabled={isLoading}
            className="flex-1 bg-slate-950 border border-slate-700/80 rounded-xl px-4 py-2.5 text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:border-blue-500 transition-colors"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="p-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-xl transition-colors shadow-lg shadow-blue-600/20"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};

