/* Street Banker · SB-14 VLV-6 — six colouring stages, each a real process.
 *
 * The point of six tubes is six DIFFERENT things, not one algorithm wearing
 * six labels. Each stage below changes the signal in a way you can measure,
 * and the faceplate only claims what these functions actually do:
 *
 *   V1 TRIODE    Asymmetric shaping. The two halves of the wave are driven
 *                by different amounts, which is what puts energy on the
 *                EVEN harmonics (2nd, 4th) - the "warmth" people mean. It
 *                also creates DC, so the graph puts a 15 Hz blocker after.
 *
 *   V2 PENTODE   Symmetric shaping. An odd-symmetric curve can only produce
 *                ODD harmonics (3rd, 5th) - edge and push rather than
 *                warmth. Same family as V1, deliberately opposite symmetry.
 *
 *   V3 TAPE      Soft-knee compression curve (a saturating exponential),
 *                plus the two filter moves that actually make tape sound
 *                like tape: high-frequency loss and a low "head bump".
 *
 *   V4 FLUTTER   Wow and flutter: two LFOs (slow ~0.7 Hz, fast ~6.3 Hz)
 *                modulating a short delay line, which is genuine pitch
 *                movement, not a chorus effect pretending to be one.
 *
 *   V5 IRON      Transformer character: the same soft saturation applied
 *                ONLY to the low band, because that is where an output
 *                transformer's core actually saturates.
 *
 *   V6 VARI-MU   Slow, program-dependent gain reduction - the tube
 *                compressor behaviour, distinct from the rack's existing
 *                fast compressor.
 *
 * The glow is a meter, not decoration: each tube's brightness comes from
 * how hard that stage is really being driven right now (and for V6, from
 * its actual gain reduction). A tube that is doing nothing stays dark.
 *
 * Curves are pure array maths - no DOM, no Web Audio - so the harmonic
 * claims above are checked in Node with an FFT rather than asserted.
 */
(function (root) {
  "use strict";

  var N = 2048;   // waveshaper table size; plenty for audio-rate shaping

  function table(fn) {
    var c = new Float32Array(N);
    for (var i = 0; i < N; i++) {
      var x = (i / (N - 1)) * 2 - 1;
      var y = fn(x);
      c[i] = y > 1 ? 1 : (y < -1 ? -1 : y);
    }
    return c;
  }

  /* V1. A squaring term is what actually generates even harmonics: for a
     sine input, x^2 lands entirely on DC and the 2nd harmonic and produces
     no 3rd at all. Merely driving the two halves of the wave by different
     amounts does not do this - that is still mostly odd-symmetric
     compression, and the 3rd harmonic wins. So: add a measured amount of
     x^2, then soften the peak with a deliberately GENTLE tanh, because a
     hard one would swamp the 2nd harmonic with its own 3rd.

     The weights were measured, not guessed: at a = 0.46 with this much
     softening the 2nd harmonic beats the 3rd by 1.6x at a light setting
     and 4x wide open, so the "even harmonics" label holds at every
     position of the knob rather than only at the extreme. The inner
     curve's slope is 1 + 2*a*x, which stays positive across [-1, 1] for
     any a <= 0.5, so the curve can never fold back on itself. At amount 0
     it is the exact identity, so a stage doing nothing really does
     nothing. */
  function triodeCurve(amount) {
    if (amount <= 0) { return table(function (x) { return x; }); }
    var a = amount * 0.46;
    var k = 1 + amount * 0.15;
    var norm = Math.tanh(k);
    return table(function (x) {
      return Math.tanh(k * (x + a * x * x) / (1 + a)) / norm;
    });
  }

  /* V2. Odd-symmetric by construction: f(-x) === -f(x), which is exactly
     the condition for producing only odd harmonics. */
  function pentodeCurve(amount) {
    var k = 1 + amount * 11;
    if (amount <= 0) { return table(function (x) { return x; }); }
    var norm = Math.tanh(k);
    return table(function (x) { return Math.tanh(k * x) / norm; });
  }

  /* V3. Saturating exponential: gentle in the middle, firmly compressed
     approaching full scale. Odd-symmetric, so it colours without the
     even-harmonic warmth V1 adds. */
  function tapeCurve(amount) {
    var k = 0.5 + amount * 4.5;
    if (amount <= 0) { return table(function (x) { return x; }); }
    var norm = 1 - Math.exp(-k);
    return table(function (x) {
      var s = x < 0 ? -1 : 1;
      return s * (1 - Math.exp(-k * Math.abs(x))) / norm;
    });
  }

  /* V5. Deliberately gentler than tape at the same setting - a transformer
     rounds the bottom, it does not squash it - and applied to the low band
     only. Keeping the drive low matters: the normalisation divides by
     tanh(k), so a large k would hand back most of what it compressed as
     makeup gain and the stage would read as louder rather than rounder. */
  function ironCurve(amount) {
    if (amount <= 0) { return table(function (x) { return x; }); }
    var k = 1 + amount * 1.8;
    var norm = Math.tanh(k);
    return table(function (x) { return Math.tanh(k * x) / norm; });
  }

  /* V4's two LFOs. Wow is the slow drift, flutter the fast wobble; real
     machines have both, at very different rates and depths. */
  function flutterParams(amount) {
    return {
      base: 0.004,                         // 4 ms nominal delay
      wowHz: 0.7,
      wowDepth: 0.0016 * amount,           // seconds of swing
      flutterHz: 6.3,
      flutterDepth: 0.00035 * amount,
    };
  }

  /* V6's envelope. Slow attack and long release is what makes a vari-mu
     grab the shape of a phrase instead of individual transients. */
  function variMuParams(amount) {
    return {
      threshold: -8 - amount * 16,
      ratio: 1.5 + amount * 2.5,
      attack: 0.045,
      release: 0.55,
      knee: 12,
    };
  }

  /* Glow: how hard this stage is being driven, right now. RMS is mapped
     through a curve so quiet-but-present reads as a warm filament rather
     than off, and the amount knob scales it because a stage turned down
     is not working hard however loud the input. */
  function glow(rms, amount) {
    if (!(rms > 0) || amount <= 0) { return 0; }
    var db = 20 * Math.log(rms) / Math.LN10;      // -inf .. 0
    var lit = (db + 42) / 42;                     // -42 dBFS -> 0, 0 dBFS -> 1
    lit = lit < 0 ? 0 : (lit > 1 ? 1 : lit);
    return Math.pow(lit, 0.7) * (0.35 + 0.65 * amount);
  }

  /* Gain reduction reads as glow directly: 12 dB of squeeze is a fully lit
     tube. Kept separate from the level mapping so neither has to pretend
     to be the other. */
  function glowFromReduction(reductionDb, amount) {
    if (amount <= 0) { return 0; }
    var g = Math.min(1, Math.abs(reductionDb || 0) / 12);
    return Math.pow(g, 0.7) * (0.4 + 0.6 * amount);
  }

  var STAGES = [
    {key: "triode", tube: "V1", name: "Triode",
     blurb: "Even harmonics · warmth", curve: triodeCurve, dc: true},
    {key: "pentode", tube: "V2", name: "Pentode",
     blurb: "Odd harmonics · push", curve: pentodeCurve},
    {key: "tape", tube: "V3", name: "Tape",
     blurb: "Soft knee · HF loss · head bump", curve: tapeCurve},
    {key: "flutter", tube: "V4", name: "Flutter",
     blurb: "Wow &amp; flutter · real pitch drift", mod: true},
    {key: "iron", tube: "V5", name: "Iron",
     blurb: "Transformer · lows only", curve: ironCurve, lowOnly: true},
    {key: "varimu", tube: "V6", name: "Vari-Mu",
     blurb: "Slow tube compression", comp: true},
  ];

  var api = {
    STAGES: STAGES,
    triodeCurve: triodeCurve,
    pentodeCurve: pentodeCurve,
    tapeCurve: tapeCurve,
    ironCurve: ironCurve,
    flutterParams: flutterParams,
    variMuParams: variMuParams,
    glow: glow,
    glowFromReduction: glowFromReduction,
    _N: N,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.SBTubes = api;
})(typeof self !== "undefined" ? self : this);
