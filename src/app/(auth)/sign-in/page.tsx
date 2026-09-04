import { redirect } from "next/navigation";
import Link from "next/link";
import { db } from "@/lib/db";
import { createSession, getSessionUser, verifyPassword } from "@/lib/auth";
import { anyAccountExists, createDemoShop, demoShopExists, DEMO_EMAIL, DEMO_PASSWORD } from "@/lib/seed-demo";
import { DatumMark, Wordmark } from "@/components/brand";
import { Button, Field, Notice, inputClass } from "@/components/ui";

export const dynamic = "force-dynamic";

export default async function SignInPage(props: { searchParams: Promise<{ error?: string; seeded?: string }> }) {
  const { error, seeded } = await props.searchParams;
  if (await getSessionUser()) redirect("/");

  /**
   * A deployment whose build-time seed did not run renders a sign-in page that
   * nobody can get past, with the reason buried in a log. Rather than leave the
   * operator stuck, detect the empty instance and offer to create the demo shop
   * from here. Any database trouble is reported plainly instead of throwing.
   */
  let databaseError: string | null = null;
  let hasAccounts = true;
  let hasDemo = true;
  try {
    hasAccounts = await anyAccountExists();
    hasDemo = await demoShopExists();
  } catch (e) {
    databaseError = e instanceof Error ? e.message.split("\n")[0].slice(0, 200) : "Unknown database error";
  }

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

  async function seedDemo() {
    "use server";
    const outcome = await createDemoShop();
    redirect(outcome.created ? "/sign-in?seeded=1" : "/sign-in?error=seed");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-void px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-10 flex flex-col items-center gap-4">
          <DatumMark size={44} className="text-platinum-dim" />
          <Wordmark size={22} />
          <p className="tech-label">From concept to cut.</p>
        </div>

        {databaseError && (
          <div className="mb-4">
            <Notice tone="risk" title="Database unreachable">
              <p className="font-mono text-[11px] leading-relaxed">{databaseError}</p>
              <p className="mt-2">
                Either the connection string is wrong or migrations have not been applied. See{" "}
                <Link href="/api/health" className="text-precision hover:underline">
                  /api/health
                </Link>{" "}
                for details.
              </p>
            </Notice>
          </div>
        )}

        {!databaseError && !hasAccounts && (
          <div className="mb-4">
            <Notice tone="review" title="No accounts on this instance">
              <p>
                The database is reachable but nothing has been seeded yet. Create the demo shop — a
                reference machine, tooling, workholding, materials and metrology — or sign up for a
                new organisation.
              </p>
              <form action={seedDemo} className="mt-3">
                <Button type="submit" variant="primary" size="sm">
                  Create the demo shop
                </Button>
              </form>
            </Notice>
          </div>
        )}

        {seeded === "1" && (
          <div className="mb-4">
            <Notice tone="pass" title="Demo shop created">
              Sign in below with the pre-filled credentials.
            </Notice>
          </div>
        )}

        <form action={signIn} className="datum-frame space-y-4 border border-line bg-surface p-6">
          {error === "1" && (
            <Notice tone="risk" title="Sign in failed">
              Email or password not recognised.
            </Notice>
          )}
          {error === "seed" && (
            <Notice tone="risk" title="Could not create the demo shop">
              Accounts already exist on this instance, so it was left untouched.
            </Notice>
          )}
          <Field label="Email">
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              className={inputClass}
              defaultValue={hasDemo || !hasAccounts ? DEMO_EMAIL : ""}
            />
          </Field>
          <Field label="Password">
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
              className={inputClass}
              defaultValue={hasDemo || !hasAccounts ? DEMO_PASSWORD : ""}
            />
          </Field>
          <Button type="submit" variant="primary" className="w-full">
            Sign in
          </Button>
        </form>

        <p className="mt-5 text-center text-[11px] leading-relaxed text-muted">
          {hasDemo ? (
            <>
              Demo shop seeded at{" "}
              <span className="font-mono text-platinum-dim">
                {DEMO_EMAIL} / {DEMO_PASSWORD}
              </span>
              .
              <br />
            </>
          ) : null}
          <Link href="/sign-up" className="text-precision hover:underline">
            Create a new organisation
          </Link>
        </p>
      </div>
    </main>
  );
}
