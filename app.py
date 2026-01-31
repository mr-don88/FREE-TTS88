# app.py - COMPLETE PROFESSIONAL TTS GENERATOR WITH 4 TABS
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
from concurrent.futures import ThreadPoolExecutor
import hashlib

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
        self.load_settings()
        self.initialize_directories()
    
    def initialize_directories(self):
        directories = ["outputs", "temp", "audio_cache", "static", "templates", "uploads", "batch_inputs"]
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
            # Format: {"parts": [{"text": "part1", "voice": "voice1"}, ...]}
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
    print("Starting up Professional TTS Generator...")
    
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
    title="Professional TTS Generator", 
    version="4.0.0",
    lifespan=lifespan
)

# Global instances
tts_processor = None
task_manager = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "languages": TTSConfig.LANGUAGES,
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

# ==================== HTML TEMPLATE CREATION ====================
def create_template_file():
    template_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional TTS Generator - 4 Tabs</title>
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
        
        .part-editor {
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f8f9fa;
        }
        
        .part-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .drag-handle {
            cursor: move;
            color: #6c757d;
            padding: 0.5rem;
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
        
        .language-badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            background: var(--light-bg);
            border-radius: 20px;
            margin: 0.25rem;
            font-size: 0.875rem;
        }
        
        .tab-icon {
            margin-right: 0.5rem;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-microphone-alt me-2"></i>
                Professional TTS Generator v4.0
            </a>
            <div class="navbar-text text-light">
                <small>4 Tabs • Always Fresh Audio • No Cache Issues</small>
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
                        <button class="btn btn-outline-secondary" onclick="resetAudioPlayer('single')">
                            <i class="fas fa-redo me-2"></i>Reset Player
                        </button>
                    </div>
                </div>
            </div>
            
            <!-- Tab 2: Multi-Voice -->
            <div class="tab-pane fade" id="multi">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Text Content (Split into Parts)</label>
                            <textarea class="form-control" id="multiText" rows="6" 
                                      placeholder="Enter your text here. You can split it into different parts for different voices.">Part 1: Welcome to our multi-voice TTS system.

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
                            <div class="part-editor" data-part-id="1">
                                <div class="part-header">
                                    <div>
                                        <span class="drag-handle"><i class="fas fa-grip-vertical"></i></span>
                                        <strong>Part 1</strong>
                                    </div>
                                    <div>
                                        <button class="btn btn-sm btn-outline-danger" onclick="removePart(1)">
                                            <i class="fas fa-times"></i>
                                        </button>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <textarea class="form-control part-text" rows="2" placeholder="Enter text for this part...">Welcome to our multi-voice TTS system.</textarea>
                                </div>
                                <div class="row">
                                    <div class="col-md-8">
                                        <select class="form-select part-voice">
                                            <option value="">Select Voice for Part 1</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
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
                            <p class="text-muted">or click to browse</p>
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
            
            <!-- Tab 4: Speech to Text (Coming Soon) -->
            <div class="tab-pane fade" id="stt">
                <div class="row">
                    <div class="col-md-8">
                        <div class="card border-0 shadow-sm">
                            <div class="card-body">
                                <h4 class="card-title"><i class="fas fa-microphone me-2 text-primary"></i>Speech to Text (Coming Soon)</h4>
                                <p class="card-text">
                                    The Speech to Text feature is currently under development. This feature will allow you to:
                                </p>
                                <ul>
                                    <li>Convert audio files to text</li>
                                    <li>Record audio directly from microphone</li>
                                    <li>Support multiple languages for transcription</li>
                                    <li>Export transcripts in various formats</li>
                                </ul>
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    This feature requires additional dependencies and will be available in the next update.
                                    For now, enjoy our comprehensive TTS features with 50+ neural voices.
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card border-0 shadow-sm">
                            <div class="card-body">
                                <h5 class="card-title"><i class="fas fa-rocket me-2"></i>Try Other Features</h5>
                                <p class="card-text">While waiting for STT, explore our powerful TTS features:</p>
                                <div class="d-grid gap-2">
                                    <a href="#single" class="btn btn-outline-primary" data-bs-toggle="tab">
                                        <i class="fas fa-user me-2"></i>Single Voice TTS
                                    </a>
                                    <a href="#multi" class="btn btn-outline-warning" data-bs-toggle="tab">
                                        <i class="fas fa-users me-2"></i>Multi-Voice TTS
                                    </a>
                                    <a href="#batch" class="btn btn-outline-info" data-bs-toggle="tab">
                                        <i class="fas fa-folder me-2"></i>Batch Processing
                                    </a>
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
        let multiParts = 1;
        let batchFiles = [];
        
        // Initialize
        document.addEventListener('DOMContentLoaded', async function() {
            await loadSettings();
            await loadLanguages();
            initRangeDisplays();
            await cleanupOldFiles();
            initBatchUpload();
            
            // Set default language and load voices
            document.getElementById('singleLanguage').value = 'Vietnamese';
            document.getElementById('batchLanguage').value = 'Vietnamese';
            await loadSingleVoices();
            await loadMultiVoices();
            await loadBatchVoices();
            
            // Initialize multi-voice parts
            updatePartVoices();
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
                    // Extract language from voice name (e.g., "vi-VN-HoaiMyNeural" -> "Vietnamese")
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
        
        // Update voice options in multi-voice parts
        function updatePartVoices() {
            const voiceOptions = document.querySelectorAll('#multiVoiceList .voice-option');
            if (voiceOptions.length === 0) return;
            
            document.querySelectorAll('.part-voice').forEach((select, index) => {
                select.innerHTML = '<option value="">Select Voice for Part ' + (index + 1) + '</option>';
                
                voiceOptions.forEach(voiceDiv => {
                    const voiceId = voiceDiv.dataset.voiceId;
                    const voiceText = voiceDiv.querySelector('strong').textContent;
                    const option = document.createElement('option');
                    option.value = voiceId;
                    option.textContent = voiceText;
                    
                    // Auto-select based on part number (even/odd for variety)
                    if (index === 0 && voiceId.includes('HoaiMy')) option.selected = true;
                    else if (index === 1 && voiceId.includes('NamMinh')) option.selected = true;
                    else if (index === 2 && voiceId.includes('Jenny')) option.selected = true;
                    
                    select.appendChild(option);
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
        
        // RESET AUDIO PLAYER - CRITICAL for cache prevention
        function resetAudioPlayer(tab) {
            const audioPlayer = document.getElementById(`${tab}AudioPlayer`);
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
            document.getElementById(`${tab}Output`).style.display = 'none';
            showToast('Audio player reset');
        }
        
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
            
            // RESET AUDIO PLAYER BEFORE GENERATION
            resetAudioPlayer('single');
            
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
            formData.append('clear_cache', true);  // Always fresh
            
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
                            <option value="">Select Voice for Part ${partId}</option>
                        </select>
                    </div>
                </div>
            `;
            
            document.getElementById('multiPartsContainer').appendChild(partDiv);
            updatePartVoices();
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
                    part.querySelector('.part-voice').innerHTML = `<option value="">Select Voice for Part ${newPartId}</option>`;
                });
                
                multiParts = parts.length;
                updatePartVoices();
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
            formData.append('text', 'Multi-voice audio'); // Main text (not used for multi)
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
            
            // Click to browse
            uploadArea.addEventListener('click', () => {
                fileInput.click();
            });
            
            // File selection
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
            
            // Handle dropped files
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
            
            // ADD CACHE BUSTER to URL - CRITICAL
            const timestamp = new Date().getTime();
            const random = Math.floor(Math.random() * 10000);
            
            if (type === 'batch') {
                // Handle batch output (usually ZIP)
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
</html>
"""
    
    template_path = "templates/index.html"
    os.makedirs("templates", exist_ok=True)
    
    with open(template_path, "w", encoding="utf-8") as f:
        f.write(template_content)
    
    print(f"Template created at: {template_path}")

# ==================== CREATE REQUIREMENTS.TXT ====================
def create_requirements_txt():
    requirements = """fastapi==0.104.1
uvicorn[standard]==0.24.0
edge-tts==6.1.9
pydub==0.25.1
webvtt-py==0.4.6
natsort==8.4.0
python-multipart==0.0.6
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    print("requirements.txt created")

# ==================== MAIN ENTRY POINT ====================
if __name__ == "__main__":
    # Create necessary files
    create_requirements_txt()
    
    # Create runtime.txt for Render
    with open("runtime.txt", "w") as f:
        f.write("python-3.11.0")
    
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("PROFESSIONAL TTS GENERATOR v4.0 - 4 TABS")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Open http://localhost:{port} in your browser")
    print("Tabs:")
    print("1. Single Voice TTS")
    print("2. Multi-Voice TTS (different voices for different parts)")
    print("3. Batch Processing (multiple text files)")
    print("4. Speech to Text (Coming Soon)")
    print("Features:")
    print("- 50+ Neural Voices from Microsoft Edge")
    print("- Multiple languages and accents")
    print("- No browser cache issues (always fresh audio)")
    print("- Audio quality settings")
    print("- Subtitle generation (SRT)")
    print("=" * 60)
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
