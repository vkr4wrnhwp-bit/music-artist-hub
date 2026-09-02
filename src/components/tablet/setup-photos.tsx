"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

/**
 * A PHOTOGRAPH OF HOW THIS SETUP WAS BUILT.
 *
 * The last person who ran the job is the only record of which parallels went
 * under the part, which stop it was pushed to, which way the stock faced and
 * how far the tool stuck out. That leaves the shop when they do. The operator
 * already has the tablet in their hand and the part in the vise.
 *
 * It is a RECORD, not a verification. A photograph of a correct-looking setup
 * is not evidence that the grip depth is what the workholding engine was told,
 * and nothing here clears a gate or satisfies a checklist item. The page says
 * so in as many words.
 *
 * A fetch to the route handler rather than a server action: server actions cap
 * request bodies at 1MB by default and a tablet camera photo is several MB.
 * The route handler already accepts up to 64MB and is the proven path.
 */
export function SetupPhotoUpload({ setupId }: { setupId: string }) {
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function upload(files: FileList) {
    setError(null);
    const body = new FormData();
    body.append("setupId", setupId);
    for (const f of Array.from(files)) body.append("files", f);
    const res = await fetch("/api/assets", { method: "POST", body });
    const json = (await res.json().catch(() => ({}))) as { errors?: string[]; error?: string };
    if (!res.ok) {
      setError(json.error ?? "The photograph could not be stored.");
      return;
    }
    if (json.errors?.length) setError(json.errors[0]);
    start(() => router.refresh());
  }

  return (
    <div>
      <label className="flex min-h-12 cursor-pointer items-center justify-center border border-dashed border-line-strong px-4 text-[11px] font-semibold uppercase tracking-[0.14em] text-platinum-dim active:bg-card">
        {pending ? "Storing…" : "Photograph this setup"}
        <input
          ref={input}
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.length) void upload(e.target.files);
            e.target.value = "";
          }}
        />
      </label>
      {error && <p className="mt-1.5 text-[11.5px] leading-relaxed text-risk">{error}</p>}
    </div>
  );
}
