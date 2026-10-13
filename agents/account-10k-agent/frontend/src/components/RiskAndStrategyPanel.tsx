import React from 'react';
import {
  AlertTriangle,
  Compass,
  Lightbulb,
  ShieldAlert,
  Zap,
} from 'lucide-react';
import {
  Citation,
  RiskFactorItem,
  StrategicInitiative,
} from '../types';
import { renderTextWithCitations } from './CitationDrawer';

interface RiskAndStrategyPanelProps {
  strategicInitiatives: StrategicInitiative[];
  riskFactors: RiskFactorItem[];
  citations: Citation[];
  onSelectCitation: (citation: Citation) => void;
}

export const RiskAndStrategyPanel: React.FC<RiskAndStrategyPanelProps> = ({
  strategicInitiatives,
  riskFactors,
  citations,
  onSelectCitation,
}) => {
  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
      {/* Column 1: Strategic Initiatives (Item 1 & Item 7) */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="w-4 h-4 text-sky-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
              Item 1 &amp; 7 Strategic Initiatives
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {strategicInitiatives.length} priorities
          </span>
        </div>

        <div className="space-y-3.5">
          {strategicInitiatives.map((init, idx) => {
            const cit = citations.find((c) => c.citation_index === init.citation_index);
            return (
              <div
                key={idx}
                className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide bg-sky-500/15 text-sky-300 border border-sky-500/30 mb-1.5">
                      {init.category}
                    </span>
                    <h4 className="text-sm font-bold text-slate-100">
                      {init.title}
                    </h4>
                  </div>
                  {init.citation_index && (
                    <button
                      type="button"
                      onClick={() => cit && onSelectCitation(cit)}
                      className="px-1.5 py-0.5 text-[11px] font-mono font-semibold rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 cursor-pointer shrink-0"
                    >
                      [{init.citation_index}]
                    </button>
                  )}
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  {renderTextWithCitations(init.description, citations, onSelectCitation)}
                </p>

                <div className="pt-2 border-t border-slate-800/80 flex items-center gap-2 text-xs text-emerald-300">
                  <Zap className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                  <span className="font-medium">
                    {renderTextWithCitations(init.investment_signal, citations, onSelectCitation)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Column 2: SEC Item 1A Risk Factors & Account Mitigation Plays */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
              SEC Item 1A Risks &amp; Mitigation Plays
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {riskFactors.length} material risks
          </span>
        </div>

        <div className="space-y-3.5">
          {riskFactors.map((risk, idx) => {
            const cit = citations.find((c) => c.citation_index === risk.citation_index);
            const sevStyles =
              risk.severity === 'high'
                ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                : risk.severity === 'medium'
                ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
                : 'bg-slate-800 text-slate-300 border-slate-700';

            return (
              <div
                key={idx}
                className="p-4 rounded-2xl bg-slate-900/90 border border-slate-800 space-y-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${sevStyles}`}
                      >
                        {risk.severity} Risk
                      </span>
                      <span className="text-[11px] font-medium text-slate-400">
                        {risk.category}
                      </span>
                    </div>
                    <h4 className="text-sm font-bold text-slate-100 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                      <span>{risk.title}</span>
                    </h4>
                  </div>
                  {risk.citation_index && (
                    <button
                      type="button"
                      onClick={() => cit && onSelectCitation(cit)}
                      className="px-1.5 py-0.5 text-[11px] font-mono font-semibold rounded bg-sky-500/15 text-sky-300 border border-sky-500/30 hover:bg-sky-500/30 cursor-pointer shrink-0"
                    >
                      [{risk.citation_index}]
                    </button>
                  )}
                </div>

                <p className="text-xs text-slate-300 leading-relaxed">
                  {renderTextWithCitations(risk.description, citations, onSelectCitation)}
                </p>

                <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/25 flex items-start gap-2.5">
                  <Lightbulb className="w-4 h-4 text-sky-400 shrink-0 mt-0.5" />
                  <div className="text-xs text-slate-200 leading-relaxed">
                    <span className="font-semibold text-sky-300 mr-1">
                      Account Opportunity:
                    </span>
                    {risk.account_opportunity}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

