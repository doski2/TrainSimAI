import ctypes
import datetime
import os
import sys
from typing import Any, Optional

# On Windows, use the standard library winreg. Avoid six.moves to satisfy type checkers.
if sys.platform == "win32":
    try:
        import winreg  # type: ignore[reportMissingImports]
    except Exception:  # pragma: no cover - unusual environments
        winreg = None  # type: ignore[assignment]
else:
    winreg = None  # type: ignore[assignment]


VALUE_CURRENT = 0
VALUE_MIN = 1
VALUE_MAX = 2


class RailDriver(object):
    # ctypes.CDLL handle loaded from raildriver.dll; None until __init__ completes
    dll: Optional[Any] = None

    _restypes = {
        "GetControllerList": ctypes.c_char_p,
        "GetLocoName": ctypes.c_char_p,
        "GetControllerValue": ctypes.c_float,
    }

    def __init__(self, dll_location=None):
        """
        Initializes the raildriver.dll interface.

        :param dll_location Optionally pass the location of raildriver.dll if in some custom location.
                            If not passed will try to guess the location by using the Windows Registry.
        """
        if not dll_location:
            if sys.platform != "win32" or winreg is None:
                raise EnvironmentError("Automatic discovery of raildriver.dll requires Windows registry (win32).")
            steam_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Valve\\Steam")
            steam_path = winreg.QueryValueEx(steam_key, "SteamPath")[0]
            railworks_path = os.path.join(steam_path, "steamApps", "common", "railworks", "plugins")
            dll_location = os.path.join(railworks_path, "raildriver.dll")
            if not os.path.isfile(dll_location):
                raise EnvironmentError("Unable to automatically locate raildriver.dll.")
        self.dll = ctypes.cdll.LoadLibrary(dll_location)
        # Configure ctypes return types
        for function_name, restype in self._restypes.items():
            getattr(self._get_dll(), function_name).restype = restype

    def __repr__(self):
        return "raildriver.RailDriver: {}".format(self.dll)

    def get_controller_index(self, name):
        for idx, n in self.get_controller_list():
            if n == name:
                return idx
        raise ValueError("Controller index not found for {}".format(name))

    def _get_dll(self):
        if self.dll is None:
            raise RuntimeError("RailDriver DLL is not loaded. Instantiate RailDriver correctly.")
        return self.dll

    def get_controller_list(self):
        """
        Returns an iterable of tuples containing (index, controller_name) pairs.

        Controller indexes start at 0.

        You may easily transform this to a {name: index} mapping by using:

        >>> controllers = {name: index for index, name in raildriver.get_controller_list()}

        :return enumerate
        """
        ret_str = self._get_dll().GetControllerList().decode()
        if not ret_str:
            return []
        return enumerate(ret_str.split("::"))

    def get_controller_value(self, index_or_name, value_type):
        """
        Returns current/min/max value of controller at given index or name.

        It is much more efficient to query using an integer index rather than string name.
        Name is fine for seldom updates but it's not advised to be used every second or so.
        See `get_controller_list` for an example how to cache a dictionary of {name: index} pairs.

        :param index_or_name integer index or string name
        :param value_type one of VALUE_CURRENT, VALUE_MIN, VALUE_MAX
        :return float
        """
        if not isinstance(index_or_name, int):
            index = self.get_controller_index(index_or_name)
        else:
            index = index_or_name
        return self._get_dll().GetControllerValue(index, value_type)

    def get_current_controller_value(self, index_or_name):
        """
        Syntactic sugar for get_controller_value(index_or_name, VALUE_CURRENT)

        :param index_or_name integer index or string name
        :return: float
        """
        return self.get_controller_value(index_or_name, VALUE_CURRENT)

    def get_current_coordinates(self):
        """
        Get current geocoordinates (lat, lon) of train

        :return: tuple (lat, lon)
        """
        return self.get_current_controller_value(400), self.get_current_controller_value(401)

    def get_current_fuel_level(self):
        """
        Get current fuel level of train

        :return: float
        """
        return self.get_current_controller_value(402)

    def get_current_gradient(self):
        """
        Get current gradient

        return: float
        """
        return self.get_current_controller_value(404)

    def get_current_heading(self):
        """
        Get current heading

        return: float
        """
        return self.get_current_controller_value(405)

    def get_current_is_in_tunnel(self):
        """
        Check if the train is currently (mostly) in tunnel

        :return: bool
        """
        return bool(self.get_current_controller_value(403))

    def get_current_time(self):
        """
        Get current time

        :return: datetime.time
        """
        hour = int(self.get_current_controller_value(406))
        minute = int(self.get_current_controller_value(407))
        second = int(self.get_current_controller_value(408))
        return datetime.time(hour=hour, minute=minute, second=second)

    def get_loco_name(self):
        """
        Returns the Provider, Product and Engine name.

        :return list
        """
        ret_str = self._get_dll().GetLocoName().decode()
        if not ret_str:
            return
        return ret_str.split(".:.")

    def get_max_controller_value(self, index_or_name):
        """
        Syntactic sugar for get_controller_value(index_or_name, VALUE_MAX)

        :param index_or_name integer index or string name
        :return: float
        """
        return self.get_controller_value(index_or_name, VALUE_MAX)

    def get_min_controller_value(self, index_or_name):
        """
        Syntactic sugar for get_controller_value(index_or_name, VALUE_MIN)

        :param index_or_name integer index or string name
        :return: float
        """
        return self.get_controller_value(index_or_name, VALUE_MIN)

    def set_controller_value(self, index_or_name, value):
        """
        Sets controller value

        :param index_or_name integer index or string name
        :param value float
        """
        if not isinstance(index_or_name, int):
            index = self.get_controller_index(index_or_name)
        else:
            index = index_or_name
        self._get_dll().SetControllerValue(index, ctypes.c_float(value))

    def set_rail_driver_connected(self, value):
        """
        Needs to be called after instantiation in order to exchange data with Train Simulator

        :param bool True to start exchanging data, False to stop
        """
        self._get_dll().SetRailDriverConnected(True)
