# -*- coding: utf-8 -*-


import telnetlib
import logging
import time
import socket

import service


class Telnet(object):
    """
    Класс для работы с оборудованием D-link
    по протоколу telnet.
    """

    def __init__(self,
                 ip,
                 port=23,
                 timeout=10,
                 debug=0,
                 eqp_type='',
                 **kwargs):
        """
        Конструктор класса.

        :param ip: ip адрес целевого оборудования
        :param port: порт целевого оборудования, значение по умолчанию - 23
        :param timeout: таймаут сокета, значение по умолчанию - 10
        :param debug: включение debug режима работы telnet
        :param eqp_type: строка типа оборудования, необходима для
                         правильного выполнения команд на оборудовании
        """

        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.exp_timeout = None
        self.eqp_type = eqp_type
        self.debug = debug
        self.success_prompt = 'Success'
        self.greet_str = None
        self.user = None
        self.telnet = telnetlib.Telnet()

        self._is_open = False
        self._is_login = False

    def open(self):
        """
        Метод открытия telnet соединения.
        """

        try:
            self.telnet.open(self.ip, self.port, self.timeout)
        except socket.error as exc:
            raise TelnetConnException(self.ip, exc)
        else:
            self.telnet.set_debuglevel(self.debug)
            self._is_open = True
            logging.debug(
                '%s - telnet соединение успешно установлено' % self.ip
            )

    def login(self, user, passwd, exp_timeout=5):
        """
        Метод для авторизации на оборудовании.

        :param user: имя пользователя
        :param passwd: пароль пользователя
        :param exp_timeout: таймаут для метода telnet.expect
        """

        if not self._is_open:
            self.open()

        if not self._is_login:
            self.user = user
            self.exp_timeout = exp_timeout

            # авторизация на оборудовании
            self.telnet.write(user + '\n')
            if 'DGS-3100' in self.eqp_type:
                time.sleep(0.2)
            self.telnet.write(passwd + '\n')

            self.greet_str = self.get_greet_str()

            if not self.greet_str:
                raise TelnetLoginException(
                    self.ip, 'ошибка авторизации - %s' % user
                )
            else:
                logging.info(
                    '%s - авторизация прошла успешно - %s' % (self.ip, user)
                )
                self._is_login = True
                # хак для некоторого типа оборудования
                # проблема заключалась в том что оборудование подставляло
                # первый символ пароля в начало первой команды несколько раз (1-3)
                # поэтому первую команду делаем пустой и очищаем буфер
                self.telnet.write('\n')
                self.listen()

    def get_greet_str(self):
        """
        Метод определения строки приветствия в консоли.

        :rtype: строка
        """

        index, match, text = self.telnet.expect(
            ['(D\S+#)', ],
            self.exp_timeout
        )

        if index >= 0:
            return match.groups()[0]

    def exec_cmd(self, *args):
        """
        Метод выполнения команд и проверки их выполнения на оборудовании.

        :param args: массив строк команд
        """

        for cmd in args:
            if isinstance(cmd, unicode):
                cmd = str(cmd)
            self.telnet.write('%s\n' % cmd)

            try:
                recv = self.listen()
            except TelnetExecException as exc:
                logging.warning(exc)
            else:
                if self.success_prompt in recv:
                    logging.info(
                        '%s - %s - команда выполнена успешно' % (self.ip, cmd)
                    )
                    continue

            logging.warning(
                '%s - команда выполнена неуспешно - %s' %
                (self.ip, cmd)
            )
            if 'DGS-3100' in self.eqp_type:
                # данный кусок необходим для выхода из интерактивного
                # режима и сброса команды, т.к. в некотором типе
                # оборудования команда вновь вставляется в
                # командную строку для исправления
                self.telnet.write('q')
                # CTRL+Z
                self.telnet.write('\032')
                self.listen()

    def save_config(self):
        """
        Метод сохранения конфигурационного файла
        оборудования.
        """

        if not self._is_login:
            raise TelnetExecException(
                self.ip, 'не произведен вход на оборудование, сохранение '
                         'конфигурационного файла невозможно'
            )

        self.telnet.write('save\n')
        if 'DGS-3100' in self.eqp_type:
            time.sleep(0.2)
            self.telnet.write('y')

        try:
            recv = self.listen(15)
        except TelnetExecException as exc:
            logging.warning(exc)
        else:
            if self.success_prompt in recv or \
                            'Done' in recv:
                logging.info(
                    '%s - конфигурационный файл успешно сохранен' % self.ip
                )
                return

        logging.warning(
            '%s - не удалось сохранить конфигурационный файл' %
            self.ip
        )

    def close(self):
        """
        Метод закрытия telnet соединения, если оно открыто.
        """

        if self._is_open:
            # очистка буфера, необходима в случае
            # если соединение будет открываться повторно
            self.telnet.read_eager()
            self.telnet.close()
            self._is_login = False
            self._is_open = False
            logging.debug(
                '%s - telnet соединение успешно закрыто' % self.ip
            )

    def listen(self, timeout=None):
        """
        Метод получения данных с оборудования до обнаружения
        строки приветсвия или истечения времени таймаута.

        :param timeout: время в секундах
        :rtype: строка
        """

        buf = ''
        _c = 0

        if not timeout:
            timeout = self.exp_timeout

        while 1:
            try:
                data = self.telnet.read_eager()
            except EOFError:
                raise TelnetConnException(
                    self.ip, 'соединение закрыто удаленной стороной'
                )
            if data:
                buf += data
            else:
                if self.greet_str in buf:
                    return buf
                elif _c == timeout:
                    raise TelnetExecException(
                        self.ip, 'таймаут получения строки приветствия'
                    )
                else:
                    time.sleep(1)
                    _c += 1


class TelnetException(service.BasicException):
    """
    Базовое исключение Telnet.
    """
    pass


class TelnetConnException(TelnetException):
    """
    Исключение невозможности открытия telnet соединения.
    """
    pass


class TelnetLoginException(TelnetException):
    """
    Исключение ошибки входа на оборудование.
    """
    pass


class TelnetExecException(TelnetException):
    """
    Исключение выполнения команд на оборудовании.
    """
    pass
