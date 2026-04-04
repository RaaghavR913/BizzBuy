import { ExternalLink } from 'lucide-react';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Meet the Team — BizzBuy',
  description: 'The founders behind BizzBuy, the AI-powered acquisition diligence platform.',
};

const FOUNDERS = [
  {
    name: 'Founder 1',
    role: 'CEO & Co-Founder',
    initials: 'F1',
    bio: 'Passionate about democratizing business acquisition intelligence.',
    gradient: 'from-accent to-violet-400',
    linkedin: '#',
  },
  {
    name: 'Founder 2',
    role: 'CTO & Co-Founder',
    initials: 'F2',
    bio: 'Building the AI engine that powers every BizzBuy report.',
    gradient: 'from-violet-400 to-purple-400',
    linkedin: '#',
  },
  {
    name: 'Founder 3',
    role: 'COO & Co-Founder',
    initials: 'F3',
    bio: 'Expert in business valuations and acquisition workflows.',
    gradient: 'from-purple-400 to-pink-400',
    linkedin: '#',
  },
  {
    name: 'Founder 4',
    role: 'Head of Product',
    initials: 'F4',
    bio: 'Designing intuitive experiences for complex financial decisions.',
    gradient: 'from-pink-400 to-rose-400',
    linkedin: '#',
  },
  {
    name: 'Founder 5',
    role: 'Lead Engineer',
    initials: 'F5',
    bio: 'Full-stack builder turning AI research into reliable products.',
    gradient: 'from-rose-400 to-orange-400',
    linkedin: '#',
  },
  {
    name: 'Founder 6',
    role: 'Head of Growth',
    initials: 'F6',
    bio: 'Connecting BizzBuy with buyers who need it most.',
    gradient: 'from-orange-400 to-amber-400',
    linkedin: '#',
  },
];

export default function TeamPage() {
  return (
    <div className="min-h-screen py-24 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        {/* Heading */}
        <div className="text-center mb-16">
          <h1 className="font-display text-4xl sm:text-5xl font-extrabold text-white mb-4">
            Meet the Founders
          </h1>
          <p className="text-lg text-t-secondary max-w-2xl mx-auto">
            We&apos;re a team of engineers, finance professionals, and operators building the tool we wish existed when we bought our first business.
          </p>
        </div>

        {/* Founders Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FOUNDERS.map((founder, i) => (
            <div
              key={founder.name}
              className="group bg-surface border border-white/[0.06] rounded-2xl p-6 hover:border-accent/30 hover:-translate-y-1 transition-all duration-300"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              {/* Avatar */}
              <div className={`w-16 h-16 rounded-full bg-gradient-to-br ${founder.gradient} flex items-center justify-center mb-4 shadow-lg group-hover:shadow-xl transition-shadow`}>
                <span className="text-lg font-bold text-white">{founder.initials}</span>
              </div>

              {/* Info */}
              <h3 className="text-base font-bold text-white mb-0.5">{founder.name}</h3>
              <p className="text-sm text-accent font-medium mb-3">{founder.role}</p>
              <p className="text-sm text-t-secondary leading-relaxed mb-4">{founder.bio}</p>

              {/* LinkedIn */}
              <a
                href={founder.linkedin}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs text-t-muted hover:text-accent transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                LinkedIn
              </a>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
