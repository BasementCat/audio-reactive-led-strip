import json
import os
import threading


class Database(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(lights={}, effects={}, effect_groups={}, effect_stacks={})
        self.lock = threading.RLock()
        self.filename = None

    def open(self, filename):
        with self.lock:
            self.filename = filename
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as fp:
                    self.update(json.load(fp))

    def save(self):
        if not self.filename:
            return
        with self.lock:
            with open(self.filename + '.temp', 'w') as fp:
                json.dump(self, fp, indent=2)
            if os.path.exists(self.filename):
                os.unlink(self.filename)
            os.rename(self.filename + '.temp', self.filename)

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, type_, value, traceback):
        self.lock.release()


class ObjProxy(object):
    def __init__(self, data):
        super().__setattr__('data', data)

    def __hasattr__(self, k):
        return k in self.data

    def __getattr__(self, k):
        try:
            return self.data[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self.data[k] = v
