"""Main UI entry point for the OMOS desktop experience."""

from __future__ import annotations

import itertools
import threading
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

try:
    import pygame
except Exception as exc:  # pragma: no cover - optional dependency handling
    pygame = None
    print(f"[audio] pygame not available: {exc}")

from ai.ai_core import answer
from ai.voice_engine import speak_async


# ---------------------------------------------------------------------------
# Paths and Theme Configuration
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
AUDIO_DIR = ASSETS_DIR / "audio"
LOGO_PATH = ASSETS_DIR / "logo.png"
BACKGROUND_TRACK = AUDIO_DIR / "bg_music.mp3"

for directory in (ASSETS_DIR, ICONS_DIR, AUDIO_DIR):
    directory.mkdir(parents=True, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ---------------------------------------------------------------------------
# Image Helpers
# ---------------------------------------------------------------------------
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # pragma: no cover - Pillow < 9 fallback
    RESAMPLE = Image.LANCZOS


def _create_placeholder_icon(text: str, size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), color="#222222")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    label = text[:2].upper() or "?"
    try:
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        text_width = right - left
        text_height = bottom - top
    except AttributeError:  # pragma: no cover - Pillow < 8 fallback
        text_width, text_height = font.getsize(label)
    position = ((size - text_width) / 2, (size - text_height) / 2)
    draw.text(position, label, font=font, fill="#f1f1f1")
    return image


def load_icon(name: str, fallback_text: str, size: tuple[int, int] = (32, 32)) -> tuple[ctk.CTkImage, ctk.CTkImage]:
    path = ICONS_DIR / f"{name}.png"
    if path.exists():
        try:
            image = Image.open(path).convert("RGBA")
        except Exception as exc:  # pragma: no cover - corrupted file fallback
            print(f"[icons] Failed to load {path}: {exc}")
            image = _create_placeholder_icon(fallback_text, max(size))
    else:
        image = _create_placeholder_icon(fallback_text, max(size))

    normal = image.resize(size, RESAMPLE)
    hover_size = (int(size[0] * 1.15), int(size[1] * 1.15))
    hover = image.resize(hover_size, RESAMPLE)
    normal_img = ctk.CTkImage(light_image=normal, dark_image=normal, size=size)
    hover_img = ctk.CTkImage(light_image=hover, dark_image=hover, size=hover_size)
    return normal_img, hover_img


def load_logo(size: tuple[int, int] = (140, 140)) -> Optional[ctk.CTkImage]:
    if LOGO_PATH.exists():
        try:
            image = Image.open(LOGO_PATH).convert("RGBA").resize(size, RESAMPLE)
            return ctk.CTkImage(light_image=image, dark_image=image, size=size)
        except Exception as exc:  # pragma: no cover - corrupted file fallback
            print(f"[logo] Failed to load logo: {exc}")
    return None


# ---------------------------------------------------------------------------
# Audio Controller
# ---------------------------------------------------------------------------
class BackgroundAudioPlayer:
    """Optional background music using pygame."""

    def __init__(self, track_path: Path) -> None:
        self.track_path = track_path
        self._available = False
        self._volume = 0.35
        if pygame is None:
            return
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self._available = True
        except Exception as exc:  # pragma: no cover - debug logging only
            print(f"[audio] Unable to initialise pygame mixer: {exc}")
            self._available = False

    def play(self, loop: bool = True) -> None:
        if not self._available:
            return
        if not self.track_path.exists():
            print(f"[audio] Background track missing at {self.track_path}")
            return
        try:
            pygame.mixer.music.load(self.track_path.as_posix())
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play(-1 if loop else 0)
        except Exception as exc:  # pragma: no cover - debug logging only
            print(f"[audio] Failed to play music: {exc}")

    def fade_out(self, duration_ms: int = 800) -> None:
        if self._available:
            try:
                pygame.mixer.music.fadeout(duration_ms)
            except Exception:
                self.stop()

    def stop(self) -> None:
        if self._available:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

    def set_volume(self, volume: float) -> None:
        value = max(0.0, min(1.0, volume))
        self._volume = value
        if self._available:
            try:
                pygame.mixer.music.set_volume(value)
            except Exception:
                pass

    def is_active(self) -> bool:
        if not self._available:
            return False
        try:
            return pygame.mixer.music.get_busy()
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Animation Utilities
# ---------------------------------------------------------------------------
class TypewriterAnimator:
    def __init__(self, widget: ctk.CTkLabel, speed_ms: int = 40) -> None:
        self.widget = widget
        self.speed_ms = speed_ms
        self._job: Optional[str] = None

    def start(self, text: str, on_complete: Optional[Callable[[], None]] = None) -> None:
        self.cancel()
        self.widget.configure(text="")

        def _step(index: int = 0) -> None:
            if index <= len(text):
                self.widget.configure(text=text[:index])
                self._job = self.widget.after(self.speed_ms, lambda: _step(index + 1))
            else:
                self._job = None
                if on_complete:
                    on_complete()

        _step()

    def cancel(self) -> None:
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None


class ProgressAnimator:
    def __init__(self, bar: ctk.CTkProgressBar, duration_ms: int = 3200, update_hook: Optional[Callable[[float], None]] = None) -> None:
        self.bar = bar
        self.duration_ms = duration_ms
        self.update_hook = update_hook
        self._job: Optional[str] = None

    def start(self, on_complete: Optional[Callable[[], None]] = None) -> None:
        self.cancel()
        total_steps = max(1, self.duration_ms // 30)
        increment = 1 / total_steps

        def _step(step_index: int = 0) -> None:
            value = min(1.0, step_index * increment)
            self.bar.set(value)
            if self.update_hook:
                self.update_hook(value)
            if value >= 1.0:
                self._job = None
                if on_complete:
                    self.bar.after(400, on_complete)
                return
            self._job = self.bar.after(30, lambda: _step(step_index + 1))

        _step()

    def cancel(self) -> None:
        if self._job is not None:
            self.bar.after_cancel(self._job)
            self._job = None


class SlideAnimator:
    def __init__(self, container: ctk.CTk | ctk.CTkFrame) -> None:
        self.container = container
        self.current: Optional[ctk.CTkFrame] = None
        self._in_motion = False

    def show(self, frame: ctk.CTkFrame) -> None:
        if self._in_motion or frame is self.current:
            if frame is not None:
                frame.place(relx=0, rely=0, relwidth=1, relheight=1, x=0)
                frame.lift()
            self.current = frame
            return

        self.container.update_idletasks()
        width = self.container.winfo_width() or self.container.winfo_screenwidth()
        frame.place(relx=0, rely=0, relwidth=1, relheight=1, x=width)
        frame.lift()

        active = self.current
        step = max(16, width // 40)
        position = width
        self._in_motion = True

        def _animate() -> None:
            nonlocal position
            position = max(0, position - step)
            frame.place_configure(x=position)
            if active is not None:
                active.place_configure(x=position - width)
            if position > 0:
                frame.after(10, _animate)
            else:
                if active is not None:
                    active.place_forget()
                frame.place_configure(x=0)
                self.current = frame
                self._in_motion = False

        _animate()


# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------
class AnimatedButton(ctk.CTkButton):
    def __init__(self, *args, grow_by: int = 12, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._grow_by = grow_by
        self._base_width = kwargs.get("width", 180)
        self.configure(hover=False)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event) -> None:
        self.configure(width=self._base_width + self._grow_by)

    def _on_leave(self, _event) -> None:
        self.configure(width=self._base_width)


class SidebarButton(ctk.CTkButton):
    def __init__(self, master, text: str, icon_pair: tuple[ctk.CTkImage, ctk.CTkImage], command: Callable[[], None], **kwargs) -> None:
        normal_icon, hover_icon = icon_pair
        super().__init__(
            master,
            text=text,
            image=normal_icon,
            command=command,
            anchor="w",
            compound="left",
            fg_color="#161616",
            hover_color="#1f1f1f",
            height=40,
            width=210,
            corner_radius=10,
            **kwargs,
        )
        self._normal_icon = normal_icon
        self._hover_icon = hover_icon
        self.configure(font=("Segoe UI", 16))
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event) -> None:
        self.configure(width=222, image=self._hover_icon)

    def _on_leave(self, _event) -> None:
        self.configure(width=210, image=self._normal_icon)


class TypingBubble:
    def __init__(self, parent: ctk.CTkFrame) -> None:
        self.container = ctk.CTkFrame(parent, fg_color="#1f1f1f", corner_radius=12)
        self.label = ctk.CTkLabel(self.container, text="OMOS is typing", font=("Consolas", 16))
        self.label.pack(padx=12, pady=6)
        self._dots = itertools.cycle(["", ".", "..", "..."])
        self._job: Optional[str] = None

    def start(self) -> None:
        if self._job is not None:
            return
        self.container.pack(pady=(10, 0), anchor="w")

        def _animate() -> None:
            self.label.configure(text=f"OMOS is typing{next(self._dots)}")
            self._job = self.container.after(400, _animate)

        _animate()

    def stop(self) -> None:
        if self._job is not None:
            self.container.after_cancel(self._job)
            self._job = None
        self.container.pack_forget()


# ---------------------------------------------------------------------------
# Panels
# ---------------------------------------------------------------------------
class AIAssistantPanel(ctk.CTkFrame):
    def __init__(self, master, speak_callback: Callable[[str], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.speak_callback = speak_callback
        self._bubble = TypingBubble(self)

        self.header = ctk.CTkLabel(self, text="AI Assistant", font=("Consolas", 26, "bold"))
        self.header.pack(anchor="w", pady=(0, 12))

        self.output = ctk.CTkTextbox(self, width=800, height=360, corner_radius=12)
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")

        self.input_row = ctk.CTkFrame(self, fg_color="transparent")
        self.input_row.pack(fill="x", pady=(12, 0))

        self.entry = ctk.CTkEntry(self.input_row, placeholder_text="Ask OMOS (local-first AI)...", height=40)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 12))
        self.entry.bind("<Return>", self._on_submit)

        self.ask_button = AnimatedButton(
            self.input_row,
            text="Ask",
            command=self._on_submit,
            width=120,
            fg_color="#1e88e5",
            hover_color="#1565c0",
        )
        self.ask_button.pack(side="left")

    def _append(self, prefix: str, message: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", f"{prefix}: {message}\n\n")
        self.output.see("end")
        self.output.configure(state="disabled")

    def _on_submit(self, _event=None) -> None:
        prompt = self.entry.get().strip()
        if not prompt:
            return
        self.entry.delete(0, "end")
        self._append("You", prompt)
        self._bubble.start()
        threading.Thread(target=self._run_assistant, args=(prompt,), daemon=True).start()

    def _run_assistant(self, prompt: str) -> None:
        try:
            response = answer(prompt)
        except Exception as exc:  # pragma: no cover - defensive programming
            response = f"I ran into an issue: {exc}"
        self.after(0, lambda: self._show_response(response))

    def _show_response(self, response: str) -> None:
        self._bubble.stop()
        self._append("OMOS", response)
        self.speak_callback(response)


class FilesPanel(ctk.CTkFrame):
    def __init__(self, master) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Files", font=("Consolas", 26, "bold")).pack(anchor="w", pady=(0, 12))
        textbox = ctk.CTkTextbox(self, corner_radius=12, height=320)
        textbox.pack(fill="both", expand=True)
        textbox.insert(
            "end",
            "Local file explorer coming soon. Integrate your file manager here.",
        )
        textbox.configure(state="disabled")


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, master, audio_player: BackgroundAudioPlayer, on_voice_toggle: Callable[[bool], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.audio_player = audio_player
        self.on_voice_toggle = on_voice_toggle

        ctk.CTkLabel(self, text="Settings", font=("Consolas", 26, "bold")).pack(anchor="w", pady=(0, 12))

        self.music_switch = ctk.CTkSwitch(self, text="Background music", command=self._toggle_music)
        self.music_switch.pack(anchor="w", pady=8)
        if self.audio_player.is_active():
            self.music_switch.select()

        self.voice_switch = ctk.CTkSwitch(self, text="Voice feedback", command=self._toggle_voice)
        self.voice_switch.pack(anchor="w", pady=8)
        self.voice_switch.select()

        volume_frame = ctk.CTkFrame(self, fg_color="#171717", corner_radius=12)
        volume_frame.pack(fill="x", pady=16)
        ctk.CTkLabel(volume_frame, text="Music volume", font=("Segoe UI", 14)).pack(anchor="w", padx=12, pady=(12, 4))
        self.volume_slider = ctk.CTkSlider(volume_frame, from_=0, to=100, command=self._set_volume)
        self.volume_slider.set(35)
        self.volume_slider.pack(fill="x", padx=12, pady=(0, 12))

    def _toggle_music(self) -> None:
        if self.music_switch.get():
            self.audio_player.play(loop=True)
        else:
            self.audio_player.fade_out(600)

    def _toggle_voice(self) -> None:
        self.on_voice_toggle(bool(self.voice_switch.get()))

    def _set_volume(self, value: float) -> None:
        self.audio_player.set_volume(value / 100)


class ShutdownPanel(ctk.CTkFrame):
    def __init__(self, master, on_shutdown: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text="Shutdown", font=("Consolas", 26, "bold")).pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(
            self,
            text="Ready to close OMOS? Your state is stored locally.",
            font=("Segoe UI", 16),
        ).pack(anchor="w", pady=(0, 24))
        AnimatedButton(
            self,
            text="Power Off",
            command=on_shutdown,
            width=180,
            fg_color="#d32f2f",
            hover_color="#b71c1c",
        ).pack(anchor="w")


class Dashboard(ctk.CTkFrame):
    def __init__(self, master, audio_player: BackgroundAudioPlayer, on_shutdown: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.audio_player = audio_player
        self.on_shutdown = on_shutdown
        self._voice_enabled = True

        self.sidebar = ctk.CTkFrame(self, fg_color="#111111", width=240)
        self.sidebar.pack(side="left", fill="y")
        self.content_container = ctk.CTkFrame(self, fg_color="#0f0f0f")
        self.content_container.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        logo = load_logo(size=(120, 120))
        if logo:
            ctk.CTkLabel(self.sidebar, image=logo, text="").pack(pady=(24, 12))
        else:
            ctk.CTkLabel(self.sidebar, text="OMOS", font=("Consolas", 28, "bold")).pack(pady=(24, 12))

        self.panel_animator = SlideAnimator(self.content_container)
        self.panels: dict[str, ctk.CTkFrame] = {}

        self._register_panel(
            "assistant",
            "AI Assistant",
            AIAssistantPanel(self.content_container, speak_callback=self._speak_if_enabled),
        )
        self._register_panel("files", "Files", FilesPanel(self.content_container))
        self._register_panel(
            "settings",
            "Settings",
            SettingsPanel(self.content_container, audio_player=self.audio_player, on_voice_toggle=self._toggle_voice),
        )
        self._register_panel(
            "shutdown",
            "Shutdown",
            ShutdownPanel(self.content_container, on_shutdown=self._handle_shutdown),
        )

        self.show_panel("assistant")

    def _register_panel(self, key: str, label: str, frame: ctk.CTkFrame) -> None:
        icon_pair = load_icon(key, fallback_text=label[:2])

        def _command() -> None:
            self.show_panel(key)

        SidebarButton(self.sidebar, text=label, icon_pair=icon_pair, command=_command).pack(
            fill="x", padx=16, pady=6
        )
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        frame.place_forget()
        self.panels[key] = frame

    def show_panel(self, key: str) -> None:
        panel = self.panels.get(key)
        if panel:
            self.panel_animator.show(panel)

    def _toggle_voice(self, enabled: bool) -> None:
        self._voice_enabled = enabled

    def _speak_if_enabled(self, text: str) -> None:
        if self._voice_enabled and text:
            speak_async(text)

    def _handle_shutdown(self) -> None:
        self._speak_if_enabled("Shutting down OMOS. Goodbye.")
        self.audio_player.fade_out(600)
        self.on_shutdown()


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------
class OpeningScreen(ctk.CTkFrame):
    def __init__(self, master, audio_player: BackgroundAudioPlayer, on_complete: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.audio_player = audio_player
        self.on_complete = on_complete

        self.headline = ctk.CTkLabel(self, text="", font=("Consolas", 44, "bold"))
        self.headline.pack(pady=(180, 20))

        self.status = ctk.CTkLabel(self, text="", font=("Consolas", 20))
        self.status.pack(pady=8)

        self.progress = ctk.CTkProgressBar(self, width=600)
        self.progress.pack(pady=40)
        self.progress.set(0)

        self.typewriter = TypewriterAnimator(self.headline)
        self.progress_animator = ProgressAnimator(self.progress, update_hook=self._on_progress)

    def start(self) -> None:
        self.typewriter.start(
            "Welcome to OMOS — Obaidan & Mahjoub OS",
            on_complete=lambda: self.progress_animator.start(self._finish),
        )
        self.status.configure(text="Initialising core services...")
        self.audio_player.play(loop=True)

    def _on_progress(self, value: float) -> None:
        if value > 0.75:
            self.status.configure(text="Loading interactive dashboard...")
        elif value > 0.45:
            self.status.configure(text="Preparing local AI modules...")

    def _finish(self) -> None:
        self.status.configure(text="System ready.")
        self.after(600, self.on_complete)


class LoginScreen(ctk.CTkFrame):
    def __init__(self, master, on_success: Callable[[], None]) -> None:
        super().__init__(master, fg_color="transparent")
        self.on_success = on_success
        self._greeted = False

        container = ctk.CTkFrame(self, fg_color="#111111", corner_radius=16)
        container.pack(expand=True, ipadx=60, ipady=40)

        logo = load_logo(size=(130, 130))
        if logo:
            ctk.CTkLabel(container, image=logo, text="").pack(pady=(0, 12))
        else:
            ctk.CTkLabel(container, text="OMOS", font=("Consolas", 38, "bold")).pack(pady=(0, 12))

        ctk.CTkLabel(container, text="Sign in to OMOS", font=("Consolas", 26)).pack(pady=(0, 20))

        self.password_entry = ctk.CTkEntry(
            container,
            placeholder_text="Enter password or press Enter",
            width=360,
            show="*",
        )
        self.password_entry.pack(pady=10)
        self.password_entry.bind("<Return>", self._submit)

        ctk.CTkLabel(
            container,
            text="Tip: leave blank and press Enter to continue",
            font=("Segoe UI", 13),
        ).pack(pady=(0, 16))

        self.enter_button = AnimatedButton(
            container,
            text="Enter",
            command=self._submit,
            width=220,
            fg_color="#00acc1",
            hover_color="#00838f",
        )
        self.enter_button.pack(pady=(10, 0))

    def on_show(self) -> None:
        if not self._greeted:
            speak_async("Hello, please sign in to OMOS.")
            self._greeted = True
        self.password_entry.delete(0, "end")
        self.password_entry.focus_set()

    def _submit(self, _event=None) -> None:
        speak_async("Access granted. Welcome aboard.")
        self.on_success()


# ---------------------------------------------------------------------------
# Application Shell
# ---------------------------------------------------------------------------
class OMOSApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OMOS")
        self.attributes("-fullscreen", True)
        self.configure(fg_color="#070707")
        self.bind("<Escape>", lambda _event: self.request_exit())
        self.protocol("WM_DELETE_WINDOW", self.request_exit)

        self.audio_player = BackgroundAudioPlayer(BACKGROUND_TRACK)
        self.screen_animator = SlideAnimator(self)

        self.opening_screen = OpeningScreen(self, self.audio_player, on_complete=self.show_login)
        self.login_screen = LoginScreen(self, on_success=self.show_dashboard)
        self.dashboard = Dashboard(self, audio_player=self.audio_player, on_shutdown=self.request_exit)

        for screen in (self.opening_screen, self.login_screen, self.dashboard):
            screen.place(relx=0, rely=0, relwidth=1, relheight=1)
            screen.place_forget()

        self.current_screen: Optional[ctk.CTkFrame] = None
        self.show_opening()

    def show_opening(self) -> None:
        self._set_screen(self.opening_screen)
        self.after(100, self.opening_screen.start)

    def show_login(self) -> None:
        self._set_screen(self.login_screen)
        self.login_screen.on_show()

    def show_dashboard(self) -> None:
        self._set_screen(self.dashboard)

    def _set_screen(self, screen: ctk.CTkFrame) -> None:
        self.screen_animator.show(screen)
        self.current_screen = screen

    def request_exit(self) -> None:
        self.audio_player.fade_out(400)
        self.after(450, self.destroy)


def main() -> None:
    app = OMOSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
    