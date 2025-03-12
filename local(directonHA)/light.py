import logging
import socket
import json
import asyncio
from typing import Any
from datetime import timedelta

from homeassistant.helpers.event import track_time_interval
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBWW_COLOR,
    LightEntity,
    ColorMode,
)

from . import (DOHOME_GATEWAY, DoHomeDevice)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None):
    light_devices = []
    devices = DOHOME_GATEWAY.devices
    for (device_type, device_info) in devices.items():
        _LOGGER.info(f"Processing device type: {device_type}")
        for device in device_info:
            _LOGGER.info(f"Device info: {device}")
            if device['type'] in ['_STRIPE', '_DT-WYRGB']:
                light_devices.append(DoHomeLight(hass, device))
    
    if light_devices:
        async_add_entities(light_devices)
        return True


class DoHomeLight(DoHomeDevice, LightEntity):

    def __init__(self, hass, device):
        super().__init__(device['name'], device)
        self._device = device
        self._state = False
        self._rgb = (255, 255, 255, 255, 255)
        self._brightness = 255
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._attr_unique_id = f"dohome_light_{device['sid']}"
        self._attr_name = device['name']
        self._attr_supported_color_modes = {ColorMode.RGBWW}
        self._attr_color_mode = ColorMode.RGBWW


    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {("dohome", self._device["sid"])},
            "name": self._attr_name,
            "manufacturer": "DoHome",
            "model": self._device["type"],
        }

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgbww_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    # @property
    # def supported_features(self):
    #     """Return the supported features."""
    #     return ColorMode.BRIGHTNESS | ColorMode.HS

    @property
    def supported_color_modes(self):
        """Return the supported color modes."""
        return [ColorMode.RGBWW]

    @property
    def color_mode(self):
        """Return the supported color modes."""
        return ColorMode.RGBWW

    @property
    def unique_id(self):
        return self._device["name"]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if ATTR_RGBWW_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGBWW_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

        # Convert HA brightness (0-255) to device brightness (0-100)
        device_brightness = int(100 * self._brightness / 255)
        
        self._state = True
        data = {
            "cmd": 6,
            "r": int(50 * self._rgb[0] / 255 * device_brightness),
            "g": int(50 * self._rgb[1] / 255 * device_brightness),
            "b": int(50 * self._rgb[2] / 255 * device_brightness),
            "w": int(50 * self._rgb[3] / 255 * device_brightness),
            "m": int(50 * self._rgb[4] / 255 * device_brightness)
        }
        op = json.dumps(data)
        cmd_str = f'cmd=ctrl&devices={{[{self._device["sid"]}]}}&op={op}'
        await self._async_send_cmd(self._device, cmd_str, 6)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = False
        data = {
            "cmd": 6,
            "r": 0,
            "g": 0,
            "b": 0,
            "w": 0,
            "m": 0
        }
        op = json.dumps(data)
        cmd_str = f'cmd=ctrl&devices={{[{self._device["sid"]}]}}&op={op}'
        await self._async_send_cmd(self._device, cmd_str, 6)

    async def _async_send_cmd(self, device: dict, cmd: str, rtn_cmd: int) -> dict | None:
        """Send command to device asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            
            # Create socket in non-blocking mode
            if self._socket is None:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            self._socket.settimeout(0.5)
            
            # Send command
            _LOGGER.debug("Sending to %s: %s", device["sta_ip"], cmd)
            await loop.sock_sendto(self._socket, cmd.encode(), (device["sta_ip"], 6091))
            
            # Receive response in a way that doesn't block the event loop
            try:
                data, _ = await asyncio.wait_for(
                    loop.sock_recvfrom(self._socket, 1024),
                    timeout=1.0
                )
                
                if not data:
                    _LOGGER.debug("No data received")
                    return None

                dic = {i.split("=")[0]: i.split("=")[1] for i in data.decode("utf-8").split("&")}
                _LOGGER.debug("Response: %s", dic)
                
                if dic["dev"][8:12] != device["sid"]:
                    _LOGGER.debug("Non matching device: %s != %s", device["sid"], dic["dev"][8:12])
                    return None

                resp = json.loads(dic["op"])
                if resp['cmd'] != rtn_cmd:
                    _LOGGER.debug("Non matching response cmd: %s != %s", rtn_cmd, resp['cmd'])
                    return None

                return resp

            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout receiving response from %s", device["sta_ip"])
                return None
                
        except Exception as ex:
            _LOGGER.error("Error in async_send_cmd: %s", str(ex))
            return None