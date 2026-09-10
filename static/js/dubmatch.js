/* Street Banker · Dub level match — bring a dub back at the level it went out at.
 *
 * A dubbing vendor renders at whatever level it likes. In practice that has
 * been far hotter than the material sent in, so the dub comes back shouting
 * next to the original and every downstream decision — a rough cut, an
 * approval, a comparison against the source — is made against a level nobody
 * chose.
 *
 * WHAT THIS DOES
 *
 * Measures the integrated loudness of the source and of the dub, both to
 * ITU-R BS.1770-4 using the meter Street Banker already ships (SBLoudness,
 * the same one behind the Mix and Master rooms — not a second opinion that
 * could disagree with the first), and applies the difference as a single
 * static gain. The result is written as a WAV through SBAudioConv.
 *
 * WHY A STATIC GAIN, AND NOT A LIMITER
 *
 * Matching loudness is an offset, not a treatment. Compressing or limiting
 * to hit a number changes the performance, and a dub that has been squashed
 * to match is no longer the thing the vendor delivered. The one exception is
 * safety: if the offset would push true peak above the ceiling, the gain is
 * reduced so it does not clip, and the page says so rather than quietly
 * delivering something other than a match.
 *
 * WHAT IT WILL NOT DO
 *
 * Claim a match it did not measure. If either file is silent, or too short
 * for the standard's gating to return a figure, integrated loudness is null
 * and the answer is that it could not be measured — not 0 LUFS, which is a
 * different and very loud claim.
 */
(function (root) {
  "use strict";

  var CEILING_DBTP = -1.0;   // where a delivery should sit, not where it can go

  function decode(ctx, url) {
    return fetch(url, {credentials: "same-origin"})
      .then(function (r) {
        if (!r.ok) { throw new Error("could not read " + url + " (" + r.status + ")"); }
        return r.arrayBuffer();
      })
      .then(function (ab) { return ctx.decodeAudioData(ab); });
  }

  function channelsOf(buf) {
    var out = [];
    for (var i = 0; i < buf.numberOfChannels; i++) {
      out.push(buf.getChannelData(i));
    }
    return out;
  }

  function measure(buf) {
    return root.SBLoudness.analyse(channelsOf(buf), buf.sampleRate);
  }

  /* The offset, and whether we had to pull it back to avoid clipping. */
  function planGain(source, dub) {
    if (source.integrated === null || dub.integrated === null) {
      return {ok: false,
              why: "One of the two files is too quiet or too short to measure "
                 + "to the standard, so there is no level to match to."};
    }
    var db = source.integrated - dub.integrated;
    var held = false;
    if (dub.truePeak !== null && dub.truePeak + db > CEILING_DBTP) {
      db = CEILING_DBTP - dub.truePeak;
      held = true;
    }
    return {ok: true, db: db, held: held,
            sourceLufs: source.integrated, dubLufs: dub.integrated,
            dubPeak: dub.truePeak};
  }

  function applyGain(buf, db) {
    var Offline = root.OfflineAudioContext || root.webkitOfflineAudioContext;
    var oc = new Offline(buf.numberOfChannels, buf.length, buf.sampleRate);
    var src = oc.createBufferSource();
    var g = oc.createGain();
    src.buffer = buf;
    g.gain.value = Math.pow(10, db / 20);
    src.connect(g);
    g.connect(oc.destination);
    src.start();
    return oc.startRendering();
  }

  /* Measure both, match, and hand back a WAV plus what was actually done. */
  function match(sourceUrl, dubUrl) {
    var Ctx = root.AudioContext || root.webkitAudioContext;
    var ctx = new Ctx();
    var source = null, dub = null, dubBuf = null;
    return decode(ctx, sourceUrl)
      .then(function (buf) { source = measure(buf); return decode(ctx, dubUrl); })
      .then(function (buf) { dubBuf = buf; dub = measure(buf); })
      .then(function () {
        var plan = planGain(source, dub);
        if (!plan.ok) { return plan; }
        return applyGain(dubBuf, plan.db).then(function (rendered) {
          var after = measure(rendered);
          var wav = root.SBAudioConv.encodeWav(
            channelsOf(rendered), rendered.sampleRate, 24, {dither: false});
          return {ok: true, wav: wav, plan: plan, after: after};
        });
      })
      .then(function (result) {
        /* Chrome caps live AudioContexts per tab; this one has done its job. */
        try { ctx.close(); } catch (e) { /* already gone */ }
        return result;
      }, function (err) {
        try { ctx.close(); } catch (e) { /* already gone */ }
        throw err;
      });
  }

  function say(plan, after) {
    var lines = [
      "Source measured " + plan.sourceLufs.toFixed(1) + " LUFS, "
        + "the dub came back at " + plan.dubLufs.toFixed(1) + " LUFS.",
      (plan.db >= 0 ? "Lifted " : "Pulled back ")
        + Math.abs(plan.db).toFixed(1) + " dB."
    ];
    if (plan.held) {
      lines.push("Held at " + CEILING_DBTP.toFixed(1) + " dBTP to avoid clipping, "
               + "so it lands a little under the source rather than distorting.");
    }
    if (after && after.integrated !== null) {
      lines.push("The file now measures " + after.integrated.toFixed(1) + " LUFS.");
    }
    return lines.join(" ");
  }

  root.SBDubMatch = {
    match: match,
    say: say,
    planGain: planGain,
    CEILING_DBTP: CEILING_DBTP
  };
})(typeof self !== "undefined" ? self : this);
