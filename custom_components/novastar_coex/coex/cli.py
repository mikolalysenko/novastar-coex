"""``coex`` command-line tool: poke a controller from a terminal.

Examples::

    coex --host 192.0.2.10 status
    coex --host 192.0.2.10 brightness 40
    coex --host 192.0.2.10 blackout          # or normal / freeze
    coex --host 192.0.2.10 mode send-only    # or all-in-one
    coex --host 192.0.2.10 preset 1
    coex --host 192.0.2.10 input HDMI1
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import sys
from typing import Any

from .client import CoexClient
from .const import DEFAULT_PORT, DisplayMode, WorkingMode
from .errors import CoexError


def _jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: _jsonable(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if f.name != "raw"
        }
    if isinstance(obj, dict):
        return {
            (k.name if isinstance(k, DisplayMode | WorkingMode) else str(k)): _jsonable(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list | tuple):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, DisplayMode | WorkingMode):
        return obj.name
    return obj


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coex", description="NovaStar COEX controller CLI")
    p.add_argument("--host", required=True, help="controller IP / hostname")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--timeout", type=float, default=5.0)
    p.add_argument(
        "--brightness-scale",
        choices=["auto", "ratio", "percent"],
        default="auto",
        help="unit for brightness writes (auto learns from displayparams)",
    )
    p.add_argument("--raw", action="store_true", help="print raw controller JSON where available")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in (
        "status",
        "screens",
        "sources",
        "presets",
        "monitor",
        "cabinets",
        "state",
        "params",
    ):
        sub.add_parser(name)
    for name in ("normal", "blackout", "freeze"):
        s = sub.add_parser(name)
        s.add_argument("--screen", action="append", default=None, help="screen id (repeatable)")
    b = sub.add_parser("brightness")
    b.add_argument("percent", type=float)
    ct = sub.add_parser("colortemp")
    ct.add_argument("kelvin", type=int)
    g = sub.add_parser("gamma")
    g.add_argument("value", type=float)
    m = sub.add_parser("mode")
    m.add_argument("mode", choices=["send-only", "all-in-one"])
    m.add_argument("--screen", default=None)
    pr = sub.add_parser("preset")
    pr.add_argument("number", type=int)
    pr.add_argument("--screen", default=None)
    i = sub.add_parser("input")
    i.add_argument("source", help="input name or groupId")
    i.add_argument("--screen", default=None)
    mp = sub.add_parser("mapping")
    mp.add_argument("state", choices=["on", "off"])
    ident = sub.add_parser("identify")
    ident.add_argument("state", choices=["on", "off"])
    return p


async def run(args: argparse.Namespace) -> int:
    async with CoexClient(
        args.host, args.port, timeout=args.timeout, brightness_scale=args.brightness_scale
    ) as c:
        out: Any
        cmd = args.cmd
        if cmd == "status":
            out = await c.get_status()
        elif cmd == "screens":
            out = await c.get_screens()
        elif cmd == "sources":
            out = await c.get_input_sources()
        elif cmd == "presets":
            out = await c.get_presets()
        elif cmd == "monitor":
            out = await c.get_monitor_info()
        elif cmd == "cabinets":
            out = await c.get_cabinets()
        elif cmd == "state":
            out = await c.get_display_state()
        elif cmd == "params":
            out = await c.get_display_params()
        elif cmd in ("normal", "blackout", "freeze"):
            await getattr(c, cmd)(args.screen)
            out = {"ok": True}
        elif cmd == "brightness":
            await c.set_brightness(args.percent)
            out = {"ok": True, "brightness": args.percent, "scale": c.brightness_scale}
        elif cmd == "colortemp":
            await c.set_color_temperature(args.kelvin)
            out = {"ok": True}
        elif cmd == "gamma":
            await c.set_gamma(args.value)
            out = {"ok": True}
        elif cmd == "mode":
            await c.set_working_mode(
                WorkingMode.SEND_ONLY if args.mode == "send-only" else WorkingMode.ALL_IN_ONE,
                args.screen,
            )
            out = {"ok": True}
        elif cmd == "preset":
            await c.apply_preset(args.number, args.screen)
            out = {"ok": True}
        elif cmd == "input":
            out = await c.select_input(args.source, args.screen)
        elif cmd == "mapping":
            await c.set_cabinet_mapping(args.state == "on")
            out = {"ok": True}
        elif cmd == "identify":
            await c.identify_controller(args.state == "on")
            out = {"ok": True}
        else:  # pragma: no cover
            raise SystemExit(f"unknown command {cmd}")

        if args.raw and dataclasses.is_dataclass(out) and hasattr(out, "raw"):
            print(json.dumps(out.raw, indent=2))
        else:
            print(json.dumps(_jsonable(out), indent=2, default=str))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(run(args))
    except (CoexError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
