import pusherclient
import json
import logging
import threading
import requests


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
log.addHandler(handler)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Signal(object):
    """
    Base Signal Class
    """
    __metaclass__ = Singleton

    def __init__(self):
        self.callbacks = []

    @classmethod
    def subscribe(cls, callback):
        instance = cls()
        instance.callbacks.append(callback)

    @classmethod
    def update(cls, message):
        raise NotImplementedError('You need to implement `update(cls, message=None) for class %s' % cls)

    @classmethod
    def publish(cls, message):
        instance = cls()
        [cb(message) for cb in instance.callbacks]


class JSONSignal(Signal):
    """
    JSON Signal
    """
    @classmethod
    def update(cls, message):
        processed_message = json.loads(message)
        cls.publish(processed_message)


class ObjectSignal(Signal):
    """
    Object Signal
        - refreses `x` seconds
    """
    def __init__(self):
        super(ObjectSignal, self).__init__()
        self.source = None
        self.update_interval = None

    def fetch(self):
        response = requests.get(self.source)
        response.raise_for_status()
        self.update(response.json())
        self.timer.start()  # Restart timer

    @classmethod
    def subscribe(cls, callback):
        super(ObjectSignal, cls).subscribe(callback)
        cls().timer.start()

    def update(self, message):
        self.publish(message)

    @property
    def timer(self):
        return threading.Timer(self.update_interval, self.fetch)


class OrderBook(JSONSignal):
    """
    Order Book Signal
    """
    pass


class Trades(JSONSignal):
    """
    Trade Signal
    """
    pass


class Ticker(ObjectSignal):
    """
    Live Ticker object, signal
        - refreshes every 10 seconds
    """
    def __init__(self):
        super(Ticker, self).__init__()

        self.source = 'https://www.bitstamp.net/api/ticker/'
        self.update_interval = 5

        self.last_check_timestamp = None
        self.daily_high = None
        self.daily_low = None
        self.daily_vwap = None
        self.daily_volume = None

    @classmethod
    def update(cls, message):
        instance = cls()
        instance.daily_high = float(message['high'])
        instance.daily_low = float(message['low'])
        instance.daily_vwap = float(message['vwap'])
        instance.daily_volume = float(message['volume'])
        instance.last_check_timestamp = int(message['timestamp'])

        cls.publish(instance)


class Transactions(ObjectSignal):
    """
    Transactions signal,
        - refreshes every 1 min
    """
    def __init__(self):
        super(Transactions, self).__init__()
        self.source = 'https://www.bitstamp.net/api/transactions/?time=hour'
        self.update_interval = 60


def connection_handler(data):
    global pusher

    order_book = pusher.subscribe('order_book')
    order_book.bind('data', OrderBook.update)

    live_trades = pusher.subscribe('live_trades')
    live_trades.bind('trade', Trades.update)


pusher = pusherclient.Pusher('de504dc5763aeef9ff52', log_level=logging.WARNING)
pusher.connection.bind('pusher:connection_established', connection_handler)
pusher.connect()