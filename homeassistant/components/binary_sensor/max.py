import logging
import queue
import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.const import (TEMP_CELSIUS, STATE_UNKNOWN, ATTR_TEMPERATURE, ATTR_STATE)
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import get_component
from homeassistant.components.max import (MAX_PUSHBUTTON, MAX_SHUTTERCONTACT)

DEPENDENCIES = ['max']

CUBE_ID = 0x123456
DOMAIN = 'max'

STATE_BOOST = 'Boost'

ATTR_NAME = 'device_name'
ATTR_ID = 'device_id'
ATTR_BATTERY_STATE = 'battery_low'
ATTR_LANGATEWAY = 'langateway'
ATTR_LASTUPDATED = 'lastupdated'
ATTR_RFERROR = 'rferror'
ATTR_SIGNALSTRENGTH = 'signalstrength'

SHUTTERCONTACT_SENSOR_CLASS = 'opening'
PUSHBUTTON_SENSOR_CLASS = 'None'
GENERIC_SENSOR_CLASS = 'None'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    max_master = get_component('max').MAX
    """Setup the Max thermostat platform."""
    if max_master is None:
        return

    devices = []
    for device in config['devices']:
        if 'shuttercontact' in device:
            devices.append(MaxShutterContact(max_master.thread, device['id']))
        elif 'pushbutton' in device:
            devices.append(MaxPushButton(max_master.thread, device['id']))

    add_devices(devices)
    max_master.devices.extend(devices)


class MaxBinaryDevice(BinarySensorDevice):
    """Representation of a Sensor."""

    def __init__(self, message_thread, device_id):
        """Initialize the thermostat."""
        self._thread = message_thread
        self._name = 'max binary sensor'
        self._id = device_id
        self._type = None
        self._state = None
        self._battery_low = None
        self._langateway = None
        self._last_updated = None
        self._rferror = None
        self._signal_strength = None
        self._sensor_class = GENERIC_SENSOR_CLASS
        self.update()

    @property
    def name(self):
        """Return the name of the max thermostat, if any."""
        return self._name

    @property
    def id(self):
        """Return the unit of measurement that is used."""
        return self._id

    @property
    def type(self):
        """Return the device type."""
        return self._type

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        state = {
            ATTR_NAME: self._name,
            ATTR_ID: self._id,
            ATTR_BATTERY_STATE: self._battery_low,
            ATTR_LANGATEWAY: self._langateway,
            ATTR_LASTUPDATED: self._last_updated,
            ATTR_RFERROR: self._rferror,
            ATTR_SIGNALSTRENGTH: self._signal_strength,
            ATTR_STATE: self._state
        }

        return state

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return self._sensor_class

    def update(self):
        """Get the latest data and updates the state."""

        if self._thread.states:
            default = None
            self._battery_low = self._thread.states[self._id].get('battery_low', default)
            self._langateway = self._thread.states[self._id].get('langateway', default)
            self._last_updated = self._thread.states[self._id].get('last_updated', default)
            self._rferror = self._thread.states[self._id].get('rferror', default)
            self._signal_strength = self._thread.states[self._id].get('signal_strenth', default)
            self._state = self._thread.states[self._id].get('state', default)


class MaxPushButton(MaxBinaryDevice):

    def __init__(self, message_thread, device_id):
        super().__init__(message_thread, device_id)
        self._type = MAX_PUSHBUTTON
        self._name = self._type + ' ' + str(self._id)
        self._sensor_class = PUSHBUTTON_SENSOR_CLASS


class MaxShutterContact(MaxBinaryDevice):

    def __init__(self, message_thread, device_id):
        super().__init__(message_thread, device_id)
        self._type = MAX_SHUTTERCONTACT
        self._name = self._type + ' ' + str(self._id)
        self._sensor_class = SHUTTERCONTACT_SENSOR_CLASS
