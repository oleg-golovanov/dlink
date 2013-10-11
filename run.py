#!/usr/bin/env python
# -*- coding: utf-8 -*-


import argparse
import logging
import os

import dlink
import settings
import service
import ping


def ip_validate(arg):
    """
    Валидация ipv4 адресов
    """

    octets = arg.split('.')
    if len(octets) != 4:
        return False
    else:
        for octet in octets:
            if not octet.isdigit():
                return False
            if not 0 <= int(octet) <= 255:
                return False
        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="""This is a tool to collect D-link's equipment configuration files"""
    )

    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        '--ip',
        metavar='',
        help='ip address of target equipment or sequence, separated by comma',
    )
    source.add_argument(
        '--input-file',
        metavar='',
        help='file with ip addresses, separated by carrier return',
        type=argparse.FileType('r')
    )

    parser.add_argument(
        '--output',
        metavar='',
        help='''
        output destination, can be path to file, if single ip,
        or path to directory, if ip sequence or input-file option
        is present; defaults:
        /dev/stdout for single ip,
        ./ for ip sequence or --input-file option
        '''
    )

    args = parser.parse_args()

    if args.ip:
        ip_addrs = args.ip.split(',')
    else:
        ip_addrs = [ip.strip() for ip in args.input_file.readlines()]

    # проверка ip адресов
    not_valid_ip = False
    for ip in ip_addrs:
        if not ip_validate(ip):
            logging.error('Not valid ip address - %s' % ip)
            not_valid_ip = True

    if not_valid_ip:
        logging.critical('Some ip addresses not valid')
        parser.exit(1)

    if not args.output:
        dir_path = '/dev/stdout' if len(ip_addrs) == 1 else '.'
        file_path = ''
    else:
        dir_path, file_path = os.path.split(args.output)
        if not dir_path:
            dir_path = '.'
        if len(ip_addrs) != 1:
            dir_path = args.output

    if not os.access(dir_path, os.F_OK):
        logging.critical('No such directory: %r' % dir_path)
        parser.exit(1)

    if not os.access(dir_path, os.W_OK):
        logging.critical('Permission denied: %r' % dir_path)
        parser.exit(1)

    for ip in ip_addrs:
        try:
            ping.ping(ip)
        except ping.PingException as exc:
            logging.error(exc)
        else:
            equipment = dlink.Dlink(ip, **settings.__dict__)
            try:
                config = equipment.get_config()
            except dlink.DlinkConfigException as exc:
                logging.error(exc)
            else:
                if len(ip_addrs) == 1:
                    path = dir_path if not args.output else os.path.join(dir_path, file_path)
                else:
                    path = os.path.join(dir_path, ip + '.cfg')
                with open(path, 'w') as _f:
                    _f.write(config)
