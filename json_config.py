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

        :param path: путь к папке с конфигурационными файлами
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

    @staticmethod
    def get_options(path):
        """
        Метод формирования структуры данных из конфигурационного файла,
        указанного в пути.

        :param path: путь к файлу
        :rtype: словарь с настройками
        """

        try:
            with open(path, 'r') as _f:
                config_str = _f.read().lower()
                options = json.loads(config_str)
        except (IOError, ValueError) as exc:
            raise ConfigException(exc)
        else:
            return collections.defaultdict(dict, options)

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

        return self.get_options(c_file_path)


class ConfigException(Exception):
    """
    Базовое исключение.
    """
    pass
