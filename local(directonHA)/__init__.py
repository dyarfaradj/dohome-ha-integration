import socket
import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

DOMAIN = 'dohome'
CONF_GATEWAYS = 'discovery_ip'
CONF_DISCOVERY_RETRY = 'discovery_retry'

DISCOVERY_IP = ''
DEFAULT_DISCOVERY_IP = '192.168.1.255'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_GATEWAYS, default=DEFAULT_DISCOVERY_IP): cv.string,
        vol.Optional(CONF_DISCOVERY_RETRY, default=2): cv.positive_int
    })
}, extra=vol.ALLOW_EXTRA)

DOHOME_COMPONENTS = ['switch', 'light', 'sensor', 'binary_sensor']
DOHOME_GATEWAY = None

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

def get_alias(name):
    alias = {
        'Plug_b33b': 'Kökslampa fönster',
        'Plug_e84c': 'TV LED Strip',
        'Plug_3ab9': 'Fläkt'
    }
    return alias.get(name, name)


def setup(hass, config):
    global DISCOVERY_IP
    DISCOVERY_IP = config[DOMAIN][CONF_GATEWAYS]
    discovery_retry = config[DOMAIN][CONF_DISCOVERY_RETRY]

    if DISCOVERY_IP == DEFAULT_DISCOVERY_IP:
        hostname = socket.getfqdn(socket.gethostname())
        hosts = socket.gethostbyname_ex(hostname)
        for add in hosts[2]:
            if add.startswith('192.168.'):
                addlist = add.split(".")
                DISCOVERY_IP = addlist[0] + '.' + addlist[1] + '.' + addlist[2] + '.255'
    _LOGGER.info("DoHome discovery_ip:%s", DISCOVERY_IP)
    
    global DOHOME_GATEWAY
    DOHOME_GATEWAY = DoHomeGateway()

    with ThreadPoolExecutor() as executor:
        for _ in range(discovery_retry):
            executor.submit(DOHOME_GATEWAY._discover_devices)

    for component in DOHOME_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    # Expose discover_devices entity
    hass.states.set(DOMAIN + '.discover_devices', 'idle')
    hass.services.register(DOMAIN, 'discover_devices', lambda call: discover_devices_service(hass, call))

    return True

def discover_devices_service(hass, call):
    """Service to trigger device discovery for a specified duration."""
    try:
        # Validate duration with reasonable limits
        duration = min(max(call.data.get('duration', 10), 1), 60)  # Min 1s, Max 60s
        
        hass.states.set(DOMAIN + '.discover_devices', 'active')
        
        if not DOHOME_GATEWAY:
            _LOGGER.error("Gateway not initialized")
            hass.states.set(DOMAIN + '.discover_devices', 'error')
            return False

        discovered_devices = DOHOME_GATEWAY._discover_devices(duration)
        
        if discovered_devices:
            for device_type, devices in discovered_devices.items():
                for device in devices:
                    discovery.load_platform(hass, device_type, DOMAIN, {device['sid']: device}, {})
            hass.states.set(DOMAIN + '.discover_devices', 'idle')
            return True
        else:
            _LOGGER.warning("No devices discovered")
            hass.states.set(DOMAIN + '.discover_devices', 'idle')
            return False
            
    except Exception as err:
        _LOGGER.error("Error during device discovery: %s", str(err))
        hass.states.set(DOMAIN + '.discover_devices', 'error')
        return False
    
class DoHomeGateway:
    GATEWAY_DISCOVERY_PORT = 6091
    SOCKET_BUFSIZE = 1024

    devices = defaultdict(list)

    def _discover_devices(self, duration=1):
        _socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        _socket.bind(('', self.GATEWAY_DISCOVERY_PORT))
        
        discovered_devices = defaultdict(list)
        
        try:
            _socket.sendto('cmd=ping\r\n'.encode(), (DISCOVERY_IP, self.GATEWAY_DISCOVERY_PORT))
            _socket.settimeout(duration)  # Set socket timeout to 30 seconds

            while True:
                data, addr = _socket.recvfrom(self.SOCKET_BUFSIZE)

                if len(data) >= 70:
                    resp = {i.split("=")[0]: i.split("=")[1] for i in data.decode("utf-8").split("&")}
                    if resp.get("cmd") == 'pong':
                        device_type = resp.get("device_type")

                        dohome_device = {
                            "sid": resp.get("device_name")[-4:],
                            "name": resp.get("device_name"),
                            "sta_ip": resp.get("sta_ip"),
                            "type": device_type
                        }

                        if dohome_device not in self.devices[device_type]:
                            self.devices[device_type].append(dohome_device)
                            discovered_devices[device_type].append(dohome_device)
                            _LOGGER.info("Discovered DoHome Device: %s", dohome_device)

        except socket.timeout:
            _LOGGER.info("Gateway finding finished in %d seconds.", duration)
        except socket.error as e:
            _LOGGER.error("Socket error: %s", str(e))
        finally:
            _socket.close()
            
        return discovered_devices  # Return the discovered devices

class DoHomeDevice(Entity):

    def __init__(self, name, device):
        self._sid = device['sid']
        self._name = get_alias(name)
        self._sta_ip = device['sta_ip']
        self._device_state_attributes = {}

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes