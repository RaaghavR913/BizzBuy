'use client';

import type { ReportOutput, RiskDimensionScore } from '@/lib/types';
import { RiskBar } from './ScoreBadge';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, Tooltip,
} from 'recharts';

function getDimBg(score: number): string {
  if (score <= 3) return 'border-emerald-200 bg-emerald-50/30';
  if (score <= 5) return 'border-yellow-200 bg-yellow-50/30';
  if (score <= 7) return 'border-orange-200 bg-orange-50/30';
  return 'border-red-200 bg-red-50/30';
}

function DimensionCard({ dim }: { dim: RiskDimensionScore }) {
  return (
    <div className={cn('rounded-xl border p-4 space-y-3', getDimBg(dim.score))}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-slate-900 text-sm">{dim.dimension}</h3>
          {dim.isDealBreaker && (
            <span className="flex items-center gap-1 text-xs text-red-600 bg-red-50 border border-red-200 px-2 py-0.5 rounded-full font-medium">
              <AlertTriangle className="w-3 h-3" />
              Deal Breaker
            </span>
          )}
        </div>
        <span className={cn(
          'text-sm font-black',
          dim.score <= 3 ? 'text-emerald-600' :
          dim.score <= 5 ? 'text-yellow-600' :
          dim.score <= 7 ? 'text-orange-600' : 'text-red-600'
        )}>
          {dim.label}
        </span>
      </div>
      <RiskBar score={dim.score} max={10} />
      <p className="text-sm text-slate-600">{dim.explanation}</p>
      {dim.keyFactors.length > 0 && (
        <ul className="space-y-1">
          {dim.keyFactors.map((f, i) => (
            <li key={i} className="text-xs text-slate-500 flex items-start gap-1.5">
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
    <section id="risk-assessment" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-slate-900">4. Risk Assessment</h2>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500">Overall Score:</span>
          <span className={cn(
            'text-lg font-black',
            riskAssessment.overallScore <= 35 ? 'text-emerald-600' :
            riskAssessment.overallScore <= 65 ? 'text-yellow-600' :
            riskAssessment.overallScore <= 80 ? 'text-orange-600' : 'text-red-600'
          )}>
            {riskAssessment.overallScore}/100
          </span>
        </div>
      </div>

      {/* Radar Chart */}
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={radarData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
            <Radar
              name="Risk Score"
              dataKey="score"
              stroke="#3b82f6"
              fill="#3b82f6"
              fillOpacity={0.2}
            />
            <Tooltip formatter={(value) => [`${value}/10`, 'Risk Score']} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {riskAssessment.dimensions.map((dim) => (
          <DimensionCard key={dim.dimension} dim={dim} />
        ))}
      </div>

      {report.agentFlags.length > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
          <h3 className="font-semibold text-slate-900 mb-3">Backend Risk Flags</h3>
          <div className="space-y-2">
            {report.agentFlags.slice(0, 6).map((flag, index) => (
              <div key={`${flag.message}-${index}`} className="text-sm text-slate-700">
                <span className={cn(
                  'font-semibold',
                  flag.severity === 'critical' ? 'text-red-600' : flag.severity === 'warning' ? 'text-yellow-700' : 'text-blue-600'
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
