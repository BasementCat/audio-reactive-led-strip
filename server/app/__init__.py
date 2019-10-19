class Task(object):
    def __init__(self, name, config, *args, **kwargs):
        self.name = name
        self.config = config

    def start(self):
        pass

    def stop(self):
        pass

    def run(self):
        pass
