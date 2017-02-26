import logging
import queue
import voluptuous as vol

from homeassistant.components.climate import (ClimateDevice, STATE_AUTO, STATE_IDLE, STATE_HEAT, ATTR_MAX_TEMP, ATTR_MIN_TEMP)
from homeassistant.const import (TEMP_CELSIUS, STATE_UNKNOWN, ATTR_TEMPERATURE)
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import get_component

DEPENDENCIES = ['max']

CUBE_ID = 0x123456
DOMAIN = 'max'

STATE_BOOST = 'Boost'

ATTR_CURRENT_TEMP = 'current_temperature'
ATTR_NAME = 'device_name'
ATTR_ID = 'device_id'
ATTR_BATTERY_STATE = 'battery_low'
ATTR_DSTSETTING = 'dstsetting'
ATTR_ISLOCKED = 'islocked'
ATTR_LANGATEWAY = 'langateway'
ATTR_LASTUPDATED = 'lastupdated'
ATTR_MODE = 'mode'
ATTR_RFERROR = 'rferror'
ATTR_SIGNALSTRENGTH = 'signalstrength'
ATTR_VALVEPOSITION = 'valveposition'

"""Max Device Types"""
MAX_CUBE = "Cube"
MAX_THERMOSTAT = "HeatingThermostat"
MAX_THERMOSTAT_PLUS = "HeatingThermostatPlus"
MAX_WALLTHERMOSTAT = "WallMountedThermostat"
MAX_SHUTTERCONTACT = "ShutterContact"
MAX_PUSHBUTTON = "PushButton"


_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    max = get_component('max').MAX
    """Setup the Max thermostat platform."""
    if max is None:
        return


    devices = []
    for device in config['devices']:
        if 'wallthermostat' in device:
            devices.append(MaxWallthermostat(max.thread, device['id']))
        elif 'thermostat' in device:
            devices.append(MaxThermostat(max.thread, device['id']))
        elif 'shuttercontact' in device:
            pass

    add_devices(devices)
    max.devices.extend(devices)



class MaxDevice(ClimateDevice):
    """Representation of a Sensor."""

    def __init__(self, message_thread, device_id):
        """Initialize the thermostat."""
        self._thread = message_thread
        self._current_temperature = None
        self._target_temperature = 21
        self._min_temperature = 4.5
        self._max_temperature = 30.5
        self._name = 'max device'
        self._id = device_id
        self._type = None
        self._battery_low = None
        self._dstsetting = None
        self._is_locked = None
        self._langateway = None
        self._last_updated = None
        self._mode = 'auto'
        self._rferror = None
        self._signal_strength = None
        self._operation_list = ['auto', 'manual', 'boost']
        self.update()


    @property
    def name(self):
        """Return the name of the max thermostat, if any."""
        return self._name

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temperature

    def set_min_temp(self, value):
        self._min_temperature = value

    @property
    def max_temp(self):
        """Return the minimum temperature."""
        return self._max_temperature

    def set_max_temp(self, value):
        self._max_temperature = value

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS


    @property
    def id(self):
        """Return the unit of measurement that is used."""
        return self._id

    @property
    def type(self):
        """Return the device type."""
        return self._type

    @property
    def operation_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._mode

    @property
    def operation_list(self):
        """Return the operation modes list."""
        return self._operation_list

    @property
    def mode(self):
        """Return current mode ie. home, away, sleep."""
        return self._mode

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        state = {
            ATTR_CURRENT_TEMP: self._current_temperature,
            ATTR_TEMPERATURE: self._target_temperature,
            ATTR_NAME: self._name,
            ATTR_ID: self._id,
            ATTR_BATTERY_STATE: self._battery_low,
            ATTR_DSTSETTING: self._dstsetting,
            ATTR_ISLOCKED: self._is_locked,
            ATTR_LANGATEWAY: self._langateway,
            ATTR_LASTUPDATED: self._last_updated,
            ATTR_MODE: self._mode,
            ATTR_RFERROR: self._rferror,
            ATTR_SIGNALSTRENGTH: self._signal_strength,
            ATTR_MIN_TEMP: self._min_temperature,
            ATTR_MAX_TEMP: self._max_temperature
        }

        return state

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        from maxcul.messages import SetTemperatureMessage

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        msg = SetTemperatureMessage(0xB9, 0, CUBE_ID, self._id, 0)
        payload = {
            'desired_temperature': temperature,
            'mode': self._mode,
        }
        self._thread.command_queue.put((msg, payload))
        self._target_temperature = temperature

    def set_operation_mode(self, operation_mode):
        """Set HVAC mode (auto, manual, boost)."""
        from maxcul.messages import SetTemperatureMessage

        if operation_mode is None:
            return

        msg = SetTemperatureMessage(0xB9, 0, CUBE_ID, self._id, 0)
        payload = {
            'desired_temperature': self._target_temperature,
            'mode': operation_mode,
        }
        self._thread.command_queue.put((msg, payload))
        self._mode = operation_mode

class MaxThermostat(MaxDevice):

    def __init__(self, message_thread, device_id):
        super().__init__(message_thread, device_id)
        self._valve_position = None
        self._type = MAX_THERMOSTAT
        self._name = self._type + ' ' + str(self._id)



    @property
    def current_operation(self):
        """Return current operation."""
        if self._valve_position is None:
            return STATE_UNKNOWN
        elif self._mode == 'boost':
            return STATE_BOOST
        elif self._valve_position > 0:
            return STATE_HEAT
        else:
            return STATE_IDLE

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        state = super().device_state_attributes
        state.update({
            ATTR_VALVEPOSITION: self._valve_position
        })
        return state

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def update(self):
        """Get the latest data and updates the state."""

        if self._thread.states:
            default = None
            self._target_temperature = self._thread.states[self._id].get('desired_temperature', default)
            self._current_temperature = self._thread.states[self._id].get('measured_temperature', default)
            self._battery_low = self._thread.states[self._id].get('battery_low', default)
            self._dstsetting = self._thread.states[self._id].get('dstsetting', default)
            self._is_locked = self._thread.states[self._id].get('is_locked', default)
            self._langateway = self._thread.states[self._id].get('langateway', default)
            self._last_updated = self._thread.states[self._id].get('last_updated', default)
            self._mode = self._thread.states[self._id].get('mode', default)
            self._rferror = self._thread.states[self._id].get('rferror', default)
            self._signal_strength = self._thread.states[self._id].get('signal_strenth', default)
            self._valve_position = self._thread.states[self._id].get('valve_position', default)

class MaxWallthermostat(MaxDevice):

    def __init__(self, message_thread, device_id):
        super().__init__(message_thread, device_id)
        self._until = None
        self._display_actual_temprature = None
        self._type = MAX_WALLTHERMOSTAT
        self._name = self._type + ' ' + str(self._id)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def current_operation(self):
        """Return current operation."""
        return self._mode

    def update(self):
        """Get the latest data and updates the state."""

        if self._thread.states:
            default = None
            self._target_temperature = self._thread.states[self._id].get('desired_temperature', default)
            self._current_temperature = self._thread.states[self._id].get('temperature', default)
            self._mode = self._thread.states[self._id].get('mode', 'auto')
            self._signal_strength = self._thread.states[self._id].get('signal_strenth', default)
            self._last_updated = self._thread.states[self._id].get('last_updated', default)
            self._battery_low = self._thread.states[self._id].get('battery_low', default)
            self._display_actual_temprature = self._thread.states[self._id].get('display_actual_temperature', default)
            self._dstsetting = self._thread.states[self._id].get('dstsetting', default)
            self._is_locked = self._thread.states[self._id].get('is_locked', default)
            self._langateway = self._thread.states[self._id].get('langateway', default)
            self._rferror = self._thread.states[self._id].get('rferror', default)
            self._until = self._thread.states[self._id].get('until_str', default)