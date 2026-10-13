import React, { useState } from 'react';
import {
  Bot,
  Loader2,
  Send,
  Sparkles,
  User,
  X,
} from 'lucide-react';
import { sendAnalystQuestion } from '../api/client';
import {
  AccountAnalysisReport,
  ChatMessage,
  Citation,
} from '../types';
import { renderTextWithCitations } from './CitationDrawer';

interface AnalystChatDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  activeAccount: AccountAnalysisReport | null;
  onSelectCitation: (citation: Citation) => void;
}

const SUGGESTED_PROMPTS = [
  'What are the top Item 1A risks and how should we pitch the CIO?',
  'Summarize CapEx, R&D, and cloud infrastructure spend in Item 7.',
  'Draft a concise executive email to the CFO referencing their 10-K.',
  'Where is this account investing in Generative AI or data platforms?',
];

export const AnalystChatDrawer: React.FC<AnalystChatDrawerProps> = ({
  isOpen,
  onClose,
  activeAccount,
  onSelectCitation,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

  if (!isOpen) return null;

  const handleSend = async (promptText?: string) => {
    const query = (promptText ?? input).trim();
    if (!query || isLoading) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    if (!promptText) setInput('');
    setIsLoading(true);

    try {
      const res = await sendAnalystQuestion({
        message: query,
        account_id: activeAccount?.account_id,
        document_name: activeAccount?.document_name,
        session_id: sessionId,
      });
      setSessionId(res.session_id);
      const botMsg: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err: any) {
      const errMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Error querying 10-K filing: ${err.message || 'Unknown error'}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <aside
      aria-label="10-K Grounded Analyst Copilot"
      className="w-96 shrink-0 bg-slate-900 border-l border-slate-800 flex flex-col h-full"
    >
      {/* Header */}
      <div className="px-4 py-3.5 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-sky-500/15 border border-sky-500/40 flex items-center justify-center text-sky-400">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-100">
              10-K Analyst Copilot
            </h3>
            <p className="text-[10px] text-slate-400 truncate max-w-[210px]">
              Scoped to: {activeAccount ? `${activeAccount.company_name} (${activeAccount.ticker})` : 'All 10-K Filings'}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close analyst chat"
          className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="space-y-4 pt-2">
            <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800/90 text-xs text-slate-300 leading-relaxed">
              Ask any question about{' '}
              <span className="font-semibold text-sky-300">
                {activeAccount?.company_name || 'the uploaded 10-K report'}
              </span>
              . Every response is grounded in the SEC Form 10-K filing with clickable page citations.
            </div>
            <div className="space-y-1.5">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-sky-400" />
                Suggested Account Research Prompts
              </div>
              {SUGGESTED_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSend(prompt)}
                  className="w-full text-left p-2.5 rounded-xl bg-slate-950/60 hover:bg-slate-800/80 border border-slate-800/80 text-xs text-slate-200 transition-colors cursor-pointer"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col gap-1.5 ${
                msg.role === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
                {msg.role === 'user' ? (
                  <>
                    <span>You</span>
                    <User className="w-3 h-3 text-slate-400" />
                  </>
                ) : (
                  <>
                    <Bot className="w-3 h-3 text-sky-400" />
                    <span className="text-sky-300 font-medium">Vertex AI 10-K Analyst</span>
                  </>
                )}
              </div>

              <div
                className={`p-3 rounded-2xl text-xs leading-relaxed max-w-[92%] whitespace-pre-wrap ${
                  msg.role === 'user'
                    ? 'bg-sky-500 text-slate-950 font-medium rounded-tr-xs'
                    : 'bg-slate-950 border border-slate-800 text-slate-200 rounded-tl-xs'
                }`}
              >
                {msg.role === 'assistant'
                  ? renderTextWithCitations(
                      msg.content,
                      msg.citations || activeAccount?.citations || [],
                      onSelectCitation
                    )
                  : msg.content}
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="flex items-center gap-2 text-xs text-slate-400 p-2">
            <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
            <span>Retrieving 10-K chunks &amp; synthesizing...</span>
          </div>
        )}
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="p-3 border-t border-slate-800 bg-slate-950/60 flex items-center gap-2"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about risks, CapEx, or pitch angles..."
          aria-label="Ask a question about the 10-K report"
          className="flex-1 px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          aria-label="Send question"
          className="p-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 disabled:opacity-40 transition-colors cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </aside>
  );
};

