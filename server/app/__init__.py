class Task(object):
    def __init__(self, name, config, *args, **kwargs):
        self.name = name
        self.config = config

    def start(self, data):
        pass

    def stop(self):
        pass

    def run(self, data):
        pass


class NoData(Exception):
    pass
