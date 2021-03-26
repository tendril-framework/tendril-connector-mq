

import json
from twisted.application import service

from tendril.asynchronous.services.mq import PikaService
from tendril.asynchronous.services.mq import default_pika_parameters

from tendril.asynchronous.utils.logger import TwistedLoggerMixin
from tendril.config import MQ_SERVER_EXCHANGE

_application_name = "engine-storage-influxdb"
application = service.Application(_application_name)

ps = PikaService(default_pika_parameters())
ps.setServiceParent(application)


class InfluxDBStorageEngine(service.Service, TwistedLoggerMixin):
    def __init__(self):
        super(InfluxDBStorageEngine, self).__init__()
        self.amqp = None

    def respond(self, msg):
        self.log.info(json.loads(msg.body)['equipmentName'])
        self.amqp.send_message(MQ_SERVER_EXCHANGE, 'rabbitwisted', msg.body)

    def startService(self):
        amqp_service = self.parent.getServiceNamed("amqp") # pylint: disable=E1111,E1121
        self.amqp = amqp_service.getFactory()
        self.amqp.read_messages(MQ_SERVER_EXCHANGE, "monitoring.#", self.respond)


ts = InfluxDBStorageEngine()
ts.setServiceParent(application)
