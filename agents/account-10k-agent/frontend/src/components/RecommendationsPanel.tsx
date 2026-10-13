import React, { useState } from 'react';
import {
  Check,
  CheckCircle2,
  Copy,
  MessageSquareQuote,
  Target,
  UserCheck,
} from 'lucide-react';
import {
  AccountRecommendation,
  Citation,
  RecommendationCategory,
} from '../types';
import { renderTextWithCitations } from './CitationDrawer';

interface RecommendationsPanelProps {
  recommendations: AccountRecommendation[];
  citations: Citation[];
  onSelectCitation: (citation: Citation) => void;
}

const CATEGORIES: Array<'All' | RecommendationCategory> = [
  'All',
  'Cloud & AI Modernization',
  'Data & Analytics',
  'Security & Compliance',
  'Cost & Operational Efficiency',
  'Revenue & GTM Expansion',
];

export const RecommendationsPanel: React.FC<RecommendationsPanelProps> = ({
  recommendations,
  citations,
  onSelectCitation,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<'All' | RecommendationCategory>('All');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const filtered =
    selectedCategory === 'All'
      ? recommendations
      : recommendations.filter((r) => r.category === selectedCategory);

  const handleCopyPitch = (rec: AccountRecommendation) => {
    const text = [
      `Account Play: ${rec.title}`,
      `Target Stakeholder: ${rec.target_stakeholder}`,
      `Rationale: ${rec.rationale}`,
      '',
      'Executive Talking Points:',
      ...rec.talking_points.map((tp) => `- "${tp}"`),
    ].join('\n');
    navigator.clipboard?.writeText(text);
    setCopiedId(rec.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const categoryBadgeColor = (cat: RecommendationCategory) => {
    switch (cat) {
      case 'Cloud & AI Modernization':
        return 'bg-sky-500/15 text-sky-300 border-sky-500/30';
      case 'Data & Analytics':
        return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30';
      case 'Security & Compliance':
        return 'bg-rose-500/15 text-rose-300 border-rose-500/30';
      case 'Cost & Operational Efficiency':
        return 'bg-amber-500/15 text-amber-300 border-amber-500/30';
      case 'Revenue & GTM Expansion':
        return 'bg-teal-500/15 text-teal-300 border-teal-500/30';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="space-y-4">
      {/* Category Filter Bar */}
      <div className="flex items-center gap-1.5 flex-wrap">
        {CATEGORIES.map((cat) => {
          const active = selectedCategory === cat;
          const count =
            cat === 'All'
              ? recommendations.length
              : recommendations.filter((r) => r.category === cat).length;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors flex items-center gap-1.5 cursor-pointer ${
                active
                  ? 'bg-sky-500 text-slate-950 font-semibold border-sky-400'
                  : 'bg-slate-900/80 text-slate-300 border-slate-800 hover:bg-slate-800'
              }`}
            >
              <span>{cat}</span>
              <span
                className={`px-1.5 py-0.2 rounded text-[10px] font-mono tabular-nums ${
                  active ? 'bg-slate-950/20 text-slate-950' : 'bg-slate-800 text-slate-400'
                }`}
              >
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Recommendations Cards */}
      <div className="space-y-4">
        {filtered.map((rec) => (
          <div
            key={rec.id}
            className="rounded-2xl bg-slate-900/90 border border-slate-800 p-5 space-y-4 hover:border-slate-700/90 transition-colors"
          >
            {/* Card Top Bar */}
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`px-2.5 py-0.5 rounded-md text-[11px] font-semibold border ${categoryBadgeColor(
                      rec.category
                    )}`}
                  >
                    {rec.category}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold border ${
                      rec.priority === 'High'
                        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                    }`}
                  >
                    {rec.priority} Priority
                  </span>
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono text-slate-300 bg-slate-950/80 border border-slate-800 tabular-nums">
                    {rec.confidence_score}% Confidence
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-100">
                  {rec.title}
                </h3>
              </div>

              <button
                type="button"
                onClick={() => handleCopyPitch(rec)}
                className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition-colors cursor-pointer shrink-0"
              >
                {copiedId === rec.id ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-300">Copied Pitch</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-slate-400" />
                    <span>Copy Executive Pitch</span>
                  </>
                )}
              </button>
            </div>

            {/* Target Executive Stakeholder */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950/70 border border-slate-800/90 text-xs">
              <UserCheck className="w-3.5 h-3.5 text-sky-400" />
              <span className="text-slate-400">Target Persona:</span>
              <span className="font-semibold text-slate-200">
                {rec.target_stakeholder}
              </span>
            </div>

            {/* 10-K Grounded Rationale */}
            <div className="text-sm text-slate-300 leading-relaxed">
              <span className="font-semibold text-slate-100 mr-1.5">
                10-K Evidence &amp; Rationale:
              </span>
              {renderTextWithCitations(rec.rationale, citations, onSelectCitation)}
            </div>

            {/* Two-Column Next Steps & Talking Points */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2 border-t border-slate-800/80">
              {/* Recommended Account Actions */}
              <div className="bg-slate-950/50 rounded-xl p-3.5 border border-slate-800/70 space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Target className="w-3.5 h-3.5 text-emerald-400" />
                  Recommended Next Steps
                </div>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {rec.recommended_actions.map((step, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Executive Outreach Talking Points */}
              <div className="bg-slate-950/50 rounded-xl p-3.5 border border-slate-800/70 space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <MessageSquareQuote className="w-3.5 h-3.5 text-sky-400" />
                  Executive Outreach Talking Points
                </div>
                <div className="space-y-2">
                  {rec.talking_points.map((tp, i) => (
                    <blockquote
                      key={i}
                      className="text-xs italic text-slate-200 pl-3 border-l-2 border-sky-500/60 leading-relaxed"
                    >
                      &ldquo;{tp}&rdquo;
                    </blockquote>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

