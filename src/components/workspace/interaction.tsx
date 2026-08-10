"use client";

import { createContext, useCallback, useContext, useMemo, useReducer } from "react";
import type { ReactNode } from "react";

/**
 * FEATURE INTERACTION MODEL
 *
 * One state object describing what the user is looking at and what they are
 * looking at it *for*. Everything else in the workspace — the 3D scene, the
 * feature lens, the context rail, the inspector, the copilot — reads from here
 * rather than holding its own copy.
 *
 * This exists because the alternative does not survive contact with the
 * product. "Hovered bore, in HOLD context, at the state the part is in after
 * Op 30" is a single coherent thing, and if three components each track a
 * piece of it they will disagree — and the one that disagrees will be the one
 * showing a grip depth against the wrong geometry.
 *
 * Nothing here is specific to any one part. There is no reference anywhere in
 * this module to a particular feature, fixture or operation.
 */

/** What the user is currently trying to decide. Views onto one object. */
export const CONTEXTS = ["PART", "HOLD", "CUT", "VERIFY", "COST"] as const;
export type Context = (typeof CONTEXTS)[number];

export const CONTEXT_LABEL: Record<Context, string> = {
  PART: "Part",
  HOLD: "Hold",
  CUT: "Cut",
  VERIFY: "Verify",
  COST: "Cost",
};

/**
 * The state of the physical component at a point in the process. A component
 * is not one shape, and most questions worth asking are about an intermediate
 * one — whether there is material left to clamp, whether a wall is thin yet.
 */
export type ManufacturingState = { kind: "STOCK" } | { kind: "AFTER_OPERATION"; operationId: string } | { kind: "FINAL" };

export type DisplayMode = "SHADED" | "WIREFRAME" | "TRANSPARENT";

export interface InteractionState {
  hoveredFeature: string | null;
  selectedFeature: string | null;
  activeContext: Context;
  activeOperation: string | null;
  manufacturingState: ManufacturingState;
  displayMode: DisplayMode;
  /** Feature the camera should frame, or null for the whole part. */
  cameraTarget: string | null;
  /** True while a single feature is isolated for close inspection. */
  specimenMode: boolean;
  /** Position of the last hover in screen space, for placing the lens. */
  pointer: { x: number; y: number } | null;
}

type Action =
  | { type: "HOVER"; featureId: string | null; pointer?: { x: number; y: number } | null }
  | { type: "SELECT"; featureId: string | null }
  | { type: "SET_CONTEXT"; context: Context }
  | { type: "SET_OPERATION"; operationId: string | null }
  | { type: "SET_MANUFACTURING_STATE"; state: ManufacturingState }
  | { type: "SET_DISPLAY_MODE"; mode: DisplayMode }
  | { type: "FRAME"; featureId: string | null }
  | { type: "SPECIMEN"; on: boolean }
  | { type: "ESCAPE" };

/**
 * `activeOperation` starts at the operation the plan starts at, when the
 * caller has one to give.
 *
 * That is not execution state and it is not a guess: it is the first entry of
 * an ordered sequence, which is a property the plan already has. It exists
 * because the alternative — every card in the runway rendered identically
 * until the user clicks one — means the strip has no subject on arrival.
 * `manufacturingState` deliberately stays FINAL: choosing to look at an
 * operation is not the same as claiming the model shows the part after it, and
 * nothing can draw that intermediate solid yet.
 */
const initialState = (initialOperation: string | null): InteractionState => ({
  hoveredFeature: null,
  selectedFeature: null,
  activeContext: "PART",
  activeOperation: initialOperation,
  manufacturingState: { kind: "FINAL" },
  displayMode: "SHADED",
  cameraTarget: null,
  specimenMode: false,
  pointer: null,
});

function reducer(state: InteractionState, action: Action): InteractionState {
  switch (action.type) {
    case "HOVER":
      // Hovering never changes selection. A machinist moving the cursor across
      // a part to read it should not be able to lose their place.
      //
      // Leaving the geometry clears the pointer as well as the feature. It
      // used to keep the last position, which left a stale coordinate behind
      // for whatever read it next.
      return {
        ...state,
        hoveredFeature: action.featureId,
        pointer: action.featureId === null ? null : (action.pointer ?? state.pointer),
      };

    case "SELECT":
      return {
        ...state,
        selectedFeature: action.featureId,
        cameraTarget: action.featureId,
        // Deselecting always leaves specimen mode; there is nothing to inspect.
        specimenMode: action.featureId === null ? false : state.specimenMode,
      };

    case "SET_CONTEXT":
      return { ...state, activeContext: action.context };

    case "SET_OPERATION":
      return {
        ...state,
        activeOperation: action.operationId,
        // Choosing an operation implies looking at the part as it is during
        // that operation, which is the whole reason operation state exists.
        //
        // The viewport cannot draw that state yet — there is no intermediate
        // solid — so nothing reads `manufacturingState` and the runway says
        // out loud that the model shows the finished part. Keep the two facts
        // together: the day the solid exists, this is already correct.
        manufacturingState: action.operationId
          ? { kind: "AFTER_OPERATION", operationId: action.operationId }
          : { kind: "FINAL" },
      };

    case "SET_MANUFACTURING_STATE":
      return { ...state, manufacturingState: action.state };

    case "SET_DISPLAY_MODE":
      return { ...state, displayMode: action.mode };

    case "FRAME":
      return { ...state, cameraTarget: action.featureId };

    case "SPECIMEN":
      // Specimen mode without something to isolate is meaningless.
      if (action.on && !state.selectedFeature) return state;
      return { ...state, specimenMode: action.on };

    case "ESCAPE":
      // One step back at a time, outermost first, so Escape is predictable.
      // Feature and operation unwind together because choosing an operation in
      // the runway selects the feature it cuts — they are one act, so they are
      // one step back.
      if (state.specimenMode) return { ...state, specimenMode: false };
      if (state.selectedFeature || state.activeOperation)
        return {
          ...state,
          selectedFeature: null,
          activeOperation: null,
          cameraTarget: null,
          manufacturingState: { kind: "FINAL" },
        };
      if (state.activeContext !== "PART") return { ...state, activeContext: "PART" };
      return state;

    default:
      return state;
  }
}

interface InteractionApi {
  state: InteractionState;
  hover: (featureId: string | null, pointer?: { x: number; y: number } | null) => void;
  select: (featureId: string | null) => void;
  setContext: (context: Context) => void;
  setOperation: (operationId: string | null) => void;
  setManufacturingState: (state: ManufacturingState) => void;
  setDisplayMode: (mode: DisplayMode) => void;
  frame: (featureId: string | null) => void;
  setSpecimen: (on: boolean) => void;
  escape: () => void;
}

const Ctx = createContext<InteractionApi | null>(null);

export function InteractionProvider({
  children,
  initialOperation = null,
}: {
  children: ReactNode;
  /** The first operation in the plan's own order, or null when there is none. */
  initialOperation?: string | null;
}) {
  const [state, dispatch] = useReducer(reducer, initialOperation, initialState);

  const api = useMemo<InteractionApi>(
    () => ({
      state,
      hover: (featureId, pointer) => dispatch({ type: "HOVER", featureId, pointer }),
      select: (featureId) => dispatch({ type: "SELECT", featureId }),
      setContext: (context) => dispatch({ type: "SET_CONTEXT", context }),
      setOperation: (operationId) => dispatch({ type: "SET_OPERATION", operationId }),
      setManufacturingState: (s) => dispatch({ type: "SET_MANUFACTURING_STATE", state: s }),
      setDisplayMode: (mode) => dispatch({ type: "SET_DISPLAY_MODE", mode }),
      frame: (featureId) => dispatch({ type: "FRAME", featureId }),
      setSpecimen: (on) => dispatch({ type: "SPECIMEN", on }),
      escape: () => dispatch({ type: "ESCAPE" }),
    }),
    [state],
  );

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

export function useInteraction(): InteractionApi {
  const api = useContext(Ctx);
  if (!api) throw new Error("useInteraction must be used inside an InteractionProvider");
  return api;
}

/**
 * Emphasis for a piece of geometry given the current interaction state.
 *
 * Hover reduces the emphasis of everything unrelated rather than shouting
 * about the thing under the cursor. The part stays legible; the answer to
 * "what am I pointing at" arrives by everything else stepping back.
 */
export function emphasisFor(featureId: string, state: InteractionState): "ACTIVE" | "NORMAL" | "RECEDED" {
  const focus = state.selectedFeature ?? state.hoveredFeature;
  if (!focus) return "NORMAL";
  return focus === featureId ? "ACTIVE" : "RECEDED";
}

export function useEscapeKey() {
  const { escape } = useInteraction();
  return useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") escape();
    },
    [escape],
  );
}
