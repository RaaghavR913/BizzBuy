import type { Metadata } from 'next';
import { Inter, Syne, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { AnalysisProvider } from '@/context/AnalysisContext';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { FluidBackground } from '@/components/ui/fluid-background';
import { SmoothScroll } from '@/components/layout/SmoothScroll';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const syne = Syne({ subsets: ['latin'], variable: '--font-display', weight: ['700', '800'] });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', weight: ['400', '500', '600', '700'] });

export const metadata: Metadata = {
  title: 'BizzBuy — AI Acquisition Diligence',
  description:
    'Know before you buy. Upload financials, answer risk questions, and get a plain-language acquisition report in minutes.',
  openGraph: {
    title: 'BizzBuy — AI Acquisition Diligence',
    description: 'The AI co-pilot for small business buyers. Affordability, risk, and transferability analysis in minutes.',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${syne.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased min-h-screen flex flex-col bg-transparent text-slate-100">
        <SmoothScroll>
          <FluidBackground />
          <AnalysisProvider>
            <Header />
            <main className="flex-1 w-full">{children}</main>
            <Footer />
          </AnalysisProvider>
        </SmoothScroll>
      </body>
    </html>
  );
}
