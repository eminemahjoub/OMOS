# OMOS Desktop Experience

OMOS (Obaidan & Mahjoub OS) is a modern, fullscreen desktop interface built with
CustomTkinter. It features an animated launch sequence, voice-enabled login,
sidebar navigation, and a local-first AI assistant with both text and speech
responses. Background music, hover effects, and smooth panel transitions round
out the experience.

## Key Features
- Opening splash screen with typewriter text, progress bar, and optional music
- Login portal with logo, password prompt, and voice greeting
- Dashboard with sidebar navigation (AI Assistant, Files, Settings, Shutdown)
- AI chat panel including typing indicator, canned responses, and TTS playback
- Settings pane for toggling voice feedback and background audio volume

## Project Layout
- `my_ui.py` – main UI application and animations
- `ai/ai_core.py` – local-first response logic for the assistant
- `ai/voice_engine.py` – queued text-to-speech engine powered by `pyttsx3`
- `assets/` – drop logo, icons, and audio tracks here (all optional)

## Getting Started
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt  # create this file or install deps manually
python my_ui.py
```

If desired dependencies are not packaged, install them manually:
```bash
pip install customtkinter pillow pyttsx3 pygame
```

Press `Esc` at any time to exit fullscreen. Customize responses in
`ai/ai_core.py` or wire in your own local language model.

