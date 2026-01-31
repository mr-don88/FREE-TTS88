# app.py - COMPLETE PROFESSIONAL TTS & STT GENERATOR
import asyncio
import json
import os
import random
import re
import time
import uuid
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks, WebSocket
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
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib
import speech_recognition as sr
import io
import tempfile
from pydub import AudioSegment
import numpy as np
from scipy.io import wavfile

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
    }
    
    OUTPUT_FORMATS = ["mp3", "wav"]
    
    STT_LANGUAGES = {
        "en-US": "English (US)",
        "en-GB": "English (UK)",
        "en-AU": "English (Australia)",
        "vi-VN": "Vietnamese",
        "zh-CN": "Chinese (Mandarin)",
        "ja-JP": "Japanese",
        "ko-KR": "Korean",
        "fr-FR": "French",
        "de-DE": "German",
        "es-ES": "Spanish",
        "it-IT": "Italian",
        "ru-RU": "Russian"
    }
    
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
        self.executor = ThreadPoolExecutor(max_workers=2)
    
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
        text = TextProcessor._process_temperatures(text)
        text = TextProcessor._process_measurements(text)
        text = TextProcessor._process_currency(text)
        text = TextProcessor._process_percentages(text)
        text = TextProcessor._process_math_operations(text)
        text = TextProcessor._process_times(text)
        text = TextProcessor._process_years(text)
        text = TextProcessor._process_special_symbols(text)
        
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
                        .replace('+', ' plus ')
                        .replace('/', ' slash ')
                        .replace('=', ' equals '))
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
                     .replace('=', ' equals ')
                     .replace('&', ' ampersand '))

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
    def _number_to_words(number: str) -> str:
        num_str = number.replace(',', '')
    
        try:
            if '.' in num_str:
                integer_part, decimal_part = num_str.split('.')
                integer_text = TextProcessor._int_to_words(integer_part)
                decimal_text = ' '.join([TextProcessor._digit_to_word(d) for d in decimal_part])
                return f"{integer_text} point {decimal_text}"
            return TextProcessor._int_to_words(num_str)
        except:
            return number

    @staticmethod
    def _int_to_words(num_str: str) -> str:
        num = int(num_str)
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
        self.cache_enabled = True
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_key(self, text: str, voice_id: str, rate: int, pitch: int, volume: int) -> str:
        timestamp = int(time.time() / 60)
        key_string = f"{timestamp}_{text}_{voice_id}_{rate}_{pitch}_{volume}"
        return hashlib.md5(key_string.encode()).hexdigest()[:16]
    
    def get_cached_audio(self, cache_key: str) -> Optional[str]:
        if not self.cache_enabled:
            return None
            
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 60:
                return cache_file
            else:
                try:
                    os.remove(cache_file)
                    meta_file = cache_file.replace('.mp3', '.meta')
                    if os.path.exists(meta_file):
                        os.remove(meta_file)
                except:
                    pass
        return None
    
    def save_to_cache(self, cache_key: str, audio_file: str, metadata: dict = None):
        if not self.cache_enabled:
            return None
            
        try:
            self.cleanup_old_cache(keep_count=self.max_cache_size)
            
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
            shutil.copy(audio_file, cache_file)
            
            if metadata:
                meta_file = os.path.join(self.cache_dir, f"{cache_key}.meta")
                with open(meta_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False)
            
            return cache_file
        except Exception as e:
            print(f"Error saving to cache: {e}")
            return None
    
    def clear_voice_cache(self, voice_id: str = None):
        try:
            if not os.path.exists(self.cache_dir):
                return True
                
            files_deleted = 0
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.mp3'):
                    filepath = os.path.join(self.cache_dir, filename)
                    
                    if voice_id:
                        meta_file = filepath.replace('.mp3', '.meta')
                        if os.path.exists(meta_file):
                            try:
                                with open(meta_file, 'r', encoding='utf-8') as f:
                                    metadata = json.load(f)
                                    if metadata.get('voice_id') == voice_id:
                                        os.remove(filepath)
                                        os.remove(meta_file)
                                        files_deleted += 1
                                        continue
                            except:
                                pass
                        
                        if voice_id.replace('-', '_') in filename:
                            os.remove(filepath)
                            meta_file = filepath.replace('.mp3', '.meta')
                            if os.path.exists(meta_file):
                                os.remove(meta_file)
                            files_deleted += 1
                    else:
                        os.remove(filepath)
                        meta_file = filepath.replace('.mp3', '.meta')
                        if os.path.exists(meta_file):
                            os.remove(meta_file)
                        files_deleted += 1
            
            print(f"Cleared {files_deleted} cache files for voice: {voice_id or 'all'}")
            return True
        except Exception as e:
            print(f"Error clearing voice cache: {e}")
            return False
    
    def cleanup_old_cache(self, keep_count: int = 50):
        try:
            if not os.path.exists(self.cache_dir):
                return
            
            cache_files = []
            for f in os.listdir(self.cache_dir):
                if f.endswith('.mp3'):
                    filepath = os.path.join(self.cache_dir, f)
                    cache_files.append((filepath, os.path.getmtime(filepath)))
            
            if len(cache_files) <= keep_count:
                return
            
            cache_files.sort(key=lambda x: x[1])
            
            for i in range(len(cache_files) - keep_count):
                if i >= 0:
                    try:
                        os.remove(cache_files[i][0])
                        meta_file = cache_files[i][0].replace('.mp3', '.meta')
                        if os.path.exists(meta_file):
                            os.remove(meta_file)
                    except:
                        pass
        except Exception as e:
            print(f"Error clearing oldest cache: {e}")
    
    def clear_all_cache(self):
        try:
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error clearing all cache: {e}")
            return False

# ==================== STT PROCESSOR (SPEECH TO TEXT) ====================
class STTProcessor:
    def __init__(self):
        self.recognizer = sr.Recognizer()
    
    async def transcribe_audio(self, audio_file_path: str, language: str = "en-US") -> dict:
        """Transcribe audio file to text"""
        try:
            # Load audio file
            audio = AudioSegment.from_file(audio_file_path)
            
            # Convert to WAV format for speech recognition
            wav_file = audio_file_path.replace(os.path.splitext(audio_file_path)[1], ".wav")
            audio.export(wav_file, format="wav")
            
            # Perform speech recognition
            with sr.AudioFile(wav_file) as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Record the audio
                audio_data = self.recognizer.record(source)
                
                # Recognize using Google Speech Recognition
                try:
                    text = self.recognizer.recognize_google(audio_data, language=language)
                    confidence = 0.85  # Google doesn't provide confidence
                except sr.UnknownValueError:
                    text = "Could not understand audio"
                    confidence = 0.0
                except sr.RequestError as e:
                    text = f"Speech recognition service error: {e}"
                    confidence = 0.0
            
            # Clean up temporary WAV file
            try:
                os.remove(wav_file)
            except:
                pass
            
            return {
                "success": True,
                "text": text,
                "language": language,
                "confidence": confidence,
                "duration": len(audio) / 1000  # Duration in seconds
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    async def transcribe_audio_bytes(self, audio_bytes: bytes, language: str = "en-US") -> dict:
        """Transcribe audio bytes to text"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name
            
            # Use the file-based transcription
            result = await self.transcribe_audio(tmp_path, language)
            
            # Clean up temporary file
            try:
                os.remove(tmp_path)
            except:
                pass
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.cache_manager = AudioCacheManager()
        self.stt_processor = STTProcessor()
        self.load_settings()
        self.initialize_directories()
    
    def initialize_directories(self):
        directories = ["outputs", "temp", "audio_cache", "static", "templates", "uploads"]
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
            if clear_cache:
                self.cache_manager.clear_voice_cache(voice_id)
                print(f"Auto-cleared cache for voice: {voice_id}")
            
            cache_key = self.cache_manager.get_cache_key(text, voice_id, rate, pitch, volume)
            
            if not clear_cache:
                cached_file = self.cache_manager.get_cached_audio(cache_key)
                if cached_file:
                    # Create a unique copy for this request
                    temp_file = f"temp/cache_{uuid.uuid4().hex[:8]}.mp3"
                    shutil.copy(cached_file, temp_file)
                    return temp_file, []
            
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
                
                if not clear_cache:
                    metadata = {
                        "voice_id": voice_id,
                        "rate": rate,
                        "pitch": pitch,
                        "volume": volume,
                        "text_hash": hashlib.md5(text.encode()).hexdigest()[:8],
                        "created_at": time.time()
                    }
                    self.cache_manager.save_to_cache(cache_key, temp_file, metadata)
                
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
                                 task_id: str = None, clear_cache: bool = False):
        self.cleanup_temp_files()
        
        self.cache_manager.cleanup_old_cache(keep_count=30)
        
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
        
        combined.export(output_file, format=output_format, bitrate="192k")
        
        srt_file = None
        if all_subtitles:
            srt_filename = f"single_voice_{output_timestamp}_{random_suffix}.srt"
            srt_file = os.path.join(output_dir, srt_filename)
            self.generate_srt(all_subtitles, output_file)
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, 
                                   message="Audio generation completed")
        
        return output_file, srt_file
    
    async def process_stt(self, audio_file: UploadFile, language: str = "en-US", task_id: str = None):
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
            
            result = await self.stt_processor.transcribe_audio(file_path, language)
            
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=100, 
                                       message="Transcription completed")
            
            # Save settings
            self.settings["stt"] = {
                "language": language,
                "last_used": datetime.now().isoformat()
            }
            self.save_settings()
            
            return {
                "success": result["success"],
                "text": result.get("text", ""),
                "language": language,
                "confidence": result.get("confidence", 0),
                "duration": result.get("duration", 0),
                "audio_url": f"/uploads/stt/{filename}" if result["success"] else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    def cleanup_temp_files(self):
        try:
            temp_files = glob.glob("temp/*.mp3")
            for file in temp_files:
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
    
    print("Shutting down TTS Generator...")
    tts_processor.cleanup_temp_files()
    if hasattr(task_manager, 'executor'):
        task_manager.executor.shutdown(wait=False)

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="Professional TTS & STT Generator", 
    version="3.0.0",
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
        "formats": TTSConfig.OUTPUT_FORMATS
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

@app.post("/api/generate/single")
async def generate_single_voice(
    text: str = Form(...),
    voice_id: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3"),
    clear_cache: bool = Form(True)  # Always fresh by default
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
                    output_format, task_id, clear_cache
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Audio generated successfully (fresh audio)"
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
            "message": "Audio generation started with fresh audio (no cache)."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stt/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...),
    language: str = Form("en-US")
):
    try:
        if not audio_file:
            raise HTTPException(status_code=400, detail="Audio file is required")
        
        # Check file type
        allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac']
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

# WebSocket for real-time STT (optional)
@app.websocket("/ws/stt")
async def websocket_stt(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            # Process audio chunk
            # This is a basic implementation - you'd need to implement streaming STT
            await websocket.send_json({"type": "processing", "message": "Audio received"})
    except Exception as e:
        await websocket.close()

# ==================== HTML TEMPLATE CREATION ====================
def create_template_file():
    template_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional TTS & STT Generator</title>
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
            padding: 1rem 2rem;
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
        
        .btn-warning {
            background: linear-gradient(135deg, var(--warning-color), #e76f51);
            border: none;
            padding: 0.75rem 2rem;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-warning:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(248, 150, 30, 0.3);
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
        
        .fresh-audio-check {
            background: #e8f5e9;
            border: 1px solid #388e3c;
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .record-btn {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            transition: all 0.3s;
            margin: 0 auto;
        }
        
        .record-btn.recording {
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(220, 53, 69, 0); }
            100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
        }
        
        .waveform {
            width: 100%;
            height: 80px;
            background: #f8f9fa;
            border-radius: 10px;
            margin: 1rem 0;
            position: relative;
            overflow: hidden;
        }
        
        .waveform-bar {
            position: absolute;
            bottom: 0;
            width: 3px;
            background: var(--primary-color);
            border-radius: 2px;
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
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-microphone-alt me-2"></i>
                Professional TTS & STT Generator v3.0
            </a>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container main-container">
        <!-- Tabs -->
        <ul class="nav nav-tabs" id="ttsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single">
                    <i class="fas fa-user me-2"></i>Single Voice TTS
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="stt-tab" data-bs-toggle="tab" data-bs-target="#stt">
                    <i class="fas fa-microphone me-2"></i>Speech to Text (STT)
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="ttsTabsContent">
            <!-- Single Voice Tab -->
            <div class="tab-pane fade show active" id="single">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Text Content</label>
                            <textarea class="form-control" id="singleText" rows="8" 
                                      placeholder="Enter your text here..."></textarea>
                            <small class="text-muted">Maximum 50 sentences for optimal performance</small>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="singleLanguage">
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}">{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Voice</label>
                            <select class="form-select" id="singleVoice">
                                <option value="">Select Voice</option>
                            </select>
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
                                        
                                        <div class="mb-3">
                                            <label class="form-label">Output Format</label>
                                            <select class="form-select" id="singleFormat">
                                                {% for format in formats %}
                                                <option value="{{ format }}">{{ format|upper }}</option>
                                                {% endfor %}
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Generate Fresh Audio Option -->
                        <div class="fresh-audio-check mb-3">
                            <div class="form-check">
                                <input class="form-check-input" type="checkbox" id="clearCacheSingle" checked>
                                <label class="form-check-label" for="clearCacheSingle">
                                    <i class="fas fa-sync-alt me-2"></i> Always Generate Fresh Audio
                                </label>
                                <small class="form-text text-muted d-block mt-1">
                                    Prevents browser cache issues (recommended)
                                </small>
                            </div>
                        </div>
                        
                        <button class="btn btn-primary w-100" onclick="generateSingle()">
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
            
            <!-- Speech to Text Tab -->
            <div class="tab-pane fade" id="stt">
                <div class="row">
                    <div class="col-md-6">
                        <div class="mb-4">
                            <h5><i class="fas fa-microphone me-2"></i>Record Audio</h5>
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
                        
                        <div class="mb-4">
                            <h5><i class="fas fa-upload me-2"></i>Or Upload Audio File</h5>
                            <div class="input-group">
                                <input type="file" class="form-control" id="audioUpload" accept=".mp3,.wav,.m4a,.ogg,.flac,.aac">
                                <button class="btn btn-outline-primary" type="button" onclick="uploadAudio()">
                                    <i class="fas fa-upload me-2"></i>Upload
                                </button>
                            </div>
                            <small class="text-muted">Supported formats: MP3, WAV, M4A, OGG, FLAC, AAC</small>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="mb-3">
                            <label class="form-label">Language for Transcription</label>
                            <select class="form-select" id="sttLanguage">
                                {% for code, name in stt_languages.items() %}
                                <option value="{{ code }}">{{ name }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <button class="btn btn-primary w-100 mb-2" onclick="transcribeAudio()" id="transcribeButton">
                                <i class="fas fa-language me-2"></i>Transcribe Audio
                            </button>
                            <button class="btn btn-outline-secondary w-100" onclick="copyTranscript()" id="copyButton" style="display: none;">
                                <i class="fas fa-copy me-2"></i>Copy Transcript
                            </button>
                        </div>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="sttTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="sttProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="sttProgressText">0%</div>
                            </div>
                            <div id="sttTaskMessage"></div>
                        </div>
                        
                        <!-- Output Section -->
                        <div class="output-card mt-4" id="sttOutput" style="display: none;">
                            <h5><i class="fas fa-file-alt me-2"></i>Transcription Result</h5>
                            <div class="mb-3">
                                <textarea class="form-control" id="transcriptText" rows="6" readonly></textarea>
                            </div>
                            <div class="d-flex justify-content-between">
                                <small class="text-muted" id="transcriptionInfo"></small>
                                <div>
                                    <button class="btn btn-sm btn-outline-primary me-2" onclick="clearTranscript()">
                                        <i class="fas fa-trash me-1"></i>Clear
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
        let currentAudioUrl = null;
        
        // STT Variables
        let mediaRecorder = null;
        let audioChunks = [];
        let isRecording = false;
        let recordingStartTime = null;
        let recordingTimer = null;
        
        // Initialize
        document.addEventListener('DOMContentLoaded', async function() {
            await loadSettings();
            await loadVoices();
            initRangeDisplays();
            await cleanupOldFiles();
            initSTT();
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
                
                const defaultLanguage = 'Vietnamese';
                document.getElementById('singleLanguage').value = defaultLanguage;
                
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        }
        
        // Load voices for single voice
        async function loadVoices() {
            try {
                const language = document.getElementById('singleLanguage').value || 'Vietnamese';
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('singleVoice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Set default Vietnamese voice
                const viVoice = data.voices.find(v => v.name === 'vi-VN-HoaiMyNeural');
                if (viVoice) {
                    voiceSelect.value = viVoice.name;
                }
            } catch (error) {
                console.error('Error loading voices:', error);
            }
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
        
        // Language change handler for single voice
        document.getElementById('singleLanguage').addEventListener('change', async function() {
            const language = this.value;
            if (language) {
                try {
                    const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                    const data = await response.json();
                    
                    const voiceSelect = document.getElementById('singleVoice');
                    voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                    
                    data.voices.forEach(voice => {
                        const option = document.createElement('option');
                        option.value = voice.name;
                        option.textContent = `${voice.display} (${voice.gender})`;
                        voiceSelect.appendChild(option);
                    });
                    
                    if (data.voices.length > 0) {
                        voiceSelect.value = data.voices[0].name;
                    }
                } catch (error) {
                    console.error('Error loading voices:', error);
                    showToast('Error loading voices for selected language', 'error');
                }
            }
        });
        
        // RESET AUDIO PLAYER - CRITICAL for cache prevention
        function resetAudioPlayer() {
            const audioPlayer = document.getElementById('singleAudioPlayer');
            if (audioPlayer) {
                // Stop all playing audio
                const audios = audioPlayer.getElementsByTagName('audio');
                for (let audio of audios) {
                    audio.pause();
                    audio.src = '';
                    audio.load();
                }
                // Clear content
                audioPlayer.innerHTML = '';
            }
            // Hide output section
            document.getElementById('singleOutput').style.display = 'none';
        }
        
        // Generate single voice audio
        async function generateSingle() {
            const text = document.getElementById('singleText').value.trim();
            const voice = document.getElementById('singleVoice').value;
            const language = document.getElementById('singleLanguage').value;
            const clearCache = document.getElementById('clearCacheSingle').checked;
            
            if (!text) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!language) {
                showToast('Please select a language', 'error');
                return;
            }
            
            if (!voice) {
                showToast('Please select a voice', 'error');
                return;
            }
            
            // RESET AUDIO PLAYER BEFORE GENERATION
            resetAudioPlayer();
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', document.getElementById('singleRate').value);
            formData.append('pitch', document.getElementById('singlePitch').value);
            formData.append('volume', document.getElementById('singleVolume').value);
            formData.append('pause', document.getElementById('singlePause').value);
            formData.append('output_format', document.getElementById('singleFormat').value);
            formData.append('clear_cache', clearCache);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('single', result.task_id);
                    showToast('Audio generation started (fresh audio)');
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
            
            // ADD CACHE BUSTER to URL - CRITICAL
            const timestamp = new Date().getTime();
            const random = Math.floor(Math.random() * 10000);
            
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
            downloadAudio.download = `tts_audio_${timestamp}.mp3`;
            
            if (result.srt_url) {
                downloadSubtitle.href = result.srt_url;
                downloadSubtitle.download = `tts_subtitle.srt`;
                downloadSubtitle.style.display = 'inline-block';
            } else {
                downloadSubtitle.style.display = 'none';
            }
            
            outputDiv.style.display = 'block';
            
            // Scroll to output
            outputDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // ==================== STT FUNCTIONS ====================
        function initSTT() {
            // Check for browser support
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                showToast('Your browser does not support audio recording', 'error');
                document.getElementById('recordButton').disabled = true;
                document.getElementById('recordButton').innerHTML = '<i class="fas fa-ban"></i>';
            }
            
            // Initialize waveform
            initWaveform();
        }
        
        function initWaveform() {
            const waveform = document.getElementById('waveform');
            waveform.innerHTML = '';
            
            for (let i = 0; i < 100; i++) {
                const bar = document.createElement('div');
                bar.className = 'waveform-bar';
                bar.style.left = `${i}%`;
                bar.style.height = '0px';
                waveform.appendChild(bar);
            }
        }
        
        function updateWaveform(level) {
            const bars = document.querySelectorAll('.waveform-bar');
            bars.forEach((bar, index) => {
                const randomHeight = Math.random() * 60 + 20;
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
                    const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    
                    // Create a temporary audio element to preview
                    const previewAudio = new Audio(audioUrl);
                    
                    // Update UI
                    document.getElementById('recordButton').classList.remove('recording');
                    document.getElementById('recordButton').innerHTML = '<i class="fas fa-microphone"></i>';
                    document.getElementById('recordButton').disabled = false;
                    document.getElementById('stopButton').disabled = true;
                    document.getElementById('recordingStatus').textContent = 'Recording stopped';
                    document.getElementById('transcribeButton').disabled = false;
                    
                    // Store the blob for transcription
                    window.recordedAudioBlob = audioBlob;
                    
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
        
        async function uploadAudio() {
            const fileInput = document.getElementById('audioUpload');
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
            document.getElementById('transcribeButton').disabled = false;
            showToast('Audio file loaded. Ready for transcription.');
        }
        
        async function transcribeAudio() {
            if (!window.recordedAudioBlob) {
                showToast('Please record or upload audio first', 'error');
                return;
            }
            
            const language = document.getElementById('sttLanguage').value;
            
            showLoading();
            
            const formData = new FormData();
            formData.append('audio_file', window.recordedAudioBlob);
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
        
        function showSTTOutput(result) {
            const outputDiv = document.getElementById('sttOutput');
            const transcriptText = document.getElementById('transcriptText');
            const transcriptionInfo = document.getElementById('transcriptionInfo');
            const copyButton = document.getElementById('copyButton');
            
            transcriptText.value = result.text;
            
            const confidence = result.confidence * 100;
            const duration = result.duration.toFixed(1);
            
            transcriptionInfo.innerHTML = `
                <i class="fas fa-info-circle me-1"></i>
                Confidence: <strong>${confidence.toFixed(1)}%</strong> | 
                Duration: <strong>${duration}s</strong> | 
                Language: <strong>${result.language}</strong>
            `;
            
            copyButton.style.display = 'inline-block';
            outputDiv.style.display = 'block';
            
            // Scroll to output
            outputDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        function copyTranscript() {
            const transcriptText = document.getElementById('transcriptText');
            transcriptText.select();
            document.execCommand('copy');
            showToast('Transcript copied to clipboard!');
        }
        
        function clearTranscript() {
            document.getElementById('transcriptText').value = '';
            document.getElementById('sttOutput').style.display = 'none';
            window.recordedAudioBlob = null;
            document.getElementById('audioUpload').value = '';
            document.getElementById('transcribeButton').disabled = true;
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
        
        // Event listeners for STT
        document.getElementById('recordButton').addEventListener('click', () => {
            if (!isRecording) {
                startRecording();
            } else {
                stopRecording();
            }
        });
        
        document.getElementById('stopButton').addEventListener('click', stopRecording);
        
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
</html>
"""
    
    template_path = "templates/index.html"
    os.makedirs("templates", exist_ok=True)
    
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print(f"Template created at: {template_path}")

# ==================== MAIN ENTRY POINT ====================
def create_requirements_txt():
    requirements = """fastapi==0.104.1
uvicorn[standard]==0.24.0
edge-tts==6.1.9
pydub==0.25.1
webvtt-py==0.4.6
natsort==8.4.0
python-multipart==0.0.6
SpeechRecognition==3.10.0
numpy==1.24.3
scipy==1.11.4
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    print("requirements.txt created")

def create_runtime_txt():
    runtime = "python-3.11.0"
    
    with open("runtime.txt", "w") as f:
        f.write(runtime)
    
    print("runtime.txt created")

def create_gunicorn_conf():
    gunicorn_conf = """# gunicorn_config.py
import multiprocessing

bind = "0.0.0.0:10000"
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
"""
    
    with open("gunicorn_config.py", "w") as f:
        f.write(gunicorn_conf)
    
    print("gunicorn_config.py created")

# ==================== RUN APPLICATION ====================
if __name__ == "__main__":
    create_requirements_txt()
    create_runtime_txt()
    create_gunicorn_conf()
    
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("PROFESSIONAL TTS & STT GENERATOR v3.0")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Open http://localhost:{port} in your browser")
    print("Features:")
    print("- 4 Tabs: Single Voice TTS, Multi-Voice TTS, Batch Processing, Speech-to-Text")
    print("- Each Generate creates new audio file with unique name")
    print("- Browser cache buster (timestamp + random)")
    print("- Header no-cache for download")
    print("- Speech-to-Text with recording and file upload")
    print("- Auto cleanup old files")
    print("=" * 60)
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
