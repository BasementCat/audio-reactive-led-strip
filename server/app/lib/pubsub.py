import uuid


events = {}
last_conditions = {}


def subscribe(event, callback, condition=None):
    events.setdefault(event, []).append((str(uuid.uuid4()), callback, condition))


# def unsubscribe(event, callback):
#     # probably not needed
#     # TODO: if needed, update to handle last_conditions
#     evs = list(events.keys()) if event is None else [event]
#     for ev in evs:
#         to_remove = []
#         for cb, cond in events[ev]:
#             if cb is callback:
#                 to_remove.append((cb, cond))
#         for v in to_remove:
#             events[ev].remove(v)

def publish(event, *args, **kwargs):
    for id, cb, cond in events.get(event, []):
        new_ka = dict(kwargs)
        do_call = True
        if cond is not None:
            # Check the condition, if it's different from the last check, call the callback
            do_call = False
            res = cond(event, *args, **kwargs)
            new_ka['condition'] = res
            if id in last_conditions:
                if res != last_conditions[id]:
                    # Condition result is different, call the callback
                    do_call = True
            else:
                # No prior result, call the callback
                do_call = True
            last_conditions[id] = res

        if do_call:
            cb(*args, **new_ka)
