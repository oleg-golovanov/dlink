# -*- coding: utf-8 -*-


import logging
import copy


class ColoredFormatter(logging.Formatter):
    """
    Класс для цветного вывода результатов работы в консоль.
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


logger = logging.getLogger('dlink')
