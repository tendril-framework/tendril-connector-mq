# -*- coding: utf-8 -*-
# pylint: disable=C0111,C0103,R0205
"""
# based on:
#  - Pika Example from
#    https://github.com/pika/pika/blob/master/examples/twisted_service.py
#  - txamqp-helpers by Dan Siemon <dan@coverfire.com> (March 2010)
#    http://git.coverfire.com/?p=txamqp-twistd.git;a=tree
#  - Post by Brian Chandler
#    https://groups.google.com/forum/#!topic/pika-python/o_deVmGondk
#  - Pika Documentation
#    https://pika.readthedocs.io/en/latest/examples/twisted_example.html
"""


from twisted.internet import protocol
from twisted.application import internet
from twisted.application import service
from twisted.internet.defer import inlineCallbacks
from twisted.internet import ssl, defer

import pika
from pika import spec
from pika.adapters import twisted_connection
from pika.exchange_type import ExchangeType

from tendril.config import MQ_SERVER_HOST
from tendril.config import MQ_SERVER_PORT
from tendril.config import MQ_SERVER_VIRTUALHOST
from tendril.config import MQ_SERVER_USERNAME
from tendril.config import MQ_SERVER_PASSWORD

from tendril.asynchronous.utils.logger import TwistedLoggerMixin

PREFETCH_COUNT = 50


class PikaService(service.MultiService, TwistedLoggerMixin):
    name = 'amqp'

    def __init__(self, parameter):
        service.MultiService.__init__(self)
        self.parameters = parameter

    def startService(self):
        self.connect()
        service.MultiService.startService(self)

    def getFactory(self):
        return self.services[0].factory

    def connect(self):
        f = PikaFactory(self.parameters)
        if self.parameters.ssl_options:
            s = ssl.ClientContextFactory()
            serv = internet.SSLClient(  # pylint: disable=E1101
                host=self.parameters.host,
                port=self.parameters.port,
                factory=f,
                contextFactory=s)
        else:
            serv = internet.TCPClient(  # pylint: disable=E1101
                host=self.parameters.host,
                port=self.parameters.port,
                factory=f)
        serv.factory = f
        f.service = serv  # pylint: disable=W0201
        name = '%s%s:%d' % ('ssl:' if self.parameters.ssl_options else '',
                            self.parameters.host, self.parameters.port)
        serv.__repr__ = lambda: '<AMQP Connection to %s>' % name
        serv.setName(name)
        serv.setServiceParent(self)


class PikaProtocol(twisted_connection.TwistedProtocolConnection, TwistedLoggerMixin):
    connected = False
    name = 'AMQP:Protocol'

    def __init__(self, factory, parameters):
        self._channel = None
        super(PikaProtocol, self).__init__(parameters)
        self.factory = factory

    @inlineCallbacks
    def connectionReady(self):
        self._channel = yield self.channel()
        yield self._channel.basic_qos(prefetch_count=PREFETCH_COUNT)
        self.connected = True
        yield self._channel.confirm_delivery()
        for (
                exchange,
                routing_key,
                callback,
        ) in self.factory.read_list:
            yield self.setup_read(exchange, routing_key, callback)

        self.send()

    @inlineCallbacks
    def read(self, exchange, routing_key, callback):
        """Add an exchange to the list of exchanges to read from."""
        if self.connected:
            yield self.setup_read(exchange, routing_key, callback)

    @inlineCallbacks
    def setup_read(self, exchange, routing_key, callback):
        """This function does the work to read from an exchange."""
        if exchange:
            yield self._channel.exchange_declare(
                exchange=exchange,
                exchange_type=ExchangeType.topic,
                durable=True,
                auto_delete=False)

        yield self._channel.queue_declare(queue=routing_key, durable=True)
        if exchange:
            yield self._channel.queue_bind(queue=routing_key, exchange=exchange)
            yield self._channel.queue_bind(
                queue=routing_key, exchange=exchange, routing_key=routing_key)

        (
            queue,
            _consumer_tag,
        ) = yield self._channel.basic_consume(
            queue=routing_key, auto_ack=False)
        d = queue.get()
        d.addCallback(self._read_item, queue, callback)
        d.addErrback(self._read_item_err)

    def _read_item(self, item, queue, callback):
        """Callback function which is called when an item is read."""
        d = queue.get()
        d.addCallback(self._read_item, queue, callback)
        d.addErrback(self._read_item_err)
        (
            channel,
            deliver,
            _props,
            msg,
        ) = item

        # log.msg(
        #     '%s (%s): %s' % (deliver.exchange, deliver.routing_key, repr(msg)),
        #     system='Pika:<=')
        d = defer.maybeDeferred(callback, item)
        d.addCallbacks(lambda _: channel.basic_ack(deliver.delivery_tag),
                       lambda _: channel.basic_nack(deliver.delivery_tag))

    @staticmethod
    def _read_item_err(error):
        print(error)

    def send(self):
        """If connected, send all waiting messages."""
        if self.connected:
            while self.factory.queued_messages:
                (
                    exchange,
                    r_key,
                    message,
                ) = self.factory.queued_messages.pop(0)
                self.send_message(exchange, r_key, message)

    @inlineCallbacks
    def send_message(self, exchange, routing_key, msg):
        """Send a single message."""
        # log.msg(
        #     '%s (%s): %s' % (exchange, routing_key, repr(msg)),
        #     system='Pika:=>')
        yield self._channel.exchange_declare(
            exchange=exchange,
            exchange_type=ExchangeType.topic,
            durable=True,
            auto_delete=False)
        prop = spec.BasicProperties(delivery_mode=2)
        try:
            yield self._channel.basic_publish(
                exchange=exchange,
                routing_key=routing_key,
                body=msg,
                properties=prop)
        except Exception as error:  # pylint: disable=W0703
            self.log.error('Error while sending message: %s' % error, system=self.name)


class PikaFactory(protocol.ReconnectingClientFactory, TwistedLoggerMixin):
    name = 'AMQP:Factory'

    def __init__(self, parameters):
        self.parameters = parameters
        self.client = None
        self.queued_messages = []
        self.read_list = []

    def startedConnecting(self, connector):
        self.log.info('Started to connect.', system=self.name)

    def buildProtocol(self, addr):
        self.resetDelay()
        self.log.info('Connected', system=self.name)
        self.client = PikaProtocol(self, self.parameters)
        return self.client

    def clientConnectionLost(self, connector, reason): # pylint: disable=W0221
        self.log.warn('Lost connection.  Reason: %s' % reason.value, system=self.name)
        protocol.ReconnectingClientFactory.clientConnectionLost(
            self, connector, reason)

    def clientConnectionFailed(self, connector, reason):
        self.log.error(
            'Connection failed. Reason: %s' % reason.value, system=self.name)
        protocol.ReconnectingClientFactory.clientConnectionFailed(
            self, connector, reason)

    def send_message(self, exchange=None, routing_key=None, message=None):
        self.queued_messages.append((exchange, routing_key, message))
        if self.client is not None:
            self.client.send()

    def read_messages(self, exchange, routing_key, callback):
        """Configure an exchange to be read from."""
        self.read_list.append((exchange, routing_key, callback))
        if self.client is not None:
            self.client.read(exchange, routing_key, callback)


def default_pika_parameters():
    return pika.ConnectionParameters(
        host=MQ_SERVER_HOST,
        port=MQ_SERVER_PORT,
        virtual_host=MQ_SERVER_VIRTUALHOST,
        credentials=pika.PlainCredentials(MQ_SERVER_USERNAME, MQ_SERVER_PASSWORD))
