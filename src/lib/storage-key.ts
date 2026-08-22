import path from "node:path";

/**
 * Storage keys, and whether one is allowed to be read.
 *
 * Split out of storage.ts, which is server-only because it touches the
 * filesystem. Building a key and deciding whether a key escapes the storage
 * root are neither, and both were wrong in ways a test would have caught.
 */

/**
 * Turns an uploaded filename into a path segment.
 *
 * The sanitiser used to keep dots, so an ordinary revision filename like
 * "rev..2.step" produced a key containing "..". get() rejected any key
 * containing "..", so the file uploaded successfully and could never be read
 * back — put() and get() disagreed about what a valid key was, and the file
 * was lost while the upload reported success.
 *
 * Runs of dots collapse to one. A leading dot is dropped so a key segment
 * cannot be a hidden file.
 */
export function sanitiseFilename(filename: string): string {
  return filename
    .replace(/[^a-zA-Z0-9._-]/g, "_")
    .replace(/\.{2,}/g, ".")
    .replace(/^\.+/, "")
    .slice(-120) || "file";
}

export function buildStorageKey(organizationId: string, checksum: string, filename: string): string {
  // The organisation is part of the key so a leaked key from one shop cannot
  // be guessed into another's namespace.
  return path.posix.join(organizationId, checksum.slice(0, 2), `${checksum.slice(0, 16)}-${sanitiseFilename(filename)}`);
}

/**
 * Whether a key resolves to somewhere inside the storage root.
 *
 * This was a substring test for "..", which is a blacklist standing between
 * the application and an arbitrary file read: path.join(root, "a/../../../etc/passwd")
 * resolves to /etc/passwd and only the substring check stopped it. Resolving
 * the path and asking where it landed answers the actual question, and stops
 * rejecting legitimate keys for containing characters that look dangerous.
 */
export function resolveWithinRoot(root: string, storageKey: string): string | null {
  if (!storageKey || path.isAbsolute(storageKey)) return null;
  const resolvedRoot = path.resolve(root);
  const target = path.resolve(resolvedRoot, storageKey);
  if (target !== resolvedRoot && !target.startsWith(resolvedRoot + path.sep)) return null;
  return target;
}
