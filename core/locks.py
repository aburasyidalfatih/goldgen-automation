"""
Cross-platform single-instance file lock.

Dipakai agar auto_poster / auto_reply / auto_analyzer tidak pernah jalan dobel
(baik lewat APScheduler internal maupun eksekusi manual dari CLI).
"""

from core.config import DATA_DIR


class ProcessLock:
    """File lock sederhana. Pakai sebagai context manager:

        with ProcessLock('poster') as lock:
            if not lock.acquired:
                return
            ...
    """

    def __init__(self, name):
        DATA_DIR.mkdir(exist_ok=True)
        self.path = DATA_DIR / f"{name}.lock"
        self.acquired = False
        self._handle = None
        self._unlock = None

    def acquire(self):
        try:
            self._handle = open(self.path, 'w')
        except Exception:
            # Kalau file lock tidak bisa dibuka, jangan blokir pekerjaan utama
            self.acquired = True
            return True

        try:
            import fcntl
            try:
                fcntl.flock(self._handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (IOError, OSError):
                self._close()
                return False
            self._unlock = lambda h: fcntl.flock(h, fcntl.LOCK_UN)
        except ImportError:
            import msvcrt
            try:
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            except (IOError, OSError):
                self._close()
                return False
            self._unlock = lambda h: msvcrt.locking(h.fileno(), msvcrt.LK_UNLCK, 1)

        self.acquired = True
        return True

    def release(self):
        if self._handle and self._unlock:
            try:
                self._unlock(self._handle)
            except Exception:
                pass
        self._close()
        self.acquired = False

    def _close(self):
        if self._handle:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False
