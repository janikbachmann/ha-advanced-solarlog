"""Checks the config flow's control flow: setup, reauth, and reconfigure.

Run with: python3 tests/test_config_flow.py

Exercises the actual logic in config_flow.py against a small stand-in for
hass.config_entries (see ha_stubs.py), whose semantics -- what
async_set_unique_id, _abort_if_unique_id_configured and
async_update_reload_and_abort do -- were checked against HA core's own
homeassistant/config_entries.py rather than assumed.
"""
import asyncio, importlib.util, pathlib, sys, types

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import ha_stubs  # noqa: F401

ROOT = str(pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "advanced_solarlog")
pkg = types.ModuleType("asl"); pkg.__path__ = [ROOT]; sys.modules["asl"] = pkg
for name in ("const", "api", "config_flow"):
    spec = importlib.util.spec_from_file_location(f"asl.{name}", f"{ROOT}/{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[f"asl.{name}"] = mod
    spec.loader.exec_module(mod)

config_flow = sys.modules["asl.config_flow"]
data_entry_flow = sys.modules["homeassistant.data_entry_flow"]


def check(label, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        sys.exit(1)


class FakeHass:
    def __init__(self):
        self.config_entries = ha_stubs._FakeConfigEntries()


async def run_step(flow, coro):
    try:
        return await coro
    except data_entry_flow.AbortFlow as err:
        return {"type": "abort", "reason": err.reason}


async def main():
    # Patch out the real network call: config_flow._async_validate hits the
    # actual device. These tests are about the flow's own bookkeeping.
    calls = []

    async def fake_validate(hass, data):
        calls.append(dict(data))
        if data.get("password") == "wrong":
            raise config_flow.AdvancedSolarLogAuthError("nope")
        if data["host"] == "unreachable.local":
            raise config_flow.AdvancedSolarLogError("no answer")
        return bool(data.get("password"))

    config_flow._async_validate = fake_validate

    # --- fresh setup: async_step_user ---
    hass = FakeHass()
    flow = config_flow.AdvancedSolarLogConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user"}

    result = await run_step(flow, flow.async_step_user({"host": "solarlog.local", "port": 80, "password": "geheim"}))
    check("fresh setup creates an entry", result["type"] == "create_entry", result)
    check("extended_data recorded true (password set)", result["data"]["extended_data"] is True, result)
    entry = ha_stubs._FakeConfigEntry("e1", "solarlog.local", result["data"], title=result["title"])
    hass.config_entries.add(entry)

    # --- duplicate host on a fresh setup aborts ---
    flow2 = config_flow.AdvancedSolarLogConfigFlow()
    flow2.hass = hass
    flow2.context = {"source": "user"}
    result = await run_step(flow2, flow2.async_step_user({"host": "solarlog.local", "port": 80, "password": ""}))
    check("duplicate host aborts on fresh setup", result["type"] == "abort" and result["reason"] == "already_configured", result)

    # --- no password: entry keeps no password key ---
    flow3 = config_flow.AdvancedSolarLogConfigFlow()
    flow3.hass = hass
    flow3.context = {"source": "user"}
    result = await run_step(flow3, flow3.async_step_user({"host": "other.local", "port": 80, "password": ""}))
    check("blank password dropped from stored data", "password" not in result["data"], result)
    check("extended_data false without a password", result["data"]["extended_data"] is False, result)

    # --- reconfigure: change host and password for the same device ---
    flow4 = config_flow.AdvancedSolarLogConfigFlow()
    flow4.hass = hass
    flow4.context = {"source": "reconfigure", "entry_id": "e1"}
    result = await run_step(
        flow4,
        flow4.async_step_reconfigure({"host": "10.0.0.5", "port": 80, "password": "neu"}),
    )
    check("reconfigure with a new host succeeds", result["type"] == "abort" and result["reason"] == "reconfigure_successful", result)
    check("unique_id follows the new host", entry.unique_id == "10.0.0.5", entry.unique_id)
    check("entry data reflects the new host", entry.data["host"] == "10.0.0.5", entry.data)
    check("entry data reflects the new password", entry.data["password"] == "neu", entry.data)

    # --- reconfigure onto a host already used by a different entry ---
    other_entry = ha_stubs._FakeConfigEntry("e2", "other.local", {"host": "other.local"})
    hass.config_entries.add(other_entry)
    flow5 = config_flow.AdvancedSolarLogConfigFlow()
    flow5.hass = hass
    flow5.context = {"source": "reconfigure", "entry_id": "e1"}
    result = await run_step(
        flow5,
        flow5.async_step_reconfigure({"host": "other.local", "port": 80, "password": ""}),
    )
    check(
        "reconfigure onto another entry's host is a form error, not an abort",
        result["type"] == "form" and result["errors"].get("base") == "already_configured",
        result,
    )
    check("that entry's data is untouched by the rejected attempt", entry.data["host"] == "10.0.0.5", entry.data)

    # --- reconfigure with a wrong password shows an error and keeps the entry ---
    flow6 = config_flow.AdvancedSolarLogConfigFlow()
    flow6.hass = hass
    flow6.context = {"source": "reconfigure", "entry_id": "e1"}
    result = await run_step(
        flow6,
        flow6.async_step_reconfigure({"host": "10.0.0.5", "port": 80, "password": "wrong"}),
    )
    check("wrong password on reconfigure is a form error", result["type"] == "form" and result["errors"]["base"] == "invalid_auth", result)
    check("entry password unchanged after a rejected attempt", entry.data["password"] == "neu", entry.data)

    # --- reconfigure showing the initial form prefills from current data ---
    flow7 = config_flow.AdvancedSolarLogConfigFlow()
    flow7.hass = hass
    flow7.context = {"source": "reconfigure", "entry_id": "e1"}
    result = await run_step(flow7, flow7.async_step_reconfigure(None))
    check("reconfigure with no input shows the form", result["type"] == "form" and result["step_id"] == "reconfigure", result)

    # --- reauth: only the password changes, host/unique_id untouched ---
    flow8 = config_flow.AdvancedSolarLogConfigFlow()
    flow8.hass = hass
    flow8.context = {"source": "reauth", "entry_id": "e1"}
    result = await run_step(flow8, flow8.async_step_reauth_confirm({"password": "erneut"}))
    check("reauth succeeds", result["type"] == "abort" and result["reason"] == "reconfigure_successful", result)
    check("reauth leaves the host untouched", entry.data["host"] == "10.0.0.5", entry.data)
    check("reauth updates the password", entry.data["password"] == "erneut", entry.data)

    # --- options flow: poll interval and extended_data toggle ---
    options_flow = config_flow.AdvancedSolarLogOptionsFlow()
    options_flow.config_entry = entry
    result = await options_flow.async_step_init({"poll_interval": 30, "extended_data": True})
    check("options flow creates an entry", result["type"] == "create_entry", result)
    check("options carry the new poll interval", result["data"]["poll_interval"] == 30, result)

    print(f"\nAll config-flow checks passed ({len(calls)} validation calls made).")


asyncio.run(main())
