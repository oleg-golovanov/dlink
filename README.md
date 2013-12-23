# DESCRIPTION

    Данное ПО является инструментом для сбора конфигурационных файлов оборудования D-Link
    и настройки этого оборудования на основе файлов настройки.
    This Software is a tool to collect D-link's equipment configuration files
    and tune this equipment, based on settings files.

    Требования / Requirements:
    * python 2.7
    * paramiko >= 1.11.0
    * pysnmp >= 4.2.4
    * pyparsing >= 2.0.1
    * docopt >= 0.6.1
    * dictdiffer >= 0.0.3
      https://github.com/fatiherikli/dictdiffer

# USAGE

    Скопируйте файл settings.py.sample, назвав новый - settings.py, ознакомьтесь
    с комментариями и заполните нужные поля.
    Copy settings.py.sample file to settings.py, read comments and fill necessary
    fields

    - Для сбора конфигурационных файлов ознакомтесь с
      For collect configuration files read

        ./run.py --help

    - Для настройки оборудования скопируйте default.json.sample, отредактируйте
      и используйте получившийся файл как аргумент в команде run.py tune. Либо
      создайте отдельную папку, пропишите путь в setting.py в соответствующее поле,
      на основе default.json.sample создайте файлы настройки необходимых типов
      оборудования (например des-3200.json, dgs-3100.json и т.д.) и обязательно
      default.json (он будет применяться если не будет найден настроечный файл
      настрваиваемого типа оборудования).
      Copy default.json.sample, edit and use result as argument in run.py tune
      command for tune equipment. Or create directory, fill necessary field
      in settings.py by path of this dir, create settings files, based on
      settings.py.sample, for various types of equipment (for example des-3200.json,
      dgs-3100.json etc.) and necessarily default.json (it will use if settings
      file of tuned equipment will not be found).

# LICENSE

    The MIT License (MIT)

    Copyright (c) 2013 Oleg Golovanov <golovanov.ov@gmail.com>

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
