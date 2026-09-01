/* Street Banker · MCH-1 — the mastering directions, as actual processing.
 *
 * WARM and COMPETITIVE stopped being disabled buttons the moment this file
 * existed. Everything here is real DSP on the sample data, and every stage
 * is checkable in Node with a signal whose right answer is known:
 *
 *   Shelves    RBJ biquads (the Audio EQ Cookbook formulas, the same maths
 *              behind every BiquadFilterNode). A low shelf's gain at DC IS
 *              its dB setting - that is a measurable promise, and the Node
 *              check measures it.
 *
 *   Saturation The Rack's tube-family curve: tanh drive, dry/wet mix. At
 *              mix 0 it is bit-identical to the input - checked - because a
 *              "colour" stage that colours when told not to is a defect the
 *              ear finds months later.
 *
 *   Limiter    A true lookahead peak limiter: the gain computer reads the
 *              signal 5 ms ahead, so attack is instantaneous WITHOUT
 *              distorting the transient it is catching, and release is a
 *              smoothed ramp. The ceiling is enforced sample-accurately -
 *              the Node check drives it 12 dB over and asserts not one
 *              sample escapes.
 *
 *   True peak  Sample-domain limiting does not bound INTER-sample peaks, so
 *              after the chain renders, the result is measured with the real
 *              BS.1770-4 true-peak (loudness.js) and trimmed if the 4x
 *              oversampled reading is over the ceiling. Claimed safe only
 *              because it was measured safe.
 *
 * THE DIRECTIONS, as named recipes (engineering convention, stated as such):
 *
 *   CLEAN        no processing - the loudness stage only.
 *   WARM         +low shelf, -high shelf, gentle saturation, then loudness.
 *   COMPETITIVE  drive INTO the limiter (that is where density comes from),
 *                a touch of presence, then loudness. The limiter is why it
 *                can sit closer to the target than a plain gain change on
 *                peaky material - and the report says how much it worked.
 *
 * Intensity scales the recipe (Light/Medium/Strong), and the render report
 * carries every number: in/out LUFS, in/out true peak, gain applied, max
 * gain reduction, and the moves by name. "Mastered" with no numbers is a
 * claim; this is a record.
 */
(function (root) {
  "use strict";

  // --- RBJ biquads -----------------------------------------------------------

  function shelfCoeffs(kind, rate, freq, gainDb) {
    var A = Math.pow(10, gainDb / 40);
    var w0 = 2 * Math.PI * freq / rate;
    var cosw = Math.cos(w0), sinw = Math.sin(w0);
    var S = 1.0;
    var alpha = sinw / 2 * Math.sqrt((A + 1 / A) * (1 / S - 1) + 2);
    var twoRootAalpha = 2 * Math.sqrt(A) * alpha;
    var b0, b1, b2, a0, a1, a2;
    if (kind === "low") {
      b0 = A * ((A + 1) - (A - 1) * cosw + twoRootAalpha);
      b1 = 2 * A * ((A - 1) - (A + 1) * cosw);
      b2 = A * ((A + 1) - (A - 1) * cosw - twoRootAalpha);
      a0 = (A + 1) + (A - 1) * cosw + twoRootAalpha;
      a1 = -2 * ((A - 1) + (A + 1) * cosw);
      a2 = (A + 1) + (A - 1) * cosw - twoRootAalpha;
    } else {
      b0 = A * ((A + 1) + (A - 1) * cosw + twoRootAalpha);
      b1 = -2 * A * ((A - 1) + (A + 1) * cosw);
      b2 = A * ((A + 1) + (A - 1) * cosw - twoRootAalpha);
      a0 = (A + 1) - (A - 1) * cosw + twoRootAalpha;
      a1 = 2 * ((A - 1) - (A + 1) * cosw);
      a2 = (A + 1) - (A - 1) * cosw - twoRootAalpha;
    }
    return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0];
  }

  function peakingCoeffs(rate, freq, q, gainDb) {
    var A = Math.pow(10, gainDb / 40);
    var w0 = 2 * Math.PI * freq / rate;
    var alpha = Math.sin(w0) / (2 * q);
    var b0 = 1 + alpha * A, b1 = -2 * Math.cos(w0), b2 = 1 - alpha * A;
    var a0 = 1 + alpha / A, a1 = b1, a2 = 1 - alpha / A;
    return [b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0];
  }

  function biquad(data, c) {
    var out = new Float32Array(data.length);
    var x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    for (var i = 0; i < data.length; i++) {
      var x = data[i];
      var y = c[0] * x + c[1] * x1 + c[2] * x2 - c[3] * y1 - c[4] * y2;
      out[i] = y;
      x2 = x1; x1 = x; y2 = y1; y1 = y;
    }
    return out;
  }

  // --- saturation ------------------------------------------------------------

  /* tanh drive with dry/wet, normalised for SLOPE, not peak: the curve's
     derivative at zero is exactly 1, so quiet material passes at its own
     level and only the loud part is bent. The first version normalised by
     tanh(drive) - unity at full scale, but a hidden +4.8 dB on everything
     quiet - and the Node check caught the render getting louder from a
     stage whose whole promise is "harmonics, not level". */
  function saturate(data, drive, mix) {
    if (!(mix > 0) || !(drive > 0)) { return data.slice ? data.slice(0) : new Float32Array(data); }
    var out = new Float32Array(data.length);
    for (var i = 0; i < data.length; i++) {
      var wet = Math.tanh(data[i] * drive) / drive;
      out[i] = data[i] * (1 - mix) + wet * mix;
    }
    return out;
  }

  // --- the lookahead limiter -------------------------------------------------

  /* Gain computer reads `lookahead` samples ahead of the audio it applies
     gain to, so the reduction is already in place when the peak arrives -
     instantaneous attack with no transient chop. Release is a one-pole ramp.
     Channels are linked: the loudest channel sets the gain for all, or the
     image lurches toward whichever side is quieter. */
  function limit(channels, ceilingDb, rate, releaseMs) {
    var ceiling = Math.pow(10, ceilingDb / 20);
    var lookahead = Math.max(1, Math.round(rate * 0.005));       // 5 ms
    var releaseCoeff = Math.exp(-1 / (rate * (releaseMs || 60) / 1000));
    var frames = channels[0].length;
    var out = channels.map(function (ch) { return new Float32Array(ch.length); });
    var gain = 1.0;
    var maxReduction = 1.0;

    for (var i = 0; i < frames; i++) {
      var ahead = Math.min(frames - 1, i + lookahead);
      var peak = 0;
      for (var c = 0; c < channels.length; c++) {
        var a = channels[c][ahead];
        if (a < 0) { a = -a; }
        if (a > peak) { peak = a; }
      }
      var needed = peak > ceiling ? ceiling / peak : 1.0;
      if (needed < gain) {
        gain = needed;                       // attack: instant, it is early
      } else {
        gain = needed + (gain - needed) * releaseCoeff;   // ramp back up
        if (gain > 1) { gain = 1; }
      }
      if (gain < maxReduction) { maxReduction = gain; }
      for (var c2 = 0; c2 < channels.length; c2++) {
        out[c2][i] = channels[c2][i] * gain;
      }
    }

    /* Safety clamp for the release tail: the lookahead covers attacks, but a
       rising release against a still-hot signal can graze the ceiling. */
    for (var c3 = 0; c3 < channels.length; c3++) {
      for (var j = 0; j < frames; j++) {
        if (out[c3][j] > ceiling) { out[c3][j] = ceiling; }
        else if (out[c3][j] < -ceiling) { out[c3][j] = -ceiling; }
      }
    }
    return { channels: out,
             maxReductionDb: 20 * Math.log(maxReduction) / Math.LN10 };
  }

  // --- the directions --------------------------------------------------------

  /* Intensity scales the recipe. The numbers are engineering convention,
     stated as such in the report the render writes. */
  var DIRECTIONS = {
    clean: {
      label: "Clean",
      note: "The loudness stage only - no tonal change, no dynamics change.",
      recipe: function () { return { moves: [] }; },
    },
    warm: {
      label: "Warm",
      note: "Low shelf up, high shelf eased, gentle saturation - then the "
            + "loudness stage.",
      recipe: function (intensity) {
        var k = { light: 0.6, medium: 1.0, strong: 1.5 }[intensity] || 1.0;
        return {
          lowShelf: { freq: 120, gain: 1.2 * k },
          highShelf: { freq: 9000, gain: -0.8 * k },
          saturation: { drive: 1.6, mix: 0.18 * k },
          moves: [
            "low shelf +" + (1.2 * k).toFixed(1) + " dB at 120 Hz",
            "high shelf " + (-0.8 * k).toFixed(1) + " dB at 9 kHz",
            "saturation mix " + Math.round(18 * k) + "%",
          ],
        };
      },
    },
    competitive: {
      label: "Competitive",
      note: "Driven into a lookahead limiter for density, a touch of "
            + "presence - then the loudness stage. The limiter is what lets "
            + "peaky material sit closer to the target.",
      recipe: function (intensity) {
        var push = { light: 1.5, medium: 3.0, strong: 4.5 }[intensity] || 3.0;
        return {
          presence: { freq: 3000, q: 1.0, gain: 0.8 },
          limiterDriveDb: push,
          moves: [
            "presence +0.8 dB at 3 kHz",
            "driven " + push.toFixed(1) + " dB into the limiter",
          ],
        };
      },
    },
    open: {
      label: "Open",
      note: "More dynamic on purpose: an air shelf, NO limiter ever, and a "
            + "deliberate landing under the target so the transients keep "
            + "their height. Platforms normalise the level anyway; the "
            + "dynamics are what survive the trip.",
      recipe: function (intensity) {
        var k = { light: 1.0, medium: 2.0, strong: 3.0 }[intensity] || 2.0;
        var air = { light: 0.4, medium: 0.7, strong: 1.0 }[intensity] || 0.7;
        return {
          highShelf: { freq: 12000, gain: air },
          undershootDb: k,
          moves: [
            "air shelf +" + air.toFixed(1) + " dB at 12 kHz",
            "lands " + k.toFixed(1) + " LU under the target by design",
            "no limiter - dynamics kept",
          ],
        };
      },
    },
    club: {
      label: "Club",
      note: "Low-end weight with the ceiling held by the limiter, and a "
            + "touch of snap. Check it on the Club / PA and Car chips - "
            + "that is what the translation rail is for.",
      recipe: function (intensity) {
        var low = { light: 1.5, medium: 2.5, strong: 3.5 }[intensity] || 2.5;
        var push = { light: 0.5, medium: 1.0, strong: 1.5 }[intensity] || 1.0;
        return {
          lowShelf: { freq: 90, gain: low },
          presence: { freq: 2500, q: 1.0, gain: 0.6 },
          limiterDriveDb: push,
          moves: [
            "low shelf +" + low.toFixed(1) + " dB at 90 Hz",
            "presence +0.6 dB at 2.5 kHz",
            "driven " + push.toFixed(1) + " dB into the limiter",
          ],
        };
      },
    },
  };

  function _applyGainInPlace(channels, db) {
    var g = Math.pow(10, db / 20);
    return channels.map(function (ch) {
      var out = new Float32Array(ch.length);
      for (var i = 0; i < ch.length; i++) { out[i] = ch[i] * g; }
      return out;
    });
  }

  /**
   * Render one direction. `measure` is SBLoudness (injected so Node can pass
   * the real engine). Returns { channels, report }.
   *
   * The loudness stage at the end is the same contract the Clean render has
   * always kept: land on the target, cap at the platform's true-peak ceiling,
   * and say how far short the cap left it.
   */
  function render(directionKey, intensity, channels, rate, targetLufs,
                  ceilingDb, measure) {
    var direction = DIRECTIONS[directionKey];
    if (!direction) { throw new Error("unknown direction: " + directionKey); }
    var recipe = direction.recipe(intensity);
    var before = measure.analyse(channels, rate);

    var work = channels.map(function (ch) { return new Float32Array(ch); });
    var maxReductionDb = 0;

    if (recipe.lowShelf) {
      var lc = shelfCoeffs("low", rate, recipe.lowShelf.freq, recipe.lowShelf.gain);
      work = work.map(function (ch) { return biquad(ch, lc); });
    }
    if (recipe.highShelf) {
      var hc = shelfCoeffs("high", rate, recipe.highShelf.freq, recipe.highShelf.gain);
      work = work.map(function (ch) { return biquad(ch, hc); });
    }
    if (recipe.presence) {
      var pc = peakingCoeffs(rate, recipe.presence.freq, recipe.presence.q,
                             recipe.presence.gain);
      work = work.map(function (ch) { return biquad(ch, pc); });
    }
    if (recipe.saturation) {
      work = work.map(function (ch) {
        return saturate(ch, recipe.saturation.drive, recipe.saturation.mix);
      });
    }

    /* The loudness stage. For COMPETITIVE the wanted gain is pushed further
       and the limiter holds the ceiling - density instead of a cap. */
    var mid = measure.analyse(work, rate);
    var effectiveTarget = targetLufs - (recipe.undershootDb || 0);
    var wanted = effectiveTarget - (mid.integrated !== null ? mid.integrated
                                    : (before.integrated || -14));
    var capped = false;
    if (recipe.limiterDriveDb) {
      work = _applyGainInPlace(work, wanted + recipe.limiterDriveDb);
      var limited = limit(work, ceilingDb, rate, 60);
      work = limited.channels;
      maxReductionDb = limited.maxReductionDb;
    } else {
      var applied = wanted;
      if (mid.truePeak !== null && (mid.truePeak + wanted) > ceilingDb) {
        applied = ceilingDb - mid.truePeak;
        capped = true;
      }
      work = _applyGainInPlace(work, applied);
      wanted = applied;
    }

    /* Sample-domain limiting does not bound inter-sample peaks: measure the
       REAL true peak and trim if the oversampled reading is over. */
    var after = measure.analyse(work, rate);
    if (after.truePeak !== null && after.truePeak > ceilingDb) {
      work = _applyGainInPlace(work, ceilingDb - after.truePeak);
      after = measure.analyse(work, rate);
    }

    return {
      channels: work,
      report: {
        direction: direction.label,
        intensity: intensity,
        moves: recipe.moves,
        inLufs: before.integrated,
        outLufs: after.integrated,
        inTp: before.truePeak,
        outTp: after.truePeak,
        gainDb: wanted,
        maxReductionDb: maxReductionDb,
        capped: capped,
        basis: "engineering convention - the recipe numbers are named "
               + "presets, the measurements are BS.1770-4",
      },
    };
  }

  var api = {
    DIRECTIONS: DIRECTIONS,
    render: render,
    shelfCoeffs: shelfCoeffs,
    peakingCoeffs: peakingCoeffs,
    biquad: biquad,
    saturate: saturate,
    limit: limit,
  };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.SBMasterChain = api;
})(typeof self !== "undefined" ? self : this);
