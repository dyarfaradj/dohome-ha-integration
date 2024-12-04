import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, DOHOME_GATEWAY, discover_devices_service

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the DoHome button platform."""
    async_add_entities([DoHomeDiscoverDevicesButton(hass)], True)

class DoHomeDiscoverDevicesButton(ButtonEntity):
    """Representation of a DoHome Discover Devices button."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the button."""
        self._hass = hass
        self._attr_name = "Discover Devices"
        self._attr_unique_id = f"{DOMAIN}_discover_devices_button"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Discover Devices button pressed")
        await self._hass.async_add_executor_job(discover_devices_service, self._hass, None)