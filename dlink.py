# -*- coding: utf-8 -*-


import os
import time
import re
import logging
import socket

import paramiko
from pysnmp.proto.rfc1902 import IpAddress, Integer, OctetString
import pyparsing as pp

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

        :param ip: ip адрес целевого оборудования
        :param community_read: имя community для чтения параметров по протоколу snmp
        :param community_write: имя community для записи параметров по протоколу snmp
        :param tftp_server: ip адрес сервера, на котором запущен демон TFTP
        :param config_load_method: метод загрузки конфигурационного файла из папки
                                   TFTP сервера
        :param tftp_path: путь к папке TFTP сервера
        :param username: имя пользователя для авторизации на сервер TFTP по протоколу ssh
        :param password: пароль пользователя для авторизации на сервер TFTP по протоколу ssh
        """

        self.ip = ip
        self.tftp_server = tftp_server
        self.config_load_method = config_load_method
        self.tftp_path = tftp_path
        self.username = username
        self.password = password
        self.snmp = snmp.Snmp(self.ip, community_read, community_write, timeout=3)

        self.chassis = service.Chassis()
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
        except snmp.SnmpException as snmp_exc:
            logging.error(snmp_exc)
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
        except snmp.SnmpException as snmp_exc:
            logging.error(snmp_exc)
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
                    port_index = int(index)
                    port_tuple = service.ports_int_2_ports_tuple(port_index)
                    port_str = service.ports_tuple_2_ports_str(
                        *port_tuple
                    )
                    self.ports[port_index] = service.Port(port_str)
                    self.ports[port_index]['port'] = port_index
                    self.ports[port_index]['speed'] = int(speed / 1000000)
                    # возможные статусы
                    # 1: up
                    # 2: down
                    # 3: testing
                    # 4: unknown
                    # 5: dormant
                    # 6: notPresent
                    # 7: lowerLayerDown
                    self.ports[port_index]['status'] = int(status)
                    self.ports[port_index]['alias'] = str(alias)
                    result += port_tuple

            self.ports.ports_tuple = service.ports_tuple_minimize(*result)

            logging.info(
                '%s - набор портов оборудования определен успешно' % self.ip
            )

    def get_config(self, timeout=10):
        """
        Метод для получения конфигурационного файла целевого оборудования.
        В методе определены oid'ы используемого оборудования.
        Метод работает следующим образом - по snmp запрашивается oid_sysname
        и по нему определяется тип оборудования, по типу оборудования
        запрашиваются соответствующие oid и на указанный TFTP сервер
        закачивается конфигурационный файл оборудования, далее он считывается
        в виде строки и удаляется с сервера.

        :param timeout: таймаут на получение конфигурационного файла

        :rtype: строка с конфигурационным файлом оборудования
        """

        try:
            if not self.eqp_type:
                self.get_eqp_type()

            if not self.firmware:
                self.get_firmware_version()

        except DlinkInitException as dlink_exc:
            logging.error(dlink_exc)
            raise DlinkConfigException(
                self.ip, 'дальнейшая работа с оборудованием невозможна'
            )

        cfg_file_name = 'config-%s.cfg' % self.ip

        # набор oid'ов для конфигурации обрудования DES-3*** на отдачу
        # конфигурационного файла на TFTP сервер
        oids_des = (
            ('1.3.6.1.4.1.171.12.1.2.1.1.3.3', IpAddress(self.tftp_server)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.4.3', Integer(2)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.5.3', OctetString(cfg_file_name)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.6.3', Integer(3)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.7.3', Integer(2)),
            ('1.3.6.1.4.1.171.12.1.2.1.1.8.3', Integer(3))
        )

        # набор oid'ов для конфигурации обрудования DGS-3*** на отдачу
        # конфигурационного файла на TFTP сервер
        oids_dgs = (
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.3.3', IpAddress(self.tftp_server)),
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.5.3', OctetString(cfg_file_name)),
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.8.3', Integer(2)),
            ('1.3.6.1.4.1.171.12.1.2.18.1.1.12.3', Integer(3))
        )

        # набор oid'ов для конфигурации обрудования DGS-3100 на отдачу
        # конфигурационного файла на TFTP сервер
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

        logging.info(
            '%s - конфигурационный файла получен успешно' % self.ip
        )
        self.chassis.config_file = result
        return result

    def parse_config(self):
        """
        Метод парсинга конфигурационного файла по
        ключевым опциям.
        """

        if not self.chassis.config_file:
            self.get_config()

        if not self.ports:
            self.get_ports()

        # определение значения по-умолчанию опции traffic_segmentation
        for port in self.ports:
            port.traffic_segmentation = self.ports.ports_tuple

        states = [
            'config',
            'enable',
            'disable',
            'create',
            'delete'
        ]

        keywords = [
            'vlan',
            'lldp',
            'stp',
            'traffic_segmentation',
            'loopdetect',
            'dhcp_local_relay'
        ]

        # common
        ports = pp.Word('0123456789:/(),-').setResultsName('ports')
        option = pp.Word(pp.alphanums + '_').setResultsName('option*')
        value = pp.Word(pp.alphanums + '_-').setResultsName('value*')
        state_lit = pp.Optional(pp.Literal('state').suppress())
        ports_lit = pp.Literal('ports').suppress()

        # general
        state = pp.oneOf(states).setResultsName('state')
        key = pp.oneOf(keywords).setResultsName('key')
        white = pp.White(' ').suppress()
        cr = pp.White('\r\n').suppress()
        other = pp.SkipTo(pp.lineEnd).setResultsName('other')
        # rules
        general = state + key + (cr ^ (white + other))
        general.ignore(pp.pythonStyleComment)
        general.ignore(pp.Regex(r'!.*'))

        # vlan
        vlan_name = pp.Word(pp.alphanums).setResultsName('name')
        vlan_action = pp.oneOf('delete add').setResultsName('action')
        vlan_type = pp.oneOf('untagged tagged').setResultsName('type')
        vlan_tag = pp.Word(pp.nums).setResultsName('tag')
        # rules
        vlan_create = vlan_name + pp.Literal('tag').suppress() + vlan_tag
        vlan_config = vlan_name + vlan_action + pp.Optional(vlan_type) + ports
        vlan = vlan_create ^ vlan_config

        # lldp rules
        lldp = pp.Optional(pp.Literal('ports').suppress() + ports) + option + value

        # traffic_segmentation
        ports_from = ports.setResultsName('ports_from')
        ports_to = (ports ^ pp.Literal('all')).setResultsName('ports_to')
        # rules
        traf_segm = ports_from + pp.Literal('forward_list').suppress() + ports_to

        # loopdetect
        loopdetect_general = pp.OneOrMore(option + state_lit + value)
        loopdetect_ports = pp.Literal('ports').suppress() + ports + option + value
        # rules
        loopdetect = loopdetect_ports ^ loopdetect_general

        # dhcp_local_relay rules
        dhcp_local_relay = pp.Literal('vlan').suppress() + vlan_name + option + value

        # stp rules
        stp = pp.Optional(ports_lit + ports) + pp.OneOrMore(option + value)
        stp.ignore(pp.Literal('mst') + pp.SkipTo(pp.lineEnd))

        logging.info(
            '%s - парсинг конфигурационного файла...' % self.ip
        )

        strings = general.searchString(self.chassis.config_file)

        for str_p in strings:
            try:
                if str_p.state in ['enable', 'disable']:
                    options_dict = {'state': str_p.state}
                    self.chassis.add_option(str_p.key, options_dict)

                else:
                    # vlan option processing
                    if str_p.key == 'vlan':
                        vlan_p = vlan.parseString(str_p.other)

                        if vlan_p.tag:
                            options_dict = {
                                vlan_p.name: {
                                    'tag': vlan_p.tag,
                                    'dhcp_local_relay': 'disable'
                                }
                            }
                            self.chassis.add_option('vlan', options_dict)

                        if vlan_p.action:
                            if vlan_p.action == 'add':
                                options_dict = {
                                    vlan_p.name: {
                                        'tag': self.chassis.vlan[vlan_p.name]['tag'],
                                        'type': vlan_p.type
                                    }
                                }
                                self.ports.add_options(vlan_p.ports, 'vlan', options_dict)

                            if vlan_p.action == 'delete':
                                self.ports.del_options(vlan_p.ports, 'vlan', vlan_p.name)

                    # lldp option processing
                    elif str_p.key == 'lldp':
                        lldp_p = lldp.parseString(str_p.other)

                        options_dict = dict(zip(lldp_p.option, lldp_p.value))

                        if lldp_p.ports:
                            self.ports.add_options(lldp_p.ports, 'lldp', options_dict)
                        else:
                            self.chassis.add_option('lldp', options_dict)

                    # traffic_segmentation option processing
                    elif str_p.key == 'traffic_segmentation':
                        traf_segm_p = traf_segm.parseString(str_p.other)

                        if traf_segm_p.ports_from == 'all':
                            ports_from = self.ports.ports_tuple
                        else:
                            ports_from = traf_segm_p.ports_from

                        if traf_segm_p.ports_to == 'all':
                            ports_to_tuple = self.ports.ports_tuple
                        else:
                            ports_to_tuple = service.ports_str_2_ports_tuple(
                                traf_segm_p.ports_to
                            )

                        self.ports.add_options(ports_from, 'traffic_segmentation', ports_to_tuple)

                    # loopdetect option processing
                    elif str_p.key == 'loopdetect':
                        loopdetect_p = loopdetect.parseString(str_p.other)

                        options_dict = dict(
                            zip(loopdetect_p.option, loopdetect_p.value)
                        )

                        if loopdetect_p.ports:
                            self.ports.add_options(loopdetect_p.ports ,'loopdetect', options_dict)
                        else:
                            self.chassis.add_option('loopdetect', options_dict)

                    # dhcp_local_relay option processing
                    elif str_p.key == 'dhcp_local_relay':
                        dhcp_p = dhcp_local_relay.parseString(str_p.other)
                        self.chassis.vlan[dhcp_p.name]['dhcp_local_relay'] = dhcp_p.value[0]

                    # stp option processing
                    elif str_p.key == 'stp':
                        stp_p = stp.parseString(str_p.other)

                        if 'instance_id' in list(stp_p.option):
                            options_dict = {
                                'instance_id': {
                                    stp_p.value[1]: {
                                        stp_p.option[0]: stp_p.value[0]
                                    }
                                }
                            }
                        else:
                            options_dict = dict(zip(stp_p.option, stp_p.value))

                        if stp_p.ports:
                            self.ports.add_options(stp_p.ports, 'stp', options_dict)
                        else:
                            self.chassis.stp.update(options_dict)

            # пропуск строк, не подпадающих под правила
            except pp.ParseException:
                pass

        for port in self.ports:
            port.define_port_type()

        logging.info(
            '%s - парсинг закончен' % self.ip
        )


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
