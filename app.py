# app.py - Professional TTS Generator with 3 Tabs and Browser Cache Fix
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
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks
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

# ==================== SYSTEM CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    LANGUAGES = {
        "Vietnamese": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "👩Female", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "🤵Male", "display": "Nam Minh"}
        ],
        "English (US)": [
            {"name": "en-US-GuyNeural", "gender": "🤵Male", "display": "Guy (US)"},
            {"name": "en-US-JennyNeural", "gender": "👩Female", "display": "Jenny (US)"},
            {"name": "en-US-AvaNeural", "gender": "👩Female", "display": "Ava (US)"},
            {"name": "en-US-AndrewNeural", "gender": "🤵Male", "display": "Andrew (US)"},
            {"name": "en-US-EmmaNeural", "gender": "👩Female", "display": "Emma (US)"},
            {"name": "en-US-BrianNeural", "gender": "🤵Male", "display": "Brian (US)"},
            {"name": "en-US-AnaNeural", "gender": "👩Female", "display": "Ana (US)"},
            {"name": "en-US-AndrewMultilingualNeural", "gender": "🤵Male", "display": "Andrew (US • Multi)"},
            {"name": "en-US-AriaNeural", "gender": "👩Female", "display": "Aria (US)"},
            {"name": "en-US-AvaMultilingualNeural", "gender": "👩Female", "display": "Ava (US • Multi)"},
            {"name": "en-US-BrianMultilingualNeural", "gender": "🤵Male", "display": "Brian (US • Multi)"},
            {"name": "en-US-ChristopherNeural", "gender": "🤵Male", "display": "Christopher (US)"},
            {"name": "en-US-EmmaMultilingualNeural", "gender": "👩Female", "display": "Emma (US • Multi)"},
            {"name": "en-US-EricNeural", "gender": "🤵Male", "display": "Eric (US)"},
            {"name": "en-US-MichelleNeural", "gender": "👩Female", "display": "Michelle (US)"},
            {"name": "en-US-RogerNeural", "gender": "🤵Male", "display": "Roger (US)"},
            {"name": "en-US-SteffanNeural", "gender": "🤵Male", "display": "Steffan (US)"}
        ],
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "👩Female", "display": "Libby (UK)"},
            {"name": "en-GB-MiaNeural", "gender": "👩Female", "display": "Mia (UK)"},
            {"name": "en-GB-RyanNeural", "gender": "🤵Male", "display": "Ryan (UK)"},
            {"name": "en-GB-MaisieNeural", "gender": "👩Female", "display": "Maisie (UK)"},
            {"name": "en-GB-SoniaNeural", "gender": "👩Female", "display": "Sonia (UK)"},
            {"name": "en-GB-ThomasNeural", "gender": "🤵Male", "display": "Thomas (UK)"}
        ],
        "English (Australia)": [
            {"name": "en-AU-NatashaNeural", "gender": "👩Female", "display": "Natasha (AU)"},
            {"name": "en-AU-WilliamNeural", "gender": "🤵Male", "display": "William (AU)"},
            {"name": "en-AU-TinaNeural", "gender": "👩Female", "display": "Tina (AU)"},
            {"name": "en-AU-KenNeural", "gender": "🤵Male", "display": "Ken (AU)"}
        ],
        "English (Canada)": [
            {"name": "en-CA-ClaraNeural", "gender": "👩Female", "display": "Clara (CA)"},
            {"name": "en-CA-LiamNeural", "gender": "🤵Male", "display": "Liam (CA)"}
        ],
        "English (India)": [
            {"name": "en-IN-NeerjaNeural", "gender": "👩Female", "display": "Neerja (IN)"},
            {"name": "en-IN-PrabhatNeural", "gender": "🤵Male", "display": "Prabhat (IN)"}
        ],
        "Mandarin Chinese (zh-CN)": [
            {"name": "zh-CN-XiaoxiaoNeural", "gender": "👩Female", "display": "晓晓"},
            {"name": "zh-CN-YunxiNeural", "gender": "🤵Male", "display": "云希"},
            {"name": "zh-CN-YunjianNeural", "gender": "🤵Male", "display": "云健"},
            {"name": "zh-CN-XiaoyiNeural", "gender": "👩Female", "display": "晓伊"},
            {"name": "zh-CN-XiaomoNeural", "gender": "👩Female", "display": "晓墨"},
            {"name": "zh-CN-XiaoxuanNeural", "gender": "👩Female", "display": "晓萱"},
            {"name": "zh-CN-XiaohanNeural", "gender": "👩Female", "display": "晓涵"},
            {"name": "zh-CN-XiaoruiNeural", "gender": "👩Female", "display": "晓瑞"}
        ],
    }
    
    OUTPUT_FORMATS = ["mp3", "wav"]
    
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

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.cache_manager = AudioCacheManager()
        self.load_settings()
        self.initialize_directories()
    
    def initialize_directories(self):
        directories = ["outputs", "temp", "audio_cache", "static", "templates", "batch_uploads"]
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
                    "language": "Vietnamese",
                    "voice1": "vi-VN-HoaiMyNeural",
                    "voice2": "vi-VN-NamMinhNeural",
                    "rate": 0,
                    "pitch": 0,
                    "volume": 100,
                    "pause": 500
                },
                "batch": {
                    "language": "Vietnamese",
                    "voice": "vi-VN-HoaiMyNeural",
                    "rate": 0,
                    "pitch": 0,
                    "volume": 100,
                    "pause": 500
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
                    temp_file = f"temp/cache_{uuid.uuid4().hex[:8]}.mp3"
                    shutil.copy(cached_file, temp_file)
                    return temp_file, []
            
            # Generate unique filename to prevent browser cache issues
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
            
            # Create unique temp file
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
        
        # Create unique output directory with UUID to prevent cache issues
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
        
        # Create unique output filename with timestamp and random suffix
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
    
    async def process_multi_voice(self, text: str, voice1: str, voice2: str, rate: int, pitch: int, 
                                 volume: int, pause: int, output_format: str = "mp3", 
                                 task_id: str = None, clear_cache: bool = False):
        self.cleanup_temp_files()
        self.cache_manager.cleanup_old_cache(keep_count=30)
        
        # Create unique output directory
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/multi_{timestamp}_{unique_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        if len(paragraphs) == 0:
            return None, None
        
        # Ensure we have at least 2 paragraphs for multi-voice
        if len(paragraphs) == 1:
            paragraphs = [paragraphs[0], paragraphs[0]]
        
        if len(paragraphs) > 10:
            paragraphs = paragraphs[:10]
            print(f"Processing {len(paragraphs)} paragraphs only for performance")
        
        async def generate_paragraph(paragraph, voice, index):
            if task_id and task_manager:
                progress = int((index / len(paragraphs)) * 90)
                task_manager.update_task(task_id, progress=progress, 
                                       message=f"Processing paragraph {index+1}/{len(paragraphs)}")
            
            return await self.generate_speech(paragraph, voice, rate, pitch, volume, clear_cache)
        
        audio_segments = []
        all_subtitles = []
        
        for i, paragraph in enumerate(paragraphs):
            voice = voice1 if i % 2 == 0 else voice2
            temp_file, subs = await generate_paragraph(paragraph, voice, i)
            
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
        
        for i, audio in enumerate(audio_segments):
            audio = audio.fade_in(50).fade_out(50)
            combined += audio
            
            if i < len(audio_segments) - 1:
                combined += AudioSegment.silent(duration=pause)
        
        # Create unique output filename
        output_timestamp = int(time.time())
        random_suffix = random.randint(1000, 9999)
        output_filename = f"multi_voice_{output_timestamp}_{random_suffix}.{output_format}"
        output_file = os.path.join(output_dir, output_filename)
        
        combined.export(output_file, format=output_format, bitrate="192k")
        
        srt_file = None
        if all_subtitles:
            srt_filename = f"multi_voice_{output_timestamp}_{random_suffix}.srt"
            srt_file = os.path.join(output_dir, srt_filename)
            self.generate_srt(all_subtitles, output_file)
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, 
                                   message="Multi-voice audio generation completed")
        
        return output_file, srt_file
    
    async def process_batch(self, files: List[UploadFile], voice_id: str, rate: int, pitch: int,
                          volume: int, pause: int, output_format: str = "mp3", 
                          task_id: str = None, clear_cache: bool = False):
        self.cleanup_temp_files()
        self.cache_manager.cleanup_old_cache(keep_count=30)
        
        # Create unique output directory
        unique_id = uuid.uuid4().hex[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/batch_{timestamp}_{unique_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        results = []
        
        for i, file in enumerate(files):
            try:
                if task_id and task_manager:
                    progress = int((i / len(files)) * 90)
                    task_manager.update_task(task_id, progress=progress, 
                                           message=f"Processing file {i+1}/{len(files)}")
                
                # Read and decode file content
                content = await file.read()
                try:
                    text = content.decode('utf-8')
                except:
                    # Try other encodings
                    try:
                        text = content.decode('utf-16')
                    except:
                        try:
                            text = content.decode('latin-1')
                        except:
                            text = content.decode('utf-8', errors='ignore')
                
                # Clean filename
                filename = file.filename.replace(' ', '_').replace('/', '_').replace('\\', '_')
                filename_base = os.path.splitext(filename)[0]
                
                # Process each sentence
                sentences = self.text_processor.split_sentences(text)
                
                if len(sentences) > 50:
                    sentences = sentences[:50]
                
                audio_segments = []
                all_subtitles = []
                
                for j in range(0, len(sentences), 2):
                    batch = sentences[j:j+2]
                    batch_text = ' '.join(batch)
                    
                    temp_file, subs = await self.generate_speech(batch_text, voice_id, rate, pitch, volume, clear_cache)
                    
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
                    continue
                
                combined = AudioSegment.empty()
                
                for k, audio in enumerate(audio_segments):
                    audio = audio.fade_in(50).fade_out(50)
                    combined += audio
                    
                    if k < len(audio_segments) - 1:
                        combined += AudioSegment.silent(duration=pause)
                
                # Create unique output filename
                file_timestamp = int(time.time())
                file_suffix = random.randint(1000, 9999)
                output_filename = f"{filename_base}_{file_timestamp}_{file_suffix}.{output_format}"
                output_file = os.path.join(output_dir, output_filename)
                
                combined.export(output_file, format=output_format, bitrate="192k")
                
                srt_file = None
                if all_subtitles:
                    srt_filename = f"{filename_base}_{file_timestamp}_{file_suffix}.srt"
                    srt_file = os.path.join(output_dir, srt_filename)
                    self.generate_srt(all_subtitles, output_file)
                
                results.append({
                    "original_filename": file.filename,
                    "audio_file": output_filename,
                    "srt_file": srt_filename if srt_file else None
                })
                
            except Exception as e:
                print(f"Error processing file {file.filename}: {e}")
                continue
        
        # Create zip file if multiple files
        if len(results) > 1:
            zip_filename = f"batch_results_{timestamp}_{unique_id}.zip"
            zip_path = os.path.join(output_dir, zip_filename)
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for result in results:
                    audio_path = os.path.join(output_dir, result["audio_file"])
                    if os.path.exists(audio_path):
                        zipf.write(audio_path, result["audio_file"])
                    
                    if result["srt_file"]:
                        srt_path = os.path.join(output_dir, result["srt_file"])
                        if os.path.exists(srt_path):
                            zipf.write(srt_path, result["srt_file"])
            
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=100, 
                                       message="Batch processing completed")
            
            return zip_path, results
        
        elif len(results) == 1:
            if task_id and task_manager:
                task_manager.update_task(task_id, progress=100, 
                                       message="Batch processing completed")
            
            output_file = os.path.join(output_dir, results[0]["audio_file"])
            srt_file = os.path.join(output_dir, results[0]["srt_file"]) if results[0]["srt_file"] else None
            
            return output_file, srt_file
        
        else:
            return None, None
    
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
    print("Starting up TTS Generator...")
    
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
    version="2.0.0",
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

# ==================== SINGLE VOICE ====================
@app.post("/api/generate/single")
async def generate_single_voice(
    text: str = Form(...),
    voice_id: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3"),
    clear_cache: bool = Form(False)
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
                        "message": "Audio generated successfully" + (" (fresh)" if clear_cache else "")
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
            "message": f"Audio generation started. {'Cache cleared for fresh audio.' if clear_cache else ''}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MULTI VOICE ====================
@app.post("/api/generate/multi")
async def generate_multi_voice(
    text: str = Form(...),
    voice1: str = Form(...),
    voice2: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3"),
    clear_cache: bool = Form(False)
):
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        if not voice1 or not voice2:
            raise HTTPException(status_code=400, detail="Both voices are required")
        
        task_id = f"multi_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "multi_voice")
        
        tts_processor.settings["multi_voice"] = {
            "voice1": voice1,
            "voice2": voice2,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "pause": pause
        }
        tts_processor.save_settings()
        
        async def background_task():
            try:
                audio_file, srt_file = await tts_processor.process_multi_voice(
                    text, voice1, voice2, rate, pitch, volume, pause, 
                    output_format, task_id, clear_cache
                )
                
                if audio_file:
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "message": "Multi-voice audio generated successfully" + (" (fresh)" if clear_cache else "")
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
            "message": f"Multi-voice audio generation started. {'Cache cleared for fresh audio.' if clear_cache else ''}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== BATCH PROCESSING ====================
@app.post("/api/generate/batch")
async def generate_batch(
    files: List[UploadFile] = File(...),
    voice_id: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3"),
    clear_cache: bool = Form(False)
):
    try:
        if not files:
            raise HTTPException(status_code=400, detail="Files are required")
        
        if not voice_id:
            raise HTTPException(status_code=400, detail="Voice is required")
        
        task_id = f"batch_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "batch")
        
        tts_processor.settings["batch"] = {
            "voice": voice_id,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "pause": pause
        }
        tts_processor.save_settings()
        
        async def background_task():
            try:
                result_file, srt_or_results = await tts_processor.process_batch(
                    files, voice_id, rate, pitch, volume, pause, 
                    output_format, task_id, clear_cache
                )
                
                if result_file:
                    if isinstance(srt_or_results, list):
                        # Multiple files -> zip
                        result = {
                            "success": True,
                            "zip_url": f"/download/{os.path.basename(result_file)}",
                            "files": srt_or_results,
                            "message": f"Batch processing completed. {len(srt_or_results)} files generated."
                        }
                    else:
                        # Single file
                        result = {
                            "success": True,
                            "audio_url": f"/download/{os.path.basename(result_file)}",
                            "srt_url": f"/download/{os.path.basename(srt_or_results)}" if srt_or_results else None,
                            "message": "Batch processing completed"
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
            "message": f"Batch processing started for {len(files)} files. {'Cache cleared for fresh audio.' if clear_cache else ''}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    
    # Search for the file in outputs directory
    for root, dirs, files in os.walk("outputs"):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Add NO-CACHE headers to prevent browser caching
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
    template_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
            --success-color: #4cc9f0;
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
        
        .voice-pair {
            background: linear-gradient(135deg, #f0f4ff, #e6f7ff);
            border-radius: 10px;
            padding: 1rem;
            margin: 1rem 0;
        }
        
        .file-upload-area {
            border: 2px dashed #dee2e6;
            border-radius: 10px;
            padding: 3rem;
            text-align: center;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .file-upload-area:hover {
            border-color: var(--primary-color);
            background: #f8f9ff;
        }
        
        .file-upload-area.dragover {
            border-color: var(--primary-color);
            background: #eef2ff;
        }
        
        .file-list {
            max-height: 200px;
            overflow-y: auto;
        }
        
        .file-item {
            background: #f8f9fa;
            border-radius: 5px;
            padding: 0.5rem;
            margin: 0.25rem 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
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
                Professional TTS Generator v2.0
            </a>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container main-container">
        <!-- Tabs -->
        <ul class="nav nav-tabs" id="ttsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single">
                    <i class="fas fa-user me-2"></i>Single Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="multi-tab" data-bs-toggle="tab" data-bs-target="#multi">
                    <i class="fas fa-users me-2"></i>Multi-Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="batch-tab" data-bs-toggle="tab" data-bs-target="#batch">
                    <i class="fas fa-folder me-2"></i>Batch Processing
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
                                    <i class="fas fa-sync-alt me-2"></i> Generate Fresh Audio
                                </label>
                                <small class="form-text text-muted d-block mt-1">
                                    Always generate new audio (recommended)
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
            
            <!-- Multi-Voice Tab -->
            <div class="tab-pane fade" id="multi">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label class="form-label">Text Content (Separate paragraphs with blank lines)</label>
                            <textarea class="form-control" id="multiText" rows="8" 
                                      placeholder="Paragraph 1 (will use Voice 1)...

Paragraph 2 (will use Voice 2)...

Paragraph 3 (will use Voice 1)...

Continue alternating..."></textarea>
                            <small class="text-muted">Each paragraph will alternate between Voice 1 and Voice 2</small>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="multiLanguage">
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}">{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <!-- Voice Pair -->
                        <div class="voice-pair mb-3">
                            <h6><i class="fas fa-user-friends me-2"></i>Voice Pair</h6>
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label">Voice 1</label>
                                        <select class="form-select" id="multiVoice1">
                                            <option value="">Select Voice 1</option>
                                        </select>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label class="form-label">Voice 2</label>
                                        <select class="form-select" id="multiVoice2">
                                            <option value="">Select Voice 2</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Voice Settings -->
                        <div class="accordion mb-3">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#multiSettings">
                                        <i class="fas fa-sliders-h me-2"></i>Voice Settings
                                    </button>
                                </h2>
                                <div id="multiSettings" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Speed: <span id="multiRateValue">0%</span>
                                            </label>
                                            <input type="range" class="form-range" id="multiRate" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pitch: <span id="multiPitchValue">0Hz</span>
                                            </label>
                                            <input type="range" class="form-range" id="multiPitch" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Volume: <span id="multiVolumeValue">100%</span>
                                            </label>
                                            <input type="range" class="form-range" id="multiVolume" min="50" max="150" value="100">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pause Duration: <span id="multiPauseValue">500ms</span>
                                            </label>
                                            <input type="range" class="form-range" id="multiPause" min="100" max="2000" value="500">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">Output Format</label>
                                            <select class="form-select" id="multiFormat">
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
                                <input class="form-check-input" type="checkbox" id="clearCacheMulti" checked>
                                <label class="form-check-label" for="clearCacheMulti">
                                    <i class="fas fa-sync-alt me-2"></i> Generate Fresh Audio
                                </label>
                                <small class="form-text text-muted d-block mt-1">
                                    Always generate new audio (recommended)
                                </small>
                            </div>
                        </div>
                        
                        <button class="btn btn-primary w-100" onclick="generateMulti()">
                            <i class="fas fa-users me-2"></i>Generate Multi-Voice Audio
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="multiTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="multiProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2" id="multiProgressText">0%</div>
                            </div>
                            <div id="multiTaskMessage"></div>
                        </div>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="multiOutput" style="display: none;">
                    <h5><i class="fas fa-users me-2"></i>Multi-Voice Audio</h5>
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
            
            <!-- Batch Processing Tab -->
            <div class="tab-pane fade" id="batch">
                <div class="row">
                    <div class="col-md-8">
                        <!-- File Upload Area -->
                        <div class="mb-3">
                            <label class="form-label">Upload Text Files (.txt)</label>
                            <div class="file-upload-area" id="batchUploadArea">
                                <i class="fas fa-cloud-upload-alt fa-3x text-muted mb-3"></i>
                                <h5>Drag & Drop Files Here</h5>
                                <p class="text-muted">or click to browse</p>
                                <input type="file" id="batchFiles" class="d-none" multiple accept=".txt">
                                <button class="btn btn-outline-primary mt-2" onclick="document.getElementById('batchFiles').click()">
                                    <i class="fas fa-folder-open me-2"></i>Browse Files
                                </button>
                            </div>
                            
                            <!-- File List -->
                            <div class="file-list mt-3" id="batchFileList" style="display: none;">
                                <h6>Selected Files:</h6>
                                <div id="batchFileItems"></div>
                            </div>
                        </div>
                        
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            <strong>Note:</strong> Each text file will be processed separately. 
                            For multiple files, a ZIP archive will be created containing all generated audio files.
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="batchLanguage">
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}">{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Voice</label>
                            <select class="form-select" id="batchVoice">
                                <option value="">Select Voice</option>
                            </select>
                        </div>
                        
                        <!-- Voice Settings -->
                        <div class="accordion mb-3">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#batchSettings">
                                        <i class="fas fa-sliders-h me-2"></i>Voice Settings
                                    </button>
                                </h2>
                                <div id="batchSettings" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Speed: <span id="batchRateValue">0%</span>
                                            </label>
                                            <input type="range" class="form-range" id="batchRate" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pitch: <span id="batchPitchValue">0Hz</span>
                                            </label>
                                            <input type="range" class="form-range" id="batchPitch" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Volume: <span id="batchVolumeValue">100%</span>
                                            </label>
                                            <input type="range" class="form-range" id="batchVolume" min="50" max="150" value="100">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">
                                                Pause Duration: <span id="batchPauseValue">500ms</span>
                                            </label>
                                            <input type="range" class="form-range" id="batchPause" min="100" max="2000" value="500">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">Output Format</label>
                                            <select class="form-select" id="batchFormat">
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
                                <input class="form-check-input" type="checkbox" id="clearCacheBatch" checked>
                                <label class="form-check-label" for="clearCacheBatch">
                                    <i class="fas fa-sync-alt me-2"></i> Generate Fresh Audio
                                </label>
                                <small class="form-text text-muted d-block mt-1">
                                    Always generate new audio (recommended)
                                </small>
                            </div>
                        </div>
                        
                        <button class="btn btn-primary w-100" onclick="generateBatch()">
                            <i class="fas fa-play-circle me-2"></i>Process Batch Files
                        </button>
                        
                        <!-- Task Status -->
                        <div class="task-status" id="batchTaskStatus">
                            <div class="progress-container">
                                <div class="progress">
                                    <div class="progress-bar" id="batchProgressBar" style="width: 0%"></div>
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
                        <a href="#" class="btn btn-success me-2" id="batchDownloadZip" style="display: none;">
                            <i class="fas fa-file-archive me-2"></i>Download ZIP
                        </a>
                        <a href="#" class="btn btn-success me-2" id="batchDownloadAudio" style="display: none;">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
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
        let batchFiles = [];
        
        // Initialize
        document.addEventListener('DOMContentLoaded', async function() {
            await loadSettings();
            await loadVoices('single');
            await loadVoices('multi1');
            await loadVoices('multi2');
            await loadVoices('batch');
            initRangeDisplays();
            initFileUpload();
            await cleanupOldFiles();
            
            // Set default values
            document.getElementById('singleLanguage').value = 'Vietnamese';
            document.getElementById('multiLanguage').value = 'Vietnamese';
            document.getElementById('batchLanguage').value = 'Vietnamese';
            
            // Load voices for all languages
            setTimeout(() => {
                document.getElementById('singleLanguage').dispatchEvent(new Event('change'));
                document.getElementById('multiLanguage').dispatchEvent(new Event('change'));
                document.getElementById('batchLanguage').dispatchEvent(new Event('change'));
            }, 500);
        });
        
        // Load settings
        async function loadSettings() {
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                // Single voice settings
                if (settings.single_voice) {
                    const sv = settings.single_voice;
                    document.getElementById('singleRate').value = sv.rate;
                    document.getElementById('singlePitch').value = sv.pitch;
                    document.getElementById('singleVolume').value = sv.volume;
                    document.getElementById('singlePause').value = sv.pause;
                }
                
                // Multi voice settings
                if (settings.multi_voice) {
                    const mv = settings.multi_voice;
                    document.getElementById('multiRate').value = mv.rate;
                    document.getElementById('multiPitch').value = mv.pitch;
                    document.getElementById('multiVolume').value = mv.volume;
                    document.getElementById('multiPause').value = mv.pause;
                }
                
                // Batch settings
                if (settings.batch) {
                    const bv = settings.batch;
                    document.getElementById('batchRate').value = bv.rate;
                    document.getElementById('batchPitch').value = bv.pitch;
                    document.getElementById('batchVolume').value = bv.volume;
                    document.getElementById('batchPause').value = bv.pause;
                }
                
                // Trigger input events to update displays
                ['single', 'multi', 'batch'].forEach(prefix => {
                    ['Rate', 'Pitch', 'Volume', 'Pause'].forEach(suffix => {
                        const id = prefix + suffix;
                        const element = document.getElementById(id);
                        if (element) {
                            element.dispatchEvent(new Event('input'));
                        }
                    });
                });
                
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        }
        
        // Load voices
        async function loadVoices(type) {
            try {
                let language, voiceSelect;
                
                if (type === 'single') {
                    language = document.getElementById('singleLanguage').value || 'Vietnamese';
                    voiceSelect = document.getElementById('singleVoice');
                } else if (type === 'multi1') {
                    language = document.getElementById('multiLanguage').value || 'Vietnamese';
                    voiceSelect = document.getElementById('multiVoice1');
                } else if (type === 'multi2') {
                    language = document.getElementById('multiLanguage').value || 'Vietnamese';
                    voiceSelect = document.getElementById('multiVoice2');
                } else if (type === 'batch') {
                    language = document.getElementById('batchLanguage').value || 'Vietnamese';
                    voiceSelect = document.getElementById('batchVoice');
                } else {
                    return;
                }
                
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Set default voices
                if (type === 'single' || type === 'batch') {
                    const viVoice = data.voices.find(v => v.name === 'vi-VN-HoaiMyNeural');
                    if (viVoice) {
                        voiceSelect.value = viVoice.name;
                    }
                } else if (type === 'multi1') {
                    const viVoice = data.voices.find(v => v.name === 'vi-VN-HoaiMyNeural');
                    if (viVoice) {
                        voiceSelect.value = viVoice.name;
                    }
                } else if (type === 'multi2') {
                    const viVoice = data.voices.find(v => v.name === 'vi-VN-NamMinhNeural');
                    if (viVoice) {
                        voiceSelect.value = viVoice.name;
                    }
                }
            } catch (error) {
                console.error('Error loading voices:', error);
            }
        }
        
        // Initialize range displays
        function initRangeDisplays() {
            const ranges = [
                { prefix: 'single', suffix: 'Rate', display: 'singleRateValue', format: '%' },
                { prefix: 'single', suffix: 'Pitch', display: 'singlePitchValue', format: 'Hz' },
                { prefix: 'single', suffix: 'Volume', display: 'singleVolumeValue', format: '%' },
                { prefix: 'single', suffix: 'Pause', display: 'singlePauseValue', format: 'ms' },
                { prefix: 'multi', suffix: 'Rate', display: 'multiRateValue', format: '%' },
                { prefix: 'multi', suffix: 'Pitch', display: 'multiPitchValue', format: 'Hz' },
                { prefix: 'multi', suffix: 'Volume', display: 'multiVolumeValue', format: '%' },
                { prefix: 'multi', suffix: 'Pause', display: 'multiPauseValue', format: 'ms' },
                { prefix: 'batch', suffix: 'Rate', display: 'batchRateValue', format: '%' },
                { prefix: 'batch', suffix: 'Pitch', display: 'batchPitchValue', format: 'Hz' },
                { prefix: 'batch', suffix: 'Volume', display: 'batchVolumeValue', format: '%' },
                { prefix: 'batch', suffix: 'Pause', display: 'batchPauseValue', format: 'ms' }
            ];
            
            ranges.forEach(range => {
                const id = range.prefix + range.suffix;
                const input = document.getElementById(id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.format;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.format;
                    });
                }
            });
        }
        
        // Language change handlers
        document.getElementById('singleLanguage').addEventListener('change', async function() {
            await loadVoices('single');
        });
        
        document.getElementById('multiLanguage').addEventListener('change', async function() {
            await loadVoices('multi1');
            await loadVoices('multi2');
        });
        
        document.getElementById('batchLanguage').addEventListener('change', async function() {
            await loadVoices('batch');
        });
        
        // Initialize file upload
        function initFileUpload() {
            const uploadArea = document.getElementById('batchUploadArea');
            const fileInput = document.getElementById('batchFiles');
            const fileList = document.getElementById('batchFileList');
            const fileItems = document.getElementById('batchFileItems');
            
            // Click to upload
            uploadArea.addEventListener('click', () => {
                fileInput.click();
            });
            
            // Drag and drop
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('dragover');
            });
            
            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                
                if (e.dataTransfer.files.length > 0) {
                    handleFiles(e.dataTransfer.files);
                }
            });
            
            // File input change
            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    handleFiles(e.target.files);
                }
            });
            
            // Handle selected files
            function handleFiles(files) {
                batchFiles = Array.from(files);
                updateFileList();
            }
            
            // Update file list display
            function updateFileList() {
                fileItems.innerHTML = '';
                
                if (batchFiles.length === 0) {
                    fileList.style.display = 'none';
                    return;
                }
                
                batchFiles.forEach((file, index) => {
                    const fileItem = document.createElement('div');
                    fileItem.className = 'file-item';
                    fileItem.innerHTML = `
                        <div>
                            <i class="fas fa-file-alt me-2"></i>
                            ${file.name} (${formatFileSize(file.size)})
                        </div>
                        <button class="btn btn-sm btn-outline-danger" onclick="removeFile(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    `;
                    fileItems.appendChild(fileItem);
                });
                
                fileList.style.display = 'block';
            }
            
            // Format file size
            function formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }
            
            // Make removeFile function globally available
            window.removeFile = function(index) {
                batchFiles.splice(index, 1);
                updateFileList();
            };
        }
        
        // Reset audio player
        function resetAudioPlayer(type) {
            const audioPlayer = document.getElementById(`${type}AudioPlayer`);
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
            document.getElementById(`${type}Output`).style.display = 'none';
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
            
            // Reset audio player before generating new audio
            resetAudioPlayer('single');
            
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
                    showToast('Audio generation started' + (clearCache ? ' (fresh audio)' : ''));
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
        
        // Generate multi-voice audio
        async function generateMulti() {
            const text = document.getElementById('multiText').value.trim();
            const voice1 = document.getElementById('multiVoice1').value;
            const voice2 = document.getElementById('multiVoice2').value;
            const language = document.getElementById('multiLanguage').value;
            const clearCache = document.getElementById('clearCacheMulti').checked;
            
            if (!text) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!language) {
                showToast('Please select a language', 'error');
                return;
            }
            
            if (!voice1 || !voice2) {
                showToast('Please select both voices', 'error');
                return;
            }
            
            // Reset audio player before generating new audio
            resetAudioPlayer('multi');
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice1', voice1);
            formData.append('voice2', voice2);
            formData.append('rate', document.getElementById('multiRate').value);
            formData.append('pitch', document.getElementById('multiPitch').value);
            formData.append('volume', document.getElementById('multiVolume').value);
            formData.append('pause', document.getElementById('multiPause').value);
            formData.append('output_format', document.getElementById('multiFormat').value);
            formData.append('clear_cache', clearCache);
            
            try {
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('multi', result.task_id);
                    showToast('Multi-voice audio generation started' + (clearCache ? ' (fresh audio)' : ''));
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
        
        // Generate batch processing
        async function generateBatch() {
            const voice = document.getElementById('batchVoice').value;
            const language = document.getElementById('batchLanguage').value;
            const clearCache = document.getElementById('clearCacheBatch').checked;
            
            if (batchFiles.length === 0) {
                showToast('Please select files to process', 'error');
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
            
            showLoading();
            
            const formData = new FormData();
            
            // Add files
            for (let file of batchFiles) {
                formData.append('files', file);
            }
            
            // Add other parameters
            formData.append('voice_id', voice);
            formData.append('rate', document.getElementById('batchRate').value);
            formData.append('pitch', document.getElementById('batchPitch').value);
            formData.append('volume', document.getElementById('batchVolume').value);
            formData.append('pause', document.getElementById('batchPause').value);
            formData.append('output_format', document.getElementById('batchFormat').value);
            formData.append('clear_cache', clearCache);
            
            try {
                const response = await fetch('/api/generate/batch', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus('batch', result.task_id);
                    showToast(`Batch processing started for ${batchFiles.length} files` + (clearCache ? ' (fresh audio)' : ''));
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
                            
                            // Show output with cache buster
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
            const resultsDiv = document.getElementById(`${type}Results`);
            
            outputDiv.style.display = 'block';
            
            if (type === 'batch') {
                // Handle batch processing results
                showBatchResults(result);
            } else {
                // Handle single/multi voice results
                const audioPlayer = document.getElementById(`${type}AudioPlayer`);
                const downloadAudio = document.getElementById(`${type}DownloadAudio`);
                const downloadSubtitle = document.getElementById(`${type}DownloadSubtitle`);
                
                // Add cache buster to URL - IMPORTANT for preventing browser cache
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
                
                // Remove old audio player and add new one
                audioPlayer.innerHTML = '';
                audioPlayer.appendChild(newAudio);
                
                // Force reload audio
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
                
                // Download link also add cache buster
                downloadAudio.href = cacheBusterUrl;
                downloadAudio.download = `tts_${type}_audio_${timestamp}.mp3`;
                
                if (result.srt_url) {
                    downloadSubtitle.href = result.srt_url;
                    downloadSubtitle.download = `tts_${type}_subtitle.srt`;
                    downloadSubtitle.style.display = 'inline-block';
                } else {
                    downloadSubtitle.style.display = 'none';
                }
            }
            
            // Scroll to output
            outputDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Show batch processing results
        function showBatchResults(result) {
            const resultsDiv = document.getElementById('batchResults');
            const downloadZip = document.getElementById('batchDownloadZip');
            const downloadAudio = document.getElementById('batchDownloadAudio');
            
            resultsDiv.innerHTML = '';
            
            if (result.zip_url) {
                // Multiple files -> show list and ZIP download
                resultsDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        Successfully processed ${result.files.length} files.
                    </div>
                    <div class="mt-3">
                        <h6>Processed Files:</h6>
                        <ul class="list-group">
                            ${result.files.map(file => `
                                <li class="list-group-item">
                                    <i class="fas fa-file-alt me-2"></i>
                                    ${file.original_filename}
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                `;
                
                // Add cache buster to ZIP URL
                const timestamp = new Date().getTime();
                const cacheBusterUrl = `${result.zip_url}?t=${timestamp}`;
                
                downloadZip.href = cacheBusterUrl;
                downloadZip.download = `tts_batch_${timestamp}.zip`;
                downloadZip.style.display = 'inline-block';
                downloadAudio.style.display = 'none';
                
            } else if (result.audio_url) {
                // Single file -> show audio player
                resultsDiv.innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        Successfully processed batch file.
                    </div>
                `;
                
                // Create audio player
                const audioPlayer = document.createElement('div');
                audioPlayer.className = 'audio-player';
                audioPlayer.innerHTML = `
                    <audio controls class="w-100">
                        <source src="${result.audio_url}?t=${new Date().getTime()}" type="audio/mpeg">
                        Your browser does not support the audio element.
                    </audio>
                `;
                resultsDiv.appendChild(audioPlayer);
                
                // Add cache buster to audio URL
                const timestamp = new Date().getTime();
                const cacheBusterUrl = `${result.audio_url}?t=${timestamp}`;
                
                downloadAudio.href = cacheBusterUrl;
                downloadAudio.download = `tts_batch_audio_${timestamp}.mp3`;
                downloadAudio.style.display = 'inline-block';
                downloadZip.style.display = 'none';
            }
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
                             type === 'warning' ? 'warning' : 'success';
            const icon = type === 'error' ? 'fa-exclamation-circle' : 
                        type === 'warning' ? 'fa-exclamation-triangle' : 'fa-check-circle';
            
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

# ==================== CREATE REQUIREMENTS FILE ====================
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

# ==================== RUN APPLICATION ====================
if __name__ == "__main__":
    create_requirements_txt()
    
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("PROFESSIONAL TTS GENERATOR v2.0")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Open http://localhost:{port} in your browser")
    print("Features:")
    print("1. Single Voice TTS")
    print("2. Multi-Voice TTS (alternating voices)")
    print("3. Batch Processing (multiple text files)")
    print("4. Browser Cache Fix (unique filenames + cache busters)")
    print("=" * 60)
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
