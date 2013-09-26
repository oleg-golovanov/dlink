# -*- coding: utf-8 -*-


import os
import time
import re
import logging
import socket

import paramiko
from pysnmp.proto.rfc1902 import IpAddress, Integer, OctetString

import service
import snmp


class Dlink(object):
    """
    Класс для работы с оборудованием d-link.
    """

    def __init__(self,
                 ip,
                 community_read,
                 community_write,
                 tftp_server='',
                 config_load_method='local',
                 tftp_path='',
                 username='',
                 password='',
                 **kwargs):
        """
        Конструктор класса.
        В нем инициализируется объект для
        работы с оборудованием по snmp.

        :param ip: ip адрес целевого оборудования
        :param community_read: имя community для чтения параметров по протоколу snmp
        :param community_write: имя community для записи параметров по протоколу snmp
        :param tftp_server: ip адрес сервера, на котором запущен демон tftp
        :param config_load_method: метод загрузки конфигурационного файла из папки
                                   tftp сервера
        :param tftp_path: путь к папке tftp сервера
        :param username: имя пользователя для авторизации на сервер tftp по протоколу ssh
        :param password: пароль пользователя для авторизации на сервер tftp по протоколу ssh
        """

        self.ip = ip
        self.tftp_server = tftp_server
        self.config_load_method = config_load_method
        self.tftp_path = tftp_path
        self.username = username
        self.password = password
        self.snmp = snmp.Snmp(self.ip, community_read, community_write, timeout=3)

        self.ports = service.Ports()
        self.eqp_type = None
        self.firmware = None

    def get_eqp_type(self):
        """
        Метод получения строки типа оборудования.

        :rtype: строка с типом оборудования
        """

        # oid, возвращающий строку с названием оборудования
        oid_sysname = '1.3.6.1.2.1.1.1.0'

        try:
            snmp_result = self.snmp.get(oid_sysname)
        except snmp.SnmpOtherException as snmp_exc:
            logging.critical(snmp_exc)
            raise DlinkInitException(
                self.ip, 'не удалось определить тип оборудования'
            )
        else:
            logging.debug(
                '%s - запрос oid sysname выполнен успешно' % self.ip
            )
            eqp_type = str(snmp_result[0][1])
            match = re.search(r'[A-z]+-\d+[A-z]*', eqp_type)
            if match:
                eqp_type = match.group()
            logging.info(
                '%s - тип оборудования определен - %s' % (self.ip, eqp_type)
            )

            self.eqp_type = eqp_type
            return eqp_type

    def get_firmware_version(self):
        """
        Метод получения строки с версией прошивки.

        :rtype: строка с версией прошивки оборудования
        """

        if not self.eqp_type:
            self.get_eqp_type()

        if 'DGS-3100' in self.eqp_type:
            # rlPhdUnitGenParamSoftwareVersion from rlphysdescription.mib
            firmware_oid = '1.3.6.1.4.1.171.10.94.89.89.53.14.1.2.1'
        elif 'DES-3010G' in self.eqp_type:
            # Agent.mib
            firmware_oid = '1.3.6.1.4.1.171.12.1.2.7.1.2.257'
        else:
            # probeSoftwareRev from RFC2021.mib
            firmware_oid = '1.3.6.1.2.1.16.19.2.0'

        try:
            snmp_result = self.snmp.get(firmware_oid)
        except snmp.SnmpException:
            raise DlinkInitException(
                self.ip, '%s - не удалось определить версию прошивки оборудования'
            )
        else:
            logging.debug(
                '%s - запрос oid firmware выполнен успешно' % self.ip
            )
            version = str(snmp_result[0][1])
            version = re.search(r'\d[\w.]+', version).group()
            logging.debug(
                '%s - версия прошивки оборудования определена - %s'
                % (self.ip, version)
            )
            self.firmware = version
            return version

    def get_ports(self):
        """
        Метод получения количества физических портов целевого оборудования.
        """

        result = []

        oids_interface = (
            '1.3.6.1.2.1.2.2.1.1',
            '1.3.6.1.2.1.2.2.1.3',
            '1.3.6.1.2.1.2.2.1.5',
            '1.3.6.1.2.1.2.2.1.8',
            '1.3.6.1.2.1.31.1.1.1.1',
            '1.3.6.1.2.1.31.1.1.1.18'
        )

        # запрашиваем оборудование по snmp на предмет имен
        # и типов интерфейсов
        try:
            snmp_result = self.snmp.next(*oids_interface)
        except snmp.SnmpException as snmp_exc:
            logging.error(snmp_exc)
        else:
            logging.debug(
                '%s - запрос oids_interface выполнен успешно' % self.ip
            )
            for (o1_1, index), (o1_3, _type), (o1_5, speed), \
                (o1_8, status), (o2_1, name), (o2_18, alias) in snmp_result:
                # выбираем только физические интерфейсы
                # 6 - ethernetCsmacd
                # 117 - gigabitEthernet
                if int(_type) in [6, 117] and 'ch' not in str(name):
                    port_tuple = service.ports_int_2_ports_tuple(int(index))
                    port_str = service.ports_tuple_2_ports_str(
                        *port_tuple
                    )
                    self.ports[port_str] = service.Port(port_str)
                    self.ports[port_str]['port'] = int(index)
                    self.ports[port_str]['speed'] = int(speed / 1000000)
                    # возможные статусы
                    # 1: up
                    # 2: down
                    # 3: testing
                    # 4: unknown
                    # 5: dormant
                    # 6: notPresent
                    # 7: lowerLayerDown
                    self.ports[port_str]['status'] = int(status)
                    self.ports[port_str]['alias'] = str(alias)
                    result += port_tuple

            self.ports['ports'] = service.ports_tuple_minimize(*result)

            logging.debug(
                '%s - набор портов оборудования определен успешно' % self.ip
            )

    def get_config(self, timeout=10):
        """
        Метод для получения конфигурационного файла целевого оборудования.
        В методе определены oid'ы используемого оборудования.
        Метод работает следующим образом - по snmp запрашивается oid_sysname
        и по нему определяется тип оборудования, по типу оборудования
        запрашиваются соответствующие oid и на указанный tftp сервер
        закачивается конфигурационный файл оборудования, далее он считывается
        в виде массива строк и удаляется с сервера. Массив строк слегка
        обрабатывается и возвращается как результат.

        :param timeout: таймаут на получение конфигурационного файла

        :rtype: строка с конфигурационным файлом оборудования
        """

        try:
            if not self.eqp_type:
                self.get_eqp_type()

            if not self.firmware:
                self.get_firmware_version()

        except DlinkInitException as dlink_exc:
            logging.critical(dlink_exc)
            raise DlinkConfigException(
                self.ip, 'дальнейшая работа невозможна'
            )

        cfg_file_name = 'config-%s.cfg' % self.ip

        # набор oid'ов для конфигурации обрудования DES-3*** на отдачу
        # конфигурационного файла на tftp сервер
        oids_des = (
            ('1.3.6.1.4.1.171.12.1.2.1.1.3.3', IpAddress(self.tftp_server)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.4.3', Integer(2)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.5.3', OctetString(cfg_file_name)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.6.3', Integer(3)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.7.3', Integer(2)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.8.3', Integer(3))
        )

        # набор oid'ов для конфигурации обрудования DGS-3*** на отдачу
        # конфигурационного файла на tftp сервер
        oids_dgs = (
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.3.3', IpAddress(self.tftp_server)),
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.5.3', OctetString(cfg_file_name)),
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.8.3', Integer(2)),
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.12.3', Integer(3))
        )

        # набор oid'ов для конфигурации обрудования DGS-3100 на отдачу
        # конфигурационного файла на tftp сервер
        oids_tg = (
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.4.1', IpAddress(self.ip)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.5.1', Integer(1)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.6.1', OctetString('startupConfig')),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.7.1', Integer(3)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.8.1', Integer(3)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.9.1', IpAddress(self.tftp_server)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.10.1', Integer(1)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.11.1', OctetString(cfg_file_name)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.12.1', Integer(3)),
            ('1.3.6.1.4.1.171.10.94.89.89.87.2.1.17.1', Integer(4))
        )

        cfg_file_end = 'End of configuration file'

        # TG
        if 'DGS-3100' in self.eqp_type:
            current_eqp = oids_tg
            # переопределяем окончание конфигурационного файла для
            # оборудования DGS-3100
            cfg_file_end = '! VOICE VLAN'
        # DES-3526, DES-3528, DES-3010G
        elif ('DES-3526' or 'DES-3528' or 'DES-3010G') in self.eqp_type:
            current_eqp = oids_des
        # DGS
        elif 'DGS-3' in self.eqp_type:
            current_eqp = oids_dgs
        # DES
        elif 'DES-3' in self.eqp_type:
            if self.firmware:
                if float(self.firmware[:4]) >= 4.00:
                    current_eqp = oids_dgs
                else:
                    current_eqp = oids_des
            else:
                current_eqp = oids_des
        else:
            raise DlinkConfigException(
                self.ip, 'не удалось определить нужный набор oid '
                'для настройки оборудования на отдачу конфигурационного файла'
            )

        # получаем конфиг, если определить тип оборудование не получилось,
        # то выводим соответствующее сообщение
        try:
            self.snmp.set(*current_eqp)
        except snmp.SnmpSetTimeoutException as snmp_exc:
            logging.critical(snmp_exc)
            raise DlinkConfigException(
                self.ip, 'не удалось настроить оборудование на отдачу '
                'конфигурационного файла'
            )

        logging.debug(
            '%s - оборудование настроено на отдачу конфигурационного файла '
            'успешно' % self.ip
        )

        result = None

        file_path = os.path.join(self.tftp_path, cfg_file_name)

        if self.config_load_method == 'local':
            FileDoesNotExistExc = OSError
            open_func = open
            rm_func = os.remove

            # заглушка
            def cap():
                pass

            conn_close_func = cap

        elif self.config_load_method == 'ssh':
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.load_system_host_keys()

            try:
                ssh.connect(
                    self.tftp_server,
                    username=self.username,
                    password=self.password
                )
            except socket.error as exc:
                logging.error(
                    '%s - %s' % (self.ip, exc)
                )
                raise DlinkConfigException(
                    self.ip, 'не удалось подключиться к серверу %s'
                    'по протоколу ssh' % self.tftp_server
                )

            sftp = ssh.open_sftp()

            FileDoesNotExistExc = IOError
            open_func = sftp.open
            rm_func = sftp.remove
            conn_close_func = ssh.close

        else:
            raise DlinkConfigException(
                self.ip, 'неверно указан метод загрузки конфигурационного файла'
            )

        _c = 0

        while 1:
            time.sleep(1)
            if _c < timeout:
                try:
                    _f = open_func(file_path, mode='r')
                # обработка ситуации когда файл еще не создан
                except FileDoesNotExistExc as exc_fdn:
                    _c += 1
                else:
                    cfg_file = _f.read()
                    if cfg_file_end in cfg_file:
                        _f.close()
                        rm_func(file_path)
                        conn_close_func()
                        result = cfg_file.replace('\r\n', '\n')
                        break
                    else:
                        end_not_obtained = True
                        _c += 1
                        _f.close()
            else:
                conn_close_func()

                if 'exc_fdn' in locals():
                    raise DlinkConfigException(
                        self.ip, 'конфигурационного файла %s не существует '
                        'на сервере %s' %
                        (file_path, self.tftp_server)
                    )
                elif 'end_not_obtained' in locals():
                    raise DlinkConfigException(
                        self.ip, 'конец файла %s не получен за %s секунд' %
                        (file_path, timeout)
                    )
                else:
                    raise DlinkConfigException(
                        self.ip, 'не удалось получить конфигурационный файл '
                        '%s с сервера %s по неизвестной причине' %
                        (file_path, self.tftp_server)
                    )

        logging.debug(
            '%s - конфигурационный файла получен успешно' % self.ip
        )
        return result


class DlinkException(service.BasicException):
    """
    Базовое исключение.
    """
    pass


class DlinkInitException(DlinkException):
    """
    Исключение получения типа и версии прошивки оборудования.
    """
    pass


class DlinkConfigException(DlinkException):
    """
    Исключение получения конфигурационного файла оборудования.
    """
    pass
