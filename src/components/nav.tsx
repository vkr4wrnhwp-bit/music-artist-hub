"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { DatumMark, Wordmark } from "./brand";
import { useResizableWidth, RESIZE_HANDLE_CLASS } from "@/lib/use-resizable";
import { readCollapsed } from "@/lib/panel-preference";

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
    match: ["/parts", "/lathe", "/reverse-engineer"],
    items: [
      { href: "/parts", label: "Part library" },
      { href: "/parts/new", label: "New part" },
      { href: "/lathe", label: "Turning" },
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
      // Read-only over tables nothing in the application writes. Both render
      // real engines and real data when a row exists; neither has a way to
      // create one, so a shop sees an empty section forever. Network and Shop
      // intelligence said so from the start and these did not.
      { href: "/jobs", label: "Jobs", shell: true },
      { href: "/quoting", label: "Quoting", shell: true },
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
  { suffix: "/tablet", label: "Tablet" },
  { suffix: "/responsibility", label: "Responsibility" },
  { suffix: "/proposals", label: "Proposals" },
  { suffix: "/cost", label: "Cost" },
  { suffix: "/review", label: "Run it past CANVAS" },
  { suffix: "/nc", label: "NC output", dev: true },
  { suffix: "/nc-analyzer", label: "NC analyzer", dev: true },
];

/**
 * The same routes, grouped by the manufacturing mode they serve — the
 * consolidation brief's rule that nobody should stare at a fifteen-item
 * flat list while working on a part. Groups reference PART_ROUTES by
 * suffix so a route exists in exactly one place; every route stays
 * reachable, only its surfacing changes.
 */
const PART_MODE_GROUPS: { mode: string; suffixes: string[] }[] = [
  { mode: "Part", suffixes: ["", "/proposals", "/responsibility", "/cost"] },
  { mode: "Hold", suffixes: ["/setups", "/soft-jaws"] },
  { mode: "Cut", suffixes: ["/tooling", "/machinist", "/nc-analyzer"] },
  { mode: "Verify", suffixes: ["/inspection", "/fair", "/readiness"] },
  { mode: "Deliver", suffixes: ["/nc", "/review", "/tablet"] },
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
  // Resizable drawer — hook precedes the collapsed early-return (hooks law).
  const drawerResize = useResizableWidth({ storageKey: "canvas.drawerWidth", defaultWidth: 210, min: 180, max: 340, edge: "end" });
  const { info } = useContext(PartShellContext);
  // Only trust the published info while it belongs to the part in the URL —
  // during a navigation between two parts the previous page's values are still
  // mounted, and a drawer naming the wrong part is worse than one naming none.
  const part = info && info.partId === partId ? info : null;

  const isOn = (href: string) => pathname === href;

  // The context drawer collapses to an edge tab — the workspace brief's rule
  // that the part, not the menu, owns the screen. Persisted per browser, and
  // Focus Workspace (the F key in the part workspace) collapses it too.
  // Starts collapsed, and the mount effect opens it only if this browser
  // says so. The other way round renders the whole drawer on first paint and
  // shuts it a frame later — three of those and the machinist's first sight
  // of the app is a screen of boxes to close.
  const [collapsed, setCollapsed] = useState(true);
  useEffect(() => {
    // No stored preference: part routes start collapsed at every width — the
    // rail and the context tabs already carry navigation there, and the part
    // owns the screen. Elsewhere, laptop widths start collapsed.
    const preferred = () => {
      let narrow = false;
      try {
        narrow = window.innerWidth < 1440;
      } catch {
        /* fine */
      }
      return readCollapsed("canvas.contextDrawer", "collapsed", partId !== null || narrow);
    };
    setCollapsed(preferred());
    // Focus collapses the drawer; leaving focus restores what was stored,
    // rather than opening a drawer the machinist had already shut.
    const onFocusMode = (e: Event) => {
      setCollapsed((e as CustomEvent).detail ? true : preferred());
    };
    window.addEventListener("canvas:focus", onFocusMode);
    // A coach mark could not find its target — if it is hiding in here,
    // open up. Expanding a drawer is non-destructive; hiding a lesson is not.
    const onReveal = () => setCollapsed(false);
    window.addEventListener("canvas:reveal-guide-target", onReveal);
    return () => {
      window.removeEventListener("canvas:focus", onFocusMode);
      window.removeEventListener("canvas:reveal-guide-target", onReveal);
    };
  }, []);
  const toggleDrawer = () => {
    setCollapsed((c) => {
      try {
        window.localStorage.setItem("canvas.contextDrawer", c ? "open" : "collapsed");
      } catch {
        /* fine */
      }
      return !c;
    });
  };

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={toggleDrawer}
        aria-label="Expand the context drawer"
        className="flex h-full w-6 shrink-0 flex-col items-center gap-2 border-r border-line bg-shell-2 pt-4 text-shell-muted transition-colors hover:text-platinum"
      >
        <span aria-hidden>▸</span>
        <span className="shell-label [writing-mode:vertical-rl]" style={{ fontSize: 9 }}>
          {part ? part.name.slice(0, 24) : active.title}
        </span>
      </button>
    );
  }

  return (
    <div
      className="relative flex h-full w-[var(--drawer-w)] shrink-0 flex-col border-r border-line bg-shell-2"
      style={{ ["--drawer-w" as string]: `${drawerResize.width}px` }}
    >
      {/* Resize handle on the drawer's canvas edge. Double-click resets. */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize the context drawer"
        title="Drag to resize · double-click to reset"
        onPointerDown={drawerResize.onPointerDown}
        onDoubleClick={drawerResize.reset}
        className={`${RESIZE_HANDLE_CLASS} right-[-3px] ${drawerResize.dragging ? "bg-precision/60" : ""}`}
      />
      <div className="flex h-[64px] shrink-0 items-stretch border-b border-line">
        <Link
          href="/"
          className="flex min-w-0 flex-1 flex-col justify-center gap-1 px-4 text-platinum-dim transition-colors hover:text-platinum"
        >
          <Wordmark size={15} />
          <span className="shell-label" style={{ fontSize: 8, letterSpacing: "0.2em" }}>
            From concept to cut.
          </span>
        </Link>
        <button
          type="button"
          onClick={toggleDrawer}
          aria-label="Collapse the context drawer"
          className="flex w-7 shrink-0 items-center justify-center text-shell-muted transition-colors hover:text-platinum"
        >
          <span aria-hidden>◂</span>
        </button>
      </div>

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
            {/* Routes grouped by manufacturing mode; only the group holding
                the current route opens by default. Fifteen flat rows became
                five groups — nothing was deleted, only surfaced differently. */}
            {PART_MODE_GROUPS.map((g) => {
              const routes = g.suffixes
                .map((s) => PART_ROUTES.find((r) => r.suffix === s)!)
                .filter(Boolean);
              const containsCurrent = routes.some((r) => isOn(`/parts/${partId}${r.suffix}`));
              return (
                <details key={g.mode} open={containsCurrent} className="group/mode">
                  <summary className="shell-label flex cursor-pointer list-none items-center justify-between px-4 py-[6px] hover:text-platinum">
                    {g.mode}
                    <span aria-hidden className="text-shell-muted group-open/mode:hidden">▸</span>
                    <span aria-hidden className="hidden text-shell-muted group-open/mode:inline">▾</span>
                  </summary>
                  {routes.map((r) => {
                    const href = `/parts/${partId}${r.suffix}`;
                    const on = isOn(href);
                    return (
                      <Link
                        key={r.suffix || "overview"}
                        href={href}
                        aria-current={on ? "page" : undefined}
                        className={`group relative flex items-center justify-between gap-2 py-[6px] pl-6 pr-3 text-[12.5px] transition-colors ${
                          on ? "bg-shell text-platinum" : "text-platinum-dim hover:text-platinum"
                        }`}
                      >
                        {on && <span aria-hidden className="absolute left-0 top-0 h-full w-[2px] bg-precision" />}
                        <span className="truncate">{r.label}</span>
                        {r.dev && <ShellTag>dev</ShellTag>}
                      </Link>
                    );
                  })}
                </details>
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
  // With everything on one row, an inferred heading beside a trail that
  // already names the page is the duplication the mobile audit flagged —
  // infer a heading only when the page brought no trail of its own.
  const heading = title ?? (children ? null : routeHeading(pathname));

  return (
    /* ONE compact command bar — the workspace-consolidation brief's header
       rule. The old two-row stack (trail row + 22px identity row) cost 92px
       of the work column on every page and duplicated the page's own
       heading. Identity, trail, metadata and status now share a single
       64px row; on narrow screens it wraps rather than clipping, and the
       right group's status module is the last thing standing. */
    <header className="canvas-shell flex min-h-[64px] shrink-0 flex-wrap items-center gap-x-4 gap-y-1 border-b border-line-strong bg-header py-2 pl-12 pr-4 lg:pl-5 lg:pr-5">
      <div className="flex min-w-0 shrink grow basis-[16rem] items-center gap-3 overflow-hidden">
        {heading && (
          <h1 className="shrink-0 truncate text-[16px] font-medium leading-none tracking-[0.01em] text-platinum">
            {heading}
          </h1>
        )}
        {chips && <span className="flex shrink-0 items-center gap-2">{chips}</span>}
        <div
          className="no-scrollbar flex min-w-0 items-center gap-3 overflow-x-auto whitespace-nowrap"
          style={{
            // A hard cut mid-chip reads as broken; a fade reads as "more to
            // the right". Only the visual mask — the trail still scrolls.
            maskImage: "linear-gradient(to right, black calc(100% - 24px), transparent)",
            WebkitMaskImage: "linear-gradient(to right, black calc(100% - 24px), transparent)",
          }}
        >
          {children}
        </div>
      </div>
      <div className="ml-auto flex min-w-0 shrink items-center gap-4 overflow-hidden">
        {meta && <span className="no-scrollbar hidden items-end gap-5 overflow-x-auto xl:flex">{meta}</span>}
        {status && <span className="shrink-0">{status}</span>}
        {user && (
          <Link href="/settings" className="hidden shrink-0 text-right leading-tight xl:block">
            <span className="block text-[11px] text-platinum-dim transition-colors hover:text-platinum">
              {user.name}
            </span>
            <span className="shell-label block" style={{ fontSize: 8.5 }}>
              {user.organizationName}
            </span>
          </Link>
        )}
        <svg className="shrink-0" width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
          <line x1="0" y1="7" x2="14" y2="7" stroke="var(--c-blue)" strokeWidth="1" />
          <line x1="7" y1="0" x2="7" y2="14" stroke="var(--c-blue)" strokeWidth="1" />
          <circle cx="7" cy="7" r="2.5" fill="none" stroke="var(--c-blue)" strokeWidth="1" />
        </svg>
      </div>
    </header>
  );
}
