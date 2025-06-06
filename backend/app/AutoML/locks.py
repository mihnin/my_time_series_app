import threading

class ReadWriteLock:
    def __init__(self):
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0
        self._writer = False

    def acquire_read(self):
        with self._read_ready:
            while self._writer:
                self._read_ready.wait()
            self._readers += 1

    def release_read(self):
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self):
        with self._read_ready:
            while self._writer or self._readers > 0:
                self._read_ready.wait()
            self._writer = True

    def release_write(self):
        with self._read_ready:
            self._writer = False
            self._read_ready.notify_all()

global_automl_lock = ReadWriteLock()
