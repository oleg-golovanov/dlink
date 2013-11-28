# -*- coding: utf-8 -*-


import logging
import copy
import sys
import re
import collections

import dictdiffer

from settings import log_level


class Base(object):
    """
    Базовый класс для классов Chassis, Ports, Port.
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


class Chassis(Base):
    """
    Класс для хранения глобальных опций и работы с ними.
    """

    def __init__(self):
        """
        Консруктор класса, в котором определяются значения
        по умолчанию.
        """

        self.config_file = None
        self.vlan = {
            'default': {
                'tag': 1
            }
        }
        self.lldp = {}
        self.loopdetect = {}
        self.dhcp_local_relay = {}
        self.stp = {}

    def add_option(self, key, option):
        """
        Метод добавления опции в набор по определенному ключу.

        :param key: ключ, к набору которого будет добавляться опция
        :param option: опция
        """

        self[key].update(option)

    def get_commands(self, option_dict):
        """
        Метод получения команд из набора настроек оборудования.

        :param option_dict: словарь с настройками оборудования
        :rtype: список строк
        """

        tune_dict = dict_substract(option_dict['global'], self.__dict__)
        commands = []

        for k, options in tune_dict.iteritems():
            for o, v in options.iteritems():
                if o == 'state':
                    commands.append('%s %s' % (v, k))
                elif o == 'instance_id':
                    for o1, v1 in v.iteritems():
                        if 'priority' in v1:
                            commands.append(
                                'config %s priority %s %s %s' % (k, v1['priority'], o, o1)
                            )
                else:
                    commands.append('config %s %s %s' % (k, o, v))

        return commands


class Ports(Base):
    """
    Класс объединяющий множество портов оборудования.
    """

    def __init__(self, *args, **kwargs):
        """
        Конструктор класса, заменяющий словарь на упорядоченный словарь.
        """

        self.__dict__ = collections.OrderedDict(*args, **kwargs)
        self.ports_tuple = None

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

    def add_options(self, ports, key, option):
        """
        Метод добавления опции в набор портов по определенному ключу.

        :param ports: набор портов в любом формате
        :param key: ключ, к набору которого будет добавляться опция
        :param option: опция
        """

        ports_int = ports_any_2_ports_int(ports)

        for port_id in ports_int:
            if isinstance(self.__dict__[port_id][key], dict):
                self.__dict__[port_id][key].update(option)
            else:
                self.__dict__[port_id][key] = option

    def del_options(self, ports, key, option):
        """
        Метод удаления опции из набора портов по определенному ключу.

        :param ports: набор портов в любом формате
        :param key: ключ, из набора которого будет удаляться опция
        :param option: опция
        """

        ports_int = ports_any_2_ports_int(ports)

        for port_id in ports_int:
            del self.__dict__[port_id][key][option]

    def get_commands(self, option_dict):
        """
        Метод получения команд из набора настроек портов.

        :param option_dict: словарь с настройками оборудования
        :rtype: список строк
        """

        port_dict = option_dict['port']
        access_dict = option_dict['access']
        trunk_dict = option_dict['trunk']

        all_ports = []
        trunk_ports = []
        access_ports = []

        for p_tuple in enumerate(self, 1):
            all_ports.append(p_tuple)
            if p_tuple[1].port_type == 0:
                trunk_ports.append(p_tuple)
            else:
                access_ports.append(p_tuple)

        def create_commands(ports, options_dict):
            commands = []

            for k, options in options_dict.iteritems():
                for o, v in options.iteritems():
                    ports_int = []
                    for p_id, p in ports:
                        try:
                            pv = p[k][o]
                        except KeyError:
                            ports_int.append(p_id)
                        else:
                            if v != pv:
                                ports_int.append(p_id)

                    if ports_int:
                        ports_str = ports_tuple_2_ports_str(
                            *ports_int_2_ports_tuple(*ports_int)
                        )
                        commands.append(
                            'config %s ports %s %s %s' % (k, ports_str, o, v)
                        )

            return commands

        return create_commands(all_ports, port_dict) + \
               create_commands(trunk_ports, trunk_dict) + \
               create_commands(access_ports, access_dict)


class Port(Base):
    """
    Класс описывающий конкретный порт оборудования.
    """

    # типы портов
    #   trunk - 0
    #   access - 1

    def __init__(self, name=''):
        """
        Конструктор класса.

        :param name: строковое имя порта
        """

        self.name = name

        self.port_type = 0
        self.vlan = {
            'default': {
                'tag': 1,
                'type': 'untagged'
            }
        }
        self.traffic_segmentation = None
        self.lldp = {}
        self.loopdetect = None
        self.stp = {}

    def define_port_type(self):
        """
        Метод определения типа порта.
        Типы портов:
          trunk - 0
          access - 1
        """

        if not 'default' in self.vlan:
            self.port_type = 1


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

def ports_tuple_unminimize(*arg):
    """
    Функция обратная функции ports_tuple_minimize.
    То есть преобразовывает конструкцию вида [(1, 1, 4), (2, 1, 3)]
    в конструкцию [(1, 1, 2), (1, 2, 3), (1, 3, 4), (2, 1, 2), (2, 2, 3)].

    :param arg: кортеж или массив кортежей
    :rtype: массив кортежей
    """
    result = []

    for port_range in arg:
        module, port_begin, port_end = port_range
        for i in xrange(port_begin, port_end):
            result.append((module, i, i + 1))

    return result

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

def ports_str_2_ports_tuple(arg):
    """
    Функция обратная функции _ports_tuple_2_ports_str.
    То есть преобразовывает строку 1:1-1:3,2:1-2:2 или
    Cisco style Gi1/0/1-Gi1/0/3,Gi2/0/1-Gi2/0/2 или
    DGS-3100 (tg) style 1:(1-3),2:(1-2) или
    snmp style 1/1-1/3,1/65-1/66 в
    конструкцию [(1, 1, 4), (2, 1, 3)].

    ВНИМАНИЕ!!! При использовании snmp style записи портов,
    недопустим переход через модуль (в модуле максимум 64 порта)!
    Например - 1/5-1/66. Это приведет к некорректному результату.

    :param arg: строка
    :rtype: массив кортежей
    """
    result = []

    if ('(' and ')') in arg:
        # tg style
        for segm in arg.split('),'):
            module, ports = segm.split(':')
            module = int(module)
            ports = ports.replace('(', '').replace(')', '')

            for port in ports.split(','):
                try:
                    port_begin, port_end = port.split('-')
                except ValueError:
                    port_begin = port
                    port_end = None

                begin = int(port_begin)
                if not port_end:
                    end = begin + 1
                else:
                    end = int(port_end) + 1

                result.append((module, begin, end))

    elif ('Gi' or 'Fa') in arg:
        # cisco style
        cisco_re = re.compile(r'[a-zA-Z](\d+)/\d+/(\d+)')

        for port in arg.split(','):
            try:
                port_begin, port_end = port.split('-')
            except ValueError:
                port_begin = port
                port_end = None

            module, begin = cisco_re.search(port_begin).groups()
            module, begin = int(module), int(begin)

            if not port_end:
                end = begin + 1
            else:
                _module, end = cisco_re.search(port_end).groups()
                end = int(end) + 1

            result.append((module, begin, end))

    else:
        # normal style
        for port in arg.split(','):
            try:
                port_begin, port_end = port.split('-')
            except ValueError:
                port_begin = port
                port_end = None

            try:
                split_symbol = re.search(r'[/:]', port_begin).group()
                module, begin = port_begin.split(split_symbol)
                module = int(module)
                begin = int(begin)
            except (ValueError, AttributeError):
                module = 1
                begin = int(port_begin)

            try:
                end = int(port_end.split(split_symbol)[1]) + 1
            except AttributeError:
                end = begin + 1
            except UnboundLocalError:
                end = int(port_end) + 1

            if begin > 64:
                module, begin, __end = ports_int_2_ports_tuple(begin)[0]
                if not port_end:
                    end = __end
                else:
                    end -= 1
                    __module, __begin, end = ports_int_2_ports_tuple(end)[0]

            result.append((module, begin, end))

    return result

def ports_tuple_2_ports_int(*arg):
    """
    Функция обратная функции _ports_int_2_ports_tuple.
    То есть преобразовывает конструкцию вида
    [(1, 1, 2), (1, 20, 21), (1, 64, 65), (3, 22, 23)]
    в массив чисел [1, 20, 64, 150].

    :param arg: кортеж или массив кортежей
    :rtype: массив целых чисел
    """
    result = []

    arg_unmin = ports_tuple_unminimize(*arg)
    for port in arg_unmin:
        module, port_begin, port_end = port
        result.append(port_begin + 64 * (module - 1))

    return result

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

def ports_str_2_ports_int(arg):
    """
    Функция преобразования строки портов 1:1-1:3,2:1-2:2 в
    массив целых чисел [1, 2, 3, 65, 66]
    """

    return ports_tuple_2_ports_int(
        *ports_str_2_ports_tuple(arg)
    )

def ports_any_2_ports_int(arg):
    """
    Функция преобразования строки, массива кортежей или массива целых чисел
    в массив целых чисел.

    :param arg: строка, массив кортежей или массив целых чисел
    :rtype: массив целых чисел
    """
    result = None

    if arg:
        if isinstance(arg, str):
            result = ports_tuple_2_ports_int(
                *ports_str_2_ports_tuple(arg)
            )
        if isinstance(arg, list):
            if isinstance(arg[0], tuple):
                result = ports_tuple_2_ports_int(*arg)
            elif isinstance(arg[0], int):
                result = arg

    return result


def dict_substract(minuend, subtrahend):
    """
    Функция вычитания одного словаря из другого.
    уменьшаемое (minuend) - вычитаемое (subtrahend) = разность (difference)

        >>> result = dict_substract({'a': 'b', 'b': 'c'}, {'b': 'c'})
        >>> print(result)
        {'a': 'b'}

    """

    def factory():
        return collections.defaultdict(factory)
    destination = collections.defaultdict(factory)

    diff = (
        i for i in
        dictdiffer.diff(subtrahend, minuend)
        if i[0] in ['add', 'change', 'push']
    )

    def add(node, changes):
        for key, value in changes:
            dictdiffer.dot_lookup(destination, node)[key] = value

    def change(node, changes):
        dest = dictdiffer.dot_lookup(destination, node, parent=True)
        last_node = node.split('.')[-1]
        _, value = changes
        dest[last_node] = value

    def push(node, changes):
        dest = dictdiffer.dot_lookup(destination, node, parent=True) \
                         .setdefault(node, [])
        for val in changes:
            dest.append(val)

    patchers = {
        'add': add,
        'change': change,
        'push': push
    }

    for action, node, changes in diff:
        patchers[action](node, changes)

    return dict(destination)

logger = logging.getLogger()
logger.setLevel(log_level)
formatter = ColoredFormatter(
    fmt='%(asctime)s   %(levelname)-8s   %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
stdout_log = logging.StreamHandler(sys.stdout)
stdout_log.setFormatter(formatter)
logger.addHandler(stdout_log)
