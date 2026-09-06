"""The bench test the X32 adapter must pass before it may say it works.

Run this on the venue network against a real X32 or M32, on a mix bus and
channel nobody is listening to. It does the one thing the honesty doctrine
asks - moves a fader a bounded amount and READS IT BACK - then puts it
back, and prints a report to paste into the adapter's spec:

    STAGE_BENCH_ADAPTERS=1 python tools/x32_bench.py --host 192.168.1.10 \
        --channel 32 --bus 16

Every step prints PASS or FAIL. The adapter graduates from
stage_adapters.BENCH_ADAPTERS to ADAPTERS only when every step passes, and
the model and firmware this prints are written into tested_model and
tested_firmware by hand. Nothing here is automatic on purpose: a person
watched the fader move, or the adapter is still UNTESTED.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--host", required=True)
    p.add_argument("--channel", type=int, default=32, help="a channel with nothing on it")
    p.add_argument("--bus", type=int, default=16, help="a mix bus nobody is wearing")
    p.add_argument("--step", type=float, default=1.0)
    a = p.parse_args(argv)
    if os.environ.get("STAGE_BENCH_ADAPTERS", "").strip() != "1":
        print("Set STAGE_BENCH_ADAPTERS=1: this adapter is UNTESTED and refuses to run otherwise.")
        return 2

    import stage_x32 as x32
    patch = {"mixes": {"Bench": a.bus}, "sources": {"Bench": a.channel}}
    adapter = x32.X32Adapter(host=a.host, patch=patch)
    results = []

    def step(name, fn):
        try:
            value = fn()
            results.append((name, True, value))
            print("PASS  %-42s %s" % (name, value))
            return value
        except Exception as e:  # the report needs every step, not the first failure
            results.append((name, False, str(e)))
            print("FAIL  %-42s %s" % (name, e))
            return None

    health = step("desk answers /xinfo", adapter.health)
    before = step("read send level (dB)", lambda: adapter.read_send_level("Bench", "Bench"))
    up = step("apply +%.1f dB and read back" % a.step,
              lambda: adapter.apply_send_delta("Bench", "Bench", a.step))
    if up is not None:
        step("read-back confirmed the write", lambda: up["confirmed"] or (_ for _ in ()).throw(
            RuntimeError("desk holds %.2f dB, expected %.2f" % (up["after"], before + a.step))))
    down = step("apply -%.1f dB (revert) and read back" % a.step,
                lambda: adapter.apply_send_delta("Bench", "Bench", -a.step))
    if down is not None and before is not None:
        step("level is back where it started",
             lambda: abs(down["after"] - before) < 0.2 or (_ for _ in ()).throw(
                 RuntimeError("%.2f dB vs %.2f dB" % (down["after"], before))))
    m = step("mute and read back", lambda: adapter.set_mute("Bench", "Bench", True))
    if m is not None:
        step("mute confirmed", lambda: m["confirmed"] or (_ for _ in ()).throw(RuntimeError("not confirmed")))
    step("unmute and read back", lambda: adapter.set_mute("Bench", "Bench", False))

    passed = all(ok for _n, ok, _v in results)
    print()
    print("RESULT: %s" % ("ALL PASSED" if passed else "FAILED - the adapter stays UNTESTED"))
    if health and isinstance(health, dict) and health.get("ok"):
        print("model: %s   firmware: %s   desk name: %s"
              % (health.get("model"), health.get("firmware"), health.get("name")))
        if passed:
            print("Write these into stage_x32.X32Adapter.SPEC tested_model / tested_firmware,")
            print("set verified True, move the adapter into stage_adapters.ADAPTERS, and say")
            print("in the commit who ran this bench and on what date.")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
