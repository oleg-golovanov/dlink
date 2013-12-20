#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
This is a tool to collect D-link's equipment configuration files

usage:
    run.py get-conf (<ip> ... | -i <file>) [-o <path>]
    run.py tune [-n] <ip> [<file>]

arguments:
    get-conf                  get configuration file from target equipment
    tune                      tune target equipment
    <ip>                      ip address of target equipment or sequence, separated by space
    <file>                    config file in json format such as default.json.sample
                              if don't use this option будет will be use settings_dir_path
                              parameter from settings.py

options:
    -h --help                 show this screen
    -i --input-file <file>    file with ip addresses, separated by carrier return
    -o --output <path>        output destination, can be path to file, if single ip,
                              or path to directory, if ip sequence or input-file option
                              is present; defaults:
                                 /dev/stdout for single ip,
                                 ./ for ip sequence or --input-file option
    -n --dry-run              print commands without execute it on equipment
"""


import sys
import logging
import os

from docopt import docopt

import settings
from lib import dlink, json_config, ping, telnet
from lib.logger import logger, ColoredFormatter


def ip_validate(arg):
    """
    Валидация ipv4 адресов
    """

    octets = arg.split('.')
    if len(octets) != 4:
        return False
    else:
        for octet in octets:
            if not octet.isdigit() or not 0 <= int(octet) <= 255:
                return False
        return True

def eqp_gen(arg):
    """
    Генератор инстансов класса Dlink
    """

    for _ip in arg:
        try:
            ping.ping(_ip)
        except ping.PingException as _exc:
            logger.error(_exc)
        else:
            yield dlink.Dlink(_ip, **settings.__dict__)

if __name__ == '__main__':
    logger.setLevel(settings.log_level)
    formatter = ColoredFormatter(
        fmt='%(asctime)s   %(levelname)-8s   %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    stdout_log = logging.StreamHandler(sys.stdout)
    stdout_log.setFormatter(formatter)
    logger.addHandler(stdout_log)

    args = docopt(__doc__)

    ip_addrs = args['<ip>']

    if args['--input-file']:
        try:
            with open(args['--input-file'], 'r') as _f:
                ip_addrs = [ip.strip() for ip in _f.readlines()]
        except IOError as exc:
            logger.critical(exc)
            sys.exit(0)

    # проверка ip адресов
    not_valid_ip = False
    for ip in ip_addrs:
        if not ip_validate(ip):
            logger.error(
                'Not valid ip address - %s' % ip
            )
            not_valid_ip = True

    if not_valid_ip:
        logger.critical(
            'Some ip addresses not valid'
        )
        sys.exit(1)

    if args['get-conf']:
        if not args['--output']:
            dir_path = '/dev/stdout' if len(ip_addrs) == 1 else '.'
            file_path = ''
        else:
            dir_path, file_path = os.path.split(args['--output'])
            if not dir_path:
                dir_path = '.'
            if len(ip_addrs) != 1:
                dir_path = args['--output']

        if not os.access(dir_path, os.F_OK):
            logger.critical(
                'No such directory: %r' % dir_path
            )
            sys.exit(1)

        if not os.access(dir_path, os.W_OK):
            logger.critical(
                'Permission denied: %r' % dir_path
            )
            sys.exit(1)

        for equipment in eqp_gen(ip_addrs):
            try:
                config = equipment.get_config()
            except dlink.DlinkConfigException as exc:
                logger.error(exc)
            else:
                if len(ip_addrs) == 1:
                    path = dir_path if not args['--output'] else os.path.join(dir_path, file_path)
                else:
                    path = os.path.join(dir_path, equipment.ip + '.cfg')
                with open(path, 'w') as _f:
                    _f.write(config)

    elif args['tune']:
        for equipment in eqp_gen(ip_addrs):
            try:
                if args['<file>']:
                    func, arg = json_config.Config.get_options, args['<file>']
                else:
                    config = json_config.Config(settings.settings_dir_path)
                    func, arg = config.load_options, equipment.get_eqp_type()
                cmd = equipment.analyze_config(func(arg))
                if not cmd:
                    logger.info('%s - tune not required' % equipment.ip)
                    sys.exit(0)
            except (json_config.ConfigException,
                    dlink.DlinkInitException,
                    dlink.DlinkConfigException) as exc:
                logger.critical(exc)
                sys.exit(1)

            if args['--dry-run']:
                print cmd
            else:
                conn = telnet.Telnet(equipment.ip, eqp_type=equipment.eqp_type)
                try:
                    conn.login(
                        settings.telnet_username,
                        settings.telnet_password
                    )
                except (telnet.TelnetConnException,
                        telnet.TelnetLoginException) as exc:
                    logger.critical(exc)
                    sys.exit(1)

                try:
                    conn.exec_cmd(*cmd)
                    conn.save_config()
                except telnet.TelnetConnException as exc:
                    logger.critical(exc)
                    sys.exit(1)
                conn.close()
