import signal
import sys
import threading
from unittest.mock import patch, MagicMock

from signals import SignalHandler


class TestSignalHandler:
    """Test cases for SignalHandler class."""

    def setup_method(self):
        """Reset the singleton instance before each test."""
        SignalHandler._instance = None

    def test_singleton_pattern(self):
        """Test that SignalHandler follows the singleton pattern."""
        handler1 = SignalHandler()
        handler2 = SignalHandler()

        assert handler1 is handler2

    def test_initialization(self):
        """Test SignalHandler initialization."""
        handler = SignalHandler()
        assert hasattr(handler, 'shutdown_requested')
        assert handler.shutdown_requested is False

    def test_shutdown_requested_property(self):
        """Test the is_shutdown_requested property."""
        handler = SignalHandler()
        assert handler.is_shutdown_requested is False

        handler.shutdown_requested = True
        assert handler.is_shutdown_requested is True

    def test_interrupt_catch_sets_flag(self):
        """Test that _interrupt_catch sets shutdown_requested flag."""
        handler = SignalHandler()

        # Simulate SIGINT
        with patch('builtins.print'):
            handler._interrupt_catch(signal.SIGINT, None)

        assert handler.shutdown_requested is True

    def test_interrupt_catch_prints_message(self):
        """Test that _interrupt_catch prints a message."""
        handler = SignalHandler()

        with patch('builtins.print') as mock_print:
            handler._interrupt_catch(signal.SIGINT, None)
            mock_print.assert_called_once()
            assert "Shutdown signal received" in str(mock_print.call_args)

    @patch('signals.sys.exit')
    @patch('signals.threading.enumerate')
    @patch('signals.threading.main_thread')
    def test_exit_catch_exits(self, mock_main_thread, mock_enumerate, mock_exit):
        """Test that _exit_catch calls sys.exit."""
        handler = SignalHandler()
        mock_main_thread.return_value = threading.current_thread()
        mock_enumerate.return_value = [threading.current_thread()]

        with patch('builtins.print'):
            handler._exit_catch(signal.SIGTERM, None)

        assert handler.shutdown_requested is True
        mock_exit.assert_called_once_with(0)

    @patch('signals.sys.exit')
    @patch('signals.threading.enumerate')
    @patch('signals.threading.main_thread')
    def test_exit_catch_waits_for_threads(self, mock_main_thread, mock_enumerate, mock_exit):
        """Test that _exit_catch waits for threads to complete."""
        handler = SignalHandler()
        main_thread = threading.current_thread()
        mock_main_thread.return_value = main_thread

        # Create mock threads
        mock_thread1 = MagicMock()
        mock_thread2 = MagicMock()
        mock_enumerate.return_value = [main_thread, mock_thread1, mock_thread2]

        with patch('builtins.print'):
            handler._exit_catch(signal.SIGTERM, None)

        # Check that join was called on non-main threads with 2-second timeout
        mock_thread1.join.assert_called_once_with(timeout=2.0)
        mock_thread2.join.assert_called_once_with(timeout=2.0)

    @patch('signal.signal')
    def test_setup_signal_handlers(self, mock_signal):
        """Test that signal handlers are set up correctly."""
        handler = SignalHandler()
        handler.setup_signal_handlers()

        # Should register handlers for SIGINT and SIGTERM
        assert mock_signal.call_count == 2

    def test_format_exception_with_none_type(self):
        """Test format_exception returns None for SystemExit."""
        result = SignalHandler.format_exception(SystemExit, None, None)
        assert result is None

    def test_format_exception_formats_correctly(self):
        """Test format_exception formats exception information."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            result = SignalHandler.format_exception(exc_type, exc_value, exc_traceback)

            assert result is not None
            assert "ValueError" in result
            assert "Test error" in result
            assert "Error time:" in result

    def test_format_exception_with_thread_name(self):
        """Test format_exception includes thread name when provided."""
        try:
            raise RuntimeError("Thread error")
        except RuntimeError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            result = SignalHandler.format_exception(
                exc_type, exc_value, exc_traceback, thread_name="TestThread"
            )

            assert "TestThread" in result
            assert "RuntimeError" in result

    def test_format_exception_includes_separator(self):
        """Test format_exception includes separator."""
        try:
            raise Exception("Test")
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            result = SignalHandler.format_exception(exc_type, exc_value, exc_traceback)

            assert "-----" in result

    def test_multiple_shutdown_requests(self):
        """Test that multiple shutdown requests don't cause issues."""
        handler = SignalHandler()

        with patch('builtins.print'):
            handler._interrupt_catch(signal.SIGINT, None)
            handler._interrupt_catch(signal.SIGINT, None)

        assert handler.shutdown_requested is True

    @patch('signals.threading.enumerate')
    @patch('signals.threading.main_thread')
    def test_exit_catch_handles_join_exception(self, mock_main_thread, mock_enumerate):
        """Test that _exit_catch handles join exceptions."""
        handler = SignalHandler()
        main_thread = threading.current_thread()
        mock_main_thread.return_value = main_thread

        # Create a mock thread that raises RuntimeError on join
        mock_thread = MagicMock()
        mock_thread.join.side_effect = RuntimeError("Cannot join")
        mock_enumerate.return_value = [main_thread, mock_thread]

        with patch('builtins.print'):
            with patch('signals.sys.exit'):
                # Should not raise an exception
                handler._exit_catch(signal.SIGTERM, None)

    def test_initialization_idempotent(self):
        """Test that multiple initializations don't reset the flag."""
        handler1 = SignalHandler()
        handler1.shutdown_requested = True

        # Create another reference without resetting singleton
        handler2 = SignalHandler()

        assert handler2.shutdown_requested is True
