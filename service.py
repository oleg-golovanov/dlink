# -*- coding: utf-8 -*-


import logging
import copy
import sys
from collections import OrderedDict

from settings import log_level


class Base(object):
    """
    Базовый класс для классов Ports, Port.
    """

    def __setitem__(self, key, value):
        """
        Метод реализующий добавление атрибутов объекта класса как у словаря
        class_instance['123'] = 123.
        """

        self.__dict__[key] = value

    def __getitem__(self, key):
        """
        Метод реализующий получения атрибутов объекта класса как у словаря
        class_instance['123'] => 123.
        """

        return self.__dict__[key]

    def __delitem__(self, key):
        """
        Метод реализующий удаление атрибутов объекта класса как у словаря
        del class_instance['123'].
        """

        del self.__dict__[key]


class Ports(Base):
    """
    Класс объединяющий множество портов оборудования.
    """

    def __init__(self, *args, **kwargs):
        """
        Конструктор класса, заменяющий словарь на упорядоченный словарь.
        """

        self.__dict__ = OrderedDict(*args, **kwargs)

    def _get_ports(self):
        """
        Метод получения портов.

        :rtype: массив объектов класса Port
        """

        ports = [
            i for i in self.__dict__.values()
            if isinstance(i, Port)
        ]

        return ports

    def __nonzero__(self):
        """
        Метод проверки существования портов.
        """

        if self._get_ports():
            return True
        else:
            return False

    def __iter__(self):
        """
        Метод для реализации обхода портов.

        :rtype: итератор объектов класса Port
        """

        return iter(self._get_ports())


class Port(Base):
    """
    Класс описывающий конкретный порт оборудования.
    """

    def __init__(self, name=''):
        """
        Конструктор класса.

        :param name: строковое имя порта
        """

        self['name'] = name


class BasicException(Exception):
    """
    Класс базового исключения.
    """

    def __init__(self, ip, msg):
        """
        Конструктор класса.

        :param ip: ip адрес целевого оборудования
        :param msg: сообщение об ошибке
        """
        self.ip = ip
        self.msg = msg

    def __str__(self):
        return '%s - %s' % (self.ip, self.msg)


class ColoredFormatter(logging.Formatter):
    """
    Класс для цветного вывода работы программы в консоль.
    """

    START = '\x1b['
    END = '\x1b[0m'

    LEVELCOLOR = {
        'WARNING': START + '93m%-8s' + END,
        'ERROR': START + '31m%-8s' + END,
        'CRITICAL': START + '91;4;1m%-8s' + END
    }

    def __init__(self, *args, **kwargs):
        logging.Formatter.__init__(self, *args, **kwargs)

    def format(self, record):
        record = copy.copy(record)
        levelname = record.levelname
        if levelname in self.LEVELCOLOR:
            record.levelname = self.LEVELCOLOR[levelname] % levelname
        return logging.Formatter.format(self, record)


def ports_tuple_minimize(*arg):
    """
    Функция для свертывания конструкция вида
    [(1, 1, 2), (1, 2, 3), (1, 3, 4), (2, 1, 2), (2, 2, 3)]
    в конструкцию [(1, 1, 4), (2, 1, 3)].

    :param arg: кортеж или массив кортежей
    :rtype: массив кортежей
    """

    range_min = [list(arg[0])]
    count = 0
    for module, port_from, port_to in arg[1:]:
        if module == range_min[count][0]:
            if port_from == range_min[count][2]:
                range_min[count][2] = port_to
            else:
                range_min.append([module, port_from, port_to])
                count += 1
        else:
            range_min.append([module, port_from, port_to])
            count += 1

    return [tuple(i) for i in range_min]


def ports_tuple_2_ports_str(*arg, **kwargs):
    """
    Функция преобразования конструкции вида [(1, 1, 4), (2, 1, 3)]
    в строку 1:1-1:3,2:1-2:2 или 1:(1-3),2:(1-2), если указать
    параметр style='tg'.

    :param arg: кортеж или массив кортежей
    :rtype: строка
    """

    # присвоение элементу 'style' словаря 'kwargs'
    # значения по умолчанию 'normal'
    kwargs.setdefault('style', 'normal')

    range_min = ports_tuple_minimize(*arg)
    range_str = []
    for module, port_from, port_to in range_min:
        if port_to - port_from == 1:
            range_str.append('%d:%d' % (module, port_from))
        else:
            if kwargs['style'] == 'tg':
                range_str.append(
                    '%d:(%d-%d)' % (module, port_from, port_to - 1)
                )
            else:
                range_str.append(
                    '%d:%d-%d:%d' % (module, port_from, module, port_to - 1)
                )

    return ','.join(i for i in range_str)

def ports_int_2_ports_tuple(*arg):
    """
    Функция преобразования массива номеров портов [1, 20, 64, 150] или
    extreme style [1001, 1020, 1064, 3022]
    в конструкцию [(1, 1, 2), (1, 20, 21), (1, 64, 65), (3, 22, 23)].

    :param arg: массив или кортеж чисел
    :rtype: массив кортежей
    """
    result = []

    for port in arg:
        # extreme style
        if port > 1000:
            module = port / 1000 - 1
            port_begin = port % 1000
        # d-link style
        else:
            module = port / 64
            if port % 64 == 0:
                module -= 1
            port_begin = port - 64 * module

        port_end = port_begin + 1
        result.append((module + 1, port_begin, port_end))

    return result


logger = logging.getLogger()
logger.setLevel(log_level)
formatter = ColoredFormatter(
    fmt='%(asctime)s   %(levelname)-8s   %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
stdout_log = logging.StreamHandler(sys.stdout)
stdout_log.setFormatter(formatter)
logger.addHandler(stdout_log)
