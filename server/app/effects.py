import time


class Effect(object):
    def __init__(self, start_value, end_value, duration, done_value=None):
        self.start_time = time.time()
        self.end_time = self.start_time + duration
        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.done_value = done_value or end_value

    @property
    def value(self):
        if self.start_value == self.end_value:
            # Value won't change
            return self.start_value

        percent = (time.time() - self.start_time) / float(self.duration)
        val = ((self.end_value - self.start_value) * percent) + self.start_value
        max_val = max(self.start_value, self.end_value)
        min_val = min(self.start_value, self.end_value)
        return int(min(max(val, min_val), max_val))

    @property
    def done(self):
        return time.time() >= self.end_time


if __name__ == '__main__':
    print("UP:")
    e = Effect(0, 255, 1)
    while not e.done:
        print(e.value)
        time.sleep(0.05)

    print("UP2:")
    e = Effect(100, 200, 1)
    while not e.done:
        print(e.value)
        time.sleep(0.05)

    print("DOWN:")
    e = Effect(255, 0, 1)
    while not e.done:
        print(e.value)
        time.sleep(0.05)

    print("STATIC:")
    e = Effect(127, 127, 1)
    while not e.done:
        print(e.value)
        time.sleep(0.05)
