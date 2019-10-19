# For threading
# from threading import Thread as BaseThread, Event
# from queue import Queue, Empty as QueueEmpty, Full as QueueFull

# For multiprocessing
from multiprocessing import Process as BaseThread, Event, Queue
from queue import Empty as QueueEmpty, Full as QueueFull

import signal


all_threads = {}
stop_event = Event()


class Thread(BaseThread):
    def __init__(self, name, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.config = config
        self.stop_event = stop_event
        self.queue = Queue(maxsize=1)
        self.is_output = False
        self.is_processor = False
        if name in all_threads:
            raise ValueError("Duplicate name")
        all_threads[name] = self

    def unrestrict_queue(self, num=None):
        if num:
            self.queue = Queue(maxsize=num)
        else:
            self.queue = Queue()

    # def create_output(self):
    #     self.queue = Queue(maxsize=1)
    #     output_queues[self.name] = self.queue

    # def call_on(self, name, fn, *args, **kwargs):
    #     # TODO: put this in a queue so it's called from the target thread, not the calling thread
    #     # TODO: maybe use the output queue, and attach an action to it
    #     t = all_threads.get(name, None)
    #     if t:
    #         fn = getattr(t, fn, None)
    #         if fn:
    #             fn(*args, **kwargs)


def send_to(thread_name, function, *args, **kwargs):
    if thread_name.startswith('@'):
        thread_name = thread_name[1:]
        for t in all_threads.values():
            if getattr(t, 'is_' + thread_name, False):
                try:
                    t.queue.put((function, args, kwargs), block=False)
                except QueueFull:
                    # print(f"Queue for {t.name} is full")
                    pass
    elif thread_name in all_threads:
        try:
            all_threads[thread_name].queue.put((function, args, kwargs), block=False)
        except QueueFull:
            # print(f"Queue for {thread_name} is full")
            pass


def get_main_thread_callbacks():
    for t in all_threads.values():
        if hasattr(t, 'main_thread'):
            yield t.main_thread


def start_threads():
    for t in all_threads.values():
        if not t.is_alive():
            t.start()


def stop_threads():
    stop_event.set()


def wait_threads():
    stop_threads()
    for t in all_threads.values():
        if t.is_alive():
            t.join()
