import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jarvis_ai.core.voice_control import VoiceController

class TestVoiceControl(unittest.TestCase):
    def setUp(self):
        self.voice = VoiceController()

    def test_voice_controller_initialization(self):
        """Test that VoiceController initializes correctly."""
        self.assertIsNotNone(self.voice)
        self.assertFalse(self.voice.voice_enabled)  # Default disabled

    def test_voice_toggle(self):
        """Test enabling and disabling voice mode."""
        # Initially disabled
        self.assertFalse(self.voice.voice_enabled)
        
        # Try to enable (may fail if libraries not installed)
        result = self.voice.toggle_voice(True)
        self.assertIn("Voice mode", result)
        
        # Disable
        result = self.voice.toggle_voice(False)
        self.assertIn("disabled", result)
        self.assertFalse(self.voice.voice_enabled)

    def test_speak_when_disabled(self):
        """Test that speak returns False when voice is disabled."""
        self.voice.voice_enabled = False
        result = self.voice.speak("Test message")
        self.assertFalse(result)

    def test_listen_when_disabled(self):
        """Test that listen returns None when voice is disabled."""
        self.voice.voice_enabled = False
        result = self.voice.listen(timeout=1, retry=False)
        self.assertIsNone(result)

    def test_voice_graceful_degradation(self):
        """Test that voice features degrade gracefully without libraries."""
        # If libraries aren't installed, voice should still work but be disabled
        if self.voice.tts_engine is None or self.voice.recognizer is None:
            result = self.voice.toggle_voice(True)
            self.assertIn("unavailable", result.lower())
            self.assertFalse(self.voice.voice_enabled)

if __name__ == '__main__':
    unittest.main()
