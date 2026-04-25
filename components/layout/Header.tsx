"use client"

import * as React from "react"
import Image from "next/image"
import Link from "next/link"
import { ArrowUpRight } from "lucide-react"

import { Button, buttonVariants } from "@/components/ui/button"
import { MenuToggleIcon } from "@/components/ui/menu-toggle-icon"
import { useScroll } from "@/components/ui/use-scroll"
import { cn } from "@/lib/utils"

const ROUTES = {
  home: "/",
  whatItDoes: "/#what-it-does",
  howItWorks: "/#how-it-works",
  pricing: "/pricing",
  analyze: "/analyze/upload",
  demo: "/analyze/upload?demo=true",
  founders: "/team",
} as const

const NAV_ITEMS: ReadonlyArray<{ label: string; href: string }> = [
  { label: "Home", href: ROUTES.home },
  { label: "What it does", href: ROUTES.whatItDoes },
  { label: "How it Works", href: ROUTES.howItWorks },
  { label: "Demo", href: ROUTES.demo },
  { label: "Pricing", href: ROUTES.pricing },
  { label: "Founders", href: ROUTES.founders },
]

export function Header() {
  const [open, setOpen] = React.useState(false)
  const scrolled = useScroll(10)

  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden"
    } else {
      document.body.style.overflow = ""
    }
    return () => {
      document.body.style.overflow = ""
    }
  }, [open])

  const linkClose = () => setOpen(false)

  return (
    <header
      className={cn(
        "sticky top-0 z-50 mx-auto w-full max-w-6xl border-b border-border/20 md:rounded-md md:border md:border-border/20",
        "md:transition-all md:ease-out",
        scrolled || open
          ? "supports-[backdrop-filter]:bg-white/[0.06] backdrop-blur-sm"
          : "bg-transparent backdrop-blur-none",
        {
          "md:top-4 md:max-w-5xl md:ring-1 md:ring-border/25": scrolled && !open,
        }
      )}
    >
      <nav
        className={cn(
          "flex h-14 w-full items-center px-4 md:h-12 md:transition-all md:ease-out",
          {
            "md:px-2": scrolled,
          }
        )}
      >
        <div className="flex w-full items-center justify-between gap-3 md:hidden">
          <Link href={ROUTES.home} className="shrink-0" aria-label="BizzBuy home">
            <Image
              src="/favicon-96x96.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 shrink-0"
              priority
            />
          </Link>
          <Button
            size="icon"
            variant="outline"
            type="button"
            aria-expanded={open}
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
          >
            <MenuToggleIcon open={open} className="size-5" duration={300} />
          </Button>
        </div>

        <div className="hidden w-full min-w-0 items-center justify-between gap-0 md:flex">
          <Link href={ROUTES.home} className="shrink-0" aria-label="BizzBuy home">
            <Image
              src="/favicon-96x96.png"
              alt=""
              width={40}
              height={40}
              className="h-10 w-10 shrink-0"
              priority
            />
          </Link>
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href + item.label}
              href={item.href}
              className={buttonVariants({
                variant: "ghost",
                className:
                  "shrink-0 px-1.5 text-xs text-foreground/90 hover:text-foreground min-[800px]:px-2 min-[800px]:text-sm whitespace-nowrap [font-family:Georgia,serif]",
              })}
            >
              {item.label}
            </Link>
          ))}
          <Link
            href={ROUTES.analyze}
            className={cn(
              buttonVariants(),
              "shrink-0 bg-primary text-black hover:bg-primary/90 [font-family:Georgia,serif]"
            )}
          >
            Analyze a Business
          </Link>
        </div>
      </nav>

      <div
        className={cn(
          "bg-background/90 fixed top-14 right-0 bottom-0 left-0 z-50 flex flex-col overflow-y-auto border-y md:hidden",
          open ? "block" : "hidden"
        )}
      >
        <div
          data-slot={open ? "open" : "closed"}
          className={cn(
            "data-[slot=open]:animate-in data-[slot=open]:zoom-in-95 data-[slot=closed]:animate-out data-[slot=closed]:zoom-out-95 ease-out",
            "flex h-full w-full min-h-0 flex-col justify-between gap-y-4 p-4"
          )}
        >
          <div className="min-h-0 flex-1 overflow-y-auto">
            <ul className="grid gap-1">
              {NAV_ITEMS.map((item) => (
                <li key={item.href + item.label}>
                  <Link
                    href={item.href}
                    onClick={linkClose}
                    className={buttonVariants({
                      variant: "ghost",
                      className:
                        "h-auto w-full justify-start gap-2 px-3 py-2.5 font-normal [font-family:Georgia,serif]",
                    })}
                  >
                    <ArrowUpRight className="size-4 shrink-0 text-accent" aria-hidden />
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div className="shrink-0">
            <Link
              href={ROUTES.analyze}
              onClick={linkClose}
              className={cn(
                buttonVariants(),
                "w-full bg-primary text-black hover:bg-primary/90 [font-family:Georgia,serif]"
              )}
            >
              Analyze a Business
            </Link>
          </div>
        </div>
      </div>
    </header>
  )
}
