import queue
import threading

_subscribers: dict[str, list[queue.Queue]] = {}
_lock = threading.Lock()


def subscribe(run_id: str) -> queue.Queue:
    q: queue.Queue = queue.Queue()
    with _lock:
        _subscribers.setdefault(run_id, []).append(q)
    return q


def notify(run_id: str, run_data: dict) -> None:
    with _lock:
        queues = _subscribers.get(run_id, [])
        for q in queues:
            q.put(run_data)


def complete(run_id: str) -> None:
    with _lock:
        queues = _subscribers.pop(run_id, [])
        for q in queues:
            q.put(None)
