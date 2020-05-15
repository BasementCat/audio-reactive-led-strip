import threading
import atexit
import logging
import sys

from werkzeug.serving import is_running_from_reloader


logger = logging.getLogger(__name__)

threads = []


class Thread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop_event = threading.Event()
        # if is_running_from_reloader():
        #     logger.debug("Not starting %s - running from reloader", self.__class__.__name__)
        #     return
        if 'run' not in sys.argv:
            logger.debug("Not starting %s, not in run command", self.__class__.__name__)
            return
        threads.append(self)
        logger.debug("Set up %s", self.__class__.__name__)
        self.setup()
        logger.info("Start %s", self.__class__.__name__)
        self.start()

    def setup(self):
        pass

    def loop(self):
        pass

    def run(self):
        while not self.stop_event.is_set():
            self.loop()


def _quit():
    for t in threads:
        logger.debug("Stopping %s", t.__class__.__name__)
        t.stop_event.set()
    for t in threads:
        logger.debug("Joining %s", t.__class__.__name__)
        t.join()

    logger.info("All threads have exited")


atexit.register(_quit)
