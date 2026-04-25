"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

export interface MenuToggleIconProps extends React.SVGProps<SVGSVGElement> {
  open: boolean
  /** Transition duration in ms (default 300) */
  duration?: number
}

export function MenuToggleIcon({
  open,
  className,
  duration = 300,
  style,
  ...props
}: MenuToggleIconProps) {
  const ms = `${duration}ms`
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      className={cn("text-foreground", className)}
      style={{ transition: `transform ${ms} ease-out`, ...style }}
      aria-hidden
      {...props}
    >
      <line
        x1="4"
        y1="8"
        x2="20"
        y2="8"
        style={{
          transformOrigin: "50% 50%",
          transform: open ? "translateY(4px) rotate(45deg)" : undefined,
          transition: `transform ${ms} ease-out`,
        }}
      />
      <line
        x1="4"
        y1="16"
        x2="20"
        y2="16"
        style={{
          transformOrigin: "50% 50%",
          transform: open ? "translateY(-4px) rotate(-45deg)" : undefined,
          transition: `transform ${ms} ease-out`,
        }}
      />
    </svg>
  )
}
