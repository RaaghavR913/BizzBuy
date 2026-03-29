import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AnalysisProvider } from '@/context/AnalysisContext';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });

export const metadata: Metadata = {
  title: 'BizBuy — AI Acquisition Diligence',
  description:
    'Know before you buy. Upload financials, answer risk questions, and get a plain-language acquisition report in minutes.',
  openGraph: {
    title: 'BizBuy — AI Acquisition Diligence',
    description: 'The AI co-pilot for small business buyers. Affordability, risk, and transferability analysis in minutes.',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased bg-slate-50 text-slate-900 min-h-screen flex flex-col">
        <AnalysisProvider>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </AnalysisProvider>
      </body>
    </html>
  );
}
