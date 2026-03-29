'use client';

import type { ReportOutput } from '@/lib/types';
import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export function SellerQuestions({ report }: { report: ReportOutput }) {
  const [copied, setCopied] = useState<string | null>(null);

  function copyQuestion(q: string) {
    navigator.clipboard.writeText(q);
    setCopied(q);
    setTimeout(() => setCopied(null), 2000);
  }

  return (
    <section id="seller-questions" className="bg-white rounded-2xl border border-slate-200 p-6 space-y-5">
      <h2 className="text-xl font-bold text-slate-900">6. Questions to Ask the Seller</h2>
      {report.questionsForSeller.map((cat, i) => (
        <div key={i} className="space-y-2">
          <h3 className="font-semibold text-blue-700 text-sm uppercase tracking-wide">{cat.category}</h3>
          <div className="space-y-2">
            {cat.questions.map((q, j) => (
              <div key={j} className="flex items-start justify-between gap-3 p-3 bg-slate-50 rounded-lg group">
                <p className="text-sm text-slate-700 flex-1">{q}</p>
                <button
                  onClick={() => copyQuestion(q)}
                  className="flex-shrink-0 p-1.5 text-slate-300 hover:text-slate-600 transition-colors opacity-0 group-hover:opacity-100"
                >
                  {copied === q ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}
