import type { CSSProperties, ReactNode } from "react"

import { cn } from "@/lib/utils"

/** Stellar Mist — full-viewport backlayer (fixed) so the gradient also reads under a transparent site header. */
const STELLAR_MIST_STYLE: CSSProperties = {
  background: `
    radial-gradient(ellipse 140% 50% at 15% 60%, rgba(124, 58, 237, 0.11), transparent 48%),
    radial-gradient(ellipse 90% 80% at 85% 25%, rgba(245, 101, 101, 0.09), transparent 58%),
    radial-gradient(ellipse 120% 65% at 40% 90%, rgba(34, 197, 94, 0.13), transparent 52%),
    radial-gradient(ellipse 100% 45% at 70% 5%, rgba(251, 191, 36, 0.07), transparent 42%),
    radial-gradient(ellipse 80% 75% at 90% 80%, rgba(168, 85, 247, 0.10), transparent 55%),
    #000000
  `.trim(),
}

type StellarMistShellProps = {
  children: ReactNode
  className?: string
  contentClassName?: string
}

export function StellarMistShell({
  children,
  className,
  contentClassName,
}: StellarMistShellProps) {
  return (
    <div className={cn("min-h-screen w-full relative bg-black", className)}>
      <div
        className="pointer-events-none fixed inset-0 z-0"
        aria-hidden
        style={STELLAR_MIST_STYLE}
      />
      <div className={cn("relative z-10", contentClassName)}>{children}</div>
    </div>
  )
}
