import { redirect } from "next/navigation";
import Link from "next/link";
import { db } from "@/lib/db";
import { createSession, getSessionUser, hashPassword } from "@/lib/auth";
import { DatumMark, Wordmark } from "@/components/brand";
import { Button, Field, Notice, inputClass } from "@/components/ui";

export default async function SignUpPage(props: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await props.searchParams;
  if (await getSessionUser()) redirect("/");

  async function signUp(formData: FormData) {
    "use server";
    const name = String(formData.get("name") ?? "").trim();
    const orgName = String(formData.get("org") ?? "").trim();
    const email = String(formData.get("email") ?? "").trim().toLowerCase();
    const password = String(formData.get("password") ?? "");

    if (!name || !orgName || !email || password.length < 8) redirect("/sign-up?error=invalid");
    if (await db.user.findUnique({ where: { email } })) redirect("/sign-up?error=exists");

    const slug = orgName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || `shop-${Date.now()}`;

    const org = await db.organization.create({
      data: { name: orgName, slug: `${slug}-${Math.random().toString(36).slice(2, 7)}`, defaultSharing: "PRIVATE" },
    });
    const user = await db.user.create({
      data: { name, email, passwordHash: await hashPassword(password), role: "OWNER", organizationId: org.id },
    });
    await createSession(user.id);
    redirect("/onboarding");
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-void px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="mb-10 flex flex-col items-center gap-4">
          <DatumMark size={44} className="text-platinum-dim" />
          <Wordmark size={22} />
          <p className="tech-label">From concept to cut.</p>
        </div>

        <form action={signUp} className="datum-frame space-y-4 border border-line bg-surface p-6">
          {error && (
            <Notice tone="risk" title={error === "exists" ? "Email already registered" : "Check your details"}>
              {error === "exists" ? "An account already exists for that address." : "All fields are required and the password must be at least 8 characters."}
            </Notice>
          )}
          <Field label="Your name">
            <input name="name" required className={inputClass} />
          </Field>
          <Field label="Organisation" hint="Your shop. All parts, machines and tooling are scoped to it.">
            <input name="org" required className={inputClass} />
          </Field>
          <Field label="Email">
            <input name="email" type="email" required className={inputClass} />
          </Field>
          <Field label="Password" hint="Minimum 8 characters.">
            <input name="password" type="password" required minLength={8} className={inputClass} />
          </Field>
          <Button type="submit" variant="primary" className="w-full">
            Create organisation
          </Button>
        </form>

        <p className="mt-5 text-center text-[11px] text-muted">
          <Link href="/sign-in" className="text-precision hover:underline">
            Sign in instead
          </Link>
        </p>
      </div>
    </main>
  );
}
