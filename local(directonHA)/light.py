import logging
import socket
import json
import asyncio
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval
import homeassistant.util.color as color_util
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGBWW_COLOR,
    LightEntity,
    ColorMode,
)

from . import (DOHOME_GATEWAY, DoHomeDevice)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.INFO)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    light_devices = []
    devices = DOHOME_GATEWAY.devices
    for (device_type, device_info) in devices.items():
        _LOGGER.info(f"Processing device type: {device_type}")
        for device in device_info:
            _LOGGER.info(f"Device info: {device}")
            if device['type'] == '_STRIPE' or device['type'] == '_DT-WYRGB':
                light_devices.append(DoHomeLight(hass, device))
    
    if light_devices:
        async_add_entities(light_devices)


class DoHomeLight(DoHomeDevice, LightEntity):

    def __init__(self, hass, device):

        self._device = device
        self._state = False
        self._rgb = (255, 255, 255, 255, 255)
        self._brightness = 100
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        DoHomeDevice.__init__(self, device['name'], device)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgbww_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def is_on(self):
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

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_RGBWW_COLOR in kwargs:
            self._rgb = kwargs[ATTR_RGBWW_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = int(100 * kwargs[ATTR_BRIGHTNESS] / 255)

        self._state = True
        data = {
            "cmd": 6,
            "r": int(50 * self._rgb[0] / 255) * self._brightness,
            "g": int(50 * self._rgb[1] / 255) * self._brightness,
            "b": int(50 * self._rgb[2] / 255) * self._brightness,
            "w": int(50 * self._rgb[3] / 255) * self._brightness,
            "m": int(50 * self._rgb[4] / 255) * self._brightness
        }
        op = json.dumps(data)
        await self._async_send_cmd(self._device, 'cmd=ctrl&devices={[' + self._device["sid"] + ']}&op=' + op + '}', 6)

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
        await self._async_send_cmd(self._device, 'cmd=ctrl&devices={[' + self._device["sid"] + ']}&op=' + op + '}', 6)

    async def _async_send_cmd(self, device, cmd, rtn_cmd):
        try:
            self._socket.settimeout(0.5)
            self._socket.sendto(cmd.encode(), (device["sta_ip"], 6091))
            data, addr = self._socket.recvfrom(1024)
        except socket.timeout:
            return None

        if data is None:
            return None
        _LOGGER.debug("result :%s", data.decode("utf-8"))
        dic = {i.split("=")[0]: i.split("=")[1] for i in data.decode("utf-8").split("&")}
        resp = []
        if dic["dev"][8:12] == device["sid"]:
            resp = json.loads(dic["op"])
            if resp['cmd'] != rtn_cmd:
                _LOGGER.debug("Non matching response. Expecting %s, but got %s", rtn_cmd, resp['cmd'])
                return None
            return resp
        else:
            _LOGGER.debug("Non matching response. device %s, but got %s", device["sid"], dic["dev"][8:12])
            return None