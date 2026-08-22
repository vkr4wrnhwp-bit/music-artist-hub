import "server-only";
import { createHash } from "node:crypto";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import path from "node:path";
import { buildStorageKey, resolveWithinRoot } from "./storage-key";

/**
 * Object storage abstraction.
 *
 * Development writes to a local directory outside the repository tree.
 * Production swaps in S3, GCS or equivalent behind this same interface, with
 * signed URLs rather than direct reads. Nothing else in the app knows where
 * bytes actually live.
 */

export interface StoredObject {
  storageKey: string;
  checksum: string;
  size: number;
}

export interface StorageDriver {
  put(organizationId: string, filename: string, data: Buffer): Promise<StoredObject>;
  get(storageKey: string): Promise<Buffer>;
  /** Production drivers return a time-limited signed URL. */
  url(storageKey: string): Promise<string>;
}

/**
 * Uploads are only durable when they land on a disk that outlives the process.
 *
 * On a serverless host nothing does: the project directory is read-only and
 * the only writable path is a per-instance temp directory cleared between
 * invocations. On a container host like Render the filesystem survives the
 * instance but not a redeploy, unless a persistent volume is mounted.
 *
 * Durability therefore cannot be inferred — mounting a volume looks identical
 * to writing into the container. So it is declared: set CANVAS_STORAGE_DURABLE=1
 * when a persistent volume is actually attached. Anything else is reported as
 * ephemeral, because quietly losing a file is far worse than an unnecessary
 * warning.
 */
const IS_SERVERLESS = Boolean(process.env.VERCEL || process.env.AWS_LAMBDA_FUNCTION_NAME);
const IS_MANAGED_HOST = IS_SERVERLESS || Boolean(process.env.RENDER || process.env.FLY_APP_NAME);

const ROOT =
  process.env.CANVAS_STORAGE_DIR ??
  (IS_SERVERLESS ? path.join("/tmp", "canvas-storage") : path.join(process.cwd(), ".storage"));

export const storageIsEphemeral =
  IS_MANAGED_HOST && process.env.CANVAS_STORAGE_DURABLE !== "1";

/** File types CANVAS will accept. Anything else is rejected at the boundary. */
export const ALLOWED_MIME = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/heic",
  "image/tiff",
  "application/pdf",
  "application/octet-stream", // STEP/STL/DXF often arrive as this
  "model/step",
  "model/stl",
  "image/vnd.dxf",
  "image/svg+xml",
  "text/plain",
]);

export const MAX_UPLOAD_BYTES = 64 * 1024 * 1024;

class LocalStorage implements StorageDriver {
  async put(organizationId: string, filename: string, data: Buffer): Promise<StoredObject> {
    const checksum = createHash("sha256").update(data).digest("hex");
    const key = buildStorageKey(organizationId, checksum, filename);
    const dest = resolveWithinRoot(ROOT, key);
    if (!dest) throw new Error("Invalid storage key");
    await mkdir(/* turbopackIgnore: true */ path.dirname(dest), { recursive: true });
    await writeFile(/* turbopackIgnore: true */ dest, data);
    return { storageKey: key, checksum, size: data.byteLength };
  }

  async get(storageKey: string): Promise<Buffer> {
    // Resolved rather than pattern-matched: the question is where the path
    // lands, not whether it contains a suspicious substring.
    const target = resolveWithinRoot(ROOT, storageKey);
    if (!target) throw new Error("Invalid storage key");
    return readFile(/* turbopackIgnore: true */ target);
  }

  async url(storageKey: string): Promise<string> {
    return `/api/assets/${encodeURIComponent(storageKey)}`;
  }
}

export const storage: StorageDriver = new LocalStorage();

export function validateUpload(file: { type: string; size: number; name: string }): string | null {
  if (file.size > MAX_UPLOAD_BYTES) return `${file.name} exceeds the 64 MB upload limit.`;
  if (file.size === 0) return `${file.name} is empty.`;
  if (file.type && !ALLOWED_MIME.has(file.type)) {
    const ext = path.extname(file.name).toLowerCase();
    const allowedExt = [".step", ".stp", ".stl", ".dxf", ".svg", ".iges", ".igs", ".x_t", ".sldprt"];
    if (!allowedExt.includes(ext)) return `${file.name} is not an accepted file type (${file.type || ext}).`;
  }
  return null;
}
