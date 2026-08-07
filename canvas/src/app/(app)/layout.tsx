import { requireUser } from "@/lib/auth";
import { Sidebar } from "@/components/nav";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();

  return (
    <div className="flex h-screen overflow-hidden bg-void">
      <Sidebar user={user} />
      <div className="flex min-w-0 flex-1 flex-col">{children}</div>
    </div>
  );
}

// Every page in this segment reads the session, so none of it is static.
export const dynamic = "force-dynamic";
