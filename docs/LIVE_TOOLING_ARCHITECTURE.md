# Live tooling — DEVELOPMENT architecture only

LatheMachine carries hasCaxis/hasYaxis/hasLiveTooling/hasSubSpindle
flags and `LiveToolingCapability` types exist in process.ts. Future
feature vocabulary (axial/radial holes, cross holes, flats, keyways,
slots, OD/face milling) is reserved. No CAM, no posts, no validation —
PROCESS_SUPPORT says DEVELOPMENT and the UI repeats it. The
mill-vs-live-tooling decision engine (one setup vs datum transfer) is
future manufacturing intelligence, documented in MILL_TURN_FUTURE.md.
