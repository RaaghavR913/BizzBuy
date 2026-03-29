import Link from 'next/link';
import { ArrowRight, ShieldCheck, TrendingUp, Users, FileText, BarChart3, CheckCircle2 } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 text-white py-24 px-4 sm:px-6 lg:px-8 overflow-hidden">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-5" />
        <div className="max-w-4xl mx-auto text-center relative">
          <div className="inline-flex items-center gap-2 bg-blue-900/50 border border-blue-700/50 rounded-full px-4 py-1.5 text-sm text-blue-300 mb-8">
            <BarChart3 className="w-3.5 h-3.5" />
            AI-Powered Acquisition Diligence
          </div>
          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-6 leading-tight">
            Know Before{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-cyan-400">
              You Buy
            </span>
          </h1>
          <p className="text-xl text-slate-300 mb-10 max-w-2xl mx-auto leading-relaxed">
            Upload your financials. Answer a few questions. Get a plain-language acquisition
            report — affordability, risk, and transferability analysis in minutes.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/analyze/upload"
              className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-200 shadow-lg shadow-blue-900/40 hover:shadow-xl hover:shadow-blue-900/50 hover:-translate-y-0.5"
            >
              Analyze a Business
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/analyze/upload?demo=true"
              className="inline-flex items-center justify-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-200"
            >
              Try Demo
              <FileText className="w-5 h-5" />
            </Link>
          </div>
          <p className="text-slate-500 text-sm mt-6">
            No account required · No permanent data storage · Free for the MVP
          </p>
        </div>
      </section>

      {/* Value Props */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Not every profitable business is an acquirable business.
            </h2>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto">
              BizBuy gives you the analysis that financial statements alone can&apos;t provide — the operational and financial risks that determine whether a deal is truly worth pursuing.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <ValuePropCard
              icon={<TrendingUp className="w-6 h-6 text-blue-600" />}
              title="Affordability Analysis"
              description="Can you actually service the debt and still take home income? We calculate your DSCR, break-even revenue, and model 3 performance scenarios so you know exactly what you're signing up for."
            />
            <ValuePropCard
              icon={<ShieldCheck className="w-6 h-6 text-blue-600" />}
              title="6-Dimension Risk Scoring"
              description="We score owner dependence, customer concentration, revenue quality, operational maturity, supplier risk, and financial transparency — the risks that hide in every acquisition."
            />
            <ValuePropCard
              icon={<Users className="w-6 h-6 text-blue-600" />}
              title="Transferability Check"
              description="Will the business survive without the owner? We evaluate process maturity, customer contract quality, team stability, and management depth to tell you what you're actually buying."
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-slate-50">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-slate-900 text-center mb-14">
            From documents to decision in 4 steps
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { step: '01', title: 'Upload Financials', desc: 'Drop in your P&L, balance sheet, and loan term sheet. Our AI extracts the data.' },
              { step: '02', title: 'Confirm Data', desc: 'Review extracted figures and correct any mistakes before analysis.' },
              { step: '03', title: 'Answer Risk Questions', desc: '6 sections covering ownership, customers, revenue, employees, suppliers, and financials.' },
              { step: '04', title: 'Get Your Report', desc: 'A complete acquisition analysis with scores, seller questions, and a final recommendation.' },
            ].map(({ step, title, desc }) => (
              <div key={step} className="flex flex-col items-start gap-3">
                <span className="text-4xl font-black text-blue-100 leading-none">{step}</span>
                <h3 className="text-base font-bold text-slate-900">{title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Report Sections Preview */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-white">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">What you get in the report</h2>
            <p className="text-slate-500">
              A complete acquisition analysis report with 9 sections designed for the non-expert buyer.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              'Executive Summary & Risk Scores',
              'Financial Snapshot Table',
              'Debt Service & Affordability',
              '6-Dimension Risk Assessment',
              'Transferability Analysis',
              'Questions to Ask the Seller',
              'Due Diligence Checklist',
              'Upside & Opportunities',
              'Final Recommendation',
            ].map((item) => (
              <div key={item} className="flex items-center gap-3 p-4 rounded-lg border border-slate-200 bg-slate-50">
                <CheckCircle2 className="w-5 h-5 text-blue-600 flex-shrink-0" />
                <span className="text-sm font-medium text-slate-700">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-blue-600">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to evaluate your deal?
          </h2>
          <p className="text-blue-100 text-lg mb-8">
            Upload your financials and get a complete acquisition risk report in under 2 minutes.
          </p>
          <Link
            href="/analyze/upload"
            className="inline-flex items-center gap-2 bg-white text-blue-600 px-8 py-4 rounded-xl text-lg font-semibold hover:bg-blue-50 transition-colors shadow-lg"
          >
            Start Your Analysis
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>
    </div>
  );
}

function ValuePropCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="p-6 rounded-2xl border border-slate-200 bg-white hover:border-blue-200 hover:shadow-md transition-all duration-200">
      <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center mb-4">
        {icon}
      </div>
      <h3 className="text-lg font-bold text-slate-900 mb-2">{title}</h3>
      <p className="text-slate-500 leading-relaxed text-sm">{description}</p>
    </div>
  );
}
