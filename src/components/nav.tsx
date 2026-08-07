"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
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

export function Sidebar({ user }: { user: { name: string; organizationName: string; role: string } }) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");

  return (
    <nav className="flex h-full w-56 shrink-0 flex-col border-r border-line bg-surface">
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
                  className={`group relative flex items-center justify-between px-4 py-1.5 text-[12px] transition-colors ${
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
    </nav>
  );
}

/** Top strip. Echoes the PLAN | MACHINE | DELIVER language from the brand. */
export function TopBar({ children }: { children?: React.ReactNode }) {
  return (
    <header className="flex h-11 shrink-0 items-center justify-between border-b border-line bg-surface px-5">
      <div className="flex items-center gap-3">{children}</div>
      <div className="flex items-center gap-3">
        <span className="tech-label hidden sm:inline">Plan │ Machine │ Deliver</span>
        <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          <line x1="0" y1="7" x2="14" y2="7" stroke="var(--c-blue)" strokeWidth="1" />
          <line x1="7" y1="0" x2="7" y2="14" stroke="var(--c-blue)" strokeWidth="1" />
          <circle cx="7" cy="7" r="2.5" fill="none" stroke="var(--c-blue)" strokeWidth="1" />
        </svg>
      </div>
    </header>
  );
}
