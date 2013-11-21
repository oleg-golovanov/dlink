# -*- coding: utf-8 -*-


import json
import os
import collections


class Config(object):
    """
    Класс для формирования необходимой для настройки оборудования
    структуры данных.
    """

    def __init__(self, path, default_config='default.json'):
        """
        Конструктор класса.

        :param path: путь до конфигурационного файла
        :param default_config: имя конфигурационного файла по умолчанию
        """

        self.path = path
        self.default = default_config

        try:
            self.c_config_files = os.listdir(path)
        except EnvironmentError as exc:
            raise ConfigException(exc)
        else:
            if self.default not in self.c_config_files:
                raise ConfigException(
                    'конфигурационный файл по-умолчанию %r отсутствует'
                    'в папке %r' % (self.default, self.path)
                )

    def load_options(self, eqp_type=None):
        """
        Метод формирования структуры данных из конфигурационного файла.

        :param eqp_type: строка типа оборудования
        :rtype: словарь с настройками
        """

        c_file_name = self.default
        if eqp_type:
            eqp_json = eqp_type.lower() + '.json'
            if eqp_json in self.c_config_files:
                c_file_name = eqp_json

        c_file_path = os.path.join(self.path, c_file_name)

        with open(c_file_path) as _f:
            config_str = _f.read().lower()
            options = json.loads(config_str)

        return collections.defaultdict(dict, options)


class ConfigException(Exception):
    """
    Базовое исключение.
    """
    pass
