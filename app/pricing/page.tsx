'use client';

import { Check, ArrowRight, Zap } from 'lucide-react';
import { useState } from 'react';

const FEATURES = [
  'Unlimited acquisition reports',
  'Full 7-agent AI analysis',
  'PDF report downloads',
  'SBA lending analysis',
  'Risk radar & transferability scoring',
  'Priority support',
];

export default function PricingPage() {
  const [clicked, setClicked] = useState(false);

  function handleGetStarted() {
    console.log('Pricing: Get Started clicked');
    setClicked(true);
    setTimeout(() => setClicked(false), 3000);
  }

  return (
    <div className="min-h-screen py-24 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-16">
          <h1 className="font-display text-4xl sm:text-5xl font-extrabold text-white mb-4">
            Simple, transparent pricing
          </h1>
          <p className="text-lg text-t-secondary max-w-xl mx-auto">
            One plan. Full access. Everything you need to make confident acquisition decisions.
          </p>
        </div>

        {/* Pricing Card */}
        <div className="max-w-md mx-auto">
          <div className="relative bg-surface border-2 border-accent/30 rounded-2xl p-8 shadow-xl shadow-accent/5">
            {/* Glow effect */}
            <div className="absolute -inset-px bg-gradient-to-b from-accent/20 via-transparent to-transparent rounded-2xl pointer-events-none" />

            <div className="relative">
              {/* Badge */}
              <div className="inline-flex items-center gap-1.5 bg-accent/10 border border-accent/20 rounded-full px-3 py-1 text-xs text-accent font-semibold mb-6">
                <Zap className="w-3 h-3" />
                MOST POPULAR
              </div>

              {/* Plan name */}
              <h2 className="text-xl font-bold text-white mb-2">BizzBuy Pro</h2>

              {/* Price */}
              <div className="flex items-baseline gap-1 mb-1">
                <span className="font-mono text-5xl font-extrabold text-white">$200</span>
                <span className="text-t-secondary text-lg">/month</span>
              </div>
              <p className="text-sm text-t-muted mb-8">Billed monthly · Cancel anytime</p>

              {/* Features */}
              <div className="space-y-3 mb-8">
                {FEATURES.map((feature) => (
                  <div key={feature} className="flex items-center gap-3">
                    <div className="w-5 h-5 rounded-full bg-accent/10 flex items-center justify-center flex-shrink-0">
                      <Check className="w-3 h-3 text-accent" />
                    </div>
                    <span className="text-sm text-t-secondary">{feature}</span>
                  </div>
                ))}
              </div>

              {/* CTA */}
              {clicked && (
                <div className="bg-accent/10 border border-accent/20 rounded-lg px-4 py-3 text-sm text-accent text-center mb-4">
                  Payment integration coming soon — backend not yet connected.
                </div>
              )}
              <button
                onClick={handleGetStarted}
                className="w-full inline-flex items-center justify-center gap-2 bg-accent hover:bg-accent-hover text-white py-3.5 rounded-xl font-semibold text-base transition-all hover:shadow-lg hover:shadow-accent/20"
              >
                Get Started
                <ArrowRight className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Enterprise teaser */}
          <div className="text-center mt-8">
            <p className="text-sm text-t-muted">
              Need custom volume or white-label?{' '}
              <button
                type="button"
                onClick={() => console.log('Enterprise contact clicked')}
                className="text-accent hover:text-accent-hover transition-colors font-medium"
              >
                Contact us →
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
