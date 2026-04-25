import type { Metadata } from 'next';
import { Inter, Playfair_Display, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { AnalysisProvider } from '@/context/AnalysisContext';
import { Header } from '@/components/layout/Header';
import { Footer } from '@/components/layout/Footer';
import { FluidBackground } from '@/components/ui/fluid-background';
import { SmoothScroll } from '@/components/layout/SmoothScroll';

const inter = Inter({ subsets: ['latin'], variable: '--font-sans' });
const playfair = Playfair_Display({ subsets: ['latin'], variable: '--font-display', weight: ['400', '500', '600', '700', '800'] });
const jetbrainsMono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono', weight: ['400', '500', '600', '700'] });

const appUrl = process.env.NEXT_PUBLIC_APP_URL
  ? new URL(process.env.NEXT_PUBLIC_APP_URL)
  : new URL('http://localhost:3000');

const defaultTitle = 'BizzBuy — AI Acquisition Diligence';
const defaultDescription =
  'Know before you buy. Upload financials, answer risk questions, and get a plain-language acquisition report in minutes.';
const ogDescription = 'The AI co-pilot for small business buyers. Affordability, risk, and transferability analysis in minutes.';

export const metadata: Metadata = {
  metadataBase: appUrl,
  title: defaultTitle,
  description: defaultDescription,
  manifest: '/site.webmanifest',
  icons: {
    icon: [
      { url: '/favicon.svg', type: 'image/svg+xml' },
      { url: '/favicon-96x96.png', sizes: '96x96', type: 'image/png' },
    ],
    shortcut: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
  openGraph: {
    title: defaultTitle,
    description: ogDescription,
    type: 'website',
    images: [
      {
        url: '/web-app-manifest-512x512.png',
        width: 512,
        height: 512,
        alt: 'BizzBuy',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: defaultTitle,
    description: ogDescription,
    images: ['/web-app-manifest-512x512.png'],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased min-h-screen flex flex-col bg-transparent text-slate-100">
        <SmoothScroll>
          <FluidBackground />
          <AnalysisProvider>
            <div className="relative z-10 flex min-h-screen w-full min-w-0 flex-1 flex-col">
              <Header />
              <main className="w-full min-w-0 flex-1">{children}</main>
              <Footer />
            </div>
          </AnalysisProvider>
        </SmoothScroll>
      </body>
    </html>
  );
}
