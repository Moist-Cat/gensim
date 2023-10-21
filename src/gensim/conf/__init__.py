from pathlib import Path
import os
import importlib
import json


class ImproperlyConfigured(Exception):
    pass


ENVIRONMENT_VARIABLE = "GENSIM_SETTINGS_MODULE"


class Settings:
    def __init__(self, settings_module=None):

        self.SETTINGS_MODULE = (
            settings_module or os.environ.get(ENVIRONMENT_VARIABLE) or "gensim.conf.pro"
        )

        mod = importlib.import_module(self.SETTINGS_MODULE)

        for setting in dir(mod):
            if setting.isupper():  # only allow upper-case settings
                settings_value = getattr(mod, setting)
                setattr(self, setting, settings_value)

    def __repr__(self):
        return f'{self.__class__.__name__}: "{self.SETTINGS_MODULE}"'


settings = Settings()
