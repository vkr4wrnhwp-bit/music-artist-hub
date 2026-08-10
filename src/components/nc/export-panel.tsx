"use client";

import { useEffect, useRef, useState } from "react";
import { mintExport, recordExport, type MintGrant } from "@/app/(app)/parts/[id]/nc/actions";
import { Button, StatusChip } from "@/components/ui";

/**
 * NC EXPORT — the client half.
 *
 * Two buttons instead of one, deliberately. PREPARE asks the server to re-run
 * the pre-flight gate and mint a single-use authorisation with the program
 * bytes; WRITE opens the save picker with those bytes already in hand. They
 * cannot be collapsed: the picker demands transient user activation and must
 * be the first thing its click handler awaits, so the gate check has to happen
 * on the earlier click. The prepared state expires in five minutes and says so.
 *
 * Everything this panel claims is limited to what a browser can know:
 * - It writes the file and reads it back through the same handle, so
 *   "read back and compared" is real evidence.
 * - It cannot see drives, detect insertion, tell removable media from a
 *   folder, or eject. It does not pretend to. The "safely remove" line is an
 *   instruction to the operator, not a status CANVAS can satisfy.
 * - Where the picker API does not exist (Firefox, Safari, iOS), the fallback
 *   is a plain download, visibly downgraded: recorded as OFFERED, never as an
 *   export, because after a.click() the browser tells CANVAS nothing.
 */

// showSaveFilePicker is Chromium-only (WICG File System Access), so lib.dom
// does not declare it. The handle types it returns are standard (WHATWG File
// System) and already in lib.dom. Feature-detected before use.
declare global {
  interface Window {
    showSaveFilePicker(options?: {
      suggestedName?: string;
      types?: { description?: string; accept: Record<string, string[]> }[];
    }): Promise<FileSystemFileHandle>;
  }
}

type Phase =
  | { kind: "IDLE"; note?: string }
  | { kind: "PREPARING" }
  | { kind: "REFUSED"; items: { id: string; label: string; detail: string }[] }
  | { kind: "PREPARED"; grant: MintGrant; secondsLeft: number }
  | { kind: "WRITING"; grant: MintGrant }
  | {
      kind: "WRITTEN";
      grant: MintGrant;
      writtenFilename: string;
      digestMatches: boolean;
      sizeMatches: boolean;
      writtenAt: string;
      gateLapsed: boolean;
    }
  | { kind: "NOT_WRITTEN"; grant: MintGrant; secondsLeft: number; reason: string }
  | { kind: "DOWNLOADED"; grant: MintGrant };

export function NcExportPanel({ partId }: { partId: string }) {
  const [phase, setPhase] = useState<Phase>({ kind: "IDLE" });
  const [canPick, setCanPick] = useState<boolean | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    setCanPick(typeof window !== "undefined" && "showSaveFilePicker" in window);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  function startCountdown(grant: MintGrant) {
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(() => {
      setPhase((p) => {
        if (p.kind !== "PREPARED" && p.kind !== "NOT_WRITTEN") return p;
        const left = Math.max(0, Math.floor((new Date(grant.expiresAtIso).getTime() - Date.now()) / 1000));
        if (left === 0) {
          if (timer.current) clearInterval(timer.current);
          return { kind: "IDLE", note: "The prepared file expired. Pre-flight is re-checked when you prepare again." };
        }
        return { ...p, secondsLeft: left };
      });
    }, 1000);
  }

  async function prepare() {
    setPhase({ kind: "PREPARING" });
    const result = await mintExport(partId);
    if (!result.ok) {
      setPhase({ kind: "REFUSED", items: result.refused });
      return;
    }
    setPhase({ kind: "PREPARED", grant: result, secondsLeft: 300 });
    startCountdown(result);
  }

  async function writeToDrive(grant: MintGrant) {
    if (new Date(grant.expiresAtIso).getTime() < Date.now()) {
      setPhase({ kind: "IDLE", note: "The prepared file expired. Prepare the export again." });
      return;
    }
    // The picker must be the first await in this handler — transient user
    // activation is consumed by intervening awaits.
    let handle: FileSystemFileHandle;
    try {
      handle = await window.showSaveFilePicker({
        suggestedName: grant.filename,
        types: [{ description: "NC program", accept: { "text/plain": [".NC"] } }],
      });
    } catch (e) {
      // Dismissal and a browser/policy refusal both surface as AbortError —
      // the platform does not let CANVAS tell them apart, so neither do we.
      const aborted = e instanceof DOMException && e.name === "AbortError";
      setPhase({
        kind: "NOT_WRITTEN",
        grant,
        secondsLeft: secondsLeft(grant),
        reason: aborted
          ? "The save was not completed. Either the dialog was dismissed or the browser refused the location — it reports both the same way. No partial file was left."
          : `The browser refused the save dialog: ${String(e)}`,
      });
      return;
    }

    setPhase({ kind: "WRITING", grant });
    try {
      const writable = await handle.createWritable();
      await writable.write(new Blob([grant.code]));
      await writable.close();

      // Read back through the same handle and compare every byte.
      const file = await handle.getFile();
      const buf = await file.arrayBuffer();
      const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", buf)))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
      const digestMatches = hash === grant.digest;
      const sizeMatches = file.size === grant.byteLength;

      const record = await recordExport({
        token: grant.token,
        outcome: digestMatches && sizeMatches ? "WRITTEN_VERIFIED" : "WRITTEN_MISMATCH",
        destinationName: handle.name,
        writtenFilename: file.name,
        clientDigest: hash,
      });
      setPhase({
        kind: "WRITTEN",
        grant,
        writtenFilename: file.name,
        digestMatches,
        sizeMatches,
        writtenAt: new Date().toISOString().replace("T", " ").slice(0, 19),
        gateLapsed: Boolean(record.gateLapsed),
      });
    } catch (e) {
      const name = e instanceof DOMException ? e.name : "";
      const reason =
        name === "NotAllowedError"
          ? "This browser did not grant write access to the location you chose. Press Write to drive and choose again."
          : name === "QuotaExceededError"
            ? "Not enough free space at the destination. The write needs room for a temporary second copy of the file."
            : `The write failed: ${String(e)}`;
      await recordExport({ token: grant.token, outcome: "WRITE_FAILED", failureDetail: reason }).catch(() => {});
      setPhase({ kind: "NOT_WRITTEN", grant, secondsLeft: secondsLeft(grant), reason });
    }
  }

  async function download(grant: MintGrant) {
    const url = URL.createObjectURL(new Blob([grant.code], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = grant.filename;
    a.click();
    URL.revokeObjectURL(url);
    await recordExport({ token: grant.token, outcome: "DOWNLOAD_OFFERED" }).catch(() => {});
    setPhase({ kind: "DOWNLOADED", grant });
  }

  /* ---------------- render ---------------- */

  return (
    <section className="border border-line bg-surface">
      <header className="flex items-center justify-between border-b border-line-strong px-4 py-2.5">
        <h3 className="instrument-label">NC export</h3>
        <StatusChip tone="risk">Not certified</StatusChip>
      </header>
      <div className="space-y-3 px-4 py-3.5">{body()}</div>
    </section>
  );

  function body() {
    switch (phase.kind) {
      case "IDLE":
        return (
          <>
            {phase.note && <p className="text-[12px] text-review">{phase.note}</p>}
            <p className="text-[12.5px] leading-relaxed text-platinum-dim">
              Insert the drive before you continue. CANVAS cannot detect it and will not report it.
            </p>
            <Button variant="primary" onClick={prepare}>
              Prepare export
            </Button>
            <p className="text-[11px] text-muted">
              Pre-flight is re-checked on the server when you press this. The prepared file expires in 5 minutes.
            </p>
          </>
        );

      case "PREPARING":
        return <p className="text-[12px] text-muted">Re-checking pre-flight…</p>;

      case "REFUSED":
        return (
          <>
            <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-risk">Export refused</p>
            <ul className="space-y-1">
              {phase.items.map((i) => (
                <li key={i.id} className="text-[12px] leading-relaxed text-platinum-dim">
                  <span className="font-mono">{i.label}</span> — {i.detail}
                </li>
              ))}
            </ul>
          </>
        );

      case "PREPARED":
      case "NOT_WRITTEN": {
        const g = phase.grant;
        return (
          <>
            {phase.kind === "NOT_WRITTEN" ? (
              <>
                <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-review">Nothing was written</p>
                <p className="text-[12px] leading-relaxed text-platinum-dim">{phase.reason}</p>
              </>
            ) : (
              <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-platinum">
                Prepared — {fmtClock(phase.secondsLeft)} remaining
              </p>
            )}
            <ProgramLine grant={g} />
            {canPick ? (
              <>
                <Button variant="primary" onClick={() => writeToDrive(g)}>
                  Write to drive
                </Button>
                <p className="text-[11px] leading-relaxed text-muted">
                  The browser will ask where to save. Choose your drive in that dialog — CANVAS cannot list drives or
                  preselect one. Keep the filename as offered; the control reads the program number from it.
                </p>
              </>
            ) : (
              <DownloadFallback grant={g} onDownload={download} />
            )}
          </>
        );
      }

      case "WRITING":
        return <p className="text-[12px] text-muted">Writing and reading back…</p>;

      case "WRITTEN": {
        const ok = phase.digestMatches && phase.sizeMatches;
        const renamed = phase.writtenFilename !== phase.grant.filename;
        return (
          <>
            <p className={`text-[12px] font-semibold uppercase tracking-[0.12em] ${ok ? "text-pass" : "text-risk"}`}>
              {ok ? "Written — read back and compared, identical" : "Written — read-back does not match"}
            </p>
            <dl className="space-y-1 font-mono text-[11.5px] text-platinum-dim">
              <Row k="File" v={phase.writtenFilename} />
              <Row k="Size" v={`${phase.grant.byteLength.toLocaleString()} bytes${phase.sizeMatches ? "" : " expected — size on disk differs"}`} />
              <Row k="SHA-256" v={`${phase.grant.digest.slice(0, 8)}…${phase.grant.digest.slice(-4)} — ${phase.digestMatches ? "matches the program CANVAS generated" : "DOES NOT MATCH"}`} />
              <Row k="Destination" v={`"${phase.writtenFilename}" — selected by operator, media type not verifiable`} />
              <Row k="Written" v={phase.writtenAt} />
            </dl>
            {renamed && ok && (
              <p className="text-[12px] leading-relaxed text-review">
                The bytes are correct. The name is not: requested {phase.grant.filename}, written as{" "}
                {phase.writtenFilename}. This control reads the program number from the filename — rename the file on
                the drive, or export again and keep the offered name.
              </p>
            )}
            {!ok && (
              <p className="text-[12px] leading-relaxed text-risk">
                Do not run this file. Delete it from the drive and export again.
              </p>
            )}
            {phase.gateLapsed && (
              <p className="text-[12px] leading-relaxed text-review">
                Pre-flight no longer passed when this export was recorded — something changed between preparing and
                writing. The file on the drive came from an authorisation that has lapsed. Re-check the pre-flight
                before running it.
              </p>
            )}
            <p className="text-[11.5px] leading-relaxed text-muted">
              CANVAS wrote the file, read it back through the same handle and compared every byte. It cannot tell
              whether the destination is a removable drive, a network share or a folder on this PC, and it cannot
              confirm the data has left the operating system&apos;s cache.
            </p>
            <p className="text-[11.5px] font-semibold uppercase tracking-[0.1em] text-platinum-dim">
              Use the operating system&apos;s safe-removal control before pulling the drive. CANVAS cannot eject and
              cannot tell you when removal is safe.
            </p>
          </>
        );
      }

      case "DOWNLOADED":
        return (
          <>
            <p className="text-[12px] font-semibold uppercase tracking-[0.12em] text-review">
              Offered for download — destination and write not verifiable in this browser
            </p>
            <ProgramLine grant={phase.grant} />
            <p className="text-[11.5px] leading-relaxed text-muted">
              CANVAS knows what it generated. Once the browser takes the file, CANVAS learns nothing further: not where
              it was saved, not whether it was saved, not what it was named. Check the size and the SHA-256 against the
              file on the drive before you run it. This is recorded as offered for download, not as an export.
            </p>
          </>
        );
    }
  }
}

function ProgramLine({ grant }: { grant: MintGrant }) {
  return (
    <p className="font-mono text-[12px] text-platinum">
      {grant.filename} — {grant.byteLength.toLocaleString()} bytes — SHA-256 {grant.digest.slice(0, 8)}…
      {grant.digest.slice(-4)}
      <span className="block text-[11px] text-muted">
        Post: {grant.postName}. Program is not certified for production.
      </span>
    </p>
  );
}

function DownloadFallback({ grant, onDownload }: { grant: MintGrant; onDownload: (g: MintGrant) => void }) {
  return (
    <>
      <p className="text-[12px] leading-relaxed text-platinum-dim">
        Direct write is not available in this browser. CANVAS writes NC files directly to a drive you choose only in
        Chrome or Edge on a desktop. Firefox and Safari do not implement the interface and have formally declined it.
      </p>
      <Button onClick={() => onDownload(grant)}>Download {grant.filename}</Button>
      <p className="text-[11px] leading-relaxed text-muted">
        The download carries less evidence: CANVAS cannot verify where the file lands or whether it was saved. For a
        shop-floor PC, use Chrome or Edge.
      </p>
    </>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-3">
      <dt className="w-24 shrink-0 text-muted">{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}

function secondsLeft(grant: MintGrant): number {
  return Math.max(0, Math.floor((new Date(grant.expiresAtIso).getTime() - Date.now()) / 1000));
}

function fmtClock(s: number): string {
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
