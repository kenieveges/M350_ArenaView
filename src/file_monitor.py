import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            self.callback()

def start_file_monitoring(log_path, callback):
    event_handler = LogFileHandler(callback)
    observer = Observer()
    observer.schedule(event_handler, path=str(log_path.parent), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()