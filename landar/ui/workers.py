from PySide6.QtCore import QThread, Signal

class ServiceWorker(QThread):
    """Run any slow service call off the UI thread. Keep a reference to the worker while it runs."""
    succeeded = Signal(object)
    failed = Signal(str)
    def __init__(self, fn, *args):
        super().__init__(); self.fn, self.args = fn, args
    def run(self):
        try: self.succeeded.emit(self.fn(*self.args))
        except Exception as e: self.failed.emit(str(e))
