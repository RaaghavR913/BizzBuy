'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { BarChart3 } from 'lucide-react';
import CardNav from '@/components/ui/CardNav';

export function Header() {
  const router = useRouter();

  const logoNode = (
    <Link href="/" className="flex items-center gap-2.5 group">
      <div className="w-8 h-8 bg-gradient-to-br from-[#D4AF37] to-yellow-600 rounded-lg flex items-center justify-center transition-shadow group-hover:shadow-lg group-hover:shadow-[#D4AF37]/20">
        <BarChart3 className="w-5 h-5 text-black" />
      </div>
      <span className="font-display tracking-tight text-xl font-bold bg-gradient-to-r from-[#D4AF37] to-yellow-500 bg-clip-text text-transparent">
        BizzBuy
      </span>
    </Link>
  );

  const navItems = [
    {
      label: "Platform",
      bgColor: "#0f0f0f",
      textColor: "#D4AF37",
      links: [
        { label: "Pricing", href: "/pricing", ariaLabel: "Pricing" },
        { label: "Analyze a Business", href: "/analyze/upload", ariaLabel: "Analyze" }
      ]
    },
    {
      label: "Company", 
      bgColor: "#131313",
      textColor: "#D4AF37",
      links: [
        { label: "Team", href: "/team", ariaLabel: "Team" },
      ]
    },
    {
      label: "Account",
      bgColor: "#131313", 
      textColor: "#D4AF37",
      links: [
        { label: "Sign In", href: "/#login", ariaLabel: "Sign In" },
      ]
    }
  ];

  return (
    <header className="fixed top-0 left-0 right-0 w-full z-50 bg-[#000]/80 backdrop-blur-md border-b border-[#D4AF37]/20 py-2">
      <CardNav 
        logo={logoNode}
        items={navItems}
        baseColor="#0a0a0a"
        menuColor="#D4AF37"
        buttonBgColor="#D4AF37"
        buttonTextColor="#000"
        buttonClick={() => router.push('/analyze/upload')}
      />
    </header>
  );
}
