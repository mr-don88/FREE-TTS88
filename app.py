# -*- coding: utf-8 -*-
"""
TTSFree - Professional Text to Speech & Speech to Text Platform
URL: https://free-tts88.onrender.com/
"""

import os
import sys
import json
import time
import asyncio
import random
import re
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# FastAPI và dependencies
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Depends, status, Cookie, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

# Database
import sqlite3
from sqlite3 import Connection
import hashlib
import jwt
from functools import wraps

# TTS
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import webvtt

# Whisper for Speech to Text
try:
    import whisper
    WHISPER_AVAILABLE = True
    print("✅ Whisper is available")
except ImportError:
    WHISPER_AVAILABLE = False
    print("⚠️ Whisper not available, Speech to Text will be disabled")

# PyTorch check
try:
    import torch
    TORCH_AVAILABLE = True
    print("✅ PyTorch is available")
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch not available")

# ==================== DATABASE CONFIGURATION ====================
class Database:
    def __init__(self, db_path: str = "ttsfree.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self) -> Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            language TEXT DEFAULT 'en',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            subscription_type TEXT DEFAULT 'free',
            subscription_expiry TIMESTAMP,
            credits INTEGER DEFAULT 100,
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0
        )
        ''')
        
        # Subscription plans
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price_monthly REAL,
            price_yearly REAL,
            credits_per_month INTEGER,
            max_audio_length INTEGER,
            max_file_size INTEGER,
            features TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_popular BOOLEAN DEFAULT 0
        )
        ''')
        
        # User files
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER,
            duration INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0,
            result_file TEXT,
            metadata TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # User credits history
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS credit_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        ''')
        
        # Insert default subscription plans
        default_plans = [
            ('Free', 'Basic features for everyone', 0, 0, 100, 300, 25, 
             '["Basic TTS", "Speech to Text", "100 credits/month", "Standard Voices"]', 1, 0),
            ('Pro', 'For professionals and creators', 9.99, 99.99, 1000, 1800, 100,
             '["All TTS voices", "Batch processing", "Priority support", "No ads", "High Quality Audio"]', 1, 1),
            ('Business', 'For teams and enterprises', 29.99, 299.99, 5000, 3600, 500,
             '["All Pro features", "API access", "Custom voices", "Team management", "Unlimited Exports"]', 1, 0)
        ]
        
        cursor.execute('SELECT COUNT(*) FROM subscription_plans')
        if cursor.fetchone()[0] == 0:
            cursor.executemany('''
            INSERT INTO subscription_plans (name, description, price_monthly, price_yearly, 
                                          credits_per_month, max_audio_length, max_file_size, features, is_active, is_popular)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', default_plans)
        
        # Create default admin user if not exists
        cursor.execute('SELECT * FROM users WHERE username = ?', ('admin',))
        if not cursor.fetchone():
            admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
            cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, is_admin, credits)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', ('admin', 'admin@ttsfree.com', admin_password, 'Administrator', 1, 999999))
        
        # Create demo user
        cursor.execute('SELECT * FROM users WHERE username = ?', ('demo',))
        if not cursor.fetchone():
            demo_password = hashlib.sha256('demo123'.encode()).hexdigest()
            cursor.execute('''
            INSERT INTO users (username, email, password_hash, full_name, credits)
            VALUES (?, ?, ?, ?, ?)
            ''', ('demo', 'demo@ttsfree.com', demo_password, 'Demo User', 500))
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")

# ==================== AUTHENTICATION ====================
class AuthManager:
    def __init__(self, secret_key: str = "ttsfree-secret-key-2024-change-in-production"):
        self.secret_key = secret_key
        self.security = HTTPBasic()
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password) == hashed
    
    def create_token(self, user_id: int, username: str, is_admin: bool = False) -> str:
        """Create JWT token"""
        payload = {
            'user_id': user_id,
            'username': username,
            'is_admin': is_admin,
            'exp': datetime.utcnow() + timedelta(days=7)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            return payload
        except:
            return None
    
    async def get_current_user(self, token: str = Cookie(None, alias="token")):
        """Get current user from token"""
        if not token:
            return None
        
        payload = self.verify_token(token)
        if not payload:
            return None
        
        db = Database()
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (payload['user_id'],))
        user = cursor.fetchone()
        conn.close()
        
        if user and user['is_active']:
            return dict(user)
        return None

# ==================== TTS CONFIGURATION ====================
class TTSConfig:
    LANGUAGES = {
        "en": {"name": "English", "voices": [
            {"id": "en-US-GuyNeural", "name": "Guy", "gender": "Male", "style": "Standard US"},
            {"id": "en-US-JennyNeural", "name": "Jenny", "gender": "Female", "style": "Standard US"},
            {"id": "en-US-AvaNeural", "name": "Ava", "gender": "Female", "style": "Friendly"},
            {"id": "en-US-AndrewNeural", "name": "Andrew", "gender": "Male", "style": "Professional"},
            {"id": "en-US-EmmaNeural", "name": "Emma", "gender": "Female", "style": "Calm"},
            {"id": "en-US-BrianNeural", "name": "Brian", "gender": "Male", "style": "Confident"},
            {"id": "en-US-AnaNeural", "name": "Ana", "gender": "Female", "style": "Child"},
            {"id": "en-US-AndrewMultilingualNeural", "name": "Andrew Multi", "gender": "Male", "style": "Multilingual"},
            {"id": "en-US-AvaMultilingualNeural", "name": "Ava Multi", "gender": "Female", "style": "Multilingual"}
        ]},
        "vi": {"name": "Tiếng Việt", "voices": [
            {"id": "vi-VN-HoaiMyNeural", "name": "Hoài My", "gender": "Female", "style": "Standard"},
            {"id": "vi-VN-NamMinhNeural", "name": "Nam Minh", "gender": "Male", "style": "Standard"}
        ]},
        "zh": {"name": "中文", "voices": [
            {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "Female", "style": "Standard"},
            {"id": "zh-CN-YunxiNeural", "name": "云希", "gender": "Male", "style": "Standard"},
            {"id": "zh-CN-YunjianNeural", "name": "云健", "gender": "Male", "style": "Confident"},
            {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "Female", "style": "Friendly"}
        ]},
        "ja": {"name": "日本語", "voices": [
            {"id": "ja-JP-NanamiNeural", "name": "七海", "gender": "Female", "style": "Standard"},
            {"id": "ja-JP-KeitaNeural", "name": "圭太", "gender": "Male", "style": "Standard"},
            {"id": "ja-JP-DaichiNeural", "name": "大地", "gender": "Male", "style": "Confident"}
        ]},
        "ko": {"name": "한국어", "voices": [
            {"id": "ko-KR-SunHiNeural", "name": "선희", "gender": "Female", "style": "Standard"},
            {"id": "ko-KR-InJoonNeural", "name": "인준", "gender": "Male", "style": "Standard"}
        ]},
        "fr": {"name": "Français", "voices": [
            {"id": "fr-FR-DeniseNeural", "name": "Denise", "gender": "Female", "style": "Standard"},
            {"id": "fr-FR-HenriNeural", "name": "Henri", "gender": "Male", "style": "Standard"}
        ]},
        "es": {"name": "Español", "voices": [
            {"id": "es-ES-AlvaroNeural", "name": "Álvaro", "gender": "Male", "style": "Standard"},
            {"id": "es-ES-ElviraNeural", "name": "Elvira", "gender": "Female", "style": "Standard"}
        ]},
        "de": {"name": "Deutsch", "voices": [
            {"id": "de-DE-KatjaNeural", "name": "Katja", "gender": "Female", "style": "Standard"},
            {"id": "de-DE-ConradNeural", "name": "Conrad", "gender": "Male", "style": "Standard"}
        ]},
        "it": {"name": "Italiano", "voices": [
            {"id": "it-IT-IsabellaNeural", "name": "Isabella", "gender": "Female", "style": "Standard"},
            {"id": "it-IT-DiegoNeural", "name": "Diego", "gender": "Male", "style": "Standard"}
        ]},
        "pt": {"name": "Português", "voices": [
            {"id": "pt-BR-FranciscaNeural", "name": "Francisca", "gender": "Female", "style": "Standard"},
            {"id": "pt-BR-AntonioNeural", "name": "Antônio", "gender": "Male", "style": "Standard"}
        ]},
        "ru": {"name": "Русский", "voices": [
            {"id": "ru-RU-SvetlanaNeural", "name": "Светлана", "gender": "Female", "style": "Standard"},
            {"id": "ru-RU-DmitryNeural", "name": "Дмитрий", "gender": "Male", "style": "Standard"}
        ]}
    }
    
    OUTPUT_FORMATS = [
        {"id": "mp3", "name": "MP3", "quality": "High"},
        {"id": "wav", "name": "WAV", "quality": "Lossless"},
        {"id": "ogg", "name": "OGG", "quality": "Compressed"}
    ]
    
    # Default pause settings
    PAUSE_SETTINGS = {
        "short": 300,
        "medium": 500,
        "long": 800,
        "very_long": 1200
    }

# ==================== TEXT PROCESSOR ====================
class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Process special cases
        text = TextProcessor._process_special_cases(text)
        
        return text
    
    @staticmethod
    def _process_special_cases(text: str) -> str:
        """Process special text cases"""
        # Process emails
        text = re.sub(
            r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b',
            lambda m: m.group(0).replace('@', ' at ').replace('.', ' dot '),
            text
        )
        
        # Process URLs
        text = re.sub(
            r'https?://\S+|www\.\S+',
            lambda m: m.group(0).replace('.', ' dot ').replace('/', ' slash '),
            text
        )
        
        # Process phone numbers
        text = re.sub(
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            lambda m: ' '.join(list(m.group(0).replace('-', '').replace('.', ''))),
            text
        )
        
        # Process numbers
        text = re.sub(
            r'\b(\d+)\b',
            lambda m: TextProcessor._number_to_words(m.group(1)),
            text
        )
        
        return text
    
    @staticmethod
    def _number_to_words(num_str: str) -> str:
        """Convert number to words (basic)"""
        try:
            num = int(num_str)
            if num < 20:
                words = ["zero", "one", "two", "three", "four", "five", "six", "seven", 
                        "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen",
                        "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
                return words[num] if num < len(words) else num_str
            elif num < 100:
                tens = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
                word = tens[num // 10 - 2]
                if num % 10 != 0:
                    word += " " + TextProcessor._number_to_words(str(num % 10))
                return word
            else:
                return num_str  # Simplified for now
        except:
            return num_str
    
    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.output_dir = "outputs"
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs("temp", exist_ok=True)
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, 
                            pitch: int = 0, volume: int = 100) -> Optional[str]:
        """Generate speech using edge-tts"""
        try:
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"{pitch}Hz"
            
            communicate = edge_tts.Communicate(
                text, 
                voice_id, 
                rate=rate_str, 
                pitch=pitch_str
            )
            
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                return None
            
            # Combine audio chunks
            audio_data = b"".join(audio_chunks)
            
            # Create temp file
            temp_file = f"temp/tts_{int(time.time())}_{random.randint(1000, 9999)}.mp3"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Apply volume adjustment
            audio = AudioSegment.from_file(temp_file)
            volume_adjustment = min(max(volume - 100, -50), 10)
            audio = audio + volume_adjustment
            
            # Apply audio processing
            audio = normalize(audio)
            audio = compress_dynamic_range(audio)
            
            audio.export(temp_file, format="mp3", bitrate="192k")
            
            return temp_file
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None
    
    async def process_tts(self, text: str, voice_id: str, output_format: str = "mp3", 
                         rate: int = 0, pitch: int = 0, volume: int = 100,
                         pause_duration: int = 300) -> Optional[str]:
        """Process TTS with full pipeline"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(self.output_dir, f"tts_{timestamp}")
            os.makedirs(output_dir, exist_ok=True)
            
            # Clean text
            text = self.text_processor.clean_text(text)
            
            # Split into sentences
            sentences = self.text_processor.split_sentences(text)
            
            if not sentences:
                return None
            
            # Generate speech for each sentence
            audio_segments = []
            
            for i, sentence in enumerate(sentences):
                if not sentence.strip():
                    continue
                    
                temp_file = await self.generate_speech(sentence, voice_id, rate, pitch, volume)
                if temp_file:
                    audio = AudioSegment.from_file(temp_file)
                    audio_segments.append(audio)
                    os.remove(temp_file)
                
                # Add progress indicator
                if i % 5 == 0:
                    print(f"Processing sentence {i+1}/{len(sentences)}...")
            
            if not audio_segments:
                return None
            
            # Combine audio segments with pauses
            combined = AudioSegment.empty()
            for i, audio in enumerate(audio_segments):
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause_duration)
            
            # Export
            output_file = os.path.join(output_dir, f"tts_output.{output_format}")
            combined.export(output_file, format=output_format, bitrate="192k")
            
            print(f"✅ TTS generated: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"Error in TTS process: {e}")
            return None
    
    async def process_batch_tts(self, texts: List[str], voice_id: str, output_format: str = "mp3",
                              rate: int = 0, pitch: int = 0, volume: int = 100) -> Optional[str]:
        """Process batch TTS - multiple texts to single audio"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = os.path.join(self.output_dir, f"batch_tts_{timestamp}")
            os.makedirs(output_dir, exist_ok=True)
            
            audio_segments = []
            
            for i, text in enumerate(texts):
                if not text.strip():
                    continue
                    
                text = self.text_processor.clean_text(text)
                temp_file = await self.generate_speech(text, voice_id, rate, pitch, volume)
                
                if temp_file:
                    audio = AudioSegment.from_file(temp_file)
                    audio_segments.append(audio)
                    os.remove(temp_file)
                
                # Add progress indicator
                if i % 5 == 0:
                    print(f"Processing batch item {i+1}/{len(texts)}...")
            
            if not audio_segments:
                return None
            
            # Combine all audio segments
            combined = AudioSegment.empty()
            for audio in audio_segments:
                combined += audio + AudioSegment.silent(duration=500)
            
            # Export
            output_file = os.path.join(output_dir, f"batch_output.{output_format}")
            combined.export(output_file, format=output_format, bitrate="192k")
            
            print(f"✅ Batch TTS generated: {output_file}")
            return output_file
            
        except Exception as e:
            print(f"Error in batch TTS: {e}")
            return None

# ==================== SPEECH TO TEXT PROCESSOR ====================
class SpeechToTextProcessor:
    def __init__(self):
        self.model = None
        self.load_model()
        self.output_dir = "outputs"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def load_model(self):
        """Load Whisper model"""
        if not WHISPER_AVAILABLE:
            return False
        
        try:
            print("🔄 Loading Whisper model...")
            self.model = whisper.load_model("base")
            print("✅ Whisper model loaded successfully")
            return True
        except Exception as e:
            print(f"❌ Error loading Whisper model: {e}")
            return False
    
    def transcribe_audio(self, audio_path: str, language: str = None, task: str = "transcribe"):
        """Transcribe audio to text"""
        if not self.model:
            return None
        
        try:
            print(f"🎤 Transcribing audio: {audio_path}")
            result = self.model.transcribe(
                audio_path,
                language=language if language and language != "auto" else None,
                task=task,  # "transcribe" or "translate"
                verbose=False,
                fp16=False,
                word_timestamps=True
            )
            
            print(f"✅ Transcription complete, got {len(result.get('text', ''))} characters")
            return {
                'text': result.get('text', ''),
                'segments': result.get('segments', []),
                'language': result.get('language', 'en')
            }
        except Exception as e:
            print(f"❌ Error transcribing audio: {e}")
            return None
    
    def generate_subtitles(self, audio_path: str, output_format: str = "srt", 
                          language: str = None, task: str = "transcribe"):
        """Generate subtitles from audio"""
        result = self.transcribe_audio(audio_path, language, task)
        if not result:
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(self.output_dir, f"stt_{timestamp}")
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = None
        
        if output_format == "srt":
            output_file = os.path.join(output_dir, f"subtitle.srt")
            self._generate_srt(result['segments'], output_file)
        elif output_format == "txt":
            output_file = os.path.join(output_dir, f"transcript.txt")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(result['text'])
        elif output_format == "json":
            output_file = os.path.join(output_dir, f"transcript.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
        elif output_format == "vtt":
            output_file = os.path.join(output_dir, f"subtitle.vtt")
            self._generate_vtt(result['segments'], output_file)
        
        if output_file:
            print(f"✅ Subtitles generated: {output_file}")
        
        return output_file
    
    def _generate_srt(self, segments: List, output_path: str):
        """Generate SRT file from segments"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, seg in enumerate(segments, 1):
                start = timedelta(seconds=seg['start'])
                end = timedelta(seconds=seg['end'])
                
                start_str = f"{start.seconds // 3600:02d}:{(start.seconds % 3600) // 60:02d}:{start.seconds % 60:02d},{int(start.microseconds / 1000):03d}"
                end_str = f"{end.seconds // 3600:02d}:{(end.seconds % 3600) // 60:02d}:{end.seconds % 60:02d},{int(end.microseconds / 1000):03d}"
                
                f.write(f"{i}\n")
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{seg['text'].strip()}\n\n")
    
    def _generate_vtt(self, segments: List, output_path: str):
        """Generate VTT file from segments"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("WEBVTT\n\n")
            
            for i, seg in enumerate(segments, 1):
                start = timedelta(seconds=seg['start'])
                end = timedelta(seconds=seg['end'])
                
                start_str = f"{start.seconds // 3600:02d}:{(start.seconds % 3600) // 60:02d}:{start.seconds % 60:02d}.{int(start.microseconds / 1000):03d}"
                end_str = f"{end.seconds // 3600:02d}:{(end.seconds % 3600) // 60:02d}:{end.seconds % 60:02d}.{int(end.microseconds / 1000):03d}"
                
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{seg['text'].strip()}\n\n")

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="TTSFree - Text to Speech & Speech to Text",
    description="Professional TTS and Speech Recognition Platform",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Initialize components
print("🔄 Initializing system components...")
db = Database()
auth = AuthManager()
tts_processor = TTSProcessor()
stt_processor = SpeechToTextProcessor()
print("✅ System components initialized")

# Create directories
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==================== MIDDLEWARE & DEPENDENCIES ====================
def require_login(func):
    """Decorator to require login"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request')
        user = await auth.get_current_user(request.cookies.get("token") if request else None)
        
        if not user:
            return RedirectResponse(url="/login?next=" + request.url.path if request else "/login", 
                                   status_code=status.HTTP_303_SEE_OTHER)
        
        kwargs['user'] = user
        return await func(*args, **kwargs)
    return wrapper

def require_credits(amount: int = 1):
    """Decorator to require credits"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get('user')
            if not user:
                return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
            
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT credits FROM users WHERE id = ?', (user['id'],))
            result = cursor.fetchone()
            current_credits = result[0] if result else 0
            conn.close()
            
            if current_credits < amount:
                raise HTTPException(
                    status_code=402,
                    detail=f"Insufficient credits. Required: {amount}, Available: {current_credits}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    
    # Get statistics
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM user_files')
    total_files = cursor.fetchone()[0]
    conn.close()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "total_users": total_users,
        "total_files": total_files,
        "whisper_available": WHISPER_AVAILABLE and stt_processor.model is not None,
        "languages": TTSConfig.LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next_url: str = "/"):
    """Login page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    if user:
        return RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "next_url": next_url
    })

@app.post("/api/login")
async def login_api(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False),
    next_url: str = Form("/")
):
    """Login API"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, username))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password",
            "next_url": next_url
        })
    
    if not auth.verify_password(password, user['password_hash']):
        conn.close()
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Invalid username or password",
            "next_url": next_url
        })
    
    if not user['is_active']:
        conn.close()
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Account is deactivated",
            "next_url": next_url
        })
    
    # Update last login
    cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
    conn.commit()
    
    # Create token
    token = auth.create_token(user['id'], user['username'], user['is_admin'])
    
    conn.close()
    
    response = RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
    
    # Set cookie
    expires = 604800 if remember else None  # 7 days if remember me
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=expires,
        samesite="lax"
    )
    
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/api/register")
async def register_api(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(""),
    language: str = Form("en")
):
    """Register API"""
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Passwords do not match"
        })
    
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Password must be at least 6 characters"
        })
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Check if username exists
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Username already exists"
        })
    
    # Check if email exists
    cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
    if cursor.fetchone():
        conn.close()
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Email already exists"
        })
    
    # Hash password
    password_hash = auth.hash_password(password)
    
    # Create user
    cursor.execute('''
    INSERT INTO users (username, email, password_hash, full_name, language, credits)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (username, email, password_hash, full_name, language, 100))
    
    user_id = cursor.lastrowid
    
    # Add credit history entry
    cursor.execute('''
    INSERT INTO credit_history (user_id, amount, reason)
    VALUES (?, ?, ?)
    ''', (user_id, 100, "Welcome bonus"))
    
    conn.commit()
    conn.close()
    
    # Auto login after registration
    token = auth.create_token(user_id, username, False)
    
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="token",
        value=token,
        httponly=True,
        max_age=604800,  # 7 days
        samesite="lax"
    )
    
    return response

@app.get("/logout")
async def logout():
    """Logout"""
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
@require_login
async def dashboard(request: Request, user: dict):
    """User dashboard"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get user files
    cursor.execute('''
    SELECT * FROM user_files 
    WHERE user_id = ? 
    ORDER BY created_at DESC 
    LIMIT 20
    ''', (user['id'],))
    files = [dict(row) for row in cursor.fetchall()]
    
    # Get credit history
    cursor.execute('''
    SELECT * FROM credit_history 
    WHERE user_id = ? 
    ORDER BY created_at DESC 
    LIMIT 10
    ''', (user['id'],))
    credit_history = [dict(row) for row in cursor.fetchall()]
    
    # Get statistics
    cursor.execute('SELECT COUNT(*) FROM user_files WHERE user_id = ?', (user['id'],))
    total_files = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(file_size) FROM user_files WHERE user_id = ?', (user['id'],))
    total_storage = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "files": files,
        "credit_history": credit_history,
        "stats": {
            "total_files": total_files,
            "total_storage": f"{total_storage / (1024*1024):.2f} MB"
        }
    })

@app.get("/text-to-speech", response_class=HTMLResponse)
async def tts_page(request: Request):
    """Text to Speech page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    
    return templates.TemplateResponse("tts.html", {
        "request": request,
        "user": user,
        "languages": TTSConfig.LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS,
        "pause_settings": TTSConfig.PAUSE_SETTINGS
    })

@app.get("/api/voices")
async def get_voices(language: str = "en"):
    """Get voices for a language"""
    if language in TTSConfig.LANGUAGES:
        return {"success": True, "voices": TTSConfig.LANGUAGES[language]["voices"]}
    else:
        # Return English voices as default
        return {"success": True, "voices": TTSConfig.LANGUAGES["en"]["voices"]}

@app.post("/api/tts/generate")
@require_login
@require_credits(5)
async def tts_generate(
    request: Request,
    text: str = Form(...),
    language: str = Form("en"),
    voice: str = Form(...),
    output_format: str = Form("mp3"),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause_duration: int = Form(300),
    user: dict = Depends(require_login)
):
    """Generate TTS audio"""
    # Check text length
    if len(text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Text too long (max 5000 characters)")
    
    # Deduct credits
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET credits = credits - 5 WHERE id = ?', (user['id'],))
    
    # Add to credit history
    cursor.execute('''
    INSERT INTO credit_history (user_id, amount, reason)
    VALUES (?, ?, ?)
    ''', (user['id'], -5, "TTS generation"))
    
    cursor.execute('SELECT credits FROM users WHERE id = ?', (user['id'],))
    new_credits = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    try:
        # Generate TTS
        output_file = await tts_processor.process_tts(
            text, voice, output_format, rate, pitch, volume, pause_duration
        )
        
        if not output_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        # Save to user files
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO user_files (user_id, filename, original_filename, file_type, file_size)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            user['id'],
            os.path.basename(output_file),
            f"tts_output.{output_format}",
            "tts",
            os.path.getsize(output_file)
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(output_file)}",
            "filename": os.path.basename(output_file),
            "credits_remaining": new_credits,
            "message": "Audio generated successfully!"
        }
        
    except Exception as e:
        print(f"Error generating TTS: {e}")
        # Refund credits on error
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET credits = credits + 5 WHERE id = ?', (user['id'],))
        conn.commit()
        conn.close()
        
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@app.post("/api/tts/batch")
@require_login
@require_credits(20)
async def tts_batch(
    request: Request,
    texts: str = Form(...),  # JSON array of texts
    language: str = Form("en"),
    voice: str = Form(...),
    output_format: str = Form("mp3"),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    user: dict = Depends(require_login)
):
    """Generate batch TTS"""
    try:
        texts_list = json.loads(texts)
        if not isinstance(texts_list, list):
            raise ValueError("Texts must be a JSON array")
        
        if len(texts_list) > 50:
            raise ValueError("Maximum 50 texts allowed")
        
        total_chars = sum(len(str(t)) for t in texts_list)
        if total_chars > 20000:
            raise ValueError("Total text too long (max 20000 characters)")
        
        # Deduct credits
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET credits = credits - 20 WHERE id = ?', (user['id'],))
        
        # Add to credit history
        cursor.execute('''
        INSERT INTO credit_history (user_id, amount, reason)
        VALUES (?, ?, ?)
        ''', (user['id'], -20, "Batch TTS generation"))
        
        cursor.execute('SELECT credits FROM users WHERE id = ?', (user['id'],))
        new_credits = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        # Generate batch TTS
        output_file = await tts_processor.process_batch_tts(
            texts_list, voice, output_format, rate, pitch, volume
        )
        
        if not output_file:
            raise HTTPException(status_code=500, detail="Failed to generate batch audio")
        
        # Save to user files
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO user_files (user_id, filename, original_filename, file_type, file_size)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            user['id'],
            os.path.basename(output_file),
            f"batch_tts.{output_format}",
            "batch_tts",
            os.path.getsize(output_file)
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(output_file)}",
            "filename": os.path.basename(output_file),
            "credits_remaining": new_credits,
            "message": f"Batch audio generated with {len(texts_list)} items!"
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error generating batch TTS: {e}")
        # Refund credits on error
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET credits = credits + 20 WHERE id = ?', (user['id'],))
        conn.commit()
        conn.close()
        
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")

@app.get("/speech-to-text", response_class=HTMLResponse)
async def stt_page(request: Request):
    """Speech to Text page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    
    whisper_available = WHISPER_AVAILABLE and stt_processor.model is not None
    
    return templates.TemplateResponse("stt.html", {
        "request": request,
        "user": user,
        "whisper_available": whisper_available,
        "languages": TTSConfig.LANGUAGES,
        "formats": ["srt", "txt", "json", "vtt"]
    })

@app.post("/api/stt/transcribe")
@require_login
@require_credits(10)
async def stt_transcribe(
    request: Request,
    audio_file: UploadFile = File(...),
    language: str = Form("auto"),
    output_format: str = Form("txt"),
    task: str = Form("transcribe"),  # "transcribe" or "translate"
    user: dict = Depends(require_login)
):
    """Transcribe audio to text"""
    # Check if STT is available
    if not WHISPER_AVAILABLE or stt_processor.model is None:
        raise HTTPException(status_code=503, detail="Speech to Text service is temporarily unavailable")
    
    # Check file type
    allowed_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.mp4', '.mpeg']
    file_ext = os.path.splitext(audio_file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}")
    
    # Save uploaded file
    timestamp = int(time.time())
    file_path = f"uploads/{timestamp}_{audio_file.filename}"
    os.makedirs("uploads", exist_ok=True)
    
    file_size = 0
    with open(file_path, "wb") as f:
        while content := await audio_file.read(1024 * 1024):  # Read in 1MB chunks
            file_size += len(content)
            f.write(content)
            
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                os.remove(file_path)
                raise HTTPException(status_code=400, detail="File too large (max 100MB)")
    
    # Deduct credits
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET credits = credits - 10 WHERE id = ?', (user['id'],))
    
    # Add to credit history
    cursor.execute('''
    INSERT INTO credit_history (user_id, amount, reason)
    VALUES (?, ?, ?)
    ''', (user['id'], -10, "Speech to Text"))
    
    cursor.execute('SELECT credits FROM users WHERE id = ?', (user['id'],))
    new_credits = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    try:
        # Transcribe
        output_file = stt_processor.generate_subtitles(file_path, output_format, language, task)
        
        # Remove uploaded file
        os.remove(file_path)
        
        if not output_file:
            raise HTTPException(status_code=500, detail="Failed to transcribe audio")
        
        # Save to user files
        conn = db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO user_files (user_id, filename, original_filename, file_type, file_size, processed)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            user['id'],
            os.path.basename(output_file),
            audio_file.filename,
            "stt",
            os.path.getsize(output_file),
            1
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "download_url": f"/download/{os.path.basename(output_file)}",
            "filename": os.path.basename(output_file),
            "credits_remaining": new_credits,
            "message": "Transcription completed successfully!"
        }
        
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        # Remove uploaded file on error
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Refund credits on error
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET credits = credits + 10 WHERE id = ?', (user['id'],))
        conn.commit()
        conn.close()
        
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Pricing page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM subscription_plans WHERE is_active = 1 ORDER BY price_monthly ASC')
    plans = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "user": user,
        "plans": plans
    })

@app.get("/ai-voices", response_class=HTMLResponse)
async def ai_voices_page(request: Request):
    """AI Voices showcase page"""
    user = await auth.get_current_user(request.cookies.get("token"))
    
    return templates.TemplateResponse("ai-voices.html", {
        "request": request,
        "user": user,
        "languages": TTSConfig.LANGUAGES
    })

@app.get("/download/{filename}")
async def download_file(filename: str, request: Request):
    """Download file"""
    user = await auth.get_current_user(request.cookies.get("token"))
    
    if not user:
        raise HTTPException(status_code=401, detail="Login required to download files")
    
    # Search for file in outputs directory
    file_path = None
    for root, dirs, files in os.walk("outputs"):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if user has access to this file
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT COUNT(*) FROM user_files 
    WHERE filename = ? AND user_id = ?
    ''', (filename, user['id']))
    
    has_access = cursor.fetchone()[0] > 0 or user['is_admin']
    conn.close()
    
    if not has_access:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/api/user/profile")
@require_login
async def get_user_profile(user: dict):
    """Get user profile"""
    return {
        "success": True,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "email": user['email'],
            "full_name": user['full_name'],
            "language": user['language'],
            "subscription_type": user['subscription_type'],
            "credits": user['credits'],
            "created_at": user['created_at']
        }
    }

@app.post("/api/user/update-profile")
@require_login
async def update_user_profile(
    full_name: str = Form(None),
    language: str = Form(None),
    user: dict = Depends(require_login)
):
    """Update user profile"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if full_name is not None:
        updates.append("full_name = ?")
        params.append(full_name)
    
    if language is not None:
        updates.append("language = ?")
        params.append(language)
    
    if updates:
        params.append(user['id'])
        query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
    
    conn.close()
    
    return {"success": True, "message": "Profile updated"}

@app.get("/api/plans")
async def get_plans():
    """Get subscription plans"""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM subscription_plans WHERE is_active = 1 ORDER BY price_monthly ASC')
    plans = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"success": True, "plans": plans}

@app.get("/api/stats")
async def get_stats():
    """Get platform statistics"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= DATE("now", "-30 days")')
    new_users_30d = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(credits) FROM users')
    total_credits = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM user_files')
    total_files = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "success": True,
        "stats": {
            "total_users": total_users,
            "new_users_30d": new_users_30d,
            "total_credits": total_credits,
            "total_files": total_files
        }
    }

# ==================== ADMIN ROUTES ====================
@app.get("/admin", response_class=HTMLResponse)
@require_login
async def admin_dashboard(request: Request, user: dict):
    """Admin dashboard"""
    if not user['is_admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get stats
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE created_at >= DATE("now", "-30 days")')
    new_users_30d = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(credits) FROM users')
    total_credits = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM user_files')
    total_files = cursor.fetchone()[0]
    
    # Get recent users
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 10')
    recent_users = [dict(row) for row in cursor.fetchall()]
    
    # Get recent files
    cursor.execute('''
    SELECT uf.*, u.username 
    FROM user_files uf 
    JOIN users u ON uf.user_id = u.id 
    ORDER BY uf.created_at DESC 
    LIMIT 10
    ''')
    recent_files = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "user": user,
        "stats": {
            "total_users": total_users,
            "new_users_30d": new_users_30d,
            "total_credits": total_credits,
            "total_files": total_files
        },
        "recent_users": recent_users,
        "recent_files": recent_files
    })

# ==================== HEALTH CHECK ====================
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "available",
            "tts": "available",
            "stt": "available" if WHISPER_AVAILABLE and stt_processor.model else "unavailable"
        }
    }

# ==================== ERROR HANDLERS ====================
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    user = await auth.get_current_user(request.cookies.get("token"))
    return templates.TemplateResponse("errors/404.html", {
        "request": request,
        "user": user
    }, status_code=404)

@app.exception_handler(500)
async def internal_exception_handler(request: Request, exc: HTTPException):
    user = await auth.get_current_user(request.cookies.get("token"))
    return templates.TemplateResponse("errors/500.html", {
        "request": request,
        "user": user
    }, status_code=500)

# ==================== STARTUP ====================
@app.on_event("startup")
async def startup_event():
    """Startup tasks"""
    print("🚀 Starting TTSFree application...")
    
    # Clean temp directory
    for file in os.listdir("temp"):
        try:
            os.remove(os.path.join("temp", file))
        except:
            pass
    
    # Clean old files (older than 7 days)
    now = time.time()
    for root, dirs, files in os.walk("outputs"):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.getmtime(file_path) < now - 7 * 24 * 3600:
                try:
                    os.remove(file_path)
                except:
                    pass
    
    # Clean old uploads (older than 1 day)
    if os.path.exists("uploads"):
        for file in os.listdir("uploads"):
            file_path = os.path.join("uploads", file)
            if os.path.getmtime(file_path) < now - 24 * 3600:
                try:
                    os.remove(file_path)
                except:
                    pass
    
    print("✅ Startup cleanup completed")
    print(f"📊 Database: ttsfree.db")
    print(f"📁 Outputs: {os.path.abspath('outputs')}")
    print(f"🌐 TTS languages: {len(TTSConfig.LANGUAGES)}")
    print(f"🤖 STT available: {WHISPER_AVAILABLE and stt_processor.model is not None}")

# ==================== MAIN ====================
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    
    print(f"""
    ==========================================
    TTSFree - Text to Speech & Speech to Text
    ==========================================
    🚀 Running on: http://localhost:{port}
    👑 Admin: http://localhost:{port}/admin
    📚 API Docs: http://localhost:{port}/api/docs
    
    👤 Demo Credentials:
    Username: demo
    Password: demo123
    
    👑 Admin Credentials:
    Username: admin
    Password: admin123
    ==========================================
    """)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
