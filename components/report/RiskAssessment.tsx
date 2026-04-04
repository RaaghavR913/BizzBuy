'use client';

import type { ReportOutput, RiskDimensionScore } from '@/lib/types';
import { RiskBar } from './ScoreBadge';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip,
} from 'recharts';

function getDimBg(score: number): string {
  if (score <= 3) return 'border-emerald-500/20 bg-emerald-500/5';
  if (score <= 5) return 'border-yellow-500/20 bg-yellow-500/5';
  if (score <= 7) return 'border-orange-500/20 bg-orange-500/5';
  return 'border-red-500/20 bg-red-500/5';
}

function DimensionCard({ dim }: { dim: RiskDimensionScore }) {
  return (
    <div className={cn('rounded-xl border p-4 space-y-3', getDimBg(dim.score))}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-white text-sm">{dim.dimension}</h3>
          {dim.isDealBreaker && (
            <span className="flex items-center gap-1 text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full font-medium">
              <AlertTriangle className="w-3 h-3" />
              Deal Breaker
            </span>
          )}
        </div>
        <span className={cn(
          'text-sm font-black',
          dim.score <= 3 ? 'text-emerald-400' :
          dim.score <= 5 ? 'text-yellow-400' :
          dim.score <= 7 ? 'text-orange-400' : 'text-red-400'
        )}>
          {dim.label}
        </span>
      </div>
      <RiskBar score={dim.score} max={10} />
      <p className="text-sm text-t-secondary">{dim.explanation}</p>
      {dim.keyFactors.length > 0 && (
        <ul className="space-y-1">
          {dim.keyFactors.map((f, i) => (
            <li key={i} className="text-xs text-t-muted flex items-start gap-1.5">
              <span className="mt-1 flex-shrink-0">•</span>
              {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function RiskAssessment({ report }: { report: ReportOutput }) {
  const { riskAssessment } = report;

  const radarData = riskAssessment.dimensions.map((d) => ({
    subject: d.dimension.replace(' & ', '\n& ').replace(' Dependence', ''),
    score: d.score,
    fullMark: 10,
  }));

  return (
    <section id="risk-assessment" className="bg-surface rounded-2xl border border-white/[0.06] p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-display font-bold text-white">4. Risk Assessment</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-t-muted">Overall Score:</span>
          <span className={cn(
            'text-lg font-black font-mono',
            riskAssessment.overallScore <= 35 ? 'text-emerald-400' :
            riskAssessment.overallScore <= 65 ? 'text-yellow-400' :
            riskAssessment.overallScore <= 80 ? 'text-orange-400' : 'text-red-400'
          )}>
            {riskAssessment.overallScore}/100
          </span>
        </div>
      </div>

      {/* Radar Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData}>
            <PolarGrid stroke="hsl(228 18% 25%)" />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: 'hsl(228 12% 60%)' }} />
            <Radar
              name="Risk Score"
              dataKey="score"
              stroke="hsl(245 78% 68%)"
              fill="hsl(245 78% 68%)"
              fillOpacity={0.15}
            />
            <Tooltip
              formatter={(value) => [`${value}/10`, 'Risk Score']}
              contentStyle={{ backgroundColor: 'hsl(228 22% 10%)', border: '1px solid hsl(0 0% 100% / 0.08)', borderRadius: '8px', color: 'hsl(228 40% 96%)' }}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {riskAssessment.dimensions.map((dim) => (
          <DimensionCard key={dim.dimension} dim={dim} />
        ))}
      </div>

      {report.agentFlags.length > 0 && (
        <div className="bg-raised border border-white/[0.06] rounded-xl p-4">
          <h3 className="font-semibold text-white mb-3">Shared Phase 2 Flags</h3>
          <div className="space-y-2">
            {report.agentFlags.slice(0, 6).map((flag, index) => (
              <div key={`${flag.message}-${index}`} className="text-sm text-t-secondary">
                <span className={cn(
                  'font-semibold',
                  flag.severity === 'critical' ? 'text-red-400' : flag.severity === 'warning' ? 'text-yellow-400' : 'text-accent'
                )}>
                  [{flag.severity.toUpperCase()}]
                </span>{' '}
                {flag.dimension}: {flag.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
