import "server-only";
import { createHash } from "node:crypto";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import path from "node:path";

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

const ROOT = process.env.CANVAS_STORAGE_DIR ?? path.join(process.cwd(), ".storage");

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
    // Organisation id is part of the key so a leaked key from one org cannot
    // be guessed into another's namespace.
    const safe = filename.replace(/[^a-zA-Z0-9._-]/g, "_").slice(-120);
    const key = path.posix.join(organizationId, checksum.slice(0, 2), `${checksum.slice(0, 16)}-${safe}`);
    const dest = path.join(ROOT, key);
    await mkdir(/* turbopackIgnore: true */ path.dirname(dest), { recursive: true });
    await writeFile(/* turbopackIgnore: true */ dest, data);
    return { storageKey: key, checksum, size: data.byteLength };
  }

  async get(storageKey: string): Promise<Buffer> {
    // Reject traversal explicitly rather than relying on the caller.
    if (storageKey.includes("..")) throw new Error("Invalid storage key");
    // Paths are always under the storage root and keyed by organisation.
    return readFile(/* turbopackIgnore: true */ path.join(ROOT, storageKey));
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
