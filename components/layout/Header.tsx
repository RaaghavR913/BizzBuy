'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { BarChart3, Menu, X } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';

const NAV_LINKS = [
  { href: '/team', label: 'Team' },
  { href: '/pricing', label: 'Pricing' },
];

export function Header() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="border-b border-white/[0.06] bg-surface/80 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 bg-gradient-to-br from-accent to-violet-400 rounded-lg flex items-center justify-center transition-shadow group-hover:shadow-lg group-hover:shadow-accent/20">
            <BarChart3 className="w-4 h-4 text-white" />
          </div>
          <span className="font-display text-lg font-bold bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">
            BizzBuy
          </span>
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                'px-3.5 py-2 rounded-lg text-sm font-medium transition-colors',
                pathname === link.href
                  ? 'text-white bg-white/[0.08]'
                  : 'text-t-secondary hover:text-white hover:bg-white/[0.05]'
              )}
            >
              {link.label}
            </Link>
          ))}
          <div className="w-px h-5 bg-white/[0.08] mx-2" />
          <Link
            href="/#login"
            className="px-3.5 py-2 rounded-lg text-sm font-medium text-t-secondary hover:text-white transition-colors"
          >
            Sign In
          </Link>
          <Link
            href="/analyze/upload"
            className="ml-1 inline-flex items-center gap-2 bg-accent hover:bg-accent-hover text-white px-5 py-2 rounded-lg text-sm font-semibold transition-all hover:shadow-lg hover:shadow-accent/20"
          >
            Analyze a Business
          </Link>
        </nav>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden p-2 text-t-secondary hover:text-white transition-colors"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Nav */}
      {mobileOpen && (
        <div className="md:hidden border-t border-white/[0.06] bg-surface/95 backdrop-blur-xl animate-fade-in">
          <div className="px-4 py-4 space-y-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className={cn(
                  'block px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  pathname === link.href
                    ? 'text-white bg-white/[0.08]'
                    : 'text-t-secondary hover:text-white hover:bg-white/[0.05]'
                )}
              >
                {link.label}
              </Link>
            ))}
            <Link
              href="/#login"
              onClick={() => setMobileOpen(false)}
              className="block px-3 py-2.5 rounded-lg text-sm font-medium text-t-secondary hover:text-white transition-colors"
            >
              Sign In
            </Link>
            <Link
              href="/analyze/upload"
              onClick={() => setMobileOpen(false)}
              className="block text-center bg-accent hover:bg-accent-hover text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors mt-2"
            >
              Analyze a Business
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
