# -*- coding: utf-8 -*-


from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto.rfc1905 import NoSuchInstance

import service


class Snmp(object):
    """
    Класс для работы с оборудование по snmp.
    """

    def __init__(self, ip, community_read, community_write, timeout=1):
        """
        Конструктор класса.
        В нем инициализирутся генератор команд для pysnmp и
        сообщества (community) для чтения и записи параметров.

        :param ip: ip адрес целевого оборудования
        :param community_read: имя community для чтения параметров по протоколу snmp
        :param community_write: имя community для записи параметров по протоколу snmp
        :param timeout: время ожидания ответа от оборудования
        """

        self.ip = ip
        self.cmdGen = cmdgen.CommandGenerator()
        self.community_read = cmdgen.CommunityData(community_read)
        self.community_write = cmdgen.CommunityData(community_write)
        # объект для работы с обрудованием по snmp
        # в конструктор передается именно кортеж
        self.target = cmdgen.UdpTransportTarget((ip, 161), timeout=timeout)

    def get(self, oid):
        """
        Метод, реализующий get snmp запрос.

        :param oid: строка необходимого oid'а в цифровом виде
        :rtype: массив с одним кортежем, состоящим из объекта oid и
                объекта значения
        """

        errorIndication, errorStatus, errorIndex, varBinds = \
            self.cmdGen.getCmd(
                self.community_read,
                self.target,
                oid
            )
        if errorIndication:
            raise SnmpGetTimeoutException(
                self.ip, errorIndication
            )
        else:
            if errorStatus:
                raise SnmpOtherException(
                    self.ip, '%s at %s' %
                    (errorStatus.prettyPrint(),
                     errorIndex and varBinds[int(errorIndex) - 1] or '?')
                )
            else:
                if varBinds[0][1] == NoSuchInstance():
                    raise SnmpOtherException(
                        self.ip, 'указан неверный oid - %s' % oid
                    )
                else:
                    return varBinds

    def set(self, *oids):
        """
        Метод, реализующий set snmp запрос.

        :param oids: перечень кортежей из строки oid'а в цифровом виде и
                     объекта типа передаваемого параметра, например -
          ('1.3.6.1.4.1.171.12.1.2.1.1.6.3', pysnmp.proto.rfc1902.Integer(3))
        """

        errorIndication, errorStatus, errorIndex, varBinds = \
            self.cmdGen.setCmd(
                self.community_write,
                self.target,
                *oids
            )
        if errorIndication:
            raise SnmpSetTimeoutException(
                self.ip, errorIndication
            )
        else:
            if errorStatus:
                raise SnmpOtherException(
                    self. ip, '%s at %s' %
                    (errorStatus.prettyPrint(),
                     errorIndex and varBinds[int(errorIndex) - 1] or '?')
                )
            else:
                pass

    def next(self, *oids):
        """
        Метод, реализующий next snmp запрос.

        :param oids: перечень строк необходимых oid'ов в цифровом виде
        :rtype: массив с массивами, состоящими из одного кортежа, который в
                свою очередь состоит из объекта oid и объекта значения
        """

        errorIndication, errorStatus, errorIndex, varBinds = \
            self.cmdGen.nextCmd(
                self.community_read,
                self.target,
                *oids
            )
        if errorIndication:
            raise SnmpGetTimeoutException(
                self.ip, errorIndication
            )
        else:
            if errorStatus:
                raise SnmpOtherException(
                    self.ip, '%s at %s' %
                    (errorStatus.prettyPrint(),
                     errorIndex and varBinds[int(errorIndex) - 1] or '?')
                )
            else:
                if varBinds:
                    return varBinds
                else:
                    raise SnmpOtherException(
                        self.ip, 'указан неверный oid - %s' % oids
                    )


class SnmpException(service.BasicException):
    """
    Базовое исключение.
    """
    pass


class SnmpGetTimeoutException(SnmpException):
    """
    Исключение превышения времени ответа оборудования при запросе значения.
    """
    pass


class SnmpSetTimeoutException(SnmpException):
    """
    Исключение превышения времени ответа оборудования при установке значения.
    """
    pass


class SnmpOtherException(SnmpException):
    """
    Остальные исключения.
    Дифференцировать их далее не имело смысла.
    """
    pass
