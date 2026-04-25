'use client';

import { usePathname } from 'next/navigation';

import { GoldenHorizonShell } from '@/components/ui/golden-horizon-shell';

export default function AnalyzeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const isUpload = pathname === '/analyze/upload';

  const content = (
    <div className="min-h-full">
      <div className="max-w-7xl mx-auto px-4 pt-20 pb-10">{children}</div>
    </div>
  );

  if (isUpload) {
    return <GoldenHorizonShell contentClassName="min-h-full">{content}</GoldenHorizonShell>;
  }

  return content;
}
