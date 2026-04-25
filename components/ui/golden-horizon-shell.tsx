import type { CSSProperties, ReactNode } from "react"

import { cn } from "@/lib/utils"

const GOLDEN_HORIZON_STYLE: CSSProperties = {
  background:
    "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(251, 191, 36, 0.25), transparent 70%), #000000",
}

type GoldenHorizonShellProps = {
  children: ReactNode
  className?: string
  contentClassName?: string
}

export function GoldenHorizonShell({
  children,
  className,
  contentClassName,
}: GoldenHorizonShellProps) {
  return (
    <div className={cn("min-h-screen w-full relative bg-black", className)}>
      <div
        className="absolute inset-0 z-0"
        aria-hidden
        style={GOLDEN_HORIZON_STYLE}
      />
      <div className={cn("relative z-10", contentClassName)}>{children}</div>
    </div>
  )
}
