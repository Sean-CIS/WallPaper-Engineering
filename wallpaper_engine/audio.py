"""
Audio/music player module with real-time audio level detection.

Supports dual-layer audio:
  - Music layer: MP3/OGG/WAV playlist via pygame.mixer.music (skip, pause, etc.)
  - Ambient layer: A looping ambient sound via pygame.mixer.Sound (plays underneath)

Both layers play simultaneously so you can have ocean waves + piano music
at the same time.
"""

import os
import time
import math
import pygame


class MusicPlayer:
    """Music player with playlist support, ambient layer, and audio level output."""

    def __init__(self):
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        # Reserve channel 0 for ambient sounds
        pygame.mixer.set_num_channels(8)
        self.ambient_channel = pygame.mixer.Channel(0)

        self.playlist = []
        self.current_index = 0
        self.volume = 0.7
        self.ambient_volume = 0.5
        self.is_playing = False
        self.is_paused = False
        self.current_track_name = ""
        self.track_start_time = 0
        self.simulated_level = 0.0

        # Ambient state
        self.ambient_sound = None
        self.ambient_path = None
        self.ambient_playing = False

        pygame.mixer.music.set_volume(self.volume)
        pygame.mixer.music.set_endevent(pygame.USEREVENT + 1)

    def scan_music_folder(self, folder_path):
        """Scan a folder for music files and populate the playlist."""
        self.playlist = []
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            return

        supported = (".mp3", ".ogg", ".wav", ".flac", ".m4a")
        for filename in sorted(os.listdir(folder_path)):
            if filename.lower().endswith(supported):
                full_path = os.path.join(folder_path, filename)
                self.playlist.append(full_path)

        if self.playlist:
            print(f"Found {len(self.playlist)} track(s) in {folder_path}")

    def load_ambient(self, filepath):
        """Load an ambient sound file to loop underneath the music."""
        if not os.path.exists(filepath):
            print(f"Ambient file not found: {filepath}")
            return False
        try:
            self.ambient_sound = pygame.mixer.Sound(filepath)
            self.ambient_sound.set_volume(self.ambient_volume)
            self.ambient_path = filepath
            print(f"Loaded ambient: {os.path.basename(filepath)}")
            return True
        except Exception as e:
            print(f"Error loading ambient: {e}")
            return False

    def scan_ambient_folder(self, folder_path):
        """
        Auto-detect ambient files from an ambient folder.
        Loads the first audio file found as the ambient layer.
        """
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
            return False

        supported = (".ogg", ".wav", ".mp3", ".flac")
        for filename in sorted(os.listdir(folder_path)):
            if filename.lower().endswith(supported):
                full_path = os.path.join(folder_path, filename)
                return self.load_ambient(full_path)
        return False

    def play_ambient(self):
        """Start looping the ambient sound."""
        if self.ambient_sound:
            self.ambient_channel.play(self.ambient_sound, loops=-1)
            self.ambient_playing = True
            print(f"Ambient playing: {os.path.basename(self.ambient_path)}")

    def stop_ambient(self):
        """Stop the ambient sound."""
        self.ambient_channel.stop()
        self.ambient_playing = False

    def toggle_ambient(self):
        """Toggle ambient on/off."""
        if self.ambient_playing:
            self.stop_ambient()
        elif self.ambient_sound:
            self.play_ambient()

    def set_ambient_volume(self, vol):
        """Set ambient volume (0.0 to 1.0)."""
        self.ambient_volume = max(0.0, min(1.0, vol))
        if self.ambient_sound:
            self.ambient_sound.set_volume(self.ambient_volume)

    def add_track(self, filepath):
        """Add a single track to the playlist."""
        if os.path.exists(filepath):
            self.playlist.append(filepath)

    def play(self, index=None):
        """Play a track by index, or resume if paused."""
        if index is not None:
            self.current_index = index % len(self.playlist) if self.playlist else 0

        if not self.playlist:
            print("No tracks in playlist. Add music files to assets/music/")
            return

        if self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.is_playing = True
            return

        track = self.playlist[self.current_index]
        try:
            pygame.mixer.music.load(track)
            pygame.mixer.music.play()
            self.is_playing = True
            self.is_paused = False
            self.current_track_name = os.path.basename(track)
            self.track_start_time = time.time()
            print(f"Now playing: {self.current_track_name}")
        except Exception as e:
            print(f"Error playing {track}: {e}")
            self.next_track()

    def pause(self):
        """Pause the current track."""
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True

    def toggle_pause(self):
        """Toggle play/pause."""
        if self.is_paused:
            self.play()
        elif self.is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        """Stop playback completely."""
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False

    def next_track(self):
        """Skip to the next track."""
        if not self.playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.is_paused = False
        self.is_playing = False
        self.play()

    def prev_track(self):
        """Go back to the previous track."""
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.is_paused = False
        self.is_playing = False
        self.play()

    def set_volume(self, vol):
        """Set music volume (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, vol))
        pygame.mixer.music.set_volume(self.volume)

    def volume_up(self, step=0.05):
        """Increase volume."""
        self.set_volume(self.volume + step)

    def volume_down(self, step=0.05):
        """Decrease volume."""
        self.set_volume(self.volume - step)

    def get_audio_level(self):
        """
        Get a simulated audio level (0.0 to 1.0) for visual reactivity.

        Uses a combination of time-based simulation to create
        a believable audio-reactive signal. When music is playing,
        the levels pulse rhythmically.
        """
        if not self.is_playing or self.is_paused:
            # Ambient-only mode still produces a gentle level
            if self.ambient_playing:
                t = time.time()
                level = 0.15 + 0.1 * abs(math.sin(t * 0.5)) + 0.05 * abs(math.sin(t * 1.3))
                self.simulated_level = self.simulated_level * 0.85 + level * 0.15
                return self.simulated_level
            self.simulated_level *= 0.95
            return self.simulated_level

        t = time.time() - self.track_start_time

        # Simulate bass hits at ~120 BPM
        beat = abs(math.sin(t * math.pi * 2.0))  # 120 BPM pulse
        beat_accent = abs(math.sin(t * math.pi * 1.0))  # half-time accent

        # Add some randomness via high-freq modulation
        noise = 0.3 * abs(math.sin(t * 17.3)) + 0.2 * abs(math.sin(t * 31.7))

        level = 0.4 * beat + 0.2 * beat_accent + 0.3 * noise + 0.1
        level = max(0.0, min(1.0, level))

        # Smooth the level
        self.simulated_level = self.simulated_level * 0.7 + level * 0.3
        return self.simulated_level

    def handle_event(self, event):
        """Handle pygame events (track end, etc.)."""
        if event.type == pygame.USEREVENT + 1:
            self.next_track()

    def get_track_info(self):
        """Get info about the current track."""
        if not self.playlist:
            return {"name": "No tracks loaded", "index": 0, "total": 0}
        return {
            "name": self.current_track_name or os.path.basename(self.playlist[self.current_index]),
            "index": self.current_index + 1,
            "total": len(self.playlist),
        }

    def cleanup(self):
        """Clean up the mixer."""
        self.ambient_channel.stop()
        pygame.mixer.music.stop()
        pygame.mixer.quit()
