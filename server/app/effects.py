import time


class Effect(object):
    def __init__(self, start_value, end_value, duration, done_value=None):
        self.start_time = time.time()
        self.end_time = self.start_time + duration
        self.start_value = start_value
        self.end_value = self.start_value if end_value is None else end_value
        self.duration = duration
        self.done_value_real = done_value or self.end_value
        try:
            len(self.start_value)
            self.single = False
        except TypeError:
            self.single = True
            self.start_value = [self.start_value]
            self.end_value = [self.end_value]
            self.done_value_real = [self.done_value_real]

    def __str__(self):
        return f'{self.start_value} -> {self.end_value} -> {self.done_value_real} for {self.end_time - self.start_time}s'

    @property
    def args(self):
        return {
            'duration': self.end_time - self.start_time,
            'start': self.start_value if self.single else ','.join(map(str, self.start_value)),
            'end': self.end_value if self.single else ','.join(map(str, self.end_value)),
            'done': self.done_value_real if self.single else ','.join(map(str, self.done_value_real)),
        }

    @property
    def value(self):
        if self.start_value == self.end_value:
            # Value won't change
            if self.single:
                return self.start_value[0]
            return self.start_value

        percent = (time.time() - self.start_time) / float(self.duration)
        val = []
        for i in range(len(self.start_value)):
            cval = ((self.end_value[i] - self.start_value[i]) * percent) + self.start_value[i]
            max_val = max(self.start_value[i], self.end_value[i])
            min_val = min(self.start_value[i], self.end_value[i])
            val.append(int(min(max(cval, min_val), max_val)))

        if self.single:
            return val[0]
        return val

    @property
    def done(self):
        return time.time() >= self.end_time

    @property
    def done_value(self):
        if self.single:
            return self.done_value_real[0]
        return self.done_value_real


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
