import signal
import sys
import threading
import traceback
from email.utils import formatdate


class SignalHandler:
    """Handles signal management and shutdown coordination."""

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(SignalHandler, cls).__new__(cls)
            cls._instance.shutdown_requested = False
        return cls._instance

    def __init__(self):
        """Initialize the signal handler."""
        if not hasattr(self, 'shutdown_requested'):
            self.shutdown_requested = False

    @staticmethod
    def format_exception(exc_type, exc_value, exc_traceback, thread_name=None):
        """Formats an exception for logging, returning a string."""
        if exc_type == SystemExit:
            return None  # We don't log SystemExit exceptions

        report = f"Error time: {formatdate(timeval=None, localtime=False, usegmt=True)}\n"
        if thread_name:
            report += f"Exception in thread: {thread_name}\n\n"

        raw_report = traceback.format_exception(exc_type, exc_value, exc_traceback)
        report += "".join(raw_report)
        return f"{report}\n{'-' * 30}\n\n"

    def _interrupt_catch(self, signum, frame):
        """Handles SIGINT (Ctrl+C) by initiating a graceful shutdown."""
        print("\nShutdown signal received. Gracefully stopping...")
        self.shutdown_requested = True

    def _exit_catch(self, signum, frame):
        """Handles SIGTERM by initiating a graceful shutdown and waiting for threads."""
        self.shutdown_requested = True

        # Wait for all threads to complete, except the main thread
        main_thread = threading.main_thread()
        for thread in threading.enumerate():
            if thread is main_thread:
                continue
            try:
                # Wait for thread to complete with 2-second timeout.
                thread.join(timeout=2.0)
            except RuntimeError:
                # Can't join a thread before it's started; ignore this error.
                pass

        print("All threads have been terminated. Exiting.")
        sys.exit(0)

    def setup_signal_handlers(self):
        """Sets up the signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._interrupt_catch)
        signal.signal(signal.SIGTERM, self._exit_catch)

    @property
    def is_shutdown_requested(self):
        """Property to check if shutdown has been requested."""
        return self.shutdown_requested


# Backward compatibility: maintain access to global flag
SHUTDOWN_REQUESTED = False


def _get_shutdown_status():
    """Get current shutdown status from the singleton."""
    return SignalHandler().shutdown_requested


# For backward compatibility - override module-level access
def __getattr__(name):
    if name == 'SHUTDOWN_REQUESTED':
        return _get_shutdown_status()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
