"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BrandLockup } from "./brand";

interface NavItem {
  href: string;
  label: string;
  /** Shells are honest about being shells. */
  shell?: boolean;
}

const GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "Make",
    items: [
      { href: "/", label: "Home" },
      { href: "/parts/new", label: "New part" },
      { href: "/reverse-engineer", label: "Reverse engineer" },
      { href: "/parts", label: "Part library" },
    ],
  },
  {
    label: "Shop",
    items: [
      { href: "/machines", label: "Machines" },
      { href: "/tools", label: "Tool crib" },
      { href: "/workholding", label: "Workholding" },
      { href: "/materials", label: "Materials" },
      { href: "/metrology", label: "Metrology" },
    ],
  },
  {
    label: "Business",
    items: [
      { href: "/jobs", label: "Jobs" },
      { href: "/quoting", label: "Quoting" },
      { href: "/network", label: "Network", shell: true },
      { href: "/intelligence", label: "Shop intelligence", shell: true },
    ],
  },
];

/**
 * Navigation is a permanent rail on a desktop workstation and an off-canvas
 * drawer on a phone. On a 390px screen a 224px rail leaves no room for the
 * thing you came to look at, so below `lg` it slides away entirely and is
 * summoned by the control in the top bar.
 */
export function Sidebar({ user }: { user: { name: string; organizationName: string; role: string } }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Navigating should always close the drawer, including when the click was a
  // link inside it — otherwise the drawer covers the page you just opened.
  useEffect(() => setOpen(false), [pathname]);

  // Escape closes it, and a locked body prevents the page scrolling underneath.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open]);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");

  const nav = (
    <>
      <div className="border-b border-line px-4 py-4">
        <BrandLockup />
      </div>

      <div className="flex-1 overflow-y-auto py-4">
        {GROUPS.map((group) => (
          <div key={group.label} className="mb-5">
            <div className="tech-label px-4 pb-2">{group.label}</div>
            {group.items.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`group relative flex items-center justify-between px-4 py-2.5 text-[13px] transition-colors lg:py-1.5 lg:text-[12px] ${
                    active ? "text-white" : "text-platinum-dim hover:text-white"
                  }`}
                >
                  {active && <span className="absolute left-0 top-0 h-full w-[2px] bg-precision" />}
                  <span>{item.label}</span>
                  {item.shell && (
                    <span className="font-mono text-[8px] uppercase tracking-[0.12em] text-unknown">shell</span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </div>

      <div className="border-t border-line px-4 py-3">
        <Link href="/settings" className="block">
          <div className="truncate text-[12px] text-platinum-dim hover:text-white">{user.name}</div>
          <div className="tech-label truncate">{user.organizationName}</div>
        </Link>
      </div>
    </>
  );

  return (
    <>
      {/* Trigger — sits in the space the top bar reserves for it. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
        className="fixed left-0 top-0 z-40 flex h-11 w-11 items-center justify-center border-b border-r border-line bg-surface text-platinum-dim lg:hidden"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <g stroke="currentColor" strokeWidth="1.25">
            <line x1="2" y1="4" x2="14" y2="4" />
            <line x1="2" y1="8" x2="14" y2="8" />
            <line x1="2" y1="12" x2="14" y2="12" />
          </g>
        </svg>
      </button>

      {/* Drawer */}
      <div
        className={`fixed inset-0 z-50 lg:hidden ${open ? "" : "pointer-events-none"}`}
        aria-hidden={!open}
      >
        <div
          onClick={() => setOpen(false)}
          className={`absolute inset-0 bg-void/80 transition-opacity duration-200 ${open ? "opacity-100" : "opacity-0"}`}
        />
        <nav
          className={`absolute inset-y-0 left-0 flex w-64 max-w-[85vw] flex-col border-r border-line bg-surface transition-transform duration-200 ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
            className="absolute right-2 top-3 z-10 flex h-8 w-8 items-center justify-center text-muted hover:text-platinum"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
              <g stroke="currentColor" strokeWidth="1.25">
                <line x1="2" y1="2" x2="12" y2="12" />
                <line x1="12" y1="2" x2="2" y2="12" />
              </g>
            </svg>
          </button>
          {nav}
        </nav>
      </div>

      {/* Permanent rail from lg up */}
      <nav className="hidden h-full w-56 shrink-0 flex-col border-r border-line bg-surface lg:flex">{nav}</nav>
    </>
  );
}

/**
 * Top strip. Reserves space on the left for the drawer trigger below `lg`, and
 * lets its contents scroll sideways rather than forcing the page wider than
 * the screen.
 */
export function TopBar({ children }: { children?: React.ReactNode }) {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between gap-3 border-b border-line bg-surface pl-12 pr-3 lg:pl-5 lg:pr-5">
      <div className="flex min-w-0 items-center gap-3 overflow-x-auto whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]{display:none}">
        {children}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span className="tech-label hidden lg:inline">Plan │ Machine │ Deliver</span>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          <line x1="0" y1="7" x2="14" y2="7" stroke="var(--c-blue)" strokeWidth="1" />
          <line x1="7" y1="0" x2="7" y2="14" stroke="var(--c-blue)" strokeWidth="1" />
          <circle cx="7" cy="7" r="2.5" fill="none" stroke="var(--c-blue)" strokeWidth="1" />
        </svg>
      </div>
    </header>
  );
}
