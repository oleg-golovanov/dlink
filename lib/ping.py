# -*- coding: utf-8 -*-


"""
Реализация ping была сделана именно как небольшая обертка на python
вокруг одноименной утилиты, в следствие того, что все сторонние питоновские
библиотеки реализующие icmp протокол были выполнены с использованием
raw sockets, что требовало выполнение сценариев с правами
суперпользователя, что небезопасно. На утилиту ping выставлен suid бит,
который позволяет использовать утилиту без прав суперпользователя.
Современные дистрибутивы линукс запрещают выставлять suid бит на файлы
скриптов, что также исключает использование сторонних библиотек.
"""


import re
import subprocess

import service


ping_path = '/bin/ping'


class Response(object):
    """
    Класс инкапсулирующий параметры
    ответа оборудования.
    """

    def __init__(self):
        self.packet_lost = 100
        self.ret_code = 1
        self.output = ''
        self.destination = ''
        self.destination_ip = ''


class PingException(service.BasicException):
    pass


def ping(target, count=3):
    """
    Функция в которой вызывается системная утилита ping и с помощью
    регулярных выражений из вывода извлекаются нужные параметры.
    Далее параметры записываюстся в экземпляр класса Response и возвращаются.
    В случае если оборудование недоступно, возбуждаетася исключение
    PingException.

    :param target: ip адрес целевого оборудования
    :param count: количество icmp запросов, значение по умолчанию - 3
    :rtype: экземпляр класса Response
    """

    proc = subprocess.Popen(
        [ping_path, '-c', str(count), target], stdout=subprocess.PIPE
    )
    # тут используется метод communicate для ожидания окончания
    # выполнения утилиты
    stdout, stderr = proc.communicate()

    resp = Response()
    resp.output = stdout

    re_space = r'\s+'
    re_other = r'[\S\s]+'
    re_dest = r'([\w.]+)'
    re_dest_ip = r'\(([\d.]+)\)'
    re_loss = r'(\d+)%\s+packet\s+loss'

    re_str = r'PING' + re_space + re_dest + re_space + re_dest_ip + \
        re_other + re_space + re_loss

    match = re.search(re_str, stdout)
    if match:
        resp.destination, resp.destination_ip, resp.packet_lost = \
            match.groups()
        if int(resp.packet_lost) < 65:
            resp.ret_code = 0
        else:
            raise PingException(
                target, 'оборудование недоступно'
            )

        return resp
    else:
        raise PingException(
            target, 'неверный ответ'
        )
