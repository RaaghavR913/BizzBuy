"""
In-process SSE fan-out (single Uvicorn worker). Thread-safe publish from job threads
via the main event loop. For multi-worker production, replace with Redis pub/sub.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

_lock = threading.Lock()
_subscribers: dict[str, list[asyncio.Queue[str]]] = {}
_main_loop: asyncio.AbstractEventLoop | None = None
_QUEUE_MAX = 32


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def subscribe(analysis_id: str) -> asyncio.Queue[str]:
    q: asyncio.Queue[str] = asyncio.Queue(maxsize=_QUEUE_MAX)
    with _lock:
        _subscribers.setdefault(analysis_id, []).append(q)
    return q


def unsubscribe(analysis_id: str, q: asyncio.Queue[str]) -> None:
    with _lock:
        lst = _subscribers.get(analysis_id)
        if not lst:
            return
        try:
            lst.remove(q)
        except ValueError:
            return
        if not lst:
            _subscribers.pop(analysis_id, None)


def publish_json_from_thread(analysis_id: str, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, default=str)
    loop = _main_loop
    if loop is None:
        return

    def _fanout() -> None:
        with _lock:
            queues = list(_subscribers.get(analysis_id, ()))
        for q in queues:
            while True:
                try:
                    q.put_nowait(data)
                    break
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                except (RuntimeError, ValueError):
                    break

    try:
        loop.call_soon_threadsafe(_fanout)
    except RuntimeError:
        pass
