'use client';

import Link from 'next/link';
import { useState } from 'react';
import { ArrowRight, ShieldCheck, TrendingUp, Users, FileText, BarChart3, CheckCircle2, Lock, Mail, Eye, EyeOff } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-center justify-center px-4 sm:px-6 lg:px-8 overflow-hidden">
        <div className="hero-grid absolute inset-0" />
        <div className="absolute inset-0 bg-gradient-to-b from-accent/[0.04] via-transparent to-transparent" />
        <div className="max-w-4xl mx-auto text-center relative animate-fade-in-up">
          <div className="inline-flex items-center gap-2 bg-accent/10 border border-accent/20 rounded-full px-4 py-1.5 text-sm text-accent mb-8">
            <BarChart3 className="w-3.5 h-3.5" />
            AI-Powered Acquisition Diligence
          </div>
          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight mb-6 leading-[1.1]">
            The Carfax for{' '}
            <span className="bg-gradient-to-r from-accent via-violet-400 to-purple-300 bg-clip-text text-transparent">
              Buying a Business
            </span>
          </h1>
          <p className="text-lg sm:text-xl text-t-secondary mb-10 max-w-2xl mx-auto leading-relaxed">
            Upload your financials. Answer a few questions. Get a plain-language acquisition
            report — affordability, risk, and transferability analysis in minutes.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/analyze/upload"
              className="inline-flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-200 shadow-lg shadow-accent/20 hover:shadow-xl hover:shadow-accent/30 hover:-translate-y-0.5"
            >
              Analyze a Business
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link
              href="/analyze/upload?demo=true"
              className="inline-flex items-center justify-center gap-2 bg-white/[0.06] hover:bg-white/[0.1] border border-white/[0.1] text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all duration-200"
            >
              Try Demo
              <FileText className="w-5 h-5" />
            </Link>
          </div>
          <p className="text-t-muted text-sm mt-6">
            No account required · No permanent data storage · Free for the MVP
          </p>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <div className="w-6 h-10 border-2 border-white/20 rounded-full flex items-start justify-center p-1.5">
            <div className="w-1.5 h-3 bg-accent/60 rounded-full" />
          </div>
        </div>
      </section>

      {/* Trust Ticker */}
      <section className="border-y border-white/[0.06] bg-surface/50 overflow-hidden py-4">
        <div className="animate-ticker flex whitespace-nowrap gap-12">
          {[...Array(2)].map((_, setIdx) => (
            <div key={setIdx} className="flex gap-12 items-center">
              {['Analyzing P&L', 'Financial Risk', 'Transferability', 'SBA Lending', '7 AI Agents', 'Customer Concentration', 'Owner Dependence', 'PDF Reports'].map((item) => (
                <span key={`${setIdx}-${item}`} className="text-sm text-t-muted font-medium flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-accent/60" />
                  {item}
                </span>
              ))}
            </div>
          ))}
        </div>
      </section>

      {/* Value Props */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16 animate-fade-in-up">
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-white mb-4">
              Not every profitable business is an acquirable business.
            </h2>
            <p className="text-lg text-t-secondary max-w-2xl mx-auto">
              BizzBuy gives you the analysis that financial statements alone can&apos;t provide — the operational and financial risks that determine whether a deal is truly worth pursuing.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <ValuePropCard
              icon={<TrendingUp className="w-6 h-6 text-accent" />}
              title="Affordability Analysis"
              description="Can you actually service the debt and still take home income? We calculate your DSCR, break-even revenue, and model 3 performance scenarios so you know exactly what you're signing up for."
              delay="delay-100"
            />
            <ValuePropCard
              icon={<ShieldCheck className="w-6 h-6 text-accent" />}
              title="6-Dimension Risk Scoring"
              description="We score owner dependence, customer concentration, revenue quality, operational maturity, supplier risk, and financial transparency — the risks that hide in every acquisition."
              delay="delay-200"
            />
            <ValuePropCard
              icon={<Users className="w-6 h-6 text-accent" />}
              title="Transferability Check"
              description="Will the business survive without the owner? We evaluate process maturity, customer contract quality, team stability, and management depth to tell you what you're actually buying."
              delay="delay-300"
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 bg-surface/50">
        <div className="max-w-4xl mx-auto">
          <h2 className="font-display text-3xl sm:text-4xl font-bold text-white text-center mb-16">
            From documents to decision in 4 steps
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {[
              { step: '01', title: 'Upload Financials', desc: 'Drop in your P&L, balance sheet, and loan term sheet. Our AI extracts the data.' },
              { step: '02', title: 'Confirm Data', desc: 'Review extracted figures and correct any mistakes before analysis.' },
              { step: '03', title: 'Answer Risk Questions', desc: '6 sections covering ownership, customers, revenue, employees, suppliers, and financials.' },
              { step: '04', title: 'Get Your Report', desc: 'A complete acquisition analysis with scores, seller questions, and a final recommendation.' },
            ].map(({ step, title, desc }, i) => (
              <div key={step} className={`flex flex-col items-start gap-3 animate-fade-in-up delay-${(i + 1) * 100}`}>
                <span className="text-5xl font-display font-extrabold text-accent/20 leading-none">{step}</span>
                <h3 className="text-base font-bold text-white">{title}</h3>
                <p className="text-sm text-t-secondary leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Report Sections Preview */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="font-display text-3xl sm:text-4xl font-bold text-white mb-4">What you get in the report</h2>
            <p className="text-t-secondary text-lg">
              A complete acquisition analysis report with 9 sections designed for the non-expert buyer.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
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
              <div key={item} className="flex items-center gap-3 p-4 rounded-xl border border-white/[0.06] bg-surface hover:border-accent/30 hover:bg-surface transition-all duration-200 group">
                <CheckCircle2 className="w-5 h-5 text-accent flex-shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm font-medium text-t-secondary group-hover:text-white transition-colors">{item}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Login Section */}
      <section id="login" className="py-24 px-4 sm:px-6 lg:px-8 bg-surface/50">
        <div className="max-w-md mx-auto">
          <div className="text-center mb-8">
            <div className="w-12 h-12 bg-accent/10 border border-accent/20 rounded-xl flex items-center justify-center mx-auto mb-4">
              <Lock className="w-6 h-6 text-accent" />
            </div>
            <h2 className="font-display text-2xl font-bold text-white mb-2">Welcome back</h2>
            <p className="text-sm text-t-secondary">Sign in to your account to access saved reports</p>
          </div>
          <LoginCard />
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4 sm:px-6 lg:px-8 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-accent/20 via-violet-900/20 to-transparent" />
        <div className="max-w-3xl mx-auto text-center relative">
          <h2 className="font-display text-3xl sm:text-4xl font-bold text-white mb-4">
            Ready to evaluate your deal?
          </h2>
          <p className="text-lg text-t-secondary mb-8">
            Upload your financials and get a complete acquisition risk report in under 2 minutes.
          </p>
          <Link
            href="/analyze/upload"
            className="inline-flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-8 py-4 rounded-xl text-lg font-semibold transition-all shadow-lg shadow-accent/20 hover:shadow-xl hover:shadow-accent/30 hover:-translate-y-0.5"
          >
            Start Your Analysis
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>
    </div>
  );
}

/* ── Sub-components ────────────────────── */

function ValuePropCard({
  icon,
  title,
  description,
  delay = '',
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  delay?: string;
}) {
  return (
    <div className={`p-6 rounded-2xl border border-white/[0.06] bg-surface hover:border-accent/30 transition-all duration-300 group animate-fade-in-up ${delay}`}>
      <div className="w-12 h-12 bg-accent/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-accent/20 transition-colors">
        {icon}
      </div>
      <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
      <p className="text-t-secondary leading-relaxed text-sm">{description}</p>
    </div>
  );
}

function LoginCard() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    console.log('Login attempt:', { email, password });
    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 3000);
  }

  return (
    <div className="bg-surface border border-white/[0.08] rounded-2xl p-6 space-y-5">
      {submitted && (
        <div className="bg-accent/10 border border-accent/20 rounded-lg px-4 py-3 text-sm text-accent text-center">
          Login coming soon — backend not yet connected.
        </div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-t-secondary">Email</label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-t-muted" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="w-full bg-raised border border-white/[0.08] rounded-lg px-10 py-2.5 text-sm text-white placeholder:text-t-muted focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/30 transition-all"
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-t-secondary">Password</label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-t-muted" />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-raised border border-white/[0.08] rounded-lg px-10 py-2.5 text-sm text-white placeholder:text-t-muted focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent/30 transition-all"
            />
            <button
              type="button"
              onClick={() => setShowPassword(!showPassword)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-t-muted hover:text-t-secondary transition-colors"
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-end">
          <button type="button" className="text-xs text-accent hover:text-accent-hover transition-colors">
            Forgot password?
          </button>
        </div>
        <button
          type="submit"
          className="w-full bg-accent hover:bg-accent-hover text-white py-2.5 rounded-lg font-semibold text-sm transition-all hover:shadow-lg hover:shadow-accent/20"
        >
          Sign In
        </button>
      </form>
      <div className="relative flex items-center gap-4">
        <div className="flex-1 h-px bg-white/[0.06]" />
        <span className="text-xs text-t-muted">or</span>
        <div className="flex-1 h-px bg-white/[0.06]" />
      </div>
      <button
        type="button"
        onClick={() => { console.log('Google login coming soon'); setSubmitted(true); setTimeout(() => setSubmitted(false), 3000); }}
        className="w-full flex items-center justify-center gap-2 bg-raised border border-white/[0.08] hover:border-white/[0.15] text-t-secondary hover:text-white py-2.5 rounded-lg text-sm font-medium transition-all"
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
        Continue with Google
      </button>
      <p className="text-center text-xs text-t-muted">
        Don&apos;t have an account?{' '}
        <button type="button" className="text-accent hover:text-accent-hover transition-colors" onClick={() => { console.log('Create account coming soon'); }}>
          Create one
        </button>
      </p>
    </div>
  );
}
