import { Suspense } from "react";
import { CoachMark } from "@/components/guide/coach-mark";
import { DensityApplier } from "@/components/density";
import { ShellThemeApplier } from "@/components/shell-theme";
import { requireUser } from "@/lib/auth";
import { PartShellProvider, Sidebar, ShellUserProvider } from "@/components/nav";

/**
 * THE SHELL FRAME
 *
 * Dark chrome on the left (icon rail + context drawer) and across the top
 * (the job command bar, rendered by each page's <TopBar>), framing a light
 * work area that fills the rest of the viewport.
 *
 * `h-screen overflow-hidden` is load-bearing: nothing here scrolls. Every page
 * scrolls inside its own `<main className="flex-1 overflow-y-auto">`, which is
 * what keeps the command bar fixed at the top of the work area rather than
 * scrolling away with the content. `min-w-0` on the work column is what stops
 * a wide table from pushing the whole shell sideways.
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();

  return (
    /* PartShellProvider wraps both halves because the drawer is rendered here,
       above every page: a part route publishes its identity and its next
       required action into this provider and the drawer reads them. Nothing is
       invented in transit — the page publishes values it has already loaded. */
    <PartShellProvider>
      <div className="flex h-dvh overflow-hidden bg-shell">
        <Sidebar user={{ name: user.name, organizationName: user.organizationName, role: user.role }} />
        <ShellUserProvider
          user={{ name: user.name, organizationName: user.organizationName, role: user.role }}
        >
          <div className="flex min-w-0 flex-1 flex-col bg-work">{children}</div>
          <Suspense fallback={null}>
            <CoachMark />
          </Suspense>
          <DensityApplier />
          <ShellThemeApplier />
        </ShellUserProvider>
      </div>
    </PartShellProvider>
  );
}

// Every page in this segment reads the session, so none of it is static.
export const dynamic = "force-dynamic";
