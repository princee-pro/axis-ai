"""
Voice Control Module.
Provides speech-to-text and text-to-speech capabilities for Jarvis.
"""

class VoiceController:
    """
    Handles voice input and output for Jarvis.
    Uses speech_recognition for STT and pyttsx3 for TTS.
    """
    def __init__(self):
        self.voice_enabled = False
        self.tts_engine = None
        self.recognizer = None
        self._init_engines()
    
    def _init_engines(self):
        """Initialize voice engines if libraries are available."""
        try:
            import pyttsx3
            self.tts_engine = pyttsx3.init()
            # Configure TTS settings
            self.tts_engine.setProperty('rate', 150)  # Speed
            self.tts_engine.setProperty('volume', 0.9)  # Volume
            print("[VOICE] Text-to-speech engine initialized.")
        except ImportError:
            print("[VOICE] pyttsx3 not installed. TTS disabled.")
            self.tts_engine = None
        except Exception as e:
            print(f"[VOICE] TTS initialization failed: {e}")
            self.tts_engine = None
        
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            print("[VOICE] Speech recognition initialized.")
        except ImportError:
            print("[VOICE] speech_recognition not installed. STT disabled.")
            self.recognizer = None
        except Exception as e:
            print(f"[VOICE] STT initialization failed: {e}")
            self.recognizer = None
    
    def toggle_voice(self, enabled):
        """
        Enable or disable voice mode.
        
        Args:
            enabled (bool): True to enable, False to disable
        
        Returns:
            str: Status message
        """
        if enabled and (self.tts_engine is None or self.recognizer is None):
            return "Voice mode unavailable. Install speech_recognition and pyttsx3."
        
        self.voice_enabled = enabled
        status = "enabled" if enabled else "disabled"
        message = f"Voice mode {status}."
        
        if enabled:
            self.speak(message)
        
        return message
    
    def speak(self, text):
        """
        Convert text to speech.
        
        Args:
            text (str): Text to speak
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.voice_enabled or self.tts_engine is None:
            return False
        
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
            return True
        except Exception as e:
            print(f"[VOICE] TTS error: {e}")
            return False
    
    def listen(self, timeout=5, retry=True):
        """
        Listen for voice command and convert to text.
        
        Args:
            timeout (int): Seconds to wait for speech
            retry (bool): Whether to retry on failure
        
        Returns:
            str: Recognized text, or None if failed
        """
        if not self.voice_enabled or self.recognizer is None:
            return None
        
        try:
            import speech_recognition as sr
            
            with sr.Microphone() as source:
                print("[VOICE] Listening...")
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=timeout)
            
            # Try Google Speech Recognition (requires internet)
            try:
                text = self.recognizer.recognize_google(audio)
                print(f"[VOICE] Recognized: {text}")
                return text
            except sr.UnknownValueError:
                if retry:
                    self.speak("Sorry, I didn't catch that. Please repeat.")
                    return self.listen(timeout=timeout, retry=False)
                else:
                    self.speak("I couldn't understand. Please try again.")
                    return None
            except sr.RequestError as e:
                print(f"[VOICE] Recognition service error: {e}")
                self.speak("Voice recognition service is unavailable.")
                return None
                
        except Exception as e:
            print(f"[VOICE] Listen error: {e}")
            return None
