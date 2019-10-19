events = {}


def subscribe(event, callback):
    events.setdefault(event, []).append(callback)


def unsubscribe(event, callback):
    # probably not needed
    evs = list(events.keys()) if event is None else [event]
    for ev in evs:
        try:
            while True:
                events[ev].remove(callback)
        except (KeyError, ValueError):
            pass

def publish(event, *args, **kwargs):
    for cb in events.get(event, []):
        cb(*args, **kwargs)
