import json
from concurrent.futures import ThreadPoolExecutor

from novastar_coex.cli import build_parser, main, run


def run_main(args):
    """Keep the CLI's asyncio.run from clearing the HA harness's main-thread loop."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(main, args).result()


async def test_cli_status_and_writes(server, state, capsys):
    base = ["--host", server.host, "--port", str(server.port)]

    assert await run(build_parser().parse_args([*base, "status"])) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["screens"][0]["screen_id"] == "screen-1"
    assert out["screens"][0]["working_mode"] == "SEND_ONLY"
    assert out["outputs"]["screen-1"]["display_mode"] == "NORMAL"
    assert "raw" not in out["screens"][0]

    assert await run(build_parser().parse_args([*base, "brightness", "55"])) == 0
    assert state.brightness_ratio == 0.55

    assert await run(build_parser().parse_args([*base, "blackout"])) == 0
    assert state.display_mode == 1

    assert await run(build_parser().parse_args([*base, "mode", "all-in-one"])) == 0
    assert state.screens[0]["workingMode"] == 1


def test_cli_main_reports_errors(capsys):
    assert run_main(["--host", "127.0.0.1", "--port", "1", "--timeout", "0.5", "screens"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_main_reports_validation_errors(capsys):
    # client-side ValueError must be a clean exit 2, not a traceback
    assert run_main(["--host", "127.0.0.1", "--port", "1", "brightness", "150"]) == 2
    assert "error:" in capsys.readouterr().err
