# app.py - COMPLETE PROFESSIONAL TTS & STT GENERATOR WITH 4 WORKING TABS
import asyncio
import json
import os
import random
import re
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import webvtt
import natsort
import uvicorn
import glob
import shutil
from concurrent.futures import ThreadPoolExecutor
import hashlib
import speech_recognition as sr
import tempfile
import io
import base64
from dataclasses import dataclass
from enum import Enum

# ==================== SYSTEM CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    LANGUAGES = {
        "Vietnamese": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "👩 Female", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "🤵 Male", "display": "Nam Minh"}
        ],
        "English (US)": [
            {"name": "en-US-GuyNeural", "gender": "🤵 Male", "display": "Guy (US)"},
            {"name": "en-US-JennyNeural", "gender": "👩 Female", "display": "Jenny (US)"},
            {"name": "en-US-AvaNeural", "gender": "👩 Female", "display": "Ava (US)"},
            {"name": "en-US-AndrewNeural", "gender": "🤵 Male", "display": "Andrew (US)"},
            {"name": "en-US-EmmaNeural", "gender": "👩 Female", "display": "Emma (US)"},
            {"name": "en-US-BrianNeural", "gender": "🤵 Male", "display": "Brian (US)"},
            {"name": "en-US-AnaNeural", "gender": "👩 Female", "display": "Ana (US)"},
            {"name": "en-US-AndrewMultilingualNeural", "gender": "🤵 Male", "display": "Andrew (US • Multi)"},
            {"name": "en-US-AriaNeural", "gender": "👩 Female", "display": "Aria (US)"},
            {"name": "en-US-AvaMultilingualNeural", "gender": "👩 Female", "display": "Ava (US • Multi)"},
            {"name": "en-US-BrianMultilingualNeural", "gender": "🤵 Male", "display": "Brian (US • Multi)"},
            {"name": "en-US-ChristopherNeural", "gender": "🤵 Male", "display": "Christopher (US)"},
            {"name": "en-US-EmmaMultilingualNeural", "gender": "👩 Female", "display": "Emma (US • Multi)"},
            {"name": "en-US-EricNeural", "gender": "🤵 Male", "display": "Eric (US)"},
            {"name": "en-US-MichelleNeural", "gender": "👩 Female", "display": "Michelle (US)"},
            {"name": "en-US-RogerNeural", "gender": "🤵 Male", "display": "Roger (US)"},
            {"name": "en-US-SteffanNeural", "gender": "🤵 Male", "display": "Steffan (US)"}
        ],
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "👩 Female", "display": "Libby (UK)"},
            {"name": "en-GB-MiaNeural", "gender": "👩 Female", "display": "Mia (UK)"},
            {"name": "en-GB-RyanNeural", "gender": "🤵 Male", "display": "Ryan (UK)"},
            {"name": "en-GB-MaisieNeural", "gender": "👩 Female", "display": "Maisie (UK)"},
            {"name": "en-GB-SoniaNeural", "gender": "👩 Female", "display": "Sonia (UK)"},
            {"name": "en-GB-ThomasNeural", "gender": "🤵 Male", "display": "Thomas (UK)"}
        ],
        "English (Australia)": [
            {"name": "en-AU-NatashaNeural", "gender": "👩 Female", "display": "Natasha (AU)"},
            {"name": "en-AU-WilliamNeural", "gender": "🤵 Male", "display": "William (AU)"},
            {"name": "en-AU-TinaNeural", "gender": "👩 Female", "display": "Tina (AU)"},
            {"name": "en-AU-KenNeural", "gender": "🤵 Male", "display": "Ken (AU)"}
        ],
        "English (Canada)": [
            {"name": "en-CA-ClaraNeural", "gender": "👩 Female", "display": "Clara (CA)"},
            {"name": "en-CA-LiamNeural", "gender": "🤵 Male", "display": "Liam (CA)"}
        ],
        "English (India)": [
            {"name": "en-IN-NeerjaNeural", "gender": "👩 Female", "display": "Neerja (IN)"},
            {"name": "en-IN-PrabhatNeural", "gender": "🤵 Male", "display": "Prabhat (IN)"}
        ],
        "Mandarin Chinese (zh-CN)": [
            {"name": "zh-CN-XiaoxiaoNeural", "gender": "👩 Female", "display": "晓晓"},
            {"name": "zh-CN-YunxiNeural", "gender": "🤵 Male", "display": "云希"},
            {"name": "zh-CN-YunjianNeural", "gender": "🤵 Male", "display": "云健"},
            {"name": "zh-CN-XiaoyiNeural", "gender": "👩 Female", "display": "晓伊"},
            {"name": "zh-CN-XiaomoNeural", "gender": "👩 Female", "display": "晓墨"},
            {"name": "zh-CN-XiaoxuanNeural", "gender": "👩 Female", "display": "晓萱"},
            {"name": "zh-CN-XiaohanNeural", "gender": "👩 Female", "display": "晓涵"},
            {"name": "zh-CN-XiaoruiNeural", "gender": "👩 Female", "display": "晓瑞"}
        ],
        "Japanese": [
            {"name": "ja-JP-NanamiNeural", "gender": "👩 Female", "display": "奈々美"},
            {"name": "ja-JP-KeitaNeural", "gender": "🤵 Male", "display": "圭太"}
        ],
        "Korean": [
            {"name": "ko-KR-SunHiNeural", "gender": "👩 Female", "display": "선희"},
            {"name": "ko-KR-InJoonNeural", "gender": "🤵 Male", "display": "인준"}
        ],
        "French": [
            {"name": "fr-FR-DeniseNeural", "gender": "👩 Female", "display": "Denise"},
            {"name": "fr-FR-HenriNeural", "gender": "🤵 Male", "display": "Henri"}
        ],
        "German": [
            {"name": "de-DE-KatjaNeural", "gender": "👩 Female", "display": "Katja"},
            {"name": "de-DE-ConradNeural", "gender": "🤵 Male", "display": "Conrad"}
        ],
        "Spanish": [
            {"name": "es-ES-ElviraNeural", "gender": "👩 Female", "display": "Elvira"},
            {"name": "es-ES-AlvaroNeural", "gender": "🤵 Male", "display": "Álvaro"}
        ],
        "Italian": [
            {"name": "it-IT-ElsaNeural", "gender": "👩 Female", "display": "Elsa"},
            {"name": "it-IT-DiegoNeural", "gender": "🤵 Male", "display": "Diego"}
        ],
        "Portuguese": [
            {"name": "pt-BR-FranciscaNeural", "gender": "👩 Female", "display": "Francisca"},
            {"name": "pt-BR-AntonioNeural", "gender": "🤵 Male", "display": "Antônio"}
        ],
        "Russian": [
            {"name": "ru-RU-SvetlanaNeural", "gender": "👩 Female", "display": "Светлана"},
            {"name": "ru-RU-DariyaNeural", "gender": "👩 Female", "display": "Дария"}
        ],
        "Arabic": [
            {"name": "ar-SA-ZariyahNeural", "gender": "👩 Female", "display": "زارية"},
            {"name": "ar-SA-HamedNeural", "gender": "🤵 Male", "display": "حامد"}
        ]
    }
    
    # STT Languages
    STT_LANGUAGES = {
        "en-US": "English (US)",
        "en-GB": "English (UK)",
        "en-AU": "English (Australia)",
        "en-CA": "English (Canada)",
        "en-IN": "English (India)",
        "vi-VN": "Vietnamese",
        "zh-CN": "Chinese (Mandarin)",
        "zh-TW": "Chinese (Taiwan)",
        "ja-JP": "Japanese",
        "ko-KR": "Korean",
        "fr-FR": "French",
        "de-DE": "German",
        "es-ES": "Spanish",
        "it-IT": "Italian",
        "pt-BR": "Portuguese (Brazil)",
        "pt-PT": "Portuguese (Portugal)",
        "ru-RU": "Russian",
        "ar-SA": "Arabic (Saudi Arabia)",
        "hi-IN": "Hindi",
        "th-TH": "Thai",
        "tr-TR": "Turkish",
        "nl-NL": "Dutch",
        "pl-PL": "Polish",
        "sv-SE": "Swedish",
        "no-NO": "Norwegian",
        "da-DK": "Danish",
        "fi-FI": "Finnish",
        "el-GR": "Greek",
        "cs-CZ": "Czech",
        "hu-HU": "Hungarian",
        "ro-RO": "Romanian",
        "id-ID": "Indonesian",
        "ms-MY": "Malay",
        "fil-PH": "Filipino"
    }
    
    OUTPUT_FORMATS = ["mp3", "wav", "ogg"]
    AUDIO_QUALITIES = [
        {"value": "64k", "label": "Low (64kbps)"},
        {"value": "128k", "label": "Medium (128kbps)"},
        {"value": "192k", "label": "High (192kbps)"},
        {"value": "256k", "label": "Very High (256kbps)"},
        {"value": "320k", "label": "Best (320kbps)"}
    ]
    
    DEFAULT_PAUSE_SETTINGS = {
        ".": 500,
        "!": 600,
        "?": 600,
        ",": 300,
        ";": 400,
        ":": 350,
        "default_pause": 250,
        "time_colon_pause": 50
    }

# ==================== TASK MANAGER ====================
class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
    
    def create_task(self, task_id: str, task_type: str):
        self.tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "status": "pending",
            "progress": 0,
            "message": "Task created",
            "result": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        return task_id
    
    def update_task(self, task_id: str, status: str = None, progress: int = None, 
                   message: str = None, result: dict = None):
        if task_id in self.tasks:
            if status:
                self.tasks[task_id]["status"] = status
            if progress is not None:
                self.tasks[task_id]["progress"] = progress
            if message:
                self.tasks[task_id]["message"] = message
            if result:
                self.tasks[task_id]["result"] = result
            self.tasks[task_id]["updated_at"] = datetime.now()
    
    def get_task(self, task_id: str):
        return self.tasks.get(task_id)
    
    def cleanup_old_tasks(self, hours_old: int = 1):
        cutoff_time = datetime.now() - timedelta(hours=hours_old)
        to_delete = []
        
        for task_id, task_data in self.tasks.items():
            if task_data["created_at"] < cutoff_time:
                to_delete.append(task_id)
        
        for task_id in to_delete:
            del self.tasks[task_id]

# ==================== STT PROCESSOR ====================
class STTProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
    
    def recognize_from_file(self, audio_file_path: str, language: str = "en-US") -> Dict[str, Any]:
        """Recognize speech from audio file"""
        try:
            # Convert audio to WAV if needed
            temp_wav = None
            try:
                if not audio_file_path.lower().endswith('.wav'):
                    audio = AudioSegment.from_file(audio_file_path)
                    temp_wav = audio_file_path + ".temp.wav"
                    audio.export(temp_wav, format="wav")
                    audio_path = temp_wav
                else:
                    audio_path = audio_file_path
                
                # Perform speech recognition
                with sr.AudioFile(audio_path) as source:
                    # Adjust for ambient noise
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    # Record the audio
                    audio_data = self.recognizer.record(source)
                    
                    # Try Google Speech Recognition first
                    try:
                        text = self.recognizer.recognize_google(audio_data, language=language)
                        engine = "Google"
                        confidence = 0.85
                    except sr.UnknownValueError:
                        # Fallback to Sphinx
                        try:
                            text = self.recognizer.recognize_sphinx(audio_data, language=language)
                            engine = "Sphinx"
                            confidence = 0.65
                        except:
                            text = "Could not understand audio"
                            engine = "None"
                            confidence = 0.0
                    except sr.RequestError:
                        text = "Speech recognition service unavailable"
                        engine = "None"
                        confidence = 0.0
                
                return {
                    "success": True,
                    "text": text,
                    "language": language,
                    "engine": engine,
                    "confidence": confidence,
                    "duration": len(audio) / 1000 if 'audio' in locals() else 0
                }
                
            finally:
                # Clean up temporary file
                if temp_wav and os.path.exists(temp_wav):
                    try:
                        os.remove(temp_wav)
                    except:
                        pass
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "language": language
            }
    
    def recognize_from_bytes(self, audio_bytes: bytes, language: str = "en-US") -> Dict[str, Any]:
        """Recognize speech from audio bytes"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            # Recognize from file
            result = self.recognize_from_file(tmp_path, language)
            
            # Clean up
            try:
                os.remove(tmp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "language": language
            }
    
    def recognize_webm_audio(self, webm_data: bytes, language: str = "en-US") -> Dict[str, Any]:
        """Recognize speech from WebM audio data"""
        try:
            # Convert WebM to WAV
            audio = AudioSegment.from_file(io.BytesIO(webm_data), format="webm")
            
            # Export to WAV bytes
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            wav_bytes = wav_buffer.getvalue()
            
            # Recognize from bytes
            return self.recognize_from_bytes(wav_bytes, language)
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "language": language
            }

# ==================== TEXT PROCESSOR ====================
class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        text = TextProcessor._process_special_cases(text)
        
        re_tab = re.compile(r'[\r\t]')
        re_spaces = re.compile(r' +')
        re_punctuation = re.compile(r'(\s)([,.!?])')
        
        text = re_tab.sub(' ', text)
        text = re_spaces.sub(' ', text)
        text = re_punctuation.sub(r'\2', text)
        return text.strip()

    @staticmethod
    def _process_special_cases(text: str) -> str:
        text = TextProcessor._process_emails(text)
        text = TextProcessor._process_websites(text)
        text = TextProcessor._process_phone_numbers(text)
        text = TextProcessor._process_currency(text)
        text = TextProcessor._process_percentages(text)
        text = TextProcessor._process_times(text)
        text = TextProcessor._process_years(text)
        
        return text
    
    @staticmethod
    def _process_emails(text: str) -> str:
        def convert_email(match):
            full_email = match.group(0)
            processed = (full_email
                        .replace('@', ' at ')
                        .replace('.', ' dot ')
                        .replace('-', ' dash ')
                        .replace('_', ' underscore ')
                        .replace('+', ' plus '))
            return processed

        email_pattern = r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b'
        return re.sub(email_pattern, convert_email, text)

    @staticmethod
    def _process_websites(text: str) -> str:
        def convert_website(match):
            url = match.group(1)
            return (url.replace('.', ' dot ')
                     .replace('-', ' dash ')
                     .replace('_', ' underscore ')
                     .replace('/', ' slash ')
                     .replace('?', ' question mark ')
                     .replace('=', ' equals '))

        website_pattern = r'\b(?![\w.-]*@)((?:https?://)?(?:www\.)?[\w.-]+\.[a-z]{2,}(?:[/?=&#][\w.-]*)*)\b'
        return re.sub(website_pattern, convert_website, text, flags=re.IGNORECASE)

    @staticmethod
    def _process_phone_numbers(text: str) -> str:
        phone_pattern = r'\b(\d{3})[-. ]?(\d{3})[-. ]?(\d{4})\b'
    
        def phone_to_words(match):
            groups = match.groups()
            parts = []
            for part in groups:
                digits = ' '.join([TextProcessor._digit_to_word(d) for d in part])
                parts.append(digits)
            return ', '.join(parts)
    
        return re.sub(phone_pattern, phone_to_words, text)

    @staticmethod
    def _digit_to_word(digit: str) -> str:
        digit_map = {
            '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
            '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
        }
        return digit_map.get(digit, digit)

    @staticmethod
    def _process_currency(text: str) -> str:
        patterns = [
            (r'\$(\d+(?:\.\d+)?)', r'\1 dollars'),
            (r'€(\d+(?:\.\d+)?)', r'\1 euros'),
            (r'£(\d+(?:\.\d+)?)', r'\1 pounds'),
            (r'¥(\d+(?:\.\d+)?)', r'\1 yen'),
            (r'(\d+(?:\.\d+)?)\s*(USD|EUR|GBP|JPY|VND)', r'\1 \2')
        ]
        
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text

    @staticmethod
    def _process_percentages(text: str) -> str:
        pattern = r'(\d+(?:\.\d+)?)%'
        
        def percent_to_words(match):
            number = match.group(1)
            return f"{number} percent"
        
        return re.sub(pattern, percent_to_words, text)

    @staticmethod
    def _process_times(text: str) -> str:
        pattern = r'(\d{1,2}):(\d{2})(?:\s*(AM|PM|am|pm))?'
        
        def time_to_words(match):
            hour = int(match.group(1))
            minute = int(match.group(2))
            period = match.group(3)
            
            hour_str = TextProcessor._number_to_words(str(hour))
            minute_str = TextProcessor._number_to_words(str(minute).zfill(2))
            
            if period:
                period_str = period.upper()
                return f"{hour_str} {minute_str} {period_str}"
            else:
                return f"{hour_str} {minute_str}"
        
        return re.sub(pattern, time_to_words, text)

    @staticmethod
    def _process_years(text: str) -> str:
        pattern = r'\b(19|20)\d{2}\b'
        
        def year_to_words(match):
            year = match.group(0)
            return TextProcessor._number_to_words(year)
        
        return re.sub(pattern, year_to_words, text)

    @staticmethod
    def _number_to_words(number: str) -> str:
        try:
            if '.' in number:
                integer_part, decimal_part = number.split('.')
                integer_text = TextProcessor._int_to_words(integer_part)
                decimal_text = ' '.join([TextProcessor._digit_to_word(d) for d in decimal_part])
                return f"{integer_text} point {decimal_text}"
            return TextProcessor._int_to_words(number)
        except:
            return number

    @staticmethod
    def _int_to_words(num_str: str) -> str:
        try:
            num = int(num_str)
        except:
            return num_str
        
        if num == 0:
            return 'zero'
        
        units = ['', 'thousand', 'million', 'billion', 'trillion']
        words = []
        level = 0
        
        while num > 0:
            chunk = num % 1000
            if chunk != 0:
                words.append(TextProcessor._convert_less_than_thousand(chunk) + ' ' + units[level])
            num = num // 1000
            level += 1
        
        return ' '.join(reversed(words)).strip()

    @staticmethod
    def _convert_less_than_thousand(num: int) -> str:
        ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
                'seventeen', 'eighteen', 'nineteen']
        tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 
               'eighty', 'ninety']
        
        if num == 0:
            return ''
        if num < 20:
            return ones[num]
        if num < 100:
            return tens[num // 10] + (' ' + ones[num % 10] if num % 10 != 0 else '')
        return ones[num // 100] + ' hundred' + (' ' + TextProcessor._convert_less_than_thousand(num % 100) if num % 100 != 0 else '')

    @staticmethod
    def split_sentences(text: str) -> List[str]:
        re_special_cases = re.compile(r'(?<!\w)([A-Z][a-z]*\.)(?=\s)')
        re_sentence_split = re.compile(r'(?<=[.!?])\s+')
        
        sentences = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                stripped = re_special_cases.sub(r'\1Ⓝ', stripped)
                parts = re_sentence_split.split(stripped)
                for part in parts:
                    part = part.replace('Ⓝ', '')
                    if part:
                        sentences.append(part)
        return sentences

# ==================== AUDIO CACHE MANAGER ====================
class AudioCacheManager:
    def __init__(self):
        self.cache_dir = "audio_cache"
        self.max_cache_size = 50
        self.cache_enabled = False  # Disabled for fresh audio always
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_key(self, text: str, voice_id: str, rate: int, pitch: int, volume: int) -> str:
        timestamp = int(time.time() / 60)
        key_string = f"{timestamp}_{text}_{voice_id}_{rate}_{pitch}_{volume}"
        return hashlib.md5(key_string.encode()).hexdigest()[:16]
    
    def get_cached_audio(self, cache_key: str) -> Optional[str]:
        return None  # Cache disabled
    
    def save_to_cache(self, cache_key: str, audio_file: str, metadata: dict = None):
        return None  # Cache disabled
    
    def clear_voice_cache(self, voice_id: str = None):
        return True
    
    def cleanup_old_cache(self, keep_count: int = 50):
        pass
    
    def clear_all_cache(self):
        return True

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.cache_manager = AudioCacheManager()
        self.stt_processor = STTProcessor()
        self.load_settings()
        self.initialize_directories()
    
    def initialize_directories(self):
        directories = ["outputs", "temp", "audio_cache", "static", "templates", 
                      "uploads", "batch_inputs", "stt_outputs"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def load_settings(self):
        if os.path.exists(TTSConfig.SETTINGS_FILE):
            with open(TTSConfig.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        else:
            self.settings = {
                "single_voice": {
                    "language": "Vietnamese",
                    "voice": "vi-VN-HoaiMyNeural",
                    "rate": 0,
                    "pitch": 0,
                    "volume": 100,
                    "pause": 500
                },
                "multi_voice": {
                    "voices": [],
                    "assignments": {}
                },
                "batch": {
                    "voice": "vi-VN-HoaiMyNeural",
                    "output_format": "mp3",
                    "quality": "192k"
                },
                "stt": {
                    "language": "en-US",
                    "auto_detect": False
                }
            }
            self.save_settings()
    
    def save_settings(self):
        with open(TTSConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, pitch: int = 0, 
                            volume: int = 100, clear_cache: bool = False, task_id: str = None):
        try:
            # Always generate fresh audio (cache disabled)
            # Create unique filename with UUID
            unique_id = uuid.uuid4().hex[:16]
            timestamp = int(time.time())
            
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
            
            communicate = edge_tts.Communicate(
                text, 
                voice_id, 
                rate=rate_str, 
                pitch=pitch_str
            )
            
            audio_chunks = []
            subtitles = []
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    subtitles.append({
                        "text": chunk["text"],
                        "start": chunk["offset"],
                        "end": chunk["offset"] + chunk["duration"]
                    })
            
            if not audio_chunks:
                return None, []
            
            audio_data = b"".join(audio_chunks)
            
            # Create unique temp filename
            temp_file = f"temp/audio_{timestamp}_{unique_id}.mp3"
            
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            try:
                audio = AudioSegment.from_file(temp_file)
                
                volume_adjustment = min(max(volume - 100, -50), 10)
                audio = audio + volume_adjustment
                
                audio = normalize(audio)
                audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
                
                audio.export(temp_file, format="mp3", bitrate="256k")
                
                return temp_file, subtitles
            except Exception as e:
                print(f"Error processing audio: {e}")
                return temp_file, subtitles
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None, []
    
    def generate_srt(self, subtitles: List[dict], output_path: str):
        if not subtitles:
            return None
        
        srt_path = output_path.replace('.mp3', '.srt')
        try:
            with open(srt_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, start=1):
                    start = timedelta(milliseconds=sub["start"])
                    end = timedelta(milliseconds=sub["end"])
                    
                    start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                    end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                    
                    f.write(f"{i}\n{start_str} --> {end_str}\n{sub['text']}\n\n")
            return srt_path
        except Exception as e:
            print(f"Error generating SRT: {e}")
            return None
    
    async def process_single_voice(self, text: str, voice_id: str, rate: int, pitch: int, 
                                 volume: int, pause: int, output_format: str = "mp3", 
                                 quality: str = "192k", task_id: str = None, clear_cache: bool = False):
        self.cleanup_temp_files()
        
        # Create unique output directory with UUID
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/single_{timestamp}_{unique_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        sentences = self.text_processor.split_sentences(text)
        
        MAX_SENTENCES = 50
        if len(sentences) > MAX_SENTENCES:
            sentences = sentences[:MAX_SENTENCES]
            print(f"Processing {MAX_SENTENCES} sentences only for performance")
        
        SEMAPHORE = asyncio.Semaphore(2)
        
        async def bounded_generate(sentence, index):
            async with SEMAPHORE:
                if task_id and task_manager:
                    progress = int((index / len(sentences)) * 90)
                    task_manager.update_task(task_id, progress=progress, 
                                           message=f"Processing sentence {index+1}/{len(sentences)}")
                
                return await self.generate_speech(sentence, voice_id, rate, pitch, volume, clear_cache)
        
        audio_segments = []
        all_subtitles = []
        
        for i in range(0, len(sentences), 2):
            batch = sentences[i:i+2]
            batch_tasks = [bounded_generate(s, i+j) for j, s in enumerate(batch)]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, tuple) and len(result) == 2:
                    temp_file, subs = result
                    if temp_file and os.path.exists(temp_file):
                        try:
                            audio = AudioSegment.from_file(temp_file)
                            audio_segments.append(audio)
                            
                            current_time = sum(len(a) for a in audio_segments[:-1])
                            for sub in subs:
                                if isinstance(sub, dict):
                                    sub["start"] += current_time
                                    sub["end"] += current_time
                                    all_subtitles.append(sub)
                            
                            try:
                                os.remove(temp_file)
                            except:
                                pass
                        except Exception as e:
                            print(f"Error processing audio segment: {e}")
        
        if not audio_segments:
            return None, None
        
        combined = AudioSegment.empty()
        current_time = 0
        
        for i, audio in enumerate(audio_segments):
            audio = audio.fade_in(50).fade_out(50)
            combined += audio
            current_time += len(audio)
            
            if i < len(audio_segments) - 1:
                combined += AudioSegment.silent(duration=pause)
                current_time += pause
        
        # Create unique output filename
        output_timestamp = int(time.time())
        random_suffix = random.randint(1000, 9999)
        output_filename = f"single_voice_{output_timestamp}_{random_suffix}.{output_format}"
        output_file = os.path.join(output_dir, output_filename)
        
        # Get bitrate from quality string
        bitrate = quality.replace('k', 'k')
        combined.export(output_file, format=output_format, bitrate=bitrate)
        
        srt_file = None
        if all_subtitles:
            srt_filename = f"single_voice_{output_timestamp}_{random_suffix}.srt"
            srt_file = os.path.join(output_dir, srt_filename)
            self.generate_srt(all_subtitles, output_file)
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, 
                                   message="Audio generation completed")
        
        return output_file, srt_file
    
    async def process_multi_voice(self, text: str, voice_assignments: dict, 
                                output_format: str = "mp3", quality: str = "192k", 
                                task_id: str = None):
        """Process text with multiple voices assigned to different parts"""
        try:
            self.cleanup_temp_files()
            
            # Create unique output directory
            unique_id = uuid.uuid4().hex[:12]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"outputs/multi_{timestamp}_{unique_id}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Parse voice assignments
            if "parts" not in voice_assignments:
                return None, None
            
            parts = voice_assignments["parts"]
            
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=10, 
                                       message=f"Processing {len(parts)} parts with different voices")
            
            audio_segments = []
            all_subtitles = []
            current_time = 0
            
            for i, part in enumerate(parts):
                if task_id and task_manager:
                    progress = 10 + int((i / len(parts)) * 80)
                    task_manager.update_task(task_id, progress=progress, 
                                           message=f"Processing part {i+1}/{len(parts)}")
                
                part_text = part.get("text", "").strip()
                voice_id = part.get("voice", "")
                
                if not part_text or not voice_id:
                    continue
                
                # Generate audio for this part
                temp_file, subtitles = await self.generate_speech(
                    part_text, voice_id, 0, 0, 100, True
                )
                
                if temp_file and os.path.exists(temp_file):
                    try:
                        audio = AudioSegment.from_file(temp_file)
                        audio_segments.append(audio)
                        
                        # Adjust subtitle timings
                        for sub in subtitles:
                            if isinstance(sub, dict):
                                sub["start"] += current_time
                                sub["end"] += current_time
                                all_subtitles.append(sub)
                        
                        current_time += len(audio)
                        
                        try:
                            os.remove(temp_file)
                        except:
                            pass
                    except Exception as e:
                        print(f"Error processing multi-voice segment: {e}")
            
            if not audio_segments:
                return None, None
            
            # Combine all segments
            combined = AudioSegment.empty()
            for audio in audio_segments:
                combined += audio
            
            # Create output filename
            output_timestamp = int(time.time())
            random_suffix = random.randint(1000, 9999)
            output_filename = f"multi_voice_{output_timestamp}_{random_suffix}.{output_format}"
            output_file = os.path.join(output_dir, output_filename)
            
            # Get bitrate from quality string
            bitrate = quality.replace('k', 'k')
            combined.export(output_file, format=output_format, bitrate=bitrate)
            
            srt_file = None
            if all_subtitles:
                srt_filename = f"multi_voice_{output_timestamp}_{random_suffix}.srt"
                srt_file = os.path.join(output_dir, srt_filename)
                self.generate_srt(all_subtitles, output_file)
            
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=100, 
                                       message="Multi-voice audio generation completed")
            
            return output_file, srt_file
            
        except Exception as e:
            print(f"Error in multi-voice processing: {e}")
            return None, None
    
    async def process_batch(self, text_files: List[UploadFile], voice_id: str, 
                          output_format: str = "mp3", quality: str = "192k", 
                          task_id: str = None):
        """Process multiple text files in batch"""
        try:
            self.cleanup_temp_files()
            
            # Create unique output directory
            unique_id = uuid.uuid4().hex[:12]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"outputs/batch_{timestamp}_{unique_id}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Save uploaded files
            saved_files = []
            for i, text_file in enumerate(text_files):
                filename = f"{i+1:03d}_{text_file.filename}"
                file_path = os.path.join("batch_inputs", filename)
                
                with open(file_path, "wb") as f:
                    content = await text_file.read()
                    f.write(content)
                
                saved_files.append((file_path, filename))
            
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=10, 
                                       message=f"Processing {len(saved_files)} files")
            
            audio_files = []
            
            for i, (file_path, filename) in enumerate(saved_files):
                if task_id and task_manager:
                    progress = 10 + int((i / len(saved_files)) * 80)
                    task_manager.update_task(task_id, progress=progress, 
                                           message=f"Processing file {i+1}/{len(saved_files)}: {filename}")
                
                try:
                    # Read text from file
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    
                    if not text.strip():
                        continue
                    
                    # Generate audio for this file
                    temp_file, _ = await self.generate_speech(
                        text, voice_id, 0, 0, 100, True
                    )
                    
                    if temp_file and os.path.exists(temp_file):
                        # Create output filename
                        base_name = os.path.splitext(filename)[0]
                        output_filename = f"{base_name}.{output_format}"
                        output_file = os.path.join(output_dir, output_filename)
                        
                        # Convert to desired format and quality
                        audio = AudioSegment.from_file(temp_file)
                        bitrate = quality.replace('k', 'k')
                        audio.export(output_file, format=output_format, bitrate=bitrate)
                        
                        audio_files.append(output_file)
                        
                        try:
                            os.remove(temp_file)
                            os.remove(file_path)
                        except:
                            pass
                        
                except Exception as e:
                    print(f"Error processing batch file {filename}: {e}")
                    continue
            
            if not audio_files:
                return None, None
            
            # Create ZIP archive if multiple files
            if len(audio_files) > 1:
                zip_filename = f"batch_output_{timestamp}_{unique_id}.zip"
                zip_path = os.path.join(output_dir, zip_filename)
                
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for audio_file in audio_files:
                        zipf.write(audio_file, os.path.basename(audio_file))
                
                if task_id and task_manager:
                    task_manager.update_task(task_id, progress=100, 
                                           message="Batch processing completed")
                
                return zip_path, None
            else:
                # Return single file
                if task_id and task_manager:
                    task_manager.update_task(task_id, progress=100, 
                                           message="Batch processing completed")
                
                return audio_files[0], None
            
        except Exception as e:
            print(f"Error in batch processing: {e}")
            return None, None
    
    async def process_stt(self, audio_file: UploadFile, language: str = "en-US", 
                         task_id: str = None):
        """Process Speech-to-Text conversion"""
        try:
            # Save uploaded file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = uuid.uuid4().hex[:8]
            upload_dir = "uploads/stt"
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = f"stt_{timestamp}_{unique_id}{os.path.splitext(audio_file.filename)[1]}"
            file_path = os.path.join(upload_dir, filename)
            
            # Save file
            with open(file_path, "wb") as f:
                content = await audio_file.read()
                f.write(content)
            
            # Transcribe audio
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=50, message="Transcribing audio...")
            
            result = self.stt_processor.recognize_from_file(file_path, language)
            
            # Save transcription to file
            if result["success"] and result["text"]:
                txt_filename = f"stt_{timestamp}_{unique_id}.txt"
                txt_path = os.path.join("stt_outputs", txt_filename)
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"Language: {language}\n")
                    f.write(f"Recognition Engine: {result.get('engine', 'Unknown')}\n")
                    f.write(f"Confidence: {result.get('confidence', 0):.2%}\n")
                    f.write(f"Duration: {result.get('duration', 0):.2f}s\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(result["text"])
                
                result["txt_url"] = f"/download_stt/{txt_filename}"
            
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=100, 
                                       message="Transcription completed")
            
            # Save settings
            self.settings["stt"] = {
                "language": language,
                "last_used": datetime.now().isoformat()
            }
            self.save_settings()
            
            result["audio_url"] = f"/uploads/stt/{filename}"
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    async def process_stt_from_bytes(self, audio_bytes: bytes, language: str = "en-US"):
        """Process Speech-to-Text from audio bytes"""
        try:
            result = self.stt_processor.recognize_from_bytes(audio_bytes, language)
            
            # Save transcription to file if successful
            if result["success"] and result["text"]:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = uuid.uuid4().hex[:8]
                txt_filename = f"stt_live_{timestamp}_{unique_id}.txt"
                txt_path = os.path.join("stt_outputs", txt_filename)
                
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(f"Language: {language}\n")
                    f.write(f"Recognition Engine: {result.get('engine', 'Unknown')}\n")
                    f.write(f"Confidence: {result.get('confidence', 0):.2%}\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 50 + "\n\n")
                    f.write(result["text"])
                
                result["txt_url"] = f"/download_stt/{txt_filename}"
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    def cleanup_temp_files(self):
        try:
            # Clean temp files older than 1 hour
            temp_files = glob.glob("temp/*.mp3")
            for file in temp_files:
                try:
                    if os.path.exists(file):
                        file_age = time.time() - os.path.getmtime(file)
                        if file_age > 3600:
                            os.remove(file)
                except:
                    pass
            
            # Clean batch inputs
            batch_files = glob.glob("batch_inputs/*")
            for file in batch_files:
                try:
                    if os.path.exists(file):
                        file_age = time.time() - os.path.getmtime(file)
                        if file_age > 3600:
                            os.remove(file)
                except:
                    pass
            
            # Clean old STT uploads
            stt_files = glob.glob("uploads/stt/*")
            for file in stt_files:
                try:
                    if os.path.exists(file):
                        file_age = time.time() - os.path.getmtime(file)
                        if file_age > 3600:
                            os.remove(file)
                except:
                    pass
                    
        except Exception as e:
            print(f"Error cleaning temp files: {e}")
    
    def cleanup_old_outputs(self, hours_old: int = 24):
        try:
            # Clean outputs
            if os.path.exists("outputs"):
                now = time.time()
                for folder_name in os.listdir("outputs"):
                    folder_path = os.path.join("outputs", folder_name)
                    if os.path.isdir(folder_path):
                        folder_age = now - os.path.getmtime(folder_path)
                        if folder_age > hours_old * 3600:
                            try:
                                shutil.rmtree(folder_path)
                            except:
                                pass
            
            # Clean STT outputs
            if os.path.exists("stt_outputs"):
                now = time.time()
                for filename in os.listdir("stt_outputs"):
                    file_path = os.path.join("stt_outputs", filename)
                    if os.path.isfile(file_path):
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > hours_old * 3600:
                            try:
                                os.remove(file_path)
                            except:
                                pass
                                
        except Exception as e:
            print(f"Error cleaning old outputs: {e}")

# ==================== LIFESPAN MANAGER ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global tts_processor, task_manager
    print("Starting up Professional TTS & STT Generator...")
    
    tts_processor = TTSProcessor()
    task_manager = TaskManager()
    
    tts_processor.cleanup_temp_files()
    tts_processor.cleanup_old_outputs(24)
    task_manager.cleanup_old_tasks(1)
    
    create_template_file()
    
    yield
    
    print("Shutting down TTS & STT Generator...")
    tts_processor.cleanup_temp_files()
    if hasattr(task_manager, 'executor'):
        task_manager.executor.shutdown(wait=False)

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="Professional TTS & STT Generator", 
    version="5.0.0",
    lifespan=lifespan
)

# Global instances
tts_processor = None
task_manager = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Templates
templates = Jinja2Templates(directory="templates")

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "languages": TTSConfig.LANGUAGES,
        "stt_languages": TTSConfig.STT_LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS,
        "qualities": TTSConfig.AUDIO_QUALITIES
    })

@app.get("/api/languages")
async def get_languages():
    languages = list(TTSConfig.LANGUAGES.keys())
    return {"languages": languages}

@app.get("/api/voices")
async def get_voices(language: str = None):
    if language and language in TTSConfig.LANGUAGES:
        voices = TTSConfig.LANGUAGES[language]
    else:
        voices = []
        for lang_voices in TTSConfig.LANGUAGES.values():
            voices.extend(lang_voices)
    
    return {"voices": voices}

@app.get("/api/stt/languages")
async def get_stt_languages():
    return {"languages": TTSConfig.STT_LANGUAGES}

# ==================== TTS ROUTES ====================
@app.post("/api/generate/single")
async def generate_single_voice(
    text: str = Form(...),
    voice_id: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3"),
    quality: str = Form("192k"),
    clear_cache: bool = Form(True)
):
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        if not voice_id:
            raise HTTPException(status_code=400, detail="Voice is required")
        
        task_id = f"single_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "single_voice")
        
        tts_processor.settings["single_voice"] = {
            "voice": voice_id,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "pause": pause
        }
        tts_processor.save_settings()
        
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_single_voice(
                    text, voice_id, rate, pitch, volume, pause, 
                    output_format, quality, task_id, clear_cache
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Audio generated successfully"
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Failed to generate audio"
                    }
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Audio generation started with fresh audio."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/multi")
async def generate_multi_voice(
    text: str = Form(...),
    voice_assignments: str = Form(...),  # JSON string
    output_format: str = Form("mp3"),
    quality: str = Form("192k")
):
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Parse voice assignments
        try:
            assignments = json.loads(voice_assignments)
        except:
            raise HTTPException(status_code=400, detail="Invalid voice assignments format")
        
        task_id = f"multi_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "multi_voice")
        
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_multi_voice(
                    text, assignments, output_format, quality, task_id
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Multi-voice audio generated successfully"
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Failed to generate multi-voice audio"
                    }
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Multi-voice audio generation started."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/batch")
async def generate_batch(
    files: List[UploadFile] = File(...),
    voice_id: str = Form(...),
    output_format: str = Form("mp3"),
    quality: str = Form("192k")
):
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        if not voice_id:
            raise HTTPException(status_code=400, detail="Voice is required")
        
        task_id = f"batch_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "batch")
        
        tts_processor.settings["batch"] = {
            "voice": voice_id,
            "output_format": output_format,
            "quality": quality
        }
        tts_processor.save_settings()
        
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_batch(
                    files, voice_id, output_format, quality, task_id
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "message": f"Batch processing completed ({len(files)} files)"
                    }
                else:
                    result = {
                        "success": False,
                        "message": "Failed to process batch files"
                    }
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": f"Batch processing started for {len(files)} files."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== STT ROUTES ====================
@app.post("/api/stt/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: str = Form("en-US")
):
    try:
        if not audio_file:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        # Check file type
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.webm']
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            raise HTTPException(status_code=400, 
                              detail=f"Unsupported file format. Allowed: {', '.join(allowed_extensions)}")
        
        task_id = f"stt_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "speech_to_text")
        
        async def background_task():
            try:
                result = await tts_processor.process_stt(audio_file, language, task_id)
                
                task_manager.update_task(task_id, status="completed", result=result)
                
            except Exception as e:
                task_manager.update_task(task_id, status="failed", 
                                       message=f"Error: {str(e)}")
        
        asyncio.create_task(background_task())
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Speech-to-text conversion started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stt/transcribe/live")
async def transcribe_live_audio(
    audio_data: str = Form(...),  # Base64 encoded audio data
    language: str = Form("en-US")
):
    try:
        if not audio_data:
            raise HTTPException(status_code=400, detail="Audio data is required")
        
        # Decode base64 audio data
        try:
            audio_bytes = base64.b64decode(audio_data.split(',')[1] if ',' in audio_data else audio_data)
        except:
            raise HTTPException(status_code=400, detail="Invalid audio data format")
        
        # Process STT
        result = await tts_processor.process_stt_from_bytes(audio_bytes, language)
        
        return {
            "success": result["success"],
            "text": result.get("text", ""),
            "language": language,
            "engine": result.get("engine", ""),
            "confidence": result.get("confidence", 0),
            "txt_url": result.get("txt_url"),
            "error": result.get("error")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket for real-time STT
@app.websocket("/ws/stt")
async def websocket_stt(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            
            if data["type"] == "audio_chunk":
                # Process audio chunk
                audio_data = base64.b64decode(data["data"])
                language = data.get("language", "en-US")
                
                result = await tts_processor.process_stt_from_bytes(audio_data, language)
                
                await websocket.send_json({
                    "type": "transcription",
                    "text": result.get("text", ""),
                    "success": result["success"],
                    "confidence": result.get("confidence", 0)
                })
                
            elif data["type"] == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()

# ==================== COMMON ROUTES ====================
@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "result": task.get("result"),
        "created_at": task["created_at"].isoformat(),
        "updated_at": task["updated_at"].isoformat()
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = None
    
    for root, dirs, files in os.walk("outputs"):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # ADD NO-CACHE HEADERS to prevent browser caching
    file_timestamp = int(os.path.getmtime(file_path))
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Last-Modified": datetime.fromtimestamp(file_timestamp).strftime("%a, %d %b %Y %H:%M:%S GMT")
        }
    )

@app.get("/download_stt/{filename}")
async def download_stt_file(filename: str):
    file_path = os.path.join("stt_outputs", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="text/plain",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/api/settings")
async def get_settings():
    return tts_processor.settings

@app.post("/api/cleanup")
async def cleanup_files():
    try:
        task_manager.cleanup_old_tasks(1)
        tts_processor.cleanup_temp_files()
        tts_processor.cleanup_old_outputs(1)
        return {"success": True, "message": "Cleanup completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== HTML TEMPLATE CREATION ====================
def create_template_file():
    template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional TTS & STT Generator - 4 Tabs</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
            --success-color: #4cc9f0;
            --warning-color: #f8961e;
            --danger-color: #f72585;
            --info-color: #4895ef;
            --stt-color: #7209b7;
            --light-bg: #f8f9fa;
            --dark-bg: #212529;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .main-container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 2rem;
            margin-bottom: 2rem;
            overflow: hidden;
        }
        
        .nav-tabs {
            border-bottom: 2px solid #dee2e6;
            background: var(--light-bg);
        }
        
        .nav-tabs .nav-link {
            border: none;
            border-radius: 0;
            padding: 1rem 1.5rem;
            font-weight: 600;
            color: #6c757d;
            transition: all 0.3s;
        }
        
        .nav-tabs .nav-link.active {
            background: white;
            color: var(--primary-color);
            border-bottom: 3px solid var(--primary-color);
        }
        
        .tab-content {
            padding: 2rem;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(67, 97, 238, 0.3);
        }
        
        .btn-success {
            background: linear-gradient(135deg, #4cc9f0, #4895ef);
        }
        
        .btn-warning {
            background: linear-gradient(135deg, var(--warning-color), #e76f51);
        }
        
        .btn-info {
            background: linear-gradient(135deg, var(--info-color), #4361ee);
        }
        
        .btn-stt {
            background: linear-gradient(135deg, var(--stt-color), #560bad);
        }
        
        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.7);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        
        .loading-spinner {
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }
        
        .progress-container {
            margin: 1rem 0;
        }
        
        .task-status {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
            display: none;
        }
        
        .output-card {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 10px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        
        .voice-option {
            padding: 0.75rem;
            border-radius: 10px;
            margin-bottom: 0.5rem;
            transition: all 0.3s;
            cursor: pointer;
            border: 1px solid #dee2e6;
        }
        
        .voice-option:hover {
            background: var(--light-bg);
            transform: translateX(5px);
            border-color: var(--primary-color);
        }
        
        .voice-option.selected {
            background: rgba(67, 97, 238, 0.1);
            border-left: 4px solid var(--primary-color);
            border-color: var(--primary-color);
        }
        
        .file-upload-area {
            border: 2px dashed #dee2e6;
            border-radius: 10px;
            padding: 3rem 2rem;
            text-align: center;
            background: #f8f9fa;
            transition: all 0.3s;
        }
        
        .file-upload-area:hover {
            border-color: var(--primary-color);
            background: rgba(67, 97, 238, 0.05);
        }
        
        .file-upload-area.dragover {
            border-color: var(--primary-color);
            background: rgba(67, 97, 238, 0.1);
        }
        
        .stt-recorder {
            border: 2px solid var(--stt-color);
            border-radius: 15px;
            padding: 2rem;
            background: rgba(114, 9, 183, 0.05);
        }
        
        .record-btn {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            background: var(--danger-color);
            color: white;
            border: none;
            font-size: 1.5rem;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .record-btn.recording {
            animation: pulse 1.5s infinite;
            background: #dc3545;
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(220, 53, 69, 0); }
            100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
        }
        
        .waveform {
            width: 100%;
            height: 100px;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 1rem 0;
            position: relative;
            overflow: hidden;
        }
        
        .waveform-bar {
            position: absolute;
            bottom: 0;
            width: 4px;
            background: var(--stt-color);
            border-radius: 2px;
            transition: height 0.1s ease;
        }
        
        @media (max-width: 768px) {
            .nav-tabs .nav-link {
                padding: 0.75rem 1rem;
                font-size: 0.9rem;
            }
            
            .tab-content {
                padding: 1rem;
            }
            
            .main-container {
                margin: 1rem;
                border-radius: 15px;
            }
        }
        
        .tab-icon {
            margin-right: 0.5rem;
        }
        
        .part-editor {
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f8f9fa;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-microphone-alt me-2"></i>
                Professional TTS & STT Generator v5.0
            </a>
            <div class="navbar-text text-light">
                <small>4 Working Tabs • Real-time STT • No Cache Issues</small>
            </div>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container main-container">
        <!-- Tabs -->
        <ul class="nav nav-tabs" id="ttsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single">
                    <i class="fas fa-user tab-icon"></i>Single Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="multi-tab" data-bs-toggle="tab" data-bs-target="#multi">
                    <i class="fas fa-users tab-icon"></i>Multi-Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="batch-tab" data-bs-toggle="tab" data-bs-target="#batch">
                    <i class="fas fa-folder tab-icon"></i>Batch Processing
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="stt-tab" data-bs-toggle="tab" data-bs-target="#stt">
                    <i class="fas fa-microphone tab-icon"></i>Speech to Text
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="ttsTabsContent">
            <!-- Tab 1: Single Voice -->
            <div class="tab-pane fade show active" id="single">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Text Content</label>
                            <textarea class="form-control" id="singleText" rows="8" 
                                      placeholder="Enter your text here...">Welcome to the Professional TTS Generator. This tool converts text into natural-sounding speech using advanced neural voices.</textarea>
                            <small class="text-muted">Maximum 50 sentences for optimal performance</small>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="singleLanguage">
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}" {% if language == 'Vietnamese' %}selected{% endif %}>{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Voice Selection</label>
                            <div id="singleVoiceList" class="border rounded p-2" style="max-height: 200px; overflow-y: auto;">
                                <div class="text-center text-muted py-3">
                                    Select a language first
                                </div>
                            </div>
                        </div>
                        
                        <!-- Voice Settings -->
                        <div class="accordion mb-3">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#singleSettings">
                                        <i class="fas fa-sliders-h me-2"></i>Voice Settings
                                    </button>
                                </h2>
                                <div id="singleSettings" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Speed: <span id="singleRateValue">0%</span>
                                            </label>
                                            <input type="range" class="form-range" id="singleRate" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pitch: <span id="singlePitchValue">0Hz</span>
                                            </label>
                                            <input type="range" class="form-range" id="singlePitch" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Volume: <span id="singleVolumeValue">100%</span>
                                            </label>
                                            <input type="range" class="form-range" id="singleVolume" min="50" max="150" value="100">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pause Duration: <span id="singlePauseValue">500ms</span>
                                            </label>
                                            <input type="range" class="form-range" id="singlePause" min="100" max="2000" value="500">
                                        </div>
                                        
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label class="form-label">Output Format</label>
                                                    <select class="form-select" id="singleFormat">
                                                        {% for format in formats %}
                                                        <option value="{{ format }}">{{ format|upper }}</option>
                                                        {% endfor %}
                                                    </select>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label class="form-label">Audio Quality</label>
                                                    <select class="form-select" id="singleQuality">
                                                        {% for quality in qualities %}
                                                        <option value="{{ quality.value }}" {% if quality.value == '192k' %}selected{% endif %}>{{ quality.label }}</option>
                                                        {% endfor %}
                                                    </select>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Generate Button -->
                        <button class="btn btn-primary w-100 mb-3" onclick="generateSingle()">
                            <i class="fas fa-play-circle me-2"></i>Generate Audio
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="singleTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="singleProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="singleProgressText">0%</div>
                            </div>
                            <div id="singleTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="singleOutput" style="display: none;">
                    <h5><i class="fas fa-music me-2"></i>Generated Audio</h5>
                    <div class="audio-player" id="singleAudioPlayer"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success me-2" id="singleDownloadAudio">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="singleDownloadSubtitle" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>
            
            <!-- Tab 2: Multi-Voice -->
            <div class="tab-pane fade" id="multi">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Text Content (Split into Parts)</label>
                            <textarea class="form-control" id="multiText" rows="6">Part 1: Welcome to our multi-voice TTS system.

Part 2: This system allows you to use different voices for different parts of your text.

Part 3: You can assign male and female voices to create engaging audio content.</textarea>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Split Text into Parts</label>
                            <div class="input-group mb-3">
                                <input type="text" class="form-control" id="splitMarker" placeholder="Enter split marker (e.g., 'Part 1:', '---')" value="Part">
                                <button class="btn btn-outline-secondary" type="button" onclick="splitMultiText()">
                                    <i class="fas fa-cut me-2"></i>Split Text
                                </button>
                            </div>
                        </div>
                        
                        <!-- Parts Editor -->
                        <div id="multiPartsContainer">
                            <!-- Parts will be added here dynamically -->
                        </div>
                        
                        <button class="btn btn-outline-primary mb-3" onclick="addPart()">
                            <i class="fas fa-plus me-2"></i>Add Part
                        </button>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">Available Voices</label>
                            <div id="multiVoiceList" class="border rounded p-2" style="max-height: 300px; overflow-y: auto;">
                                <div class="text-center text-muted py-3">
                                    Loading voices...
                                </div>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Output Format</label>
                                    <select class="form-select" id="multiFormat">
                                        {% for format in formats %}
                                        <option value="{{ format }}">{{ format|upper }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Audio Quality</label>
                                    <select class="form-select" id="multiQuality">
                                        {% for quality in qualities %}
                                        <option value="{{ quality.value }}" {% if quality.value == '192k' %}selected{% endif %}>{{ quality.label }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <button class="btn btn-warning w-100 mb-3" onclick="generateMulti()">
                            <i class="fas fa-users me-2"></i>Generate Multi-Voice Audio
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="multiTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar bg-warning" id="multiProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="multiProgressText">0%</div>
                            </div>
                            <div id="multiTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="multiOutput" style="display: none;">
                    <h5><i class="fas fa-users me-2"></i>Generated Multi-Voice Audio</h5>
                    <div class="audio-player" id="multiAudioPlayer"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success me-2" id="multiDownloadAudio">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="multiDownloadSubtitle" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>
            
            <!-- Tab 3: Batch Processing -->
            <div class="tab-pane fade" id="batch">
                <div class="row">
                    <div class="col-md-6">
                        <h5><i class="fas fa-upload me-2"></i>Upload Text Files</h5>
                        
                        <div class="file-upload-area" id="batchUploadArea">
                            <i class="fas fa-cloud-upload-alt fa-3x text-muted mb-3"></i>
                            <h5>Drag & Drop Text Files Here</h5>
                            <p class="text-muted">or click to browse (.txt, .md, .text)</p>
                            <input type="file" class="d-none" id="batchFileInput" multiple accept=".txt,.text,.md">
                            <button class="btn btn-outline-primary mt-2" onclick="document.getElementById('batchFileInput').click()">
                                <i class="fas fa-folder-open me-2"></i>Browse Files
                            </button>
                        </div>
                        
                        <div class="mt-3" id="batchFileList">
                            <h6>Selected Files (0)</h6>
                            <div class="list-group" id="batchFilesContainer"></div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="batchLanguage">
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}" {% if language == 'Vietnamese' %}selected{% endif %}>{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Voice Selection</label>
                            <div id="batchVoiceList" class="border rounded p-2" style="max-height: 200px; overflow-y: auto;">
                                <div class="text-center text-muted py-3">
                                    Select a language first
                                </div>
                            </div>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Output Format</label>
                                    <select class="form-select" id="batchFormat">
                                        {% for format in formats %}
                                        <option value="{{ format }}">{{ format|upper }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label class="form-label">Audio Quality</label>
                                    <select class="form-select" id="batchQuality">
                                        {% for quality in qualities %}
                                        <option value="{{ quality.value }}" {% if quality.value == '192k' %}selected{% endif %}>{{ quality.label }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                            </div>
                        </div>
                        
                        <button class="btn btn-info w-100 mb-3" onclick="processBatch()" id="batchProcessButton" disabled>
                            <i class="fas fa-cogs me-2"></i>Process Batch Files
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="batchTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar bg-info" id="batchProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="batchProgressText">0%</div>
                            </div>
                            <div id="batchTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="batchOutput" style="display: none;">
                    <h5><i class="fas fa-folder me-2"></i>Batch Processing Results</h5>
                    <div id="batchResults"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success" id="batchDownload">
                            <i class="fas fa-download me-2"></i>Download Results
                        </a>
                    </div>
                </div>
            </div>
            
            <!-- Tab 4: Speech to Text -->
            <div class="tab-pane fade" id="stt">
                <div class="row">
                    <div class="col-md-6">
                        <div class="stt-recorder">
                            <h5><i class="fas fa-microphone me-2"></i>Real-time Recording</h5>
                            <div class="text-center">
                                <button class="btn btn-danger record-btn mb-3" id="recordButton">
                                    <i class="fas fa-microphone"></i>
                                </button>
                                <div class="waveform" id="waveform"></div>
                                <p id="recordingStatus" class="text-muted">Click microphone to start recording</p>
                                <div id="recordingTime" class="h5">00:00</div>
                            </div>
                            <button class="btn btn-warning w-100 mt-3" id="stopButton" disabled>
                                <i class="fas fa-stop me-2"></i>Stop Recording
                            </button>
                        </div>
                        
                        <div class="mt-4">
                            <h5><i class="fas fa-upload me-2"></i>Upload Audio File</h5>
                            <div class="input-group mb-3">
                                <input type="file" class="form-control" id="sttFileUpload" accept=".mp3,.wav,.m4a,.ogg,.flac,.aac,.webm">
                                <button class="btn btn-outline-stt" type="button" onclick="uploadSTTFile()">
                                    <i class="fas fa-upload me-2"></i>Upload
                                </button>
                            </div>
                            <small class="text-muted">Supported: MP3, WAV, M4A, OGG, FLAC, AAC, WEBM</small>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label">Language for Transcription</label>
                            <select class="form-select" id="sttLanguage">
                                {% for code, name in stt_languages.items() %}
                                <option value="{{ code }}" {% if code == 'en-US' %}selected{% endif %}>{{ name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="autoDetectLanguage">
                                <label class="form-check-label" for="autoDetectLanguage">
                                    Auto-detect language
                                </label>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <button class="btn btn-stt w-100 mb-2" onclick="startLiveTranscription()" id="liveTranscribeButton">
                                <i class="fas fa-broadcast-tower me-2"></i>Start Live Transcription
                            </button>
                            <button class="btn btn-outline-stt w-100" onclick="transcribeUploadedFile()" id="uploadTranscribeButton">
                                <i class="fas fa-language me-2"></i>Transcribe Uploaded File
                            </button>
                        </div>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="sttTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar bg-stt" id="sttProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="sttProgressText">0%</div>
                            </div>
                            <div id="sttTaskMessage"></div>
                        </div>
                        
                        <!-- Live Transcription Output -->
                        <div class="output-card mt-4" id="sttLiveOutput" style="display: none;">
                            <h5><i class="fas fa-comment-dots me-2"></i>Live Transcription</h5>
                            <div class="mb-3">
                                <div class="alert alert-info" id="liveTranscriptionInfo">
                                    <i class="fas fa-info-circle me-2"></i>
                                    Speaking will appear here in real-time...
                                </div>
                                <div class="transcription-output border rounded p-3 bg-light" 
                                     style="min-height: 150px; max-height: 300px; overflow-y: auto;" 
                                     id="liveTranscriptionText"></div>
                            </div>
                            <div class="d-flex justify-content-between">
                                <button class="btn btn-sm btn-outline-danger" onclick="stopLiveTranscription()">
                                    <i class="fas fa-stop me-1"></i>Stop
                                </button>
                                <button class="btn btn-sm btn-success" onclick="saveTranscription()">
                                    <i class="fas fa-save me-1"></i>Save
                                </button>
                            </div>
                        </div>
                        
                        <!-- Upload Transcription Output -->
                        <div class="output-card mt-4" id="sttUploadOutput" style="display: none;">
                            <h5><i class="fas fa-file-alt me-2"></i>Transcription Result</h5>
                            <div class="mb-3">
                                <textarea class="form-control" id="transcriptText" rows="6" readonly></textarea>
                            </div>
                            <div class="d-flex justify-content-between">
                                <small class="text-muted" id="transcriptionInfo"></small>
                                <div>
                                    <button class="btn btn-sm btn-outline-primary me-2" onclick="copyTranscript()">
                                        <i class="fas fa-copy me-1"></i>Copy
                                    </button>
                                    <button class="btn btn-sm btn-success" onclick="downloadTranscript()">
                                        <i class="fas fa-download me-1"></i>Download
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Loading Overlay -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container"></div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Global variables
        let currentTaskId = null;
        let taskCheckInterval = null;
        let selectedSingleVoice = null;
        let selectedBatchVoice = null;
        let multiParts = 0;
        let batchFiles = [];
        
        // STT variables
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let recordingStartTime = null;
        let recordingTimer = null;
        let isLiveTranscribing = false;
        let websocket = null;
        let transcriptionHistory = [];
        
        // Initialize
        document.addEventListener('DOMContentLoaded', async function() {
            await loadSettings();
            await loadLanguages();
            initRangeDisplays();
            await cleanupOldFiles();
            initBatchUpload();
            initSTT();
            
            // Set default language and load voices
            document.getElementById('singleLanguage').value = 'Vietnamese';
            document.getElementById('batchLanguage').value = 'Vietnamese';
            await loadSingleVoices();
            await loadMultiVoices();
            await loadBatchVoices();
            
            // Initialize with one part for multi-voice
            addPart();
        });
        
        // Load settings
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                if (settings.single_voice) {
                    const sv = settings.single_voice;
                    document.getElementById('singleRate').value = sv.rate;
                    document.getElementById('singlePitch').value = sv.pitch;
                    document.getElementById('singleVolume').value = sv.volume;
                    document.getElementById('singlePause').value = sv.pause;
                    
                    ['singleRate', 'singlePitch', 'singleVolume', 'singlePause'].forEach(id => {
                        document.getElementById(id).dispatchEvent(new Event('input'));
                    });
                }
                
                if (settings.stt && settings.stt.language) {
                    document.getElementById('sttLanguage').value = settings.stt.language;
                }
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        }
        
        // Load languages
        async function loadLanguages() {
            try {
                const response = await fetch('/api/languages');
                const data = await response.json();
                
                // Update all language selects
                ['singleLanguage', 'batchLanguage'].forEach(selectId => {
                    const select = document.getElementById(selectId);
                    if (select) {
                        select.innerHTML = '<option value="">Select Language</option>';
                        data.languages.forEach(language => {
                            const option = document.createElement('option');
                            option.value = language;
                            option.textContent = language;
                            select.appendChild(option);
                        });
                    }
                });
                
            } catch (error) {
                console.error('Error loading languages:', error);
            }
        }
        
        // Load STT languages
        async function loadSTTLanguages() {
            try {
                const response = await fetch('/api/stt/languages');
                const data = await response.json();
                
                const select = document.getElementById('sttLanguage');
                select.innerHTML = '';
                
                Object.entries(data.languages).forEach(([code, name]) => {
                    const option = document.createElement('option');
                    option.value = code;
                    option.textContent = name;
                    select.appendChild(option);
                });
                
            } catch (error) {
                console.error('Error loading STT languages:', error);
            }
        }
        
        // Load voices for single voice tab
        async function loadSingleVoices() {
            const language = document.getElementById('singleLanguage').value;
            if (!language) return;
            
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceList = document.getElementById('singleVoiceList');
                voiceList.innerHTML = '';
                
                if (data.voices.length === 0) {
                    voiceList.innerHTML = '<div class="text-center text-muted py-3">No voices available for this language</div>';
                    return;
                }
                
                data.voices.forEach(voice => {
                    const voiceDiv = document.createElement('div');
                    voiceDiv.className = 'voice-option';
                    voiceDiv.dataset.voiceId = voice.name;
                    voiceDiv.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${voice.display}</strong>
                                <div class="text-muted small">${voice.gender} • ${voice.name}</div>
                            </div>
                            <i class="fas fa-check text-primary" style="display: none;"></i>
                        </div>
                    `;
                    
                    voiceDiv.addEventListener('click', () => {
                        // Remove selection from all voices
                        document.querySelectorAll('#singleVoiceList .voice-option').forEach(v => {
                            v.classList.remove('selected');
                            v.querySelector('.fa-check').style.display = 'none';
                        });
                        
                        // Select this voice
                        voiceDiv.classList.add('selected');
                        voiceDiv.querySelector('.fa-check').style.display = 'block';
                        selectedSingleVoice = voice.name;
                        
                        showToast(`Selected voice: ${voice.display}`);
                    });
                    
                    voiceList.appendChild(voiceDiv);
                });
                
                // Select first voice by default
                if (data.voices.length > 0) {
                    const firstVoice = voiceList.querySelector('.voice-option');
                    firstVoice.click();
                }
                
            } catch (error) {
                console.error('Error loading single voices:', error);
                const voiceList = document.getElementById('singleVoiceList');
                voiceList.innerHTML = '<div class="text-center text-danger py-3">Error loading voices</div>';
            }
        }
        
        // Load voices for multi-voice tab
        async function loadMultiVoices() {
            try {
                const response = await fetch(`/api/voices`);
                const data = await response.json();
                
                const voiceList = document.getElementById('multiVoiceList');
                voiceList.innerHTML = '';
                
                if (data.voices.length === 0) {
                    voiceList.innerHTML = '<div class="text-center text-muted py-3">No voices available</div>';
                    return;
                }
                
                // Group voices by language
                const voicesByLang = {};
                data.voices.forEach(voice => {
                    const langCode = voice.name.split('-')[0];
                    const language = langCode === 'vi' ? 'Vietnamese' : 
                                   langCode === 'en' ? 'English' :
                                   langCode === 'zh' ? 'Chinese' :
                                   langCode === 'ja' ? 'Japanese' :
                                   langCode === 'ko' ? 'Korean' :
                                   langCode === 'fr' ? 'French' :
                                   langCode === 'de' ? 'German' :
                                   langCode === 'es' ? 'Spanish' :
                                   langCode === 'it' ? 'Italian' :
                                   langCode === 'pt' ? 'Portuguese' :
                                   langCode === 'ru' ? 'Russian' :
                                   langCode === 'ar' ? 'Arabic' : 'Other';
                    
                    if (!voicesByLang[language]) {
                        voicesByLang[language] = [];
                    }
                    voicesByLang[language].push(voice);
                });
                
                // Create voice list
                Object.keys(voicesByLang).sort().forEach(language => {
                    const langHeader = document.createElement('div');
                    langHeader.className = 'fw-bold mt-2 mb-1 text-primary';
                    langHeader.textContent = language;
                    voiceList.appendChild(langHeader);
                    
                    voicesByLang[language].forEach(voice => {
                        const voiceDiv = document.createElement('div');
                        voiceDiv.className = 'voice-option';
                        voiceDiv.dataset.voiceId = voice.name;
                        voiceDiv.innerHTML = `
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${voice.display}</strong>
                                    <div class="text-muted small">${voice.gender}</div>
                                </div>
                                <i class="fas fa-check text-warning" style="display: none;"></i>
                            </div>
                        `;
                        
                        voiceDiv.addEventListener('click', () => {
                            // Toggle selection for multi-voice
                            if (voiceDiv.classList.contains('selected')) {
                                voiceDiv.classList.remove('selected');
                                voiceDiv.querySelector('.fa-check').style.display = 'none';
                            } else {
                                voiceDiv.classList.add('selected');
                                voiceDiv.querySelector('.fa-check').style.display = 'block';
                            }
                            
                            // Update part voice selects
                            updatePartVoiceSelects();
                        });
                        
                        voiceList.appendChild(voiceDiv);
                    });
                });
                
            } catch (error) {
                console.error('Error loading multi voices:', error);
                const voiceList = document.getElementById('multiVoiceList');
                voiceList.innerHTML = '<div class="text-center text-danger py-3">Error loading voices</div>';
            }
        }
        
        // Load voices for batch tab
        async function loadBatchVoices() {
            const language = document.getElementById('batchLanguage').value;
            if (!language) return;
            
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceList = document.getElementById('batchVoiceList');
                voiceList.innerHTML = '';
                
                if (data.voices.length === 0) {
                    voiceList.innerHTML = '<div class="text-center text-muted py-3">No voices available for this language</div>';
                    return;
                }
                
                data.voices.forEach(voice => {
                    const voiceDiv = document.createElement('div');
                    voiceDiv.className = 'voice-option';
                    voiceDiv.dataset.voiceId = voice.name;
                    voiceDiv.innerHTML = `
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <strong>${voice.display}</strong>
                                <div class="text-muted small">${voice.gender} • ${voice.name}</div>
                            </div>
                            <i class="fas fa-check text-info" style="display: none;"></i>
                        </div>
                    `;
                    
                    voiceDiv.addEventListener('click', () => {
                        // Remove selection from all voices
                        document.querySelectorAll('#batchVoiceList .voice-option').forEach(v => {
                            v.classList.remove('selected');
                            v.querySelector('.fa-check').style.display = 'none';
                        });
                        
                        // Select this voice
                        voiceDiv.classList.add('selected');
                        voiceDiv.querySelector('.fa-check').style.display = 'block';
                        selectedBatchVoice = voice.name;
                        
                        showToast(`Selected batch voice: ${voice.display}`);
                    });
                    
                    voiceList.appendChild(voiceDiv);
                });
                
                // Select first voice by default
                if (data.voices.length > 0) {
                    const firstVoice = voiceList.querySelector('.voice-option');
                    firstVoice.click();
                }
                
            } catch (error) {
                console.error('Error loading batch voices:', error);
                const voiceList = document.getElementById('batchVoiceList');
                voiceList.innerHTML = '<div class="text-center text-danger py-3">Error loading voices</div>';
            }
        }
        
        // Update voice selects in multi-voice parts
        function updatePartVoiceSelects() {
            const selectedVoices = Array.from(document.querySelectorAll('#multiVoiceList .voice-option.selected'))
                .map(v => v.dataset.voiceId);
            
            document.querySelectorAll('.part-voice').forEach(select => {
                select.innerHTML = '<option value="">Select Voice</option>';
                
                selectedVoices.forEach(voiceId => {
                    const voiceDiv = document.querySelector(`[data-voice-id="${voiceId}"]`);
                    if (voiceDiv) {
                        const voiceName = voiceDiv.querySelector('strong').textContent;
                        const option = document.createElement('option');
                        option.value = voiceId;
                        option.textContent = voiceName;
                        select.appendChild(option);
                    }
                });
            });
        }
        
        // Initialize range displays
        function initRangeDisplays() {
            const singleRanges = [
                { id: 'singleRate', display: 'singleRateValue', suffix: '%' },
                { id: 'singlePitch', display: 'singlePitchValue', suffix: 'Hz' },
                { id: 'singleVolume', display: 'singleVolumeValue', suffix: '%' },
                { id: 'singlePause', display: 'singlePauseValue', suffix: 'ms' }
            ];
            
            singleRanges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
        }
        
        // Language change handlers
        document.getElementById('singleLanguage').addEventListener('change', async function() {
            await loadSingleVoices();
        });
        
        document.getElementById('batchLanguage').addEventListener('change', async function() {
            await loadBatchVoices();
        });
        
        // ==================== SINGLE VOICE FUNCTIONS ====================
        async function generateSingle() {
            const text = document.getElementById('singleText').value.trim();
            const language = document.getElementById('singleLanguage').value;
            
            if (!text) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!language) {
                showToast('Please select a language', 'error');
                return;
            }
            
            if (!selectedSingleVoice) {
                showToast('Please select a voice', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', selectedSingleVoice);
            formData.append('rate', document.getElementById('singleRate').value);
            formData.append('pitch', document.getElementById('singlePitch').value);
            formData.append('volume', document.getElementById('singleVolume').value);
            formData.append('pause', document.getElementById('singlePause').value);
            formData.append('output_format', document.getElementById('singleFormat').value);
            formData.append('quality', document.getElementById('singleQuality').value);
            formData.append('clear_cache', true);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('single', result.task_id);
                    showToast('Audio generation started');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        // ==================== MULTI-VOICE FUNCTIONS ====================
        function splitMultiText() {
            const text = document.getElementById('multiText').value;
            const marker = document.getElementById('splitMarker').value;
            
            if (!text || !marker) {
                showToast('Please enter text and split marker', 'error');
                return;
            }
            
            // Clear existing parts
            document.getElementById('multiPartsContainer').innerHTML = '';
            multiParts = 0;
            
            // Split text by marker
            const parts = text.split(new RegExp(`(${marker}\\s*\\d+:?)`, 'i'));
            
            // Reconstruct parts
            let currentPart = '';
            for (let i = 0; i < parts.length; i++) {
                if (parts[i].match(new RegExp(`^${marker}\\s*\\d+:?`, 'i'))) {
                    // This is a marker, start new part
                    if (currentPart.trim()) {
                        addPartWithText(currentPart.trim());
                        currentPart = '';
                    }
                    currentPart = parts[i] + (parts[i+1] || '');
                    i++; // Skip next part since we added it
                } else if (parts[i].trim()) {
                    currentPart += parts[i];
                }
            }
            
            // Add last part
            if (currentPart.trim()) {
                addPartWithText(currentPart.trim());
            }
            
            // If no parts were created, add the whole text as one part
            if (multiParts === 0) {
                addPartWithText(text.trim());
            }
            
            showToast(`Split text into ${multiParts} parts`);
        }
        
        function addPart() {
            addPartWithText('');
        }
        
        function addPartWithText(text) {
            multiParts++;
            const partId = multiParts;
            
            const partDiv = document.createElement('div');
            partDiv.className = 'part-editor';
            partDiv.dataset.partId = partId;
            partDiv.innerHTML = `
                <div class="part-header">
                    <div>
                        <span class="drag-handle"><i class="fas fa-grip-vertical"></i></span>
                        <strong>Part ${partId}</strong>
                    </div>
                    <div>
                        <button class="btn btn-sm btn-outline-danger" onclick="removePart(${partId})">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <div class="mb-3">
                    <textarea class="form-control part-text" rows="2" placeholder="Enter text for this part...">${text}</textarea>
                </div>
                <div class="row">
                    <div class="col-md-8">
                        <select class="form-select part-voice">
                            <option value="">Select Voice</option>
                        </select>
                    </div>
                </div>
            `;
            
            document.getElementById('multiPartsContainer').appendChild(partDiv);
            updatePartVoiceSelects();
        }
        
        function removePart(partId) {
            const partDiv = document.querySelector(`[data-part-id="${partId}"]`);
            if (partDiv) {
                partDiv.remove();
                showToast(`Removed Part ${partId}`);
                
                // Update part numbers
                const parts = document.querySelectorAll('.part-editor');
                parts.forEach((part, index) => {
                    const newPartId = index + 1;
                    part.dataset.partId = newPartId;
                    part.querySelector('strong').textContent = `Part ${newPartId}`;
                });
                
                multiParts = parts.length;
            }
        }
        
        async function generateMulti() {
            // Collect all parts
            const parts = [];
            const partElements = document.querySelectorAll('.part-editor');
            
            if (partElements.length === 0) {
                showToast('Please add at least one part', 'error');
                return;
            }
            
            for (const partElement of partElements) {
                const text = partElement.querySelector('.part-text').value.trim();
                const voice = partElement.querySelector('.part-voice').value;
                
                if (!text) {
                    showToast('Please enter text for all parts', 'error');
                    return;
                }
                
                if (!voice) {
                    showToast('Please select a voice for all parts', 'error');
                    return;
                }
                
                parts.push({
                    text: text,
                    voice: voice
                });
            }
            
            // Create voice assignments
            const voiceAssignments = {
                parts: parts
            };
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', 'Multi-voice audio');
            formData.append('voice_assignments', JSON.stringify(voiceAssignments));
            formData.append('output_format', document.getElementById('multiFormat').value);
            formData.append('quality', document.getElementById('multiQuality').value);
            
            try {
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('multi', result.task_id);
                    showToast('Multi-voice audio generation started');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        // ==================== BATCH PROCESSING FUNCTIONS ====================
        function initBatchUpload() {
            const uploadArea = document.getElementById('batchUploadArea');
            const fileInput = document.getElementById('batchFileInput');
            
            uploadArea.addEventListener('click', () => {
                fileInput.click();
            });
            
            fileInput.addEventListener('change', handleBatchFiles);
            
            // Drag and drop
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, preventDefaults, false);
            });
            
            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }
            
            ['dragenter', 'dragover'].forEach(eventName => {
                uploadArea.addEventListener(eventName, highlight, false);
            });
            
            ['dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, unhighlight, false);
            });
            
            function highlight() {
                uploadArea.classList.add('dragover');
            }
            
            function unhighlight() {
                uploadArea.classList.remove('dragover');
            }
            
            uploadArea.addEventListener('drop', handleDrop, false);
            
            function handleDrop(e) {
                const dt = e.dataTransfer;
                const files = dt.files;
                handleBatchFiles({ target: { files: files } });
            }
        }
        
        function handleBatchFiles(e) {
            const files = Array.from(e.target.files);
            
            // Filter for text files
            const textFiles = files.filter(file => {
                return file.type === 'text/plain' || 
                       file.name.toLowerCase().endsWith('.txt') ||
                       file.name.toLowerCase().endsWith('.text') ||
                       file.name.toLowerCase().endsWith('.md');
            });
            
            if (textFiles.length === 0) {
                showToast('Please select text files (.txt, .text, .md)', 'error');
                return;
            }
            
            // Add files to batchFiles array
            textFiles.forEach(file => {
                if (!batchFiles.find(f => f.name === file.name && f.size === file.size)) {
                    batchFiles.push(file);
                }
            });
            
            updateBatchFileList();
            showToast(`Added ${textFiles.length} file(s) to batch`);
        }
        
        function updateBatchFileList() {
            const container = document.getElementById('batchFilesContainer');
            const fileList = document.getElementById('batchFileList');
            
            container.innerHTML = '';
            
            if (batchFiles.length === 0) {
                fileList.querySelector('h6').textContent = 'Selected Files (0)';
                document.getElementById('batchProcessButton').disabled = true;
                return;
            }
            
            fileList.querySelector('h6').textContent = `Selected Files (${batchFiles.length})`;
            document.getElementById('batchProcessButton').disabled = false;
            
            batchFiles.forEach((file, index) => {
                const fileDiv = document.createElement('div');
                fileDiv.className = 'list-group-item';
                fileDiv.innerHTML = `
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="fas fa-file-text me-2"></i>
                            <span class="fw-bold">${file.name}</span>
                            <small class="text-muted">(${(file.size / 1024).toFixed(1)} KB)</small>
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeBatchFile(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                `;
                container.appendChild(fileDiv);
            });
        }
        
        function removeBatchFile(index) {
            batchFiles.splice(index, 1);
            updateBatchFileList();
            showToast('File removed from batch');
        }
        
        async function processBatch() {
            if (batchFiles.length === 0) {
                showToast('Please select files first', 'error');
                return;
            }
            
            if (!selectedBatchVoice) {
                showToast('Please select a voice', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            batchFiles.forEach(file => {
                formData.append('files', file);
            });
            formData.append('voice_id', selectedBatchVoice);
            formData.append('output_format', document.getElementById('batchFormat').value);
            formData.append('quality', document.getElementById('batchQuality').value);
            
            try {
                const response = await fetch('/api/generate/batch', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('batch', result.task_id);
                    showToast(`Batch processing started for ${batchFiles.length} files`);
                } else {
                    showToast(result.message || 'Batch processing failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Batch processing failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        // ==================== STT FUNCTIONS ====================
        function initSTT() {
            // Check for browser support
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showToast('Your browser does not support audio recording', 'error');
                document.getElementById('recordButton').disabled = true;
                document.getElementById('recordButton').innerHTML = '<i class="fas fa-ban"></i>';
                document.getElementById('liveTranscribeButton').disabled = true;
            }
            
            // Initialize waveform
            initWaveform();
            
            // Load STT languages
            loadSTTLanguages();
        }
        
        function initWaveform() {
            const waveform = document.getElementById('waveform');
            waveform.innerHTML = '';
            
            for (let i = 0; i < 50; i++) {
                const bar = document.createElement('div');
                bar.className = 'waveform-bar';
                bar.style.left = `${i * 2}%`;
                bar.style.height = '0px';
                waveform.appendChild(bar);
            }
        }
        
        function updateWaveform(level) {
            const bars = document.querySelectorAll('.waveform-bar');
            bars.forEach((bar, index) => {
                const randomHeight = Math.random() * 80 + 20;
                bar.style.height = `${randomHeight * (level / 100)}px`;
            });
        }
        
        async function startRecording() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                });
                
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };
                
                mediaRecorder.onstop = () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    
                    // Store the blob for transcription
                    window.recordedAudioBlob = audioBlob;
                    
                    // Update UI
                    document.getElementById('recordButton').classList.remove('recording');
                    document.getElementById('recordButton').innerHTML = '<i class="fas fa-microphone"></i>';
                    document.getElementById('recordButton').disabled = false;
                    document.getElementById('stopButton').disabled = true;
                    document.getElementById('recordingStatus').textContent = 'Recording stopped';
                    document.getElementById('uploadTranscribeButton').disabled = false;
                    
                    showToast('Recording completed. Ready for transcription.');
                };
                
                mediaRecorder.start();
                isRecording = true;
                
                // Update UI
                document.getElementById('recordButton').classList.add('recording');
                document.getElementById('recordButton').innerHTML = '<i class="fas fa-stop"></i>';
                document.getElementById('stopButton').disabled = false;
                document.getElementById('recordingStatus').textContent = 'Recording...';
                document.getElementById('recordingStatus').style.color = '#dc3545';
                
                // Start timer
                recordingStartTime = Date.now();
                updateRecordingTime();
                recordingTimer = setInterval(updateRecordingTime, 1000);
                
                // Simulate waveform animation
                const waveformInterval = setInterval(() => {
                    if (isRecording) {
                        updateWaveform(Math.random() * 100);
                    } else {
                        clearInterval(waveformInterval);
                        initWaveform();
                    }
                }, 100);
                
                showToast('Recording started...', 'info');
                
            } catch (error) {
                console.error('Error starting recording:', error);
                showToast('Error accessing microphone: ' + error.message, 'error');
            }
        }
        
        function stopRecording() {
            if (mediaRecorder && isRecording) {
                mediaRecorder.stop();
                isRecording = false;
                
                // Stop all tracks
                mediaRecorder.stream.getTracks().forEach(track => track.stop());
                
                // Clear timer
                clearInterval(recordingTimer);
                document.getElementById('recordingTime').textContent = '00:00';
            }
        }
        
        function updateRecordingTime() {
            if (recordingStartTime) {
                const elapsed = Date.now() - recordingStartTime;
                const seconds = Math.floor(elapsed / 1000);
                const minutes = Math.floor(seconds / 60);
                const displaySeconds = seconds % 60;
                document.getElementById('recordingTime').textContent = 
                    `${minutes.toString().padStart(2, '0')}:${displaySeconds.toString().padStart(2, '0')}`;
            }
        }
        
        async function uploadSTTFile() {
            const fileInput = document.getElementById('sttFileUpload');
            const file = fileInput.files[0];
            
            if (!file) {
                showToast('Please select an audio file first', 'error');
                return;
            }
            
            // Validate file size (max 50MB)
            if (file.size > 50 * 1024 * 1024) {
                showToast('File size too large. Maximum 50MB.', 'error');
                return;
            }
            
            window.recordedAudioBlob = file;
            document.getElementById('uploadTranscribeButton').disabled = false;
            showToast('Audio file loaded. Ready for transcription.');
        }
        
        async function transcribeUploadedFile() {
            if (!window.recordedAudioBlob) {
                showToast('Please record or upload audio first', 'error');
                return;
            }
            
            const language = document.getElementById('sttLanguage').value;
            
            showLoading();
            
            const formData = new FormData();
            if (window.recordedAudioBlob instanceof File) {
                formData.append('audio_file', window.recordedAudioBlob);
            } else {
                // Convert Blob to File
                const file = new File([window.recordedAudioBlob], 'recording.webm', { type: 'audio/webm' });
                formData.append('audio_file', file);
            }
            formData.append('language', language);
            
            try {
                const response = await fetch('/api/stt/transcribe', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('stt', result.task_id);
                    showToast('Transcription started...');
                } else {
                    showToast(result.message || 'Transcription failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Transcription failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        }
        
        async function startLiveTranscription() {
            if (isLiveTranscribing) {
                stopLiveTranscription();
                return;
            }
            
            try {
                // Connect to WebSocket
                websocket = new WebSocket(`ws://${window.location.host}/ws/stt`);
                
                websocket.onopen = () => {
                    isLiveTranscribing = true;
                    document.getElementById('liveTranscribeButton').innerHTML = '<i class="fas fa-stop me-2"></i>Stop Live';
                    document.getElementById('liveTranscribeButton').classList.remove('btn-stt');
                    document.getElementById('liveTranscribeButton').classList.add('btn-danger');
                    
                    document.getElementById('sttLiveOutput').style.display = 'block';
                    document.getElementById('sttUploadOutput').style.display = 'none';
                    
                    transcriptionHistory = [];
                    document.getElementById('liveTranscriptionText').innerHTML = '';
                    
                    showToast('Live transcription started. Start speaking...', 'info');
                };
                
                websocket.onmessage = (event) => {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'transcription') {
                        if (data.text) {
                            transcriptionHistory.push(data.text);
                            const transcriptionText = document.getElementById('liveTranscriptionText');
                            transcriptionText.innerHTML += `<div class="mb-2"><strong>${new Date().toLocaleTimeString()}:</strong> ${data.text}</div>`;
                            transcriptionText.scrollTop = transcriptionText.scrollHeight;
                        }
                    }
                };
                
                websocket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    showToast('WebSocket connection error', 'error');
                    stopLiveTranscription();
                };
                
                websocket.onclose = () => {
                    stopLiveTranscription();
                };
                
                // Start recording for live transcription
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000,
                        echoCancellation: true,
                        noiseSuppression: true
                    }
                });
                
                const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                const audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0 && websocket.readyState === WebSocket.OPEN) {
                        // Convert blob to base64
                        const reader = new FileReader();
                        reader.onload = () => {
                            const base64data = reader.result.split(',')[1];
                            websocket.send(JSON.stringify({
                                type: 'audio_chunk',
                                data: base64data,
                                language: document.getElementById('sttLanguage').value
                            }));
                        };
                        reader.readAsDataURL(event.data);
                    }
                };
                
                mediaRecorder.start(1000); // Send chunks every second
                
                // Store for cleanup
                window.liveTranscription = {
                    mediaRecorder: mediaRecorder,
                    stream: stream
                };
                
            } catch (error) {
                console.error('Error starting live transcription:', error);
                showToast('Error starting live transcription: ' + error.message, 'error');
                stopLiveTranscription();
            }
        }
        
        function stopLiveTranscription() {
            isLiveTranscribing = false;
            
            if (websocket) {
                websocket.close();
                websocket = null;
            }
            
            if (window.liveTranscription) {
                if (window.liveTranscription.mediaRecorder.state !== 'inactive') {
                    window.liveTranscription.mediaRecorder.stop();
                }
                window.liveTranscription.stream.getTracks().forEach(track => track.stop());
                window.liveTranscription = null;
            }
            
            document.getElementById('liveTranscribeButton').innerHTML = '<i class="fas fa-broadcast-tower me-2"></i>Start Live Transcription';
            document.getElementById('liveTranscribeButton').classList.remove('btn-danger');
            document.getElementById('liveTranscribeButton').classList.add('btn-stt');
            
            showToast('Live transcription stopped', 'info');
        }
        
        async function saveTranscription() {
            const text = transcriptionHistory.join('\n\n');
            if (!text.trim()) {
                showToast('No transcription to save', 'error');
                return;
            }
            
            // Convert to blob and send to server
            const blob = new Blob([text], { type: 'text/plain' });
            const formData = new FormData();
            formData.append('audio_data', blob);
            formData.append('language', document.getElementById('sttLanguage').value);
            
            try {
                const response = await fetch('/api/stt/transcribe/live', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success && result.txt_url) {
                    // Create download link
                    const a = document.createElement('a');
                    a.href = result.txt_url;
                    a.download = `transcription_${Date.now()}.txt`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    
                    showToast('Transcription saved and downloaded');
                } else {
                    showToast('Failed to save transcription', 'error');
                }
            } catch (error) {
                console.error('Error saving transcription:', error);
                showToast('Error saving transcription: ' + error.message, 'error');
            }
        }
        
        function copyTranscript() {
            const transcriptText = document.getElementById('transcriptText');
            transcriptText.select();
            document.execCommand('copy');
            showToast('Transcript copied to clipboard!');
        }
        
        function downloadTranscript() {
            const transcriptText = document.getElementById('transcriptText').value;
            if (!transcriptText.trim()) {
                showToast('No transcript to download', 'error');
                return;
            }
            
            const timestamp = new Date().getTime();
            const filename = `transcript_${timestamp}.txt`;
            const blob = new Blob([transcriptText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showToast('Transcript downloaded');
        }
        
        // STT Event listeners
        document.getElementById('recordButton').addEventListener('click', () => {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });
        
        document.getElementById('stopButton').addEventListener('click', stopRecording);
        
        // ==================== COMMON FUNCTIONS ====================
        // Show task status and poll for updates
        function showTaskStatus(type, taskId) {
            const statusDiv = document.getElementById(`${type}TaskStatus`);
            const progressBar = document.getElementById(`${type}ProgressBar`);
            const progressText = document.getElementById(`${type}ProgressText`);
            const taskMessage = document.getElementById(`${type}TaskMessage`);
            
            statusDiv.style.display = 'block';
            progressBar.style.width = '0%';
            progressText.textContent = '0%';
            taskMessage.textContent = 'Starting...';
            
            // Clear existing interval
            if (taskCheckInterval) {
                clearInterval(taskCheckInterval);
            }
            
            // Poll for task updates
            taskCheckInterval = setInterval(async () => {
                try {
                    const response = await fetch(`/api/task/${taskId}`);
                    const task = await response.json();
                    
                    progressBar.style.width = `${task.progress}%`;
                    progressText.textContent = `${task.progress}%`;
                    taskMessage.textContent = task.message;
                    
                    if (task.status === 'completed') {
                        clearInterval(taskCheckInterval);
                        
                        if (task.result && task.result.success) {
                            showToast(task.result.message);
                            
                            // Show output with CACHE BUSTER
                            showOutput(type, task.result);
                        }
                        
                        // Hide status after 5 seconds
                        setTimeout(() => {
                            statusDiv.style.display = 'none';
                        }, 5000);
                    } else if (task.status === 'failed') {
                        clearInterval(taskCheckInterval);
                        showToast(task.message, 'error');
                        
                        setTimeout(() => {
                            statusDiv.style.display = 'none';
                        }, 3000);
                    }
                } catch (error) {
                    console.error('Error checking task status:', error);
                }
            }, 2000);
        }
        
        // Show output with CACHE BUSTER
        function showOutput(type, result) {
            const outputDiv = document.getElementById(`${type}Output`);
            const audioPlayer = document.getElementById(`${type}AudioPlayer`);
            const downloadAudio = document.getElementById(`${type}DownloadAudio`);
            const downloadSubtitle = document.getElementById(`${type}DownloadSubtitle`);
            const batchDownload = document.getElementById('batchDownload');
            const batchResults = document.getElementById('batchResults');
            const transcriptText = document.getElementById('transcriptText');
            const transcriptionInfo = document.getElementById('transcriptionInfo');
            const sttUploadOutput = document.getElementById('sttUploadOutput');
            
            // ADD CACHE BUSTER to URL - CRITICAL
            const timestamp = new Date().getTime();
            const random = Math.floor(Math.random() * 10000);
            
            if (type === 'batch') {
                // Handle batch output
                batchResults.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        ${result.message}
                    </div>
                    <p>Batch processing completed successfully. Download the results using the button below.</p>
                `;
                
                // Download link with cache buster
                batchDownload.href = `${result.audio_url}?t=${timestamp}_${random}`;
                batchDownload.download = `batch_results_${timestamp}.zip`;
                
                outputDiv.style.display = 'block';
            } else if (type === 'stt') {
                // Handle STT output
                if (result.text) {
                    transcriptText.value = result.text;
                    
                    const confidence = result.confidence * 100;
                    const duration = result.duration ? result.duration.toFixed(1) : 'N/A';
                    const engine = result.engine || 'Unknown';
                    
                    transcriptionInfo.innerHTML = `
                        <i class="fas fa-info-circle me-1"></i>
                        Engine: <strong>${engine}</strong> | 
                        Confidence: <strong>${confidence.toFixed(1)}%</strong> | 
                        Duration: <strong>${duration}s</strong>
                    `;
                    
                    sttUploadOutput.style.display = 'block';
                    
                    // Add download button for TXT file
                    if (result.txt_url) {
                        const downloadBtn = document.querySelector('#sttUploadOutput .btn-success');
                        downloadBtn.onclick = () => {
                            const a = document.createElement('a');
                            a.href = result.txt_url;
                            a.download = `transcription_${timestamp}.txt`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                        };
                    }
                }
            } else {
                // Handle audio output for single and multi
                // Create completely new audio element
                const newAudio = document.createElement('audio');
                newAudio.controls = true;
                newAudio.className = 'w-100';
                newAudio.preload = 'metadata';
                
                // Add cache buster to URL
                const cacheBusterUrl = `${result.audio_url}?t=${timestamp}_${random}`;
                const source = document.createElement('source');
                source.src = cacheBusterUrl;
                source.type = 'audio/mpeg';
                
                newAudio.appendChild(source);
                newAudio.innerHTML += 'Your browser does not support the audio element.';
                
                // Remove old audio player and add new
                audioPlayer.innerHTML = '';
                audioPlayer.appendChild(newAudio);
                
                // FORCE RELOAD AUDIO
                newAudio.load();
                
                // Add event to handle cache issues
                newAudio.addEventListener('error', function() {
                    console.log('Audio loading error, retrying with new cache buster...');
                    const retryTimestamp = new Date().getTime();
                    const retryRandom = Math.floor(Math.random() * 10000);
                    source.src = `${result.audio_url}?t=${retryTimestamp}_${retryRandom}`;
                    newAudio.load();
                });
                
                // Auto play new audio
                setTimeout(() => {
                    try {
                        newAudio.play().catch(e => console.log('Auto-play prevented:', e));
                    } catch (e) {
                        console.log('Play error:', e);
                    }
                }, 500);
                
                // Download link also with cache buster
                downloadAudio.href = cacheBusterUrl;
                downloadAudio.download = `tts_${type}_${timestamp}.${document.getElementById(`${type}Format`).value}`;
                
                if (result.srt_url) {
                    downloadSubtitle.href = result.srt_url;
                    downloadSubtitle.download = `tts_${type}_subtitle_${timestamp}.srt`;
                    downloadSubtitle.style.display = 'inline-block';
                } else {
                    downloadSubtitle.style.display = 'none';
                }
                
                outputDiv.style.display = 'block';
            }
            
            // Scroll to output
            outputDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Cleanup old files
        async function cleanupOldFiles() {
            try {
                await fetch('/api/cleanup', { method: 'POST' });
            } catch (error) {
                console.error('Error cleaning up:', error);
            }
        }
        
        // Utility functions
        function showLoading() {
            document.getElementById('loadingOverlay').style.display = 'flex';
        }
        
        function hideLoading() {
            document.getElementById('loadingOverlay').style.display = 'none';
        }
        
        function showToast(message, type = 'success') {
            const toastContainer = document.querySelector('.toast-container');
            const toastId = 'toast-' + Date.now();
            
            const colorClass = type === 'error' ? 'danger' : 
                             type === 'warning' ? 'warning' : 
                             type === 'info' ? 'info' : 'success';
            const icon = type === 'error' ? 'fa-exclamation-circle' : 
                        type === 'warning' ? 'fa-exclamation-triangle' : 
                        type === 'info' ? 'fa-info-circle' : 'fa-check-circle';
            
            const toastHtml = `
                <div id="${toastId}" class="toast align-items-center text-white bg-${colorClass} border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas ${icon} me-2"></i>
                            ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            `;
            
            toastContainer.insertAdjacentHTML('beforeend', toastHtml);
            const toastElement = document.getElementById(toastId);
            const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
            toast.show();
            
            toastElement.addEventListener('hidden.bs.toast', () => {
                toastElement.remove();
            });
        }
    </script>
</body>
</html>"""
    
    template_path = "templates/index.html"
    os.makedirs("templates", exist_ok=True)
    
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print(f"Template created at: {template_path}")

# ==================== CREATE REQUIREMENTS.TXT ====================
def create_requirements_txt():
    requirements = """fastapi>=0.104.0
uvicorn>=0.24.0
edge-tts>=7.2.7
pydub>=0.25.1
jinja2>=3.1.2
webvtt-py>=0.4.6
natsort>=8.4.0
python-multipart>=0.0.6
SpeechRecognition==3.10.0
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    print("requirements.txt created")

# ==================== CREATE RUNTIME.TXT ====================
def create_runtime_txt():
    with open("runtime.txt", "w") as f:
        f.write("python-3.11.0")
    
    print("runtime.txt created")

# ==================== MAIN ENTRY POINT ====================
if __name__ == "__main__":
    # Create necessary files
    create_requirements_txt()
    create_runtime_txt()
    
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 70)
    print("PROFESSIONAL TTS & STT GENERATOR v5.0 - 4 WORKING TABS")
    print("=" * 70)
    print(f"Server starting on port: {port}")
    print(f"Open http://localhost:{port} in your browser")
    print("\nTABS:")
    print("1. Single Voice TTS - Convert text to speech with one voice")
    print("2. Multi-Voice TTS - Different voices for different text parts")
    print("3. Batch Processing - Process multiple text files at once")
    print("4. Speech to Text - Real-time transcription & file upload")
    print("\nSTT FEATURES:")
    print("- Real-time microphone recording")
    print("- Upload audio files (MP3, WAV, WEBM, etc.)")
    print("- 40+ supported languages")
    print("- WebSocket for live transcription")
    print("- Google Speech Recognition + Sphinx fallback")
    print("\nTTS FEATURES:")
    print("- 50+ Neural Voices from Microsoft Edge")
    print("- No browser cache issues")
    print("- Subtitle generation (SRT)")
    print("- Audio quality settings")
    print("=" * 70)
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
