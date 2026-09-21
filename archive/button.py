"""Buttons fuer Aktionen am EnergyOptimizer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import AdvancedSolarLogClient, AdvancedSolarLogError
from .const import DOMAIN
from .coordinator import AdvancedSolarLogCoordinator
from .entity import AdvancedSolarLogEntity


@dataclass(frozen=True, kw_only=True)
class EOButtonDescription(ButtonEntityDescription):
    """Button mit auszufuehrender Aktion."""

    press_fn: Callable[[AdvancedSolarLogClient], Awaitable[None]]


BUTTONS: tuple[EOButtonDescription, ...] = (
    EOButtonDescription(
        key="refresh",
        translation_key="refresh_solarlog",
        press_fn=lambda client: client.async_refresh_solarlog(),
    ),
    EOButtonDescription(
        key="ack_alarms",
        translation_key="ack_alarms",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda client: client.async_ack_alarms(-1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Buttons anlegen."""
    coordinator: AdvancedSolarLogCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AdvancedSolarLogButton(coordinator, description) for description in BUTTONS
    )


class AdvancedSolarLogButton(AdvancedSolarLogEntity, ButtonEntity):
    """Loest eine POST-Route auf dem Geraet aus."""

    entity_description: EOButtonDescription

    def __init__(
        self,
        coordinator: AdvancedSolarLogCoordinator,
        description: EOButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._entry_id}_{description.key}"

    async def async_press(self) -> None:
        """Aktion ausfuehren und danach neu pollen."""
        try:
            await self.entity_description.press_fn(self.coordinator.client)
        except AdvancedSolarLogError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
