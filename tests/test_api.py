"""Smoke test: api.py against a stand-in Solar-Log server.

Run with: python3 tests/test_api.py
"""
import asyncio, importlib.util, json, pathlib, sys, types
import bcrypt
from aiohttp import CookieJar, web, ClientSession
from yarl import URL

ROOT = str(pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "advanced_solarlog")
pkg = types.ModuleType("asl"); pkg.__path__ = [ROOT]; sys.modules["asl"] = pkg
for name in ("const", "api"):
    spec = importlib.util.spec_from_file_location(f"asl.{name}", f"{ROOT}/{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[f"asl.{name}"] = mod
    spec.loader.exec_module(mod)
api = sys.modules["asl.api"]

PASSWORD = "geheim"
SESSION_COOKIE = "abc123"

# The 801/170 block as a Solar-Log with battery and two inverters reports it.
BASIC = {
    "100": "21.09.26 14:32:05",
    "101": 4210, "102": 4290, "103": 231, "104": 612,
    "105": 18400, "106": 21100, "107": 412000, "108": 4120000, "109": 41230000,
    "110": 1180, "111": 7100, "112": 9200, "113": 210000, "114": 2010000,
    "115": 20110000, "116": 9840,
}
BATTERY = [51.2, 78.0, 0.0, 900.0]          # voltage, level, charge W, discharge W
ENERGY = [[1735689600, 3900000, 0, 1750000]]  # year rows: [ts, production, ?, self-consumption]
INVERTER_POWER = {"0": "2600", "1": "1610"}
INVERTER_ENERGY = [[1735689600, [2400000, 1720000]]]
DEVICE_LIST = {"0": "Ok", "1": "Ok", "2": "Err"}
DEVICE_NAMES = {"0": "Fronius Dach Sued", "1": "Fronius Dach Ost"}

requests_seen = []


async def handle_getjp(request):
    body = await request.text()
    # Older firmware sends the session token prepended to the body.
    token, _, payload = body.rpartition("; ") if "; " in body else ("", "", body)
    requests_seen.append(payload)
    query = json.loads(payload)

    logged_in = request.cookies.get("SolarLog") == SESSION_COOKIE or token.endswith(SESSION_COOKIE)

    if "801" in query:
        # The main measurements are readable without a session.
        return web.Response(text=json.dumps({"801": {"170": BASIC}}))

    if not logged_in:
        return web.Response(text='{"ACCESS DENIED"}')

    if "858" in query:
        return web.Response(text=json.dumps({"858": BATTERY}))
    if "878" in query:
        return web.Response(text=json.dumps({"878": ENERGY}))
    if "782" in query:
        return web.Response(text=json.dumps({"782": INVERTER_POWER}))
    if "854" in query:
        return web.Response(text=json.dumps({"854": INVERTER_ENERGY}))
    if "740" in query:
        return web.Response(text=json.dumps({"740": DEVICE_LIST}))
    if "141" in query:
        device_id = next(iter(query["141"]))
        return web.Response(
            text=json.dumps({"141": {device_id: {"119": DEVICE_NAMES[device_id]}}})
        )
    return web.Response(text='{"QUERY IMPOSSIBLE 000"}')


async def handle_login(request):
    body = await request.text()
    fields = dict(part.split("=", 1) for part in body.split("&"))
    if fields.get("u") != "user":
        return web.Response(text="FAILED - User was wrong")
    if fields.get("p") != PASSWORD:
        return web.Response(text="FAILED - Password was wrong")
    response = web.Response(text="SUCCESS")
    response.set_cookie("SolarLog", SESSION_COOKIE)
    return response


# A second, separate stand-in server for firmware that requires the
# bcrypt-hashed login (rejects the plain password, then a per-device salt).
HASHED_PASSWORD = "geheim2"
HASHED_SALT = bcrypt.gensalt().decode()
HASHED_EXPECTED = bcrypt.hashpw(HASHED_PASSWORD.encode(), HASHED_SALT.encode()).decode()
HASHED_SESSION_COOKIE = "hashedxyz"

hashed_requests_seen = []


async def handle_hashed_login(request):
    body = await request.text()
    fields = dict(part.split("=", 1) for part in body.split("&"))
    if fields.get("u") != "user":
        return web.Response(text="FAILED - User was wrong")
    if fields.get("p") == HASHED_EXPECTED:
        response = web.Response(text="SUCCESS")
        response.set_cookie("SolarLog", HASHED_SESSION_COOKIE)
        return response
    return web.Response(text="FAILED - Password was wrong")


async def handle_hashed_getjp(request):
    body = await request.text()
    hashed_requests_seen.append(body)
    # This firmware only ever parses a plain JSON body -- a body carrying
    # the "token=...;" prefix from the older-firmware fallback is rejected.
    if not body.startswith("{"):
        return web.Response(text='{"QUERY IMPOSSIBLE 000"}')
    query = json.loads(body)
    if "550" in query:
        return web.Response(text=json.dumps({"550": {"104": HASHED_SALT}}))
    if "801" in query:
        return web.Response(text=json.dumps({"801": {"170": BASIC}}))
    if request.cookies.get("SolarLog") != HASHED_SESSION_COOKIE:
        return web.Response(text='{"ACCESS DENIED"}')
    if "858" in query:
        return web.Response(text=json.dumps({"858": BATTERY}))
    return web.Response(text='{"QUERY IMPOSSIBLE 000"}')


hashed_app = web.Application()
hashed_app.router.add_post("/getjp", handle_hashed_getjp)
hashed_app.router.add_post("/login", handle_hashed_login)


# A third stand-in server for firmware whose login wants an account name other
# than "user". It answers a "user" login exactly the way a device with no
# password set does, so the client cannot tell the two apart from one reply.
INSTALLER_USERNAME = "installateur"
INSTALLER_SESSION_COOKIE = "installerxyz"


async def handle_installer_login(request):
    body = await request.text()
    fields = dict(part.split("=", 1) for part in body.split("&"))
    if fields.get("u") != INSTALLER_USERNAME:
        return web.Response(text="FAILED - User was wrong")
    if fields.get("p") != PASSWORD:
        return web.Response(text="FAILED - Password was wrong")
    response = web.Response(text="SUCCESS")
    response.set_cookie("SolarLog", INSTALLER_SESSION_COOKIE)
    return response


async def handle_installer_getjp(request):
    body = await request.text()
    token, _, payload = body.rpartition("; ") if "; " in body else ("", "", body)
    query = json.loads(payload)
    if "801" in query:
        return web.Response(text=json.dumps({"801": {"170": BASIC}}))
    logged_in = (
        request.cookies.get("SolarLog") == INSTALLER_SESSION_COOKIE
        or token.endswith(INSTALLER_SESSION_COOKIE)
    )
    if not logged_in:
        return web.Response(text='{"ACCESS DENIED"}')
    if "858" in query:
        return web.Response(text=json.dumps({"858": BATTERY}))
    return web.Response(text='{"QUERY IMPOSSIBLE 000"}')


installer_app = web.Application()
installer_app.router.add_post("/getjp", handle_installer_getjp)
installer_app.router.add_post("/login", handle_installer_login)


# A fourth server: no password set at all, so every account name is refused.
async def handle_open_login(request):
    return web.Response(text="FAILED - User was wrong")


async def handle_open_getjp(request):
    query = json.loads(await request.text())
    if "801" in query:
        return web.Response(text=json.dumps({"801": {"170": BASIC}}))
    return web.Response(text=json.dumps({"858": BATTERY}))


open_app = web.Application()
open_app.router.add_post("/getjp", handle_open_getjp)
open_app.router.add_post("/login", handle_open_login)


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        sys.exit(1)


async def main():
    app = web.Application()
    app.router.add_post("/getjp", handle_getjp)
    app.router.add_post("/login", handle_login)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8123)
    await site.start()

    try:
        # aiohttp's default cookie jar drops cookies for bare IP addresses;
        # the test server is 127.0.0.1, a real Solar-Log would be a hostname.
        async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as session:
            # --- without a password: only the main values ---
            client = api.AdvancedSolarLogClient(session, "127.0.0.1", port=8123)
            check("connection test succeeds", await client.async_test_connection())

            values = await client.async_get_basic_data()
            check("production read", values["101"] == 4210, values)
            check("consumption read", values["110"] == 1180, values)

            stamp = api.parse_timestamp(values["100"])
            check("timestamp parsed", stamp is not None and stamp.year == 2026, stamp)

            denied = False
            try:
                await client.async_get_battery()
            except api.AdvancedSolarLogAuthError:
                denied = True
            check("battery needs a session", denied)
            check("extended data reported unavailable", not await client.async_test_extended_data())

            # --- with the password: everything ---
            client = api.AdvancedSolarLogClient(session, "127.0.0.1", port=8123, password=PASSWORD)
            check("login succeeds", await client.async_login())
            check("extended data available", await client.async_test_extended_data())

            battery = await client.async_get_battery()
            check("state of charge read", battery["level"] == 78.0, battery)
            check("discharge power read", battery["discharge_power"] == 900.0, battery)
            check("charge power read", battery["charge_power"] == 0.0, battery)
            check("battery voltage read", battery["voltage"] == 51.2, battery)

            energy = await client.async_get_energy()
            check("yearly production read", energy["production"] == 3900000, energy)
            check("self-consumption read", energy["self_consumption"] == 1750000, energy)

            devices = await client.async_get_device_list()
            check("failed inverter skipped", set(devices) == {0, 1}, devices)
            check("inverter named", devices[0] == "Fronius Dach Sued", devices)

            power = await client.async_get_inverter_power()
            check("inverter power read", power[1] == 1610.0, power)

            yields = await client.async_get_inverter_energy()
            check("inverter yield read", yields[0] == 2400000, yields)

            # --- wrong password (own session: the shared one is already logged in) ---
            async with ClientSession(cookie_jar=CookieJar(unsafe=True)) as bad_session:
                bad = api.AdvancedSolarLogClient(
                    bad_session, "127.0.0.1", port=8123, password="falsch"
                )
                rejected = False
                try:
                    await bad.async_login()
                except api.AdvancedSolarLogAuthError:
                    rejected = True
                check("wrong password rejected", rejected)

            # --- unreachable host ---
            offline = api.AdvancedSolarLogClient(session, "127.0.0.1", port=8199)
            unreachable = False
            try:
                await offline.async_test_connection()
            except api.AdvancedSolarLogError:
                unreachable = True
            check("unreachable host raises", unreachable)

        # --- login over Home Assistant's actual shared session: a *default*
        # cookie jar (unsafe=False), against an IP-literal host. aiohttp
        # silently refuses to *automatically* store cookies for bare IP
        # addresses with that jar, which used to leave every later request
        # unauthenticated even right after a successful login (reproduces a
        # real report: login succeeds, then every protected field comes back
        # "ACCESS DENIED" regardless of the password). The client must force
        # the cookie into the jar itself instead of relying on aiohttp's
        # normal Set-Cookie handling. ---
        async with ClientSession() as safe_session:
            check(
                "the jar would normally refuse this cookie for a bare IP host (sanity check)",
                not safe_session.cookie_jar.filter_cookies(URL("http://127.0.0.1:8123")),
            )
            client = api.AdvancedSolarLogClient(
                safe_session, "127.0.0.1", port=8123, password=PASSWORD
            )
            check("login succeeds with the default cookie jar", await client.async_login())
            check(
                "the cookie is now in the jar, forced in past the IP-host check",
                bool(safe_session.cookie_jar.filter_cookies(URL("http://127.0.0.1:8123"))),
            )
            battery = await client.async_get_battery()
            check(
                "battery still readable",
                battery is not None and battery["level"] == 78.0,
                battery,
            )

        # --- hashed-password (newer) firmware on an IP host: this firmware
        # only ever sees a plain JSON body -- it must reject anything with
        # the "token=...;" prefix the plain-password fallback uses -- so
        # this proves the forced cookie-jar insert works standalone. ---
        hashed_runner = web.AppRunner(hashed_app)
        await hashed_runner.setup()
        hashed_site = web.TCPSite(hashed_runner, "127.0.0.1", 8124)
        await hashed_site.start()
        try:
            async with ClientSession() as hashed_session:
                client = api.AdvancedSolarLogClient(
                    hashed_session, "127.0.0.1", port=8124, password=HASHED_PASSWORD
                )
                check(
                    "login succeeds against hashed-password firmware",
                    await client.async_login(),
                )
                check(
                    "no body-token fallback used for hashed-password firmware",
                    client._token == "",
                    client._token,
                )
                battery = await client.async_get_battery()
                check(
                    "battery readable via the forced cookie jar alone",
                    battery is not None and battery["level"] == 78.0,
                    battery,
                )
                check(
                    "no request carried the token=...; prefix",
                    all(not body.startswith("token=") for body in hashed_requests_seen),
                    hashed_requests_seen,
                )
        finally:
            await hashed_runner.cleanup()

        # --- firmware whose login wants a different account name. It answers
        # a "user" login with "FAILED - User was wrong" -- which the client
        # used to read as "this device has no password", silently giving up
        # and leaving every protected value denied for good. ---
        installer_runner = web.AppRunner(installer_app)
        await installer_runner.setup()
        await web.TCPSite(installer_runner, "127.0.0.1", 8125).start()
        try:
            async with ClientSession() as installer_session:
                client = api.AdvancedSolarLogClient(
                    installer_session, "127.0.0.1", port=8125, password=PASSWORD
                )
                check(
                    "login finds the account name the device accepts",
                    await client.async_login(),
                )
                check(
                    "the accepted account name is remembered",
                    client.username == INSTALLER_USERNAME,
                    client.username,
                )
                check(
                    "password survives a 'User was wrong' answer",
                    client.password == PASSWORD,
                    client.password,
                )
                battery = await client.async_get_battery()
                check(
                    "protected values readable after the fallback login",
                    battery is not None and battery["level"] == 78.0,
                    battery,
                )
        finally:
            await installer_runner.cleanup()

        # --- a device with no password set refuses every account name; that
        # must come back as "no session", not as an exception. ---
        open_runner = web.AppRunner(open_app)
        await open_runner.setup()
        await web.TCPSite(open_runner, "127.0.0.1", 8126).start()
        try:
            async with ClientSession() as open_session:
                client = api.AdvancedSolarLogClient(
                    open_session, "127.0.0.1", port=8126, password=PASSWORD
                )
                check(
                    "an unprotected device reports no session rather than raising",
                    await client.async_login() is False,
                )
        finally:
            await open_runner.cleanup()

        # --- a dropped session is picked up again instead of failing for good ---
        relogin_state = {"logged_in": False, "logins": 0}

        async def handle_relogin_login(request):
            relogin_state["logged_in"] = True
            relogin_state["logins"] += 1
            response = web.Response(text="SUCCESS")
            response.set_cookie("SolarLog", SESSION_COOKIE)
            return response

        async def handle_relogin_getjp(request):
            body = await request.text()
            _, _, payload = body.rpartition("; ") if "; " in body else ("", "", body)
            query = json.loads(payload)
            if "801" in query:
                return web.Response(text=json.dumps({"801": {"170": BASIC}}))
            if not relogin_state["logged_in"]:
                return web.Response(text='{"ACCESS DENIED"}')
            # The device forgets the session after answering once.
            relogin_state["logged_in"] = False
            return web.Response(text=json.dumps({"858": BATTERY}))

        relogin_app = web.Application()
        relogin_app.router.add_post("/getjp", handle_relogin_getjp)
        relogin_app.router.add_post("/login", handle_relogin_login)
        relogin_runner = web.AppRunner(relogin_app)
        await relogin_runner.setup()
        await web.TCPSite(relogin_runner, "127.0.0.1", 8127).start()
        try:
            async with ClientSession() as relogin_session:
                client = api.AdvancedSolarLogClient(
                    relogin_session, "127.0.0.1", port=8127, password=PASSWORD
                )
                await client.async_login()
                check("first protected read works", await client.async_get_battery())
                check(
                    "a dropped session is re-established on the next read",
                    await client.async_get_battery() is not None,
                )
                check(
                    "re-login actually happened",
                    relogin_state["logins"] > 1,
                    relogin_state,
                )
        finally:
            await relogin_runner.cleanup()

        # --- the client must stay read-only ---
        own_methods = api.AdvancedSolarLogClient.__dict__
        writers = [
            name for name in own_methods
            if not name.startswith("_")
            and any(word in name for word in ("switch", "command", "save", "write", "restart", "set_"))
        ]
        check("no write methods on the client", not writers, writers)

        check(
            "every request went to the JSON interface",
            all(part.startswith("{") for part in requests_seen),
            requests_seen,
        )
    finally:
        await runner.cleanup()

    print(f"\nAll API checks passed ({len(requests_seen)} requests).")


asyncio.run(main())
