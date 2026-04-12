import { ExternalLink } from 'lucide-react';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Meet the Team — BizzBuy',
  description: 'The founders behind BizzBuy, the AI-powered acquisition diligence platform.',
};

const FOUNDERS = [
  {
    name: 'Jainam Manot',
    role: 'UI/UX & Business Logic',
    initials: 'JM',
    bio: '',
    gradient: 'from-accent to-violet-400',
    linkedin: 'https://www.linkedin.com/in/jainam-manot/',
    image: '',
  },
  {
    name: 'Akshat Lunia',
    role: 'Lead Backend Developer',
    initials: 'AL',
    bio: '',
    gradient: 'from-violet-400 to-purple-400',
    linkedin: 'https://www.linkedin.com/in/akshat-lunia/',
    image: '',
  },
  {
    name: 'Raaghav Ramji',
    role: 'Agent creator & AI Wizard',
    initials: 'RR',
    bio: '',
    gradient: 'from-purple-400 to-pink-400',
    linkedin: 'https://www.linkedin.com/in/raaghavramji/',
    image: '',
  },
  {
    name: '',
    role: '',
    initials: '',
    bio: '',
    gradient: 'from-pink-400 to-rose-400',
    linkedin: '',
    image: '',
  },
  {
    name: '',
    role: '',
    initials: '',
    bio: '',
    gradient: 'from-rose-400 to-orange-400',
    linkedin: '',
    image: '',
  },
  {
    name: '',
    role: '',
    initials: '',
    bio: '',
    gradient: 'from-orange-400 to-amber-400',
    linkedin: '',
    image: '',
  },
];

export default function TeamPage() {
  return (
    <div className="min-h-screen py-24 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-16">
          <h1 className="font-sans text-4xl sm:text-5xl font-bold tracking-tight text-white mb-4">
            Meet the Founders
          </h1>
          <p className="text-lg text-t-secondary max-w-2xl mx-auto">
            We&apos;re a team of engineers, finance professionals, and operators building the tool we wish existed when we bought our first business.
          </p>
        </div>

        {/* Founders Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FOUNDERS.map((founder, i) => 
            founder.name ? (
              <div
                key={founder.name}
                className="group bg-surface border border-white/[0.06] rounded-2xl p-6 hover:border-accent/30 hover:-translate-y-1 transition-all duration-300"
                style={{ animationDelay: `${i * 80}ms` }}
              >
                {/* Avatar */}
                {founder.image ? (
                  <div className="w-16 h-16 rounded-full overflow-hidden mb-4 shadow-lg group-hover:shadow-xl transition-shadow border-2 border-white/10">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={founder.image} alt={founder.name} className="w-full h-full object-cover" />
                  </div>
                ) : (
                  <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${founder.gradient} flex items-center justify-center mb-4 shadow-lg group-hover:shadow-xl transition-shadow`}>
                    <span className="text-lg font-bold text-white">{founder.initials}</span>
                  </div>
                )}
                
                {/* Info */}
                <h3 className="text-base font-bold text-white mb-0.5">{founder.name}</h3>
                <p className="text-sm text-accent font-medium mb-3">{founder.role}</p>
                <p className="text-sm text-t-secondary leading-relaxed mb-4">{founder.bio}</p>

                {/* LinkedIn */}
                {founder.linkedin && (
                  <a
                    href={founder.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-xs text-t-muted hover:text-accent transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    LinkedIn
                  </a>
                )}
              </div>
            ) : (
              <div
                key={`empty-${i}`}
                className="bg-surface/50 border border-white/[0.02] border-dashed rounded-2xl p-6 opacity-50"
              />
            )
          )}
        </div>
      </div>
    </div>
  );
}
