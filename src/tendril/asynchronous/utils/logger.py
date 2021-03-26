

from twisted.logger import Logger


def getLogger(name):
    return Logger(name)


class TwistedLoggerMixin(object):
    @property
    def log(self):
        if hasattr(self, '_log'):
            return self._log
        self._log = getLogger(self.__class__.__name__)
        return self._log
