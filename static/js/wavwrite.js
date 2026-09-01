/* Street Banker · WAV-1 — write a WAV, correctly.
 *
 * The Rack has an encoder inside its own closure. This is a second, smaller
 * one that stands on its own so the Master Station can render without pulling
 * in 4,700 lines of DSP it does not use, and so the encoder can be checked in
 * Node against the format's own rules rather than by listening to the result.
 *
 * Two things this gets right that a naive encoder does not:
 *
 *   Clipping is CHECKED, not assumed away. Float samples outside ±1 do not
 *   wrap around when they are converted - they are clamped, and the number of
 *   samples that needed clamping is returned. A master that clipped 400 times
 *   during export should say so rather than arrive quietly broken.
 *
 *   Dither is applied ONLY when the bit depth is actually being reduced, and
 *   never to 32-bit float. Dithering a float buffer adds noise for nothing;
 *   not dithering a 24-to-16 reduction leaves correlated truncation noise on
 *   the quietest part of the record, which is where it is audible.
 *
 * Interleaving is the other half: WAV frames are L,R,L,R, and getting that
 * wrong produces a file that plays at the right length and sounds like static.
 */
(function (root) {
  "use strict";

  /* TPDF dither at one LSB, the standard choice for a final reduction: two
     independent uniform values summed, so the noise is triangular and its
     level does not depend on the signal. */
  function tpdf(scale) {
    return ((Math.random() + Math.random()) - 1) / scale;
  }

  /**
   * channels : array of Float32Array, one per channel, all the same length
   * rate     : sample rate in Hz
   * depth    : 16 | 24 | 32  (32 writes IEEE float and is never dithered)
   * dither   : apply TPDF when reducing depth. Default true for 16 and 24.
   *
   * Returns { buffer: ArrayBuffer, clipped: n, frames: n, bytes: n }
   */
  function encode(channels, rate, depth, dither) {
    depth = depth || 16;
    if (depth !== 16 && depth !== 24 && depth !== 32) {
      throw new Error("unsupported bit depth: " + depth);
    }
    if (!channels || !channels.length) { throw new Error("no channels"); }
    if (dither === undefined) { dither = depth !== 32; }
    if (depth === 32) { dither = false; }   // nothing is being reduced

    var count = channels.length;
    var frames = channels[0].length;
    var bytesPerSample = depth / 8;
    var dataBytes = frames * count * bytesPerSample;
    var isFloat = depth === 32;
    var fmtChunk = 16;
    var buffer = new ArrayBuffer(44 + dataBytes);
    var view = new DataView(buffer);

    function str(offset, text) {
      for (var i = 0; i < text.length; i++) {
        view.setUint8(offset + i, text.charCodeAt(i));
      }
    }

    str(0, "RIFF");
    view.setUint32(4, 36 + dataBytes, true);
    str(8, "WAVE");
    str(12, "fmt ");
    view.setUint32(16, fmtChunk, true);
    view.setUint16(20, isFloat ? 3 : 1, true);      // 3 = IEEE float, 1 = PCM
    view.setUint16(22, count, true);
    view.setUint32(24, rate, true);
    view.setUint32(28, rate * count * bytesPerSample, true);  // byte rate
    view.setUint16(32, count * bytesPerSample, true);         // block align
    view.setUint16(34, depth, true);
    str(36, "data");
    view.setUint32(40, dataBytes, true);

    var peak16 = 32767, peak24 = 8388607;
    var clipped = 0;
    var offset = 44;

    /* Interleaved: one frame at a time across every channel. */
    for (var f = 0; f < frames; f++) {
      for (var c = 0; c < count; c++) {
        var sample = channels[c][f];
        if (isFloat) {
          view.setFloat32(offset, sample, true);
          offset += 4;
          continue;
        }
        var scale = depth === 16 ? peak16 : peak24;
        if (dither) { sample += tpdf(scale); }
        if (sample > 1) { sample = 1; clipped++; }
        else if (sample < -1) { sample = -1; clipped++; }
        var value = Math.round(sample * scale);
        if (value > scale) { value = scale; }
        if (value < -scale - 1) { value = -scale - 1; }
        if (depth === 16) {
          view.setInt16(offset, value, true);
          offset += 2;
        } else {
          view.setUint8(offset, value & 0xFF);
          view.setUint8(offset + 1, (value >> 8) & 0xFF);
          view.setUint8(offset + 2, (value >> 16) & 0xFF);
          offset += 3;
        }
      }
    }

    return { buffer: buffer, clipped: clipped, frames: frames,
             bytes: 44 + dataBytes };
  }

  /**
   * Apply one gain in dB to every channel, returning new buffers.
   *
   * Separate from encode() because the caller needs to know the peak AFTER
   * the gain and BEFORE the write - that is the number that decides whether a
   * master is safe, and finding it out from the encoder's clip count is too
   * late to do anything about.
   */
  function applyGain(channels, db) {
    var factor = Math.pow(10, db / 20);
    var out = [];
    var peak = 0;
    for (var c = 0; c < channels.length; c++) {
      var src = channels[c];
      var dst = new Float32Array(src.length);
      for (var i = 0; i < src.length; i++) {
        var v = src[i] * factor;
        dst[i] = v;
        var a = v < 0 ? -v : v;
        if (a > peak) { peak = a; }
      }
      out.push(dst);
    }
    return { channels: out, peak: peak,
             peakDb: peak > 0 ? 20 * Math.log(peak) / Math.LN10 : -Infinity };
  }

  var api = { encode: encode, applyGain: applyGain };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.SBWav = api;
})(typeof self !== "undefined" ? self : this);
