/**
 * WHICH MACHINE, WHICH MATERIAL
 *
 * Two lookups that used to end in `?? machines[0]` and `?? materials[0]`.
 * They are here rather than inline in package.ts so the rule they encode can
 * be stated once and checked: when the shop has no record of the thing the
 * part names, the answer is null. Everything downstream is written for a
 * null and says what it cannot do without it.
 */

export function selectPrimaryMachine<M extends { id: string }, S extends { machineId: string | null }>(
  setups: S[],
  machines: M[],
): M | null {
  const assigned = setups.find((s) => s.machineId);
  if (!assigned) return null;
  return machines.find((m) => m.id === assigned.machineId) ?? null;
}

export function selectMaterial<M extends { name: string }>(materials: M[], name: string | null): M | null {
  if (!name) return null;
  return materials.find((m) => m.name === name) ?? null;
}

/**
 * The workholding device a setup names, or null.
 *
 * Three call sites fell back to workholdingDevices[0] when the setup named
 * none. The device drives jaw width, jaw height and maximum opening, so the
 * fallback dimensioned a set of soft jaws for a vise the setup does not use —
 * and the soft-jaw page already renders an explanation when there is no
 * device, so the fallback was talking over a message that was written for
 * exactly this case.
 */
export function selectWorkholdingDevice<D extends { id: string }, S extends { workholdingId: string | null }>(
  devices: D[],
  setup: S | null | undefined,
): D | null {
  if (!setup?.workholdingId) return null;
  return devices.find((d) => d.id === setup.workholdingId) ?? null;
}
