'use client';

import { useState, type ReactNode } from 'react';
import { ShieldCheck, TrendingUp, Users, BarChart3, CheckCircle2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { TiltedCard } from '@/components/ui/tilted-card';
import { SplitText } from '@/components/ui/split-text';
import { BlurText } from '@/components/ui/blur-text';
import { AnimatedButton } from '@/components/ui/animated-button';
import '@/components/ui/ai-badge.css';

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-center justify-center px-4 sm:px-6 lg:px-8 overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-accent/[0.04] via-transparent to-transparent" />
        <motion.div 
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="max-w-4xl mx-auto text-center relative"
        >
          <div className="ai-badge mb-8">
            <BarChart3 className="w-5 h-5 shrink-0" aria-hidden />
            <span>BizzBuy</span>
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight mb-6 leading-[1.1] [font-family:Georgia,serif]">
            The Carfax for{' '}
            <span className="bg-gradient-to-r from-accent via-yellow-500 to-yellow-200 bg-clip-text text-transparent">
              Buying a Business
            </span>
          </h1>
          <div className="text-lg sm:text-xl text-t-secondary mb-10 max-w-2xl mx-auto leading-relaxed">
            <BlurText
              text="Upload your financials. Answer a few questions. Get a plain-language acquisition report in minutes."
              delay={0.02}
              className="[font-family:Georgia,serif]"
            />
          </div>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <AnimatedButton
              href="/analyze/upload"
              text="Analyze a Business"
              className="[font-family:Georgia,serif]"
            />
          </div>
        </motion.div>

      </section>

      {/* Trust Ticker */}
      <section className="border-y border-white/[0.06] bg-surface/50 overflow-hidden py-4">
        <div className="animate-ticker flex whitespace-nowrap gap-12 [font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif]">
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
      <section
        id="what-it-does"
        className="scroll-mt-24 py-24 px-4 sm:px-6 md:scroll-mt-28 lg:px-8 [font-family:Times,Times_New_Roman,serif]"
      >
        <div className="max-w-6xl mx-auto">
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              <SplitText text="Not every profitable business is built to be acquired." delay={0.03} />
            </h2>
          </motion.div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <ValuePropCard
              icon={<TrendingUp className="w-6 h-6 text-accent" />}
              title="Affordability Analysis"
              description={
                <>
                  <p className="mb-3">
                    Can the business cover the debt and still pay you?
                  </p>
                  <ul className="list-disc space-y-2 pl-5 marker:text-t-secondary">
                    <li>We calculate your DSCR and break-even point</li>
                    <li>
                      We model 3 scenarios so you see the upside, downside, and reality
                    </li>
                  </ul>
                </>
              }
              delay="delay-100"
            />
            <ValuePropCard
              icon={<ShieldCheck className="w-6 h-6 text-accent" />}
              title="Dimension Risk Assessment"
              description={
                <>
                  <p className="mb-3">We score the risks most buyers miss:</p>
                  <ul className="list-disc space-y-2 pl-5 marker:text-t-secondary">
                    <li>Owner dependence</li>
                    <li>Customer concentration</li>
                    <li>Revenue quality</li>
                    <li>Operations & suppliers</li>
                    <li>Financial transparency</li>
                  </ul>
                </>
              }
              delay="delay-200"
            />
            <ValuePropCard
              icon={<Users className="w-6 h-6 text-accent" />}
              title="Transferability Check"
              description={
                <>
                  <p className="mb-3">Will the business survive with a new owner?</p>
                  <p className="mb-2">We assess:</p>
                  <ul className="list-disc space-y-2 pl-5 marker:text-t-secondary">
                    <li>Processes and systems</li>
                    <li>Customer contracts</li>
                    <li>Team stability</li>
                    <li>Management depth</li>
                  </ul>
                </>
              }
              delay="delay-300"
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section
        id="how-it-works"
        className="scroll-mt-24 pt-24 pb-12 px-4 sm:px-6 md:scroll-mt-28 lg:px-8 bg-surface/50"
      >
        <div className="max-w-7xl mx-auto">
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6 }}
            className="flex justify-center w-full mb-12"
          >
            <h2 className="text-3xl sm:text-4xl font-bold text-center">
              <SplitText text="Turn documents into decisions in 4 steps" delay={0.04} />
            </h2>
          </motion.div>

          {/* Desktop/Tablet Horizontal Timeline */}
          <div className="hidden md:flex relative items-start justify-between w-full mt-12 px-8">
             {/* Connecting Line */}
             <div className="absolute top-[32px] left-[10%] right-[10%] h-[2px] bg-gradient-to-r from-accent/0 via-accent/40 to-accent/0 z-0" />
             
             {/* Nodes */}
             {[
               { step: '01', title: 'Upload', desc: 'Drop in your P&L, balance sheet, and loan term sheet. Our AI extracts the data.' },
               { step: '02', title: 'Review', desc: 'Review extracted figures and correct any mistakes before analysis.' },
               { step: '03', title: 'Risk', desc: '6 sections covering ownership, customers, revenue, employees, suppliers, and financials.' },
               { step: '04', title: 'Report', desc: 'A complete acquisition analysis with scores, seller questions, and a final recommendation.' },
             ].map((step, i) => (
                <motion.div 
                  key={step.step}
                  initial={{ opacity: 0, y: 30 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: "-50px" }}
                  transition={{ duration: 0.5, delay: i * 0.1 }}
                  className="flex-1 flex justify-center"
                >
                  <TimelineNode {...step} />
                </motion.div>
             ))}
          </div>

          {/* Mobile Vertical Timeline */}
          <div className="flex md:hidden flex-col gap-6 mt-12 w-full">
            {[
               { step: '01', title: 'Upload', desc: 'Drop in your P&L, balance sheet, and loan term sheet. Our AI extracts the data.' },
               { step: '02', title: 'Review', desc: 'Review extracted figures and correct any mistakes before analysis.' },
               { step: '03', title: 'Risk', desc: '6 sections covering ownership, customers, revenue, employees, suppliers, and financials.' },
               { step: '04', title: 'Report', desc: 'A complete acquisition analysis with scores, seller questions, and a final recommendation.' },
             ].map((step, i) => (
              <motion.div 
                key={step.step} 
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="flex gap-4 items-start bg-surface p-5 rounded-2xl border border-white/[0.05]"
              >
                <div className="w-12 h-12 shrink-0 rounded-full bg-accent/10 border border-accent/20 flex items-center justify-center text-accent font-bold text-lg">{step.step}</div>
                <div>
                  <h3 className="text-white font-bold mb-2">{step.title}</h3>
                  <p className="text-sm text-t-secondary leading-relaxed">{step.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Report Sections Preview */}
      <section className="py-24 px-4 sm:px-6 lg:px-8">
        <div className="max-w-5xl mx-auto">
          <motion.div 
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6 }}
            className="text-center mb-14"
          >
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-accent mb-4 [font-family:Georgia,serif]">
              What&apos;s inside the report?
            </h2>
            <p className="text-t-secondary text-lg">
              A structured acquisition analysis across 9 sections, designed for clarity at any expertise level.
            </p>
          </motion.div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 [font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif]">
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
            ].map((item, i) => (
              <motion.div 
                key={item} 
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                viewport={{ once: true, margin: "-50px" }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="flex items-center gap-3 p-4 rounded-xl border border-white/[0.06] bg-surface hover:border-accent/30 hover:bg-surface transition-colors duration-200 group"
              >
                <CheckCircle2 className="w-5 h-5 text-accent flex-shrink-0 group-hover:scale-110 transition-transform" />
                <span className="text-sm font-medium text-t-secondary group-hover:text-white transition-colors">{item}</span>
              </motion.div>
            ))}
          </div>
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
  icon: ReactNode;
  title: string;
  description: ReactNode;
  delay?: string;
}) {
  const parsedDelay = delay.startsWith('delay-') ? parseInt(delay.replace('delay-', ''), 10) / 1000 : 0;
  return (
    <motion.div 
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, delay: parsedDelay }}
      className="h-full"
    >
      <TiltedCard className="h-full" rotationIntensity={10}>
        <div className="w-12 h-12 bg-accent/10 rounded-xl flex items-center justify-center mb-4 transition-colors">
          {icon}
        </div>
        <h3 className="text-lg font-bold text-white mb-2">{title}</h3>
        <div className="text-t-secondary leading-relaxed text-sm">{description}</div>
      </TiltedCard>
    </motion.div>
  );
}

function TimelineNode({ step, title, desc }: { step: string, title: string, desc: string }) {
  const [isHovered, setIsHovered] = useState(false);
  
  return (
    <div 
      className="relative flex flex-col items-center w-full max-w-[200px] z-10 cursor-pointer group"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div 
        className="w-14 h-14 sm:w-16 sm:h-16 rounded-full border-2 border-accent bg-surface flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:bg-accent group-hover:shadow-[0_0_30px_rgba(109,40,217,0.4)]"
      >
        <span className="font-sans font-black text-lg sm:text-xl text-accent group-hover:text-white transition-colors">{step}</span>
      </div>
      
      <h3 
        className="mt-6 text-xs sm:text-sm font-bold text-center uppercase tracking-wider transition-all duration-300 text-white/60 group-hover:text-white group-hover:-translate-y-1 px-2 [font-family:system-ui,-apple-system,BlinkMacSystemFont,sans-serif]"
      >
        {title}
      </h3>

      <AnimatePresence>
        {isHovered && (
          <motion.div
            initial={{ opacity: 0, y: 15, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="absolute top-28 w-64 p-5 bg-surface border border-white/[0.08] rounded-2xl shadow-2xl z-50 pointer-events-none"
          >
            <div className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 bg-surface border-t border-l border-white/[0.08] rotate-45" />
            <p className="text-sm text-t-secondary leading-relaxed text-center relative z-10">{desc}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
