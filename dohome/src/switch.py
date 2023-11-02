import logging
import socket
import json
from datetime import timedelta
from homeassistant.helpers.event import track_time_interval

from homeassistant.components.switch import SwitchEntity

from .. import (DOHOME_GATEWAY, DoHomeDevice)

_LOGGER = logging.getLogger(__name)


def setup_platform(hass, config, add_devices, discovery_info=None):
    switch_devices = []
    devices = DOHOME_GATEWAY.devices
    for (device_type, device_info) in devices.items():
        for device in device_info:
            if device['type'] == '_DT-PLUG':
                switch_devices.append(DoHomeSwitch(
                    hass, device["name"], "soft_poweroff", device))
            if device['type'] == '_THIMR':
                switch_devices.append(DoHomeSwitch(
                    hass, device["name"], "relay", device))
            if device['type'] == '_REALY2':
                switch_devices.append(DoHomeSwitch(
                    hass, "Relay_" + device["sid"] + '_1', "relay1", device))
                switch_devices.append(DoHomeSwitch(
                    hass, "Relay_" + device["sid"] + '_2', "relay2", device))
            if device['type'] == '_REALY4':
                switch_devices.append(DoHomeSwitch(
                    hass, "Relay_" + device["sid"] + '_1', "relay1", device))
                switch_devices.append(DoHomeSwitch(
                    hass, "Relay_" + device["sid"] + '_2', "relay2", device))
                switch_devices.append(DoHomeSwitch(
                    hass, "Relay_" + device["sid"] + '_3', "relay3", device))
                switch_devices.append(DoHomeSwitch(
                    hass, "Relay_" + device["sid"] + '_4', "relay4", device))

    if switch_devices:
        add_devices(switch_devices)


class DoHomeSwitch(DoHomeDevice, SwitchEntity):
    def __init__(self, hass, name, data_key, device):
        self._device = device
        self._data_key = data_key
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        DoHomeDevice.__init__(self, name, device)

        track_time_interval(hass, self.update_status, timedelta(seconds=1))

    @property
    def is_on(self):
        return self._state

    def turn_on(self, **kwargs):
        self._set_switch_state(1)

    def turn_off(self):
        self._set_switch_state(0)

    def update_status(self, now):
        resp = self._send_cmd(
            self._device, 'cmd=ctrl&devices=[' + self._device["sid"] + ']&op={"cmd":25}', 25)
        if resp is not None and self._data_key in resp:
            new_state = resp[self._data_key]
            if self._state != new_state:
                self._state = new_state
                self.schedule_update_ha_state()

    def _set_switch_state(self, state):
        if self._device['type'] in ('_DT-PLUG', '_THIMR'):
            op_value = 1 if state == 1 else 0
        else:
            op_value = state

        cmd = f'cmd=ctrl&devices=[{self._device["sid"]}]&op={{"cmd": 5, "{self._data_key}": {op_value}}}'
        self._send_cmd(self._device, cmd, 5)

    def _send_cmd(self, device, cmd, rtn_cmd):
        try:
            self._socket.settimeout(0.5)
            self._socket.sendto(cmd.encode(), (device["sta_ip"], 6091))
            data, _ = self._socket.recvfrom(1024)
        except socket.timeout:
            _LOGGER.error("Socket timeout occurred while sending command.")
            return None

        if data is None:
            _LOGGER.error("No response data received.")
            return None

        decoded_data = data.decode("utf-8")
        _LOGGER.debug("Received response data: %s", decoded_data)

        response_dict = {i.split("=")[0]: i.split("=")[1]
                         for i in decoded_data.split("&")}

        if response_dict["dev"][8:12] == device["sid"]:
            response_op = json.loads(response_dict["op"])
            if response_op['cmd'] != rtn_cmd:
                _LOGGER.warning(
                    "Non-matching response. Expected %s, but got %s", rtn_cmd, response_op['cmd']
                )
                return None
            return response_op
        else:
            _LOGGER.warning(
                "Non-matching response. Expected device %s, but got %s", device["sid"], response_dict["dev"][8:12]
            )
            return None
