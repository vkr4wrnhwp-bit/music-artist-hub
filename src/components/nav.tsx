"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { DatumMark, Wordmark } from "./brand";

/**
 * THE CANVAS SHELL
 *
 * Two dark layers on the left and one across the top. Machine chrome: always
 * present, never the subject. The work surface it frames is light, and that
 * is where the part lives.
 *
 *   72px  icon rail      — which part of the shop you are in
 *   210px context drawer — what is in it, or what this part still needs
 *   92px  command bar    — which job, which revision, what state
 *
 * Everything in here sits inside `.canvas-shell`, which re-points the `--c-*`
 * role tokens at their dark-shell values (see globals.css). That is why the
 * breadcrumbs, status chips and provenance badges the pages already render
 * into the command bar are legible without any page being edited.
 *
 * ROUTES ARE REAL OR THEY ARE NOT HERE. Every entry below resolves to a page
 * that exists. Two routes are shells and say so.
 */

interface NavItem {
  href: string;
  label: string;
  /** Shells are honest about being shells. */
  shell?: boolean;
  /** Real output, development-grade. Same honesty, different claim. */
  dev?: boolean;
}

type IconKey =
  | "home"
  | "part"
  | "machine"
  | "tool"
  | "workholding"
  | "metrology"
  | "jobs"
  | "knowledge"
  | "settings";

interface Section {
  id: string;
  /** Rail label. Short enough to sit under a 20px icon in 72px. */
  rail: string;
  /** Drawer heading. */
  title: string;
  href: string;
  icon: IconKey;
  /** Path prefixes that put the rail on this section. */
  match: string[];
  items: NavItem[];
}

const SECTIONS: Section[] = [
  {
    id: "home",
    rail: "Home",
    title: "Make",
    href: "/",
    icon: "home",
    match: [],
    items: [
      { href: "/", label: "Home" },
      { href: "/parts/new", label: "New part" },
      { href: "/reverse-engineer", label: "Reverse engineer" },
    ],
  },
  {
    id: "parts",
    rail: "Parts",
    title: "Parts",
    href: "/parts",
    icon: "part",
    match: ["/parts", "/reverse-engineer"],
    items: [
      { href: "/parts", label: "Part library" },
      { href: "/parts/new", label: "New part" },
      { href: "/reverse-engineer", label: "Reverse engineer" },
    ],
  },
  {
    id: "machines",
    rail: "Machines",
    title: "Machines",
    href: "/machines",
    icon: "machine",
    match: ["/machines"],
    items: [{ href: "/machines", label: "Machines" }],
  },
  {
    id: "tooling",
    rail: "Tooling",
    title: "Tooling",
    href: "/tools",
    icon: "tool",
    match: ["/tools", "/materials"],
    items: [
      { href: "/tools", label: "Tool crib" },
      { href: "/materials", label: "Materials" },
    ],
  },
  {
    id: "workholding",
    rail: "Workholding",
    title: "Workholding",
    href: "/workholding",
    icon: "workholding",
    match: ["/workholding"],
    items: [{ href: "/workholding", label: "Workholding" }],
  },
  {
    id: "metrology",
    rail: "Metrology",
    title: "Metrology",
    href: "/metrology",
    icon: "metrology",
    match: ["/metrology"],
    items: [{ href: "/metrology", label: "Metrology" }],
  },
  {
    id: "jobs",
    rail: "Jobs",
    title: "Business",
    href: "/jobs",
    icon: "jobs",
    match: ["/jobs", "/quoting"],
    items: [
      { href: "/jobs", label: "Jobs" },
      { href: "/quoting", label: "Quoting" },
    ],
  },
  {
    id: "knowledge",
    rail: "Knowledge",
    title: "Shop knowledge",
    href: "/knowledge",
    icon: "knowledge",
    match: ["/knowledge", "/network", "/intelligence"],
    items: [
      { href: "/knowledge", label: "Shop knowledge" },
      { href: "/network", label: "Network", shell: true },
      { href: "/intelligence", label: "Shop intelligence", shell: true },
    ],
  },
  {
    id: "settings",
    rail: "Settings",
    title: "Settings",
    href: "/settings",
    icon: "settings",
    match: ["/settings", "/onboarding"],
    items: [
      { href: "/settings", label: "Settings" },
      { href: "/onboarding", label: "Shop setup" },
    ],
  },
];

/**
 * The project drawer for a part. These are the twelve routes a part revision
 * actually has — the drawer is a map of the work, not a summary of it. It
 * asserts nothing about progress, because the shell has no evidence to assert
 * it with.
 */
const PART_ROUTES: { suffix: string; label: string; dev?: boolean }[] = [
  { suffix: "", label: "Overview" },
  { suffix: "/setups", label: "Setups" },
  { suffix: "/tooling", label: "Tooling" },
  { suffix: "/soft-jaws", label: "Soft jaws" },
  { suffix: "/inspection", label: "Inspection" },
  { suffix: "/fair", label: "First article" },
  { suffix: "/readiness", label: "Readiness" },
  { suffix: "/machinist", label: "Machinist" },
  { suffix: "/responsibility", label: "Responsibility" },
  { suffix: "/proposals", label: "Proposals" },
  { suffix: "/cost", label: "Cost" },
  { suffix: "/review", label: "Run it past CANVAS" },
  { suffix: "/nc", label: "NC output", dev: true },
  { suffix: "/nc-analyzer", label: "NC analyzer", dev: true },
];

/** `/parts/<id>/…` — but `/parts/new` is a form, not a part. */
function partIdOf(pathname: string): string | null {
  const m = /^\/parts\/([^/]+)(?:\/|$)/.exec(pathname);
  if (!m || m[1] === "new") return null;
  return m[1];
}

function sectionFor(pathname: string): Section {
  if (partIdOf(pathname)) return SECTIONS.find((s) => s.id === "parts")!;
  let best: Section | null = null;
  let bestLen = 0;
  for (const s of SECTIONS) {
    for (const p of s.match) {
      if ((pathname === p || pathname.startsWith(p + "/")) && p.length > bestLen) {
        best = s;
        bestLen = p.length;
      }
    }
  }
  return best ?? SECTIONS[0];
}

/**
 * The heading for the command bar when a page has not supplied one. It is the
 * route's own navigation label — the same string the drawer shows — never an
 * invented title and never derived from data the shell has not been given.
 */
function routeHeading(pathname: string): string | null {
  const partId = partIdOf(pathname);
  if (partId) {
    const rest = pathname.slice(`/parts/${partId}`.length);
    if (rest.startsWith("/features/")) return "Feature";
    const hit = PART_ROUTES.find((r) => (r.suffix === "" ? rest === "" : rest === r.suffix));
    return hit?.label ?? null;
  }
  for (const s of SECTIONS) {
    const item = s.items.find((i) => i.href === pathname);
    if (item) return item.label;
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Shell user — so the command bar can show who is signed in without    */
/* every page having to thread the session through.                     */
/* ------------------------------------------------------------------ */

export interface ShellUser {
  name: string;
  organizationName: string;
  role: string;
}

const ShellUserContext = createContext<ShellUser | null>(null);

export function ShellUserProvider({ user, children }: { user: ShellUser; children: ReactNode }) {
  return <ShellUserContext.Provider value={user}>{children}</ShellUserContext.Provider>;
}

/* ------------------------------------------------------------------ */
/* Part identity for the drawer                                        */
/* ------------------------------------------------------------------ */

/**
 * What the project drawer is allowed to say about the part you are in.
 *
 * The drawer is rendered by the layout, above every page, so a page cannot
 * hand it anything through props. It registers instead: the part workspace
 * renders `<PartShellInfoBridge>` with values it has already loaded from the
 * database, and clears them on the way out.
 *
 * There is no progress field and there will not be one. Readiness is
 * gate-based and is stated by the engine that owns it. What the drawer carries
 * is the part's identity and the single next required action — both real
 * values, both already on the page.
 */
export interface PartShellInfo {
  partId: string;
  name: string;
  /** Part number, or null when the revision does not carry one. */
  number: string | null;
  revision: string | null;
  nextAction: {
    action: string;
    href: string | null;
    linkLabel: string | null;
    severity: "BLOCKING" | "REVIEW" | "IMPROVEMENT";
  } | null;
}

const PartShellContext = createContext<{
  info: PartShellInfo | null;
  publish: (info: PartShellInfo | null) => void;
}>({ info: null, publish: () => {} });

export function PartShellProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<PartShellInfo | null>(null);
  const value = useMemo(() => ({ info, publish: setInfo }), [info]);
  return <PartShellContext.Provider value={value}>{children}</PartShellContext.Provider>;
}

/** Renders nothing. Publishes the page's own values to the shell drawer. */
export function PartShellInfoBridge(info: PartShellInfo) {
  const { publish } = useContext(PartShellContext);
  const { partId, name, number, revision } = info;
  const action = info.nextAction?.action ?? null;
  const href = info.nextAction?.href ?? null;
  const linkLabel = info.nextAction?.linkLabel ?? null;
  const severity = info.nextAction?.severity ?? null;

  useEffect(() => {
    publish({
      partId,
      name,
      number,
      revision,
      nextAction: action && severity ? { action, href, linkLabel, severity } : null,
    });
    return () => publish(null);
  }, [publish, partId, name, number, revision, action, href, linkLabel, severity]);

  return null;
}

/* ------------------------------------------------------------------ */
/* Icons — line geometry, 1.25 stroke, square ends. Instruments, not    */
/* illustrations. No fills, no rounding, no emoji.                      */
/* ------------------------------------------------------------------ */

function RailIcon({ name }: { name: IconKey }) {
  const common = {
    width: 20,
    height: 20,
    viewBox: "0 0 20 20",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.25,
    "aria-hidden": true as const,
  };
  switch (name) {
    case "home":
      return (
        <svg {...common}>
          <path d="M2.5 9 L10 3 L17.5 9" />
          <path d="M4.5 8.2 V16.5 H15.5 V8.2" />
          <path d="M8.2 16.5 V11.8 H11.8 V16.5" />
        </svg>
      );
    case "part":
      return (
        <svg {...common}>
          <path d="M10 2.6 L17 6.3 V13.7 L10 17.4 L3 13.7 V6.3 Z" />
          <path d="M3 6.3 L10 10 L17 6.3" />
          <path d="M10 10 V17.4" />
        </svg>
      );
    case "machine":
      return (
        <svg {...common}>
          <path d="M2.5 16.8 H17.5" />
          <path d="M6.4 16.8 V13.2 H13.6 V16.8" />
          <path d="M8.4 2.8 H11.6 V8 H8.4 Z" />
          <path d="M10 8 V13.2" />
          <path d="M4 2.8 V8" />
        </svg>
      );
    case "tool":
      return (
        <svg {...common}>
          <path d="M7.8 2.6 H12.2 V9.4 H7.8 Z" />
          <path d="M7.8 9.4 V15.4 L10 17.6 L12.2 15.4 V9.4" />
          <path d="M7.8 12 L12.2 10.4" />
          <path d="M7.8 14.6 L12.2 13" />
        </svg>
      );
    case "workholding":
      return (
        <svg {...common}>
          <path d="M1.8 6.6 H5.2 V13.4 H1.8 Z" />
          <path d="M14.8 6.6 H18.2 V13.4 H14.8 Z" />
          <path d="M7 4.8 H13 V15.2 H7 Z" />
          <path d="M5.2 10 H7" />
          <path d="M13 10 H14.8" />
        </svg>
      );
    case "metrology":
      return (
        <svg {...common}>
          <path d="M2 6.6 H18" />
          <path d="M2 6.6 V10.4" />
          <path d="M5.2 6.6 V13.6 H7.4" />
          <path d="M12.6 6.6 V13.6 H10.4" />
          <path d="M8.4 3.4 H16 V6.6" />
          <path d="M15 6.6 V9" />
        </svg>
      );
    case "jobs":
      return (
        <svg {...common}>
          <path d="M4 2.8 H16 V17.2 H4 Z" />
          <path d="M6.4 6.6 H8" />
          <path d="M9.6 6.6 H13.6" />
          <path d="M6.4 10 H8" />
          <path d="M9.6 10 H13.6" />
          <path d="M6.4 13.4 H8" />
          <path d="M9.6 13.4 H13.6" />
        </svg>
      );
    case "knowledge":
      return (
        <svg {...common}>
          <path d="M10 5.4 V17" />
          <path d="M2.6 3.4 H8.4 L10 5.4 L11.6 3.4 H17.4" />
          <path d="M2.6 3.4 V15 H8.4 L10 17 L11.6 15 H17.4 V3.4" />
        </svg>
      );
    case "settings":
      return (
        <svg {...common}>
          <path d="M2.6 5.4 H17.4" />
          <path d="M2.6 10 H17.4" />
          <path d="M2.6 14.6 H17.4" />
          <path d="M7 3.6 V7.2" />
          <path d="M13 8.2 V11.8" />
          <path d="M8.6 12.8 V16.4" />
        </svg>
      );
  }
}

/* ------------------------------------------------------------------ */
/* Rail + drawer                                                       */
/* ------------------------------------------------------------------ */

function ShellTag({ children }: { children: ReactNode }) {
  return (
    <span className="shrink-0 border border-line px-1 py-[1px] text-[8px] font-semibold uppercase tracking-[0.12em] text-unknown">
      {children}
    </span>
  );
}

function Rail({ active }: { active: Section }) {
  return (
    <nav
      aria-label="Sections"
      className="flex h-full w-[72px] shrink-0 flex-col border-r border-line bg-shell"
    >
      <Link
        href="/"
        aria-label="CANVAS home"
        className="flex h-[64px] shrink-0 items-center justify-center border-b border-line text-platinum-dim transition-colors hover:text-platinum"
      >
        <DatumMark size={26} />
      </Link>

      <div className="no-scrollbar flex-1 overflow-y-auto py-2">
        {SECTIONS.map((s) => {
          const on = s.id === active.id;
          return (
            <Link
              key={s.id}
              href={s.href}
              aria-current={on ? "page" : undefined}
              className={`relative flex w-full flex-col items-center gap-1.5 px-0.5 py-2.5 transition-colors ${
                on ? "bg-shell-2 text-precision" : "text-platinum-dim hover:bg-shell-2 hover:text-platinum"
              }`}
            >
              {on && <span aria-hidden className="absolute left-0 top-0 h-full w-[2px] bg-precision" />}
              <RailIcon name={s.icon} />
              <span className="text-[8.5px] font-medium uppercase leading-none tracking-[0.01em]">{s.rail}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

function Drawer({
  pathname,
  active,
  user,
}: {
  pathname: string;
  active: Section;
  user: ShellUser;
}) {
  const partId = partIdOf(pathname);
  const { info } = useContext(PartShellContext);
  // Only trust the published info while it belongs to the part in the URL —
  // during a navigation between two parts the previous page's values are still
  // mounted, and a drawer naming the wrong part is worse than one naming none.
  const part = info && info.partId === partId ? info : null;

  const isOn = (href: string) => pathname === href;

  return (
    <div className="flex h-full w-[210px] shrink-0 flex-col border-r border-line bg-shell-2">
      <Link
        href="/"
        className="flex h-[64px] shrink-0 flex-col justify-center gap-1 border-b border-line px-4 text-platinum-dim transition-colors hover:text-platinum"
      >
        <Wordmark size={15} />
        <span className="shell-label" style={{ fontSize: 8, letterSpacing: "0.2em" }}>
          From concept to cut.
        </span>
      </Link>

      <div className="flex-1 overflow-y-auto py-4">
        {partId ? (
          <div className="mb-5">
            {/* Which part you are in. No thumbnail — there is no render stored
                for a revision, and a placeholder tile would be a picture of
                nothing. No progress — readiness is gate-based and belongs to
                the engine, which states it on the page. */}
            <div className="px-4 pb-3">
              <div className="shell-label">Part</div>
              {part ? (
                <>
                  <p className="mt-1.5 text-[13px] leading-snug text-platinum">{part.name}</p>
                  <p className="mt-0.5 font-mono text-[10.5px] tracking-[0.06em] text-shell-muted">
                    {part.number ?? "no part number"}
                    {part.revision ? ` · Rev ${part.revision}` : ""}
                  </p>
                </>
              ) : (
                <p className="mt-1.5 text-[12px] leading-snug text-shell-muted">Part revision</p>
              )}
            </div>
            {PART_ROUTES.map((r) => {
              const href = `/parts/${partId}${r.suffix}`;
              const on = isOn(href);
              return (
                <Link
                  key={r.suffix || "overview"}
                  href={href}
                  aria-current={on ? "page" : undefined}
                  className={`group relative flex items-center justify-between gap-2 py-[7px] pl-4 pr-3 text-[12.5px] transition-colors ${
                    on ? "bg-shell text-platinum" : "text-platinum-dim hover:text-platinum"
                  }`}
                >
                  {on && <span aria-hidden className="absolute left-0 top-0 h-full w-[2px] bg-precision" />}
                  <span className="truncate">{r.label}</span>
                  {r.dev && <ShellTag>dev</ShellTag>}
                </Link>
              );
            })}
            {/* The one instruction, at the foot of the map. Same value the
                runway renders — `nextActions()[0]` — so the two cannot drift.
                It is here because the drawer is on every part route and the
                runway is only on one. */}
            {part?.nextAction ? (
              <div
                className={`mt-4 mx-3 border border-line bg-shell px-3 py-2.5 border-l-2 ${
                  part.nextAction.severity === "BLOCKING"
                    ? "border-l-risk"
                    : part.nextAction.severity === "REVIEW"
                      ? "border-l-review"
                      : "border-l-pass"
                }`}
              >
                <div className="shell-label">Next required action</div>
                <p className="mt-1.5 text-[12px] font-medium leading-snug text-platinum">{part.nextAction.action}</p>
                {part.nextAction.href && (
                  <Link
                    href={part.nextAction.href}
                    className="mt-2 inline-block border border-precision/60 px-2 py-1 text-[9.5px] font-semibold uppercase tracking-[0.14em] text-precision transition-colors hover:bg-precision/10"
                  >
                    {part.nextAction.linkLabel ?? "Open"}
                  </Link>
                )}
              </div>
            ) : (
              /* The drawer lists the work. It does not score it — readiness is
                 gate-based and is stated on the page, by the engine that owns it. */
              <p className="mt-3 px-4 text-[11px] leading-relaxed text-muted">
                Readiness is stated on the page, gate by gate.
              </p>
            )}
          </div>
        ) : (
          <div className="mb-5">
            <div className="shell-label px-4 pb-2">{active.title}</div>
            {active.items.map((item) => {
              const on = isOn(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={on ? "page" : undefined}
                  className={`group relative flex items-center justify-between gap-2 py-[7px] pl-4 pr-3 text-[12.5px] transition-colors ${
                    on ? "bg-shell text-platinum" : "text-platinum-dim hover:text-platinum"
                  }`}
                >
                  {on && <span aria-hidden className="absolute left-0 top-0 h-full w-[2px] bg-precision" />}
                  <span className="truncate">{item.label}</span>
                  {item.shell && <ShellTag>shell</ShellTag>}
                </Link>
              );
            })}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-line px-4 py-3">
        <Link href="/settings" className="block">
          <div className="truncate text-[12px] text-platinum-dim transition-colors hover:text-platinum">
            {user.name}
          </div>
          <div className="shell-label truncate">{user.organizationName}</div>
        </Link>
      </div>
    </div>
  );
}

/**
 * Navigation is a permanent two-layer rail on a desktop workstation and an
 * off-canvas drawer on a phone. On a 390px screen a 282px shell leaves no room
 * for the thing you came to look at, so below `lg` it slides away entirely and
 * is summoned by the control in the top-left corner of the command bar.
 */
export function Sidebar({ user }: { user: ShellUser }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const active = sectionFor(pathname);

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

  return (
    <>
      {/* Trigger — sits in the space the command bar reserves for it. */}
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation"
        aria-expanded={open}
        className="canvas-shell fixed left-0 top-0 z-40 flex h-11 w-11 items-center justify-center border-b border-r border-line bg-shell text-platinum-dim lg:hidden"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <g stroke="currentColor" strokeWidth="1.25">
            <line x1="2" y1="4" x2="14" y2="4" />
            <line x1="2" y1="8" x2="14" y2="8" />
            <line x1="2" y1="12" x2="14" y2="12" />
          </g>
        </svg>
      </button>

      {/* Off-canvas: the same two layers, side by side. */}
      <div
        className={`canvas-shell fixed inset-0 z-50 lg:hidden ${open ? "" : "pointer-events-none"}`}
        aria-hidden={!open}
        inert={!open}
      >
        <div
          onClick={() => setOpen(false)}
          className={`absolute inset-0 bg-void/80 transition-opacity duration-200 ${
            open ? "opacity-100" : "opacity-0"
          }`}
        />
        <div
          className={`absolute inset-y-0 left-0 flex w-[282px] max-w-[85vw] transition-transform duration-200 ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <Rail active={active} />
          <div className="relative min-w-0 flex-1">
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
              className="absolute right-1 top-3 z-10 flex h-8 w-8 items-center justify-center text-muted hover:text-platinum"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                <g stroke="currentColor" strokeWidth="1.25">
                  <line x1="2" y1="2" x2="12" y2="12" />
                  <line x1="12" y1="2" x2="2" y2="12" />
                </g>
              </svg>
            </button>
            <Drawer pathname={pathname} active={active} user={user} />
          </div>
        </div>
      </div>

      {/* Permanent shell from lg up. */}
      <div className="canvas-shell hidden h-full shrink-0 lg:flex">
        <Rail active={active} />
        <Drawer pathname={pathname} active={active} user={user} />
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Job command bar                                                     */
/* ------------------------------------------------------------------ */

/**
 * A labelled machine value for the command bar's metadata row.
 *
 * The caller supplies both halves. The shell does not know a part's material,
 * stock, program number or operator and will not guess at them — a header that
 * invents a program number is a header that gets the wrong program run.
 */
export function BarMeta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="flex shrink-0 flex-col gap-[3px] leading-none">
      <span className="shell-label" style={{ fontSize: 9 }}>
        {label}
      </span>
      <span className="font-mono text-[11.5px] leading-none text-platinum">{children}</span>
    </span>
  );
}

/**
 * The dark job command bar.
 *
 * `children` is the context trail and is unchanged from the original API, so
 * every existing page keeps working untouched. The four optional slots below
 * let a page promote its own identity into the bar; when a page supplies none,
 * the heading falls back to the route's own navigation label.
 */
export function TopBar({
  children,
  title,
  chips,
  meta,
  status,
}: {
  children?: ReactNode;
  /** Part / job title. Large, left of the second row. */
  title?: ReactNode;
  /** Revision and classification chips, beside the title. */
  chips?: ReactNode;
  /** Metadata row — material, stock, program, operator. Use <BarMeta>. */
  meta?: ReactNode;
  /** Status module. Readiness belongs here, gate-based, never a score. */
  status?: ReactNode;
}) {
  const pathname = usePathname();
  const user = useContext(ShellUserContext);
  const heading = title ?? routeHeading(pathname);

  return (
    <header className="canvas-shell flex min-h-[92px] shrink-0 flex-col justify-center gap-2.5 border-b border-line-strong bg-header py-3 pl-12 pr-4 lg:pl-6 lg:pr-6">
      {/* Context trail + who is signed in */}
      <div className="flex items-center justify-between gap-4">
        <div className="no-scrollbar flex min-w-0 items-center gap-3 overflow-x-auto whitespace-nowrap">
          {children}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {user && (
            <Link href="/settings" className="hidden text-right leading-tight lg:block">
              <span className="block text-[11.5px] text-platinum-dim transition-colors hover:text-platinum">
                {user.name}
              </span>
              <span className="shell-label block" style={{ fontSize: 9 }}>
                {user.organizationName}
              </span>
            </Link>
          )}
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <line x1="0" y1="7" x2="14" y2="7" stroke="var(--c-blue)" strokeWidth="1" />
            <line x1="7" y1="0" x2="7" y2="14" stroke="var(--c-blue)" strokeWidth="1" />
            <circle cx="7" cy="7" r="2.5" fill="none" stroke="var(--c-blue)" strokeWidth="1" />
          </svg>
        </div>
      </div>

      {/* Job identity.
          `overflow-hidden` on the left group is load-bearing: it is the only
          thing stopping a long title's chips from painting over the metadata
          on a narrow screen.

          WHAT GIVES WAY, AND WHY.
          The work column is the viewport minus a 282px shell, so `lg` (1024)
          is the width at which this row has the LEAST room, not the most.
          Gating the metadata on `lg` switched it on exactly where it did not
          fit: measured, the right group is 831px against a 694px content box
          at 1024, so the readiness verdict was pushed 103px off the right edge
          of a shell that clips and does not scroll. Metadata now waits for
          `xl`.

          Above that the row WRAPS rather than squeezing. Full title plus full
          metadata plus status needs 1246px and the content box only reaches
          that around 1460, so between 1280 and there the metadata takes its
          own line and the header grows by one row. That is the honest trade:
          the alternative is a silent horizontal scroller quietly hiding the
          machine and the program number, or a part name ellipsised to nothing
          — which is what the previous version did, rendering the h1 at zero
          width across a 250px band of ordinary laptop widths.

          The right group is `min-w-0 … overflow-hidden` rather than `shrink-0`
          so it can never bleed past the header again, and the status module
          inside it stays `shrink-0`, so readiness is the last thing standing. */}
      <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
        <div className="flex min-w-[12rem] shrink grow basis-[18rem] items-center gap-3 overflow-hidden">
          {heading && (
            <h1 className="truncate text-[22px] font-medium leading-none tracking-[0.01em] text-platinum">
              {heading}
            </h1>
          )}
          {chips && <span className="flex shrink-0 items-center gap-2">{chips}</span>}
        </div>
        <div className="ml-auto flex min-w-0 shrink items-end gap-5 overflow-hidden">
          {meta && <span className="no-scrollbar hidden items-end gap-5 overflow-x-auto xl:flex">{meta}</span>}
          {status}
          {!meta && !status && <span className="instrument-label hidden lg:inline">Plan │ Machine │ Deliver</span>}
        </div>
      </div>
    </header>
  );
}
