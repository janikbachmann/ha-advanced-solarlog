"""Smoke-Test: api.py gegen einen nachgebauten EnergyOptimizer-Server.

Aufruf: python3 tests/test_api.py
"""
import asyncio, base64, importlib.util, pathlib, sys, types
from aiohttp import web, ClientSession

ROOT = str(pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "advanced_solarlog")
pkg = types.ModuleType("eo"); pkg.__path__ = [ROOT]; sys.modules["eo"] = pkg
for name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"eo.{name}", f"{ROOT}/{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[f"eo.{name}"] = mod
    spec.loader.exec_module(mod)
api = sys.modules["eo.api"]

PASSWORD = "geheim"
STATUS = {"prod": 4210.5, "cons": 1180.0, "grid": -3030.5, "batt": -900.0, "soc": 78.0,
          "avg_s": 30, "sl_age": 12, "sl_next": 48, "failsafe": False, "battblk": False,
          "al_n": 1, "al_sev": 1, "led": "connected",
          "energy": {"dp": 18.4, "dc": 7.1, "dgi": 1.2, "dgo": 11.9,
                     "tp": 41230.0, "tc": 20110.0, "tgi": 8800.0, "tgo": 24000.0},
          "cost": {"buy": 32.4, "sell": 95.2, "saved": 141.0, "base": 50.0},
          "shelly": [{"idx": 0, "name": "Boiler", "id": "shellyplus1pm-aabbcc",
                      "pw": 2000, "pri": 1, "auto": True, "on": True, "reach": True,
                      "apower": 1970, "volt": 231, "amp": 8.52, "temp": 41.3,
                      "e_day": 3.2, "e_tot": 812.4, "pv_day": 2.9, "rt_on": 95, "ov": 0, "lock": 0}],
          "ext": [{"idx": 0, "name": "Waermepumpe", "pw": 1500, "pri": 2, "auto": False, "on": False,
                   "rt_on": 0, "ov": 0, "lock": 0}],
          "mqtt": {"conn": True}, "cfg": {"sl_ip": "192.168.1.50"}}
SYSINFO = {"heap_free": 210000, "uptime": 98765, "eth": True, "temp": 46.2, "cpu0": 12,
           "nvs_err": False, "boots": 14, "crashes": 1, "rst_txt": "Software-Neustart",
           "rst_bad": False, "coredump": False, "build": "2026-09-01 10:22", "notify": {"cfg": True}}
ALARMS = {"al": [{"id": 2, "name": "Keine Produktion", "sev": 1, "since": 1758000000,
                  "mins": 42, "acked": False, "detail": ""}], "n": 1, "max": 1}
calls = []

def authed(request):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return False
    user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
    return user == "admin" and pw == PASSWORD

def guard(handler):
    async def wrapped(request):
        calls.append(f"{request.method} {request.path}?{request.query_string}".rstrip("?"))
        if not authed(request):
            return web.json_response({"ok": False, "auth": False}, status=401)
        return await handler(request)
    return wrapped

async def main():
    app = web.Application()
    app.router.add_get("/api/status", guard(lambda r: _json(STATUS)))
    app.router.add_get("/api/sysinfo", guard(lambda r: _json(SYSINFO)))
    app.router.add_get("/api/alarms", guard(lambda r: _json(ALARMS)))
    app.router.add_post("/api/refresh", guard(lambda r: _json({"ok": True})))
    app.router.add_post("/api/alarms/ack", guard(lambda r: _json({"ok": True})))
    app.router.add_post("/api/shelly/{i}/{cmd}", guard(lambda r: _json({"ok": True})))
    app.router.add_post("/api/ext/{i}/{cmd}", guard(lambda r: _json({"ok": True})))
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8123); await site.start()

    async with ClientSession() as session:
        client = api.AdvancedSolarLogClient(session, "127.0.0.1", 8123, PASSWORD)
        status = await client.async_get_status()
        sysinfo = await client.async_get_sysinfo()
        alarms = await client.async_get_alarms()
        assert status["batt"] == -900.0 and status["soc"] == 78.0, "Batteriewerte fehlen"
        assert sysinfo["rst_txt"] == "Software-Neustart"
        assert alarms["n"] == 1
        # Der ausgelieferte Client muss rein lesend sein - keine Schreibmethoden.
        writers = [n for n in dir(client) if n.startswith("async_") and n not in
                   ("async_get_status", "async_get_sysinfo", "async_get_alarms")]
        assert not writers, f"Unerwartete schreibende Methoden: {writers}"
        assert all(c.startswith("GET ") for c in calls), calls
        print("OK: nur lesende Routen, Aufrufe:", calls)

        bad = api.AdvancedSolarLogClient(session, "127.0.0.1", 8123, "falsch")
        try:
            await bad.async_get_status()
        except api.AdvancedSolarLogAuthError as err:
            print("OK: 401 ->", type(err).__name__)
        else:
            raise AssertionError("401 wurde nicht als AuthError erkannt")

        offline = api.AdvancedSolarLogClient(session, "127.0.0.1", 8199, None)
        try:
            await offline.async_get_status()
        except api.AdvancedSolarLogAuthError:
            raise AssertionError("Verbindungsfehler falsch klassifiziert")
        except api.AdvancedSolarLogError as err:
            print("OK: offline ->", type(err).__name__)

        openclient = api.AdvancedSolarLogClient(session, "127.0.0.1", 8123, None)
        try:
            await openclient.async_get_status()
        except api.AdvancedSolarLogAuthError:
            print("OK: ohne Passwort gegen geschuetztes Geraet -> AuthError")
    await runner.cleanup()

def _json(payload):
    async def _inner():
        return web.json_response(payload)
    return _inner()

asyncio.run(main())
