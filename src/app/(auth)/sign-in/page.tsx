import { redirect } from "next/navigation";
import Link from "next/link";
import { db } from "@/lib/db";
import { createSession, getSessionUser, verifyPassword } from "@/lib/auth";
import { DatumMark, Wordmark } from "@/components/brand";
import { Button, Field, Notice, inputClass } from "@/components/ui";

export default async function SignInPage(props: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await props.searchParams;
  if (await getSessionUser()) redirect("/");

  async function signIn(formData: FormData) {
    "use server";
    const email = String(formData.get("email") ?? "").trim().toLowerCase();
    const password = String(formData.get("password") ?? "");

    const user = await db.user.findUnique({ where: { email } });
    // Same response either way — an auth form should not confirm which
    // email addresses exist in the system.
    if (!user || !(await verifyPassword(password, user.passwordHash))) {
      redirect("/sign-in?error=1");
    }
    await createSession(user.id);
    await db.user.update({ where: { id: user.id }, data: { lastSeenAt: new Date() } });
    redirect("/");
  }

  return (
    <main className="precision-grid flex min-h-screen items-center justify-center bg-void px-6">
      <div className="w-full max-w-sm">
        <div className="mb-10 flex flex-col items-center gap-4">
          <DatumMark size={44} className="text-platinum-dim" />
          <Wordmark size={22} />
          <p className="tech-label">From concept to cut.</p>
        </div>

        <form action={signIn} className="datum-frame space-y-4 border border-line bg-surface p-6">
          {error && (
            <Notice tone="risk" title="Sign in failed">
              Email or password not recognised.
            </Notice>
          )}
          <Field label="Email">
            <input name="email" type="email" required autoComplete="email" className={inputClass} defaultValue="demo@canvas.local" />
          </Field>
          <Field label="Password">
            <input name="password" type="password" required autoComplete="current-password" className={inputClass} defaultValue="canvas-demo" />
          </Field>
          <Button type="submit" variant="primary" className="w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-5 text-center text-[11px] leading-relaxed text-muted">
          Demo shop seeded at <span className="font-mono text-platinum-dim">demo@canvas.local / canvas-demo</span>.
          <br />
          <Link href="/sign-up" className="text-precision hover:underline">
            Create a new organisation
          </Link>
        </p>
      </div>
    </main>
  );
}
