import time


class FPSCounter(object):
    def __init__(self, name, interval=5):
        self.name = name
        self.interval = interval
        self.iterations = []
        self.last_print = time.time()

    def __enter__(self):
        self.iterations.append(time.time())

    def __exit__(self, type_, value, traceback):
        now = time.time()
        self.iterations[-1] = now - self.iterations[-1]
        if now - self.last_print >= self.interval:
            fps = len(self.iterations) / self.interval
            avg_duration = sum(self.iterations) / len(self.iterations)
            print(f"{self.name} FPS: {fps}, {avg_duration * 1000} ms per")
            self.iterations = []
            self.last_print = now