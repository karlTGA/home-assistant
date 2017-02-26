import logging
import queue
import voluptuous as vol
from os import path

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (ATTR_ENTITY_ID)
from homeassistant.helpers.entity import Entity
from homeassistant.config import load_yaml_config_file


#REQUIREMENTS = ['maxcul==0.1.1']
REQUIREMENTS = ['https://github.com/karlTGA/MaxCul-Python/archive/develop.zip#maxcul==0.1.2']

CUBE_ID = 0x123456
MAX = None
DOMAIN = 'max'

CONF_CULPATH = 'culpath'
CONF_BAUDRATE = 'baudrate'

DEFAULT_BAUDRATE = 38400
DEFAULT_CULPATH = "/dev/ttyUSB0"

"""Max Device Types"""
MAX_CUBE = "Cube"
MAX_THERMOSTAT = "HeatingThermostat"
MAX_THERMOSTAT_PLUS = "HeatingThermostatPlus"
MAX_WALLTHERMOSTAT = "WallMountedThermostat"
MAX_SHUTTERCONTACT = "ShutterContact"
MAX_PUSHBUTTON = "PushButton"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BAUDRATE, default=DEFAULT_BAUDRATE): cv.positive_int,
        vol.Required(CONF_CULPATH, default=DEFAULT_CULPATH): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

"""Const for set assocition service"""
ATTR_TARGET_ID = 'target_id'
ATTR_TARGET_TYPE = 'target_type'

SERVICE_SET_MAX_ASSOCIATION = 'set_association'
SET_MAX_ASSOCIATION_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_TARGET_ID): cv.entity_id,
})

"""Const for set_config_temperature service"""
ATTR_COMFORT_TEMPERATURE = 'comfort_temperature'
ATTR_ECO_TEMPERATURE = 'eco_temperature'
ATTR_MAX_TEMPERATURE = 'max_temperature'
ATTR_MIN_TEMPERATURE = 'min_temperature'
ATTR_MEASUREMENT_OFFSET = 'measurement_offset'
ATTR_WINDOW_OPEN_TEMPERATURE = 'window_open_temperature'
ATTR_WINDOW_OPEN_DURATION = 'window_open_duration'

SERVICE_SET_MAX_CONFIG_TEMPERATURE = 'set_config_temperature'
SET_MAX_CONFIG_TEMPERATURE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    vol.Required(ATTR_COMFORT_TEMPERATURE):vol.Coerce(float),
    vol.Required(ATTR_ECO_TEMPERATURE): vol.Coerce(float),
    vol.Required(ATTR_MAX_TEMPERATURE): vol.Coerce(float),
    vol.Required(ATTR_MIN_TEMPERATURE): vol.Coerce(float),
    vol.Required(ATTR_MEASUREMENT_OFFSET): vol.Coerce(float),
    vol.Required(ATTR_WINDOW_OPEN_TEMPERATURE): vol.Coerce(float),
    vol.Required(ATTR_WINDOW_OPEN_DURATION): cv.positive_int
})


def setup(hass, config):

    conf = config[DOMAIN]
    culpath = conf.get(CONF_CULPATH)
    baudrate = conf.get(CONF_BAUDRATE)

    descriptions = load_yaml_config_file(
        path.join(path.dirname(__file__), 'services.yaml')).get(DOMAIN)

    """Define the set_association service"""
    def set_association(service):
        """associate the thermostat with a other device"""
        from maxcul.messages import AddLinkPartnerMessage

        entity_id = service.data.get(ATTR_ENTITY_ID)
        target_id = service.data.get(ATTR_TARGET_ID)

        dev1 = None
        dev2 = None
        for dev in MAX.devices:
            if dev.entity_id == entity_id:
                dev1 = dev
            elif dev.entity_id == target_id:
                dev2 = dev

        if dev1 is None or dev2 is None:
            return

        msg = AddLinkPartnerMessage(0xB9, 0, CUBE_ID, dev1.id, 0)
        msg.counter = 0xB9
        msg.sender_id = CUBE_ID
        msg.receiver_id = dev1.id
        msg.group_id = 0
        payload = {
            'assocDevice': dev2.id,
            'assocDeviceType': dev2.type
        }
        MAX.thread.command_queue.put((msg, payload))

        msg = AddLinkPartnerMessage(0xB9, 0, CUBE_ID, dev2.id, 0)
        payload = {
            'assocDevice': dev1.id,
            'assocDeviceType': dev1.type
        }
        MAX.thread.command_queue.put((msg, payload))

    hass.services.register(DOMAIN, SERVICE_SET_MAX_ASSOCIATION, set_association, descriptions.get(SERVICE_SET_MAX_ASSOCIATION), schema=SET_MAX_ASSOCIATION_SCHEMA)

    """Define the set_config_temperature service"""
    def set_config_temperature(service):
        """associate the thermostat with a other device"""
        from maxcul.messages import ConfigTemperaturesMessage

        entity_id = service.data.get(ATTR_ENTITY_ID)
        comfort_temperature = service.data.get(ATTR_COMFORT_TEMPERATURE)
        eco_temperature = service.data.get(ATTR_ECO_TEMPERATURE)
        max_temperature = service.data.get(ATTR_MAX_TEMPERATURE)
        min_temperature = service.data.get(ATTR_MIN_TEMPERATURE)
        measurement_offset = service.data.get(ATTR_MEASUREMENT_OFFSET)
        window_open_temperature = service.data.get(ATTR_WINDOW_OPEN_TEMPERATURE)
        window_open_duration = service.data.get(ATTR_WINDOW_OPEN_DURATION)

        entity = None
        for dev in MAX.devices:
            if dev.entity_id == entity_id:
                entity = dev

        if entity is None or entity.type in ["Cube", "ShutterContact", "PushButton"]:
            return

        msg = ConfigTemperaturesMessage(0xB9, 0, CUBE_ID, entity.id, 0)
        payload = {
            'comfort_Temperature': comfort_temperature,
            'eco_Temperature': eco_temperature,
            'max_Temperature': max_temperature,
            'min_Temperature': min_temperature,
            'measurement_Offset': measurement_offset,
            'window_Open_Temperatur': window_open_temperature,
            'window_Open_Duration': window_open_duration
        }
        MAX.thread.command_queue.put((msg, payload))
        entity.set_max_temp(max_temperature)
        entity.set_min_temp(min_temperature)

    hass.services.register(DOMAIN, SERVICE_SET_MAX_CONFIG_TEMPERATURE, set_config_temperature, descriptions.get(SERVICE_SET_MAX_CONFIG_TEMPERATURE), schema=SET_MAX_CONFIG_TEMPERATURE_SCHEMA)


    global MAX
    if MAX is None:
        MAX = MaxCul(culpath, baudrate)
        return True
    else:
        return False

class MaxCul(Entity):
    def __init__(self, culpath, baudrate):
        """Setup the Max cul platform."""
        from maxcul.communication import CULMessageThread
        from logbook.more import ColorizedStderrHandler
        self._log_handler = ColorizedStderrHandler()
        self._log_handler.push_application()
        self._name = 'Max CUL Stick'
        self._devices = []
        self._queue = queue.Queue()
        self._thread = CULMessageThread(self._queue, culpath, baudrate)
        self._thread.start()
        # message_thread.join()

    @property
    def name(self):
        """Return the name of the max thermostat, if any."""
        return self._name

    @property
    def thread(self):
        """Return the unit of measurement that is used."""
        return self._thread

    @property
    def queue(self):
        """Return the unit of measurement that is used."""
        return self._queue

    @property
    def devices(self):
        """Return the unit of measurement that is used."""
        return self._devices



