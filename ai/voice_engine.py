"""Thread-safe asynchronous text-to-speech engine for OMOS."""

# ---------------- Future Imports ----------------
from __future__ import annotations

# ---------------- Standard Library Imports ----------------
import atexit
import queue
import threading

# ---------------- Third-party Imports ----------------
import pyttsx3


class VoiceEngine:
    """Manage a background worker that feeds text into pyttsx3 safely."""

    def __init__(self, queue_maxsize: int = 10) -> None:
        # Queue keeps utterances ordered without blocking the UI thread.
        self._queue: "queue.Queue[str]" = queue.Queue(maxsize=queue_maxsize)
        # Background worker thread handles pyttsx3 interactions.
        self._worker_thread: threading.Thread | None = None
        # Flags coordinate initialization and shutdown.
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        # Lazy-loaded pyttsx3 engine reference.
        self._engine: pyttsx3.Engine | None = None
        self._start_worker()

    def _start_worker(self) -> None:
        """Spin up the worker thread if it is not already running."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        # Wait briefly so that the engine is ready before first speak request.
        self._ready_event.wait(timeout=3)

    def _initialise_engine(self) -> None:
        """Create the pyttsx3 engine instance once and reuse it."""
        if self._engine is not None:
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 190)
            self._engine = engine
        except Exception as exc:  # pragma: no cover - best-effort logging
            print(f"[voice] Failed to initialise pyttsx3: {exc}")
            self._engine = None

    def _worker(self) -> None:
        """Continuously consume queued text and speak it aloud."""
        self._initialise_engine()
        self._ready_event.set()
        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                # Ignore empty strings without blocking subsequent utterances.
                if not text.strip():
                    continue
                if self._engine is None:
                    print("[voice] Engine unavailable; dropping utterance")
                    continue
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:  # pragma: no cover - best-effort logging
                print(f"[voice] Speaking failed: {exc}")
            finally:
                self._queue.task_done()

    def speak(self, text: str) -> None:
        """Queue text for speech without blocking the caller."""
        if self._stop_event.is_set():
            return
        self._start_worker()
        try:
            self._queue.put_nowait(text)
        except queue.Full:  # pragma: no cover - rare defensive path
            print("[voice] Queue full; dropping utterance")

    def shutdown(self) -> None:
        """Signal the worker to finish and release resources."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        # Wake the worker if it is waiting on an empty queue.
        try:
            self._queue.put_nowait("")
        except queue.Full:
            pass
        if self._worker_thread:
            self._worker_thread.join(timeout=1)
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass


# ---------------- Module-level helpers ----------------
_VOICE_ENGINE = VoiceEngine()


def speak_async(text: str) -> None:
    """Expose a simple function-based API for the UI layer."""
    _VOICE_ENGINE.speak(text)


def shutdown() -> None:
    """Allow consumers to stop the TTS worker explicitly if needed."""
    _VOICE_ENGINE.shutdown()


# Ensure the worker thread terminates cleanly when Python exits.
atexit.register(shutdown)
