# Copyright (C) 2019 Chintalagiri Shashank
#
# This file is part of Tendril.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
Paths Configuration Options
===========================
"""


from tendril.utils.config import ConfigOption
from tendril.utils import log
logger = log.get_logger(__name__, log.DEFAULT)

depends = ['tendril.config.core']


config_elements_mq = [
    ConfigOption(
        'MQ_SERVER_HOST',
        "'localhost'",
        "RabbitMQ Server Host"
    ),
    ConfigOption(
        'MQ_SERVER_PORT',
        "5672",
        "RabbitMQ Server Port"
    ),
    ConfigOption(
        'MQ_SERVER_VIRTUALHOST',
        "'tendril'",
        "RabbitMQ Server VirtualHost to use. All MQ Connections from tendril will use this virtual "
        "host unless locally overridden in some as yet unspecified way."
    ),
    ConfigOption(
        'MQ_SERVER_USERNAME',
        "'tendril'",
        "RabbitMQ Server Username to use."
    ),
    ConfigOption(
        'MQ_SERVER_PASSWORD',
        "'tendril'",
        "RabbitMQ Server Password to use."
    ),
    ConfigOption(
        'MQ_SERVER_SSL',
        "True",
        "Whether to use SSL when connecting to the RabbitMQ Server."
    ),
    ConfigOption(
        'MQ_SERVER_EXCHANGE',
        "'tendril.topic'",
        "RabbitMQ Server Exchange to use. All MQ Connections from tendril will use this exchange "
        "unless locally overridden in some as yet unspecified way."
    ),
]


def load(manager):
    logger.debug("Loading {0}".format(__name__))
    manager.load_elements(config_elements_mq,
                          doc="Tendril RabbitMQ Configuration")
