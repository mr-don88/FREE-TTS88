# app.py - Professional TTS Generator with User Management & Advanced Features
import asyncio
import json
import os
import random
import re
import time
import uuid
import zipfile
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks, Depends, Cookie
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import webvtt
import natsort
import uvicorn
import glob
import shutil
from concurrent.futures import ThreadPoolExecutor

# ==================== DATABASE SIMPLE (Using JSON files) ====================
class Database:
    def __init__(self):
        self.users_file = "users.json"
        self.sessions_file = "sessions.json"
        self.settings_file = "tts_settings.json"
        self.usage_file = "usage.json"
        self.init_db()
    
    def init_db(self):
        """Initialize database files"""
        for file_path in [self.users_file, self.sessions_file, self.settings_file, self.usage_file]:
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    if file_path == self.usage_file:
                        json.dump({}, f)
                    elif file_path == self.settings_file:
                        json.dump(self.get_default_settings(), f, indent=2)
                    else:
                        json.dump({}, f)
    
    def get_default_settings(self):
        """Get default TTS settings"""
        return {
            "single_voice": {
                "language": "Vietnamese",
                "voice": "vi-VN-HoaiMyNeural",
                "rate": 0,
                "pitch": 0,
                "volume": 100,
                "pause": 500
            },
            "multi_voice": {
                "char1": {
                    "language": "Vietnamese",
                    "voice": "vi-VN-HoaiMyNeural", 
                    "rate": 0, 
                    "pitch": 0, 
                    "volume": 100
                },
                "char2": {
                    "language": "Vietnamese",
                    "voice": "vi-VN-NamMinhNeural", 
                    "rate": -10, 
                    "pitch": 0, 
                    "volume": 100
                },
                "pause": 500,
                "repeat": 1
            },
            "qa_voice": {
                "question": {
                    "language": "Vietnamese",
                    "voice": "vi-VN-HoaiMyNeural", 
                    "rate": 0, 
                    "pitch": 0, 
                    "volume": 100
                },
                "answer": {
                    "language": "Vietnamese",
                    "voice": "vi-VN-NamMinhNeural", 
                    "rate": -10, 
                    "pitch": 0, 
                    "volume": 100
                },
                "pause_q": 200,
                "pause_a": 500,
                "repeat": 2
            }
        }
    
    def load_users(self):
        """Load users from file"""
        try:
            with open(self.users_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_users(self, users):
        """Save users to file"""
        with open(self.users_file, 'w') as f:
            json.dump(users, f, indent=2)
    
    def load_sessions(self):
        """Load sessions from file"""
        try:
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_sessions(self, sessions):
        """Save sessions to file"""
        with open(self.sessions_file, 'w') as f:
            json.dump(sessions, f, indent=2)
    
    def load_settings(self):
        """Load TTS settings from file"""
        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return self.get_default_settings()
    
    def save_settings(self, settings):
        """Save TTS settings to file"""
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    
    def load_usage(self):
        """Load usage data from file"""
        try:
            with open(self.usage_file, 'r') as f:
                return json.load(f)
        except:
            return {}
    
    def save_usage(self, usage):
        """Save usage data to file"""
        with open(self.usage_file, 'w') as f:
            json.dump(usage, f, indent=2)
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA256 with salt"""
        salt = "tts_system_2024"
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password) == hashed_password
    
    def create_user(self, username: str, password: str, email: str, full_name: str = ""):
        """Create new user"""
        users = self.load_users()
        
        if username in users:
            return False, "Username already exists"
        
        user_data = {
            "username": username,
            "password": self.hash_password(password),
            "email": email,
            "full_name": full_name,
            "role": "user",
            "created_at": datetime.now().isoformat(),
            "subscription": {
                "plan": "free",
                "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
                "characters_limit": 30000,
                "features": ["single"]
            },
            "usage": {
                "characters_used": 0,
                "last_reset": datetime.now().isoformat(),
                "total_requests": 0
            }
        }
        
        users[username] = user_data
        self.save_users(users)
        return True, "User created successfully"
    
    def authenticate_user(self, username: str, password: str):
        """Authenticate user"""
        users = self.load_users()
        
        if username not in users:
            return None
        
        user_data = users[username]
        if self.verify_password(password, user_data["password"]):
            return user_data
        return None
    
    def create_session(self, username: str) -> str:
        """Create session token"""
        sessions = self.load_sessions()
        session_token = secrets.token_urlsafe(32)
        
        session_data = {
            "username": username,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        
        sessions[session_token] = session_data
        self.save_sessions(sessions)
        return session_token
    
    def validate_session(self, session_token: str):
        """Validate session token"""
        sessions = self.load_sessions()
        
        if session_token not in sessions:
            return None
        
        session_data = sessions[session_token]
        # Check if session is expired (24 hours)
        created_at = datetime.fromisoformat(session_data["created_at"])
        if datetime.now() - created_at > timedelta(hours=24):
            del sessions[session_token]
            self.save_sessions(sessions)
            return None
        
        # Update last activity
        session_data["last_activity"] = datetime.now().isoformat()
        sessions[session_token] = session_data
        self.save_sessions(sessions)
        
        return session_data["username"]
    
    def delete_session(self, session_token: str):
        """Delete session"""
        sessions = self.load_sessions()
        if session_token in sessions:
            del sessions[session_token]
            self.save_sessions(sessions)
    
    def get_user(self, username: str):
        """Get user data"""
        users = self.load_users()
        return users.get(username)
    
    def update_user(self, username: str, user_data: dict):
        """Update user data"""
        users = self.load_users()
        if username in users:
            users[username] = user_data
            self.save_users(users)
            return True
        return False
    
    def record_usage(self, username: str, characters_used: int):
        """Record usage for user"""
        users = self.load_users()
        if username in users:
            user_data = users[username]
            
            # Reset weekly usage if needed
            last_reset = datetime.fromisoformat(user_data["usage"]["last_reset"])
            if datetime.now() - last_reset > timedelta(days=7):
                user_data["usage"]["characters_used"] = 0
                user_data["usage"]["last_reset"] = datetime.now().isoformat()
            
            # Update usage
            user_data["usage"]["characters_used"] += characters_used
            user_data["usage"]["total_requests"] += 1
            
            users[username] = user_data
            self.save_users(users)
            return True
        return False
    
    def can_user_use_feature(self, username: str, feature: str) -> Tuple[bool, str]:
        """Check if user can use a feature"""
        users = self.load_users()
        if username not in users:
            return False, "User not found"
        
        user_data = users[username]
        subscription = user_data["subscription"]
        
        # Check if feature is allowed in subscription
        if feature not in subscription["features"]:
            return False, f"Feature '{feature}' requires premium subscription"
        
        # Check weekly character limit for free tier
        if subscription["plan"] == "free":
            if user_data["usage"]["characters_used"] >= subscription["characters_limit"]:
                return False, "Weekly character limit reached. Please upgrade to premium."
        
        # Check if subscription is expired
        expires_at = datetime.fromisoformat(subscription["expires_at"])
        if datetime.now() > expires_at:
            return False, "Subscription expired. Please renew."
        
        return True, "Access granted"
    
    def get_all_users(self):
        """Get all users (admin only)"""
        return self.load_users()
    
    def update_subscription(self, username: str, plan: str, days: int = 30):
        """Update user subscription"""
        users = self.load_users()
        if username not in users:
            return False
        
        user_data = users[username]
        
        if plan == "free":
            features = ["single"]
            char_limit = 30000
        elif plan == "premium":
            features = ["single", "multi", "qa"]
            char_limit = 1000000
        elif plan == "pro":
            features = ["single", "multi", "qa", "unlimited"]
            char_limit = 10000000
        else:
            return False
        
        user_data["subscription"] = {
            "plan": plan,
            "expires_at": (datetime.now() + timedelta(days=days)).isoformat(),
            "characters_limit": char_limit,
            "features": features
        }
        
        users[username] = user_data
        self.save_users(users)
        return True
    
    def init_admin_user(self):
        """Initialize admin user if not exists"""
        users = self.load_users()
        if "admin" not in users:
            admin_user = {
                "username": "admin",
                "password": self.hash_password("admin123"),
                "email": "admin@tts.com",
                "full_name": "Administrator",
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "subscription": {
                    "plan": "pro",
                    "expires_at": (datetime.now() + timedelta(days=3650)).isoformat(),
                    "characters_limit": 10000000,
                    "features": ["single", "multi", "qa", "unlimited"]
                },
                "usage": {
                    "characters_used": 0,
                    "last_reset": datetime.now().isoformat(),
                    "total_requests": 0
                }
            }
            users["admin"] = admin_user
            self.save_users(users)
            print("Admin user created: admin / admin123")

# Initialize database
database = Database()
database.init_admin_user()

# ==================== AUTHENTICATION MIDDLEWARE ====================
async def get_current_user(request: Request):
    """Get current user from session"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    
    username = database.validate_session(session_token)
    if not username:
        return None
    
    return database.get_user(username)

async def require_login(request: Request):
    """Require user to be logged in"""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    return user

async def require_admin(request: Request):
    """Require admin privileges"""
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login")
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

# ==================== TTS CONFIGURATION ====================
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

        "Cantonese (zh-HK)": [
            {"name": "zh-HK-HiuGaaiNeural", "gender": "👩Female", "display": "曉佳"},
            {"name": "zh-HK-HiuMaanNeural", "gender": "👩Female", "display": "曉曼"},
            {"name": "zh-HK-WanLungNeural", "gender": "🤵Male", "display": "雲龍"}
        ],

        "Taiwanese (zh-TW)": [
            {"name": "zh-TW-HsiaoChenNeural", "gender": "👩Female", "display": "曉臻"},
            {"name": "zh-TW-YunJheNeural", "gender": "🤵Male", "display": "雲哲"},
            {"name": "zh-TW-HsiaoYuNeural", "gender": "👩Female", "display": "曉雨"}
        ],

        "Japanese": [
            {"name": "ja-JP-NanamiNeural", "gender": "👩Female", "display": "七海"},
            {"name": "ja-JP-KeitaNeural", "gender": "🤵Male", "display": "圭太"},
            {"name": "ja-JP-DaichiNeural", "gender": "🤵Male", "display": "大地"},
            {"name": "ja-JP-ShioriNeural", "gender": "👩Female", "display": "詩織"},
            {"name": "ja-JP-AoiNeural", "gender": "👩Female", "display": "葵"},
            {"name": "ja-JP-MayuNeural", "gender": "👩Female", "display": "繭"},
            {"name": "ja-JP-NaokiNeural", "gender": "🤵Male", "display": "直樹"}
        ],

        "Korean": [
            {"name": "ko-KR-SunHiNeural", "gender": "👩Female", "display": "선희"},
            {"name": "ko-KR-InJoonNeural", "gender": "🤵Male", "display": "인준"},
            {"name": "ko-KR-BongJinNeural", "gender": "🤵Male", "display": "봉진"},
            {"name": "ko-KR-GookMinNeural", "gender": "🤵Male", "display": "국민"},
            {"name": "ko-KR-JiMinNeural", "gender": "👩Female", "display": "지민"},
            {"name": "ko-KR-SeoHyeonNeural", "gender": "👩Female", "display": "서현"},
            {"name": "ko-KR-SoonBokNeural", "gender": "👩Female", "display": "순복"}
        ],

        "French (France)": [
            {"name": "fr-FR-DeniseNeural", "gender": "👩Female", "display": "Denise"},
            {"name": "fr-FR-HenriNeural", "gender": "🤵Male", "display": "Henri"},
            {"name": "fr-FR-AlainNeural", "gender": "🤵Male", "display": "Alain"},
            {"name": "fr-FR-JacquelineNeural", "gender": "👩Female", "display": "Jacqueline"},
            {"name": "fr-FR-ClaudeNeural", "gender": "🤵Male", "display": "Claude"},
            {"name": "fr-FR-CelesteNeural", "gender": "👩Female", "display": "Celeste"},
            {"name": "fr-FR-EloiseNeural", "gender": "👩Female", "display": "Eloise"}
        ],

        "French (Canada)": [
            {"name": "fr-CA-SylvieNeural", "gender": "👩Female", "display": "Sylvie"},
            {"name": "fr-CA-AntoineNeural", "gender": "🤵Male", "display": "Antoine"},
            {"name": "fr-CA-JeanNeural", "gender": "🤵Male", "display": "Jean"}
        ],

        "Spanish (Spain)": [
            {"name": "es-ES-AlvaroNeural", "gender": "🤵Male", "display": "Álvaro"},
            {"name": "es-ES-ElviraNeural", "gender": "👩Female", "display": "Elvira"},
            {"name": "es-ES-AbrilNeural", "gender": "👩Female", "display": "Abril"},
            {"name": "es-ES-ManuelNeural", "gender": "🤵Male", "display": "Manuel"},
            {"name": "es-ES-TrianaNeural", "gender": "👩Female", "display": "Triana"},
            {"name": "es-ES-LiaNeural", "gender": "👩Female", "display": "Lia"}
        ],

        "Spanish (Mexico)": [
            {"name": "es-MX-DaliaNeural", "gender": "👩Female", "display": "Dalia"},
            {"name": "es-MX-JorgeNeural", "gender": "🤵Male", "display": "Jorge"},
            {"name": "es-MX-BeatrizNeural", "gender": "👩Female", "display": "Beatriz"},
            {"name": "es-MX-CandelaNeural", "gender": "👩Female", "display": "Candela"},
            {"name": "es-MX-CarlotaNeural", "gender": "👩Female", "display": "Carlota"},
            {"name": "es-MX-CecilioNeural", "gender": "🤵Male", "display": "Cecilio"}
        ],

        "Spanish (Colombia)": [
            {"name": "es-CO-SalomeNeural", "gender": "👩Female", "display": "Salome"},
            {"name": "es-CO-GonzaloNeural", "gender": "🤵Male", "display": "Gonzalo"}
        ],

        "German": [
            {"name": "de-DE-KatjaNeural", "gender": "👩Female", "display": "Katja"},
            {"name": "de-DE-ConradNeural", "gender": "🤵Male", "display": "Conrad"},
            {"name": "de-DE-AmalaNeural", "gender": "👩Female", "display": "Amala"},
            {"name": "de-DE-BerndNeural", "gender": "🤵Male", "display": "Bernd"},
            {"name": "de-DE-ChristophNeural", "gender": "🤵Male", "display": "Christoph"},
            {"name": "de-DE-LouisaNeural", "gender": "👩Female", "display": "Louisa"},
            {"name": "de-DE-MajaNeural", "gender": "👩Female", "display": "Maja"}
        ],

        "Italian": [
            {"name": "it-IT-IsabellaNeural", "gender": "👩Female", "display": "Isabella"},
            {"name": "it-IT-DiegoNeural", "gender": "🤵Male", "display": "Diego"},
            {"name": "it-IT-BenignoNeural", "gender": "🤵Male", "display": "Benigno"},
            {"name": "it-IT-PalmiraNeural", "gender": "👩Female", "display": "Palmira"},
            {"name": "it-IT-CalimeroNeural", "gender": "🤵Male", "display": "Calimero"},
            {"name": "it-IT-CataldoNeural", "gender": "🤵Male", "display": "Cataldo"},
            {"name": "it-IT-ElsaNeural", "gender": "👩Female", "display": "Elsa"}
        ],

        "Portuguese (Brazil)": [
            {"name": "pt-BR-FranciscaNeural", "gender": "👩Female", "display": "Francisca"},
            {"name": "pt-BR-AntonioNeural", "gender": "🤵Male", "display": "Antônio"},
            {"name": "pt-BR-BrendaNeural", "gender": "👩Female", "display": "Brenda"},
            {"name": "pt-BR-DonatoNeural", "gender": "🤵Male", "display": "Donato"},
            {"name": "pt-BR-ElzaNeural", "gender": "👩Female", "display": "Elza"},
            {"name": "pt-BR-FabioNeural", "gender": "🤵Male", "display": "Fabio"}
        ],

        "Portuguese (Portugal)": [
            {"name": "pt-PT-DuarteNeural", "gender": "🤵Male", "display": "Duarte"},
            {"name": "pt-PT-RaquelNeural", "gender": "👩Female", "display": "Raquel"},
            {"name": "pt-PT-FernandaNeural", "gender": "👩Female", "display": "Fernanda"}
        ],

        "Russian": [
            {"name": "ru-RU-SvetlanaNeural", "gender": "👩Female", "display": "Светлана"},
            {"name": "ru-RU-DmitryNeural", "gender": "🤵Male", "display": "Дмитрий"},
            {"name": "ru-RU-DariyaNeural", "gender": "👩Female", "display": "Дария"},
            {"name": "ru-RU-AlexanderNeural", "gender": "🤵Male", "display": "Александр"}
        ],

        "Arabic (Saudi Arabia)": [
            {"name": "ar-SA-ZariyahNeural", "gender": "👩Female", "display": "زارية"},
            {"name": "ar-SA-HamedNeural", "gender": "🤵Male", "display": "حامد"}
        ],

        "Arabic (Egypt)": [
            {"name": "ar-EG-SalmaNeural", "gender": "👩Female", "display": "سلمى"},
            {"name": "ar-EG-ShakirNeural", "gender": "🤵Male", "display": "شاكر"}
        ],

        "Arabic (UAE)": [
            {"name": "ar-AE-FatimaNeural", "gender": "👩Female", "display": "فاطمة"},
            {"name": "ar-AE-HamdanNeural", "gender": "🤵Male", "display": "حمدان"}
        ],

        "Dutch": [
            {"name": "nl-NL-ColetteNeural", "gender": "👩Female", "display": "Colette"},
            {"name": "nl-NL-FennaNeural", "gender": "👩Female", "display": "Fenna"},
            {"name": "nl-NL-MaartenNeural", "gender": "🤵Male", "display": "Maarten"},
            {"name": "nl-BE-ArnaudNeural", "gender": "🤵Male", "display": "Arnaud"},
            {"name": "nl-BE-DenaNeural", "gender": "👩Female", "display": "Dena"}
        ],

        "Polish": [
            {"name": "pl-PL-AgnieszkaNeural", "gender": "👩Female", "display": "Agnieszka"},
            {"name": "pl-PL-MarekNeural", "gender": "🤵Male", "display": "Marek"},
            {"name": "pl-PL-ZofiaNeural", "gender": "👩Female", "display": "Zofia"}
        ],

        "Turkish": [
            {"name": "tr-TR-AhmetNeural", "gender": "🤵Male", "display": "Ahmet"},
            {"name": "tr-TR-EmelNeural", "gender": "👩Female", "display": "Emel"},
            {"name": "tr-TR-FatmaNeural", "gender": "👩Female", "display": "Fatma"}
        ],

        "Thai": [
            {"name": "th-TH-PremwadeeNeural", "gender": "👩Female", "display": "เปรมวดี"},
            {"name": "th-TH-NiwatNeural", "gender": "🤵Male", "display": "นิวัฒน์"},
            {"name": "th-TH-AcharaNeural", "gender": "👩Female", "display": "อัจฉรา"}
        ],

        "Hindi": [
            {"name": "hi-IN-MadhurNeural", "gender": "🤵Male", "display": "मधुर"},
            {"name": "hi-IN-SwaraNeural", "gender": "👩Female", "display": "स्वरा"},
            {"name": "hi-IN-KiranNeural", "gender": "👩Female", "display": "किरण"}
        ],

        "Swedish": [
            {"name": "sv-SE-HilleviNeural", "gender": "👩Female", "display": "Hillevi"},
            {"name": "sv-SE-MattiasNeural", "gender": "🤵Male", "display": "Mattias"},
            {"name": "sv-SE-SofieNeural", "gender": "👩Female", "display": "Sofie"}
        ],

        "Norwegian": [
            {"name": "nb-NO-PernilleNeural", "gender": "👩Female", "display": "Pernille"},
            {"name": "nb-NO-FinnNeural", "gender": "🤵Male", "display": "Finn"},
            {"name": "nb-NO-IsleneNeural", "gender": "👩Female", "display": "Islene"}
        ],

        "Danish": [
            {"name": "da-DK-ChristelNeural", "gender": "👩Female", "display": "Christel"},
            {"name": "da-DK-JeppeNeural", "gender": "🤵Male", "display": "Jeppe"}
        ],

        "Finnish": [
            {"name": "fi-FI-NooraNeural", "gender": "👩Female", "display": "Noora"},
            {"name": "fi-FI-SelmaNeural", "gender": "👩Female", "display": "Selma"},
            {"name": "fi-FI-HarriNeural", "gender": "🤵Male", "display": "Harri"}
        ],

        "Czech": [
            {"name": "cs-CZ-VlastaNeural", "gender": "👩Female", "display": "Vlasta"},
            {"name": "cs-CZ-AntoninNeural", "gender": "🤵Male", "display": "Antonín"}
        ],

        "Greek": [
            {"name": "el-GR-AthinaNeural", "gender": "👩Female", "display": "Αθηνά"},
            {"name": "el-GR-NestorasNeural", "gender": "🤵Male", "display": "Νέστορας"}
        ],

        "Hebrew": [
            {"name": "he-IL-HilaNeural", "gender": "👩Female", "display": "הילה"},
            {"name": "he-IL-AvriNeural", "gender": "🤵Male", "display": "אברי"}
        ],

        "Indonesian": [
            {"name": "id-ID-GadisNeural", "gender": "👩Female", "display": "Gadis"},
            {"name": "id-ID-ArdiNeural", "gender": "🤵Male", "display": "Ardi"}
        ],

        "Malay": [
            {"name": "ms-MY-YasminNeural", "gender": "👩Female", "display": "Yasmin"},
            {"name": "ms-MY-OsmanNeural", "gender": "🤵Male", "display": "Osman"}
        ],

        "Filipino": [
            {"name": "fil-PH-BlessicaNeural", "gender": "👩Female", "display": "Blessica"},
            {"name": "fil-PH-AngeloNeural", "gender": "🤵Male", "display": "Angelo"}
        ],

        "Ukrainian": [
            {"name": "uk-UA-PolinaNeural", "gender": "👩Female", "display": "Поліна"},
            {"name": "uk-UA-OstapNeural", "gender": "🤵Male", "display": "Остап"}
        ],

        "Romanian": [
            {"name": "ro-RO-AlinaNeural", "gender": "👩Female", "display": "Alina"},
            {"name": "ro-RO-EmilNeural", "gender": "🤵Male", "display": "Emil"}
        ],

        "Hungarian": [
            {"name": "hu-HU-NoemiNeural", "gender": "👩Female", "display": "Noémi"},
            {"name": "hu-HU-TamasNeural", "gender": "🤵Male", "display": "Tamás"}
        ],

        "Bulgarian": [
            {"name": "bg-BG-KalinaNeural", "gender": "👩Female", "display": "Калина"},
            {"name": "bg-BG-BorislavNeural", "gender": "🤵Male", "display": "Борислав"}
        ],

        "Croatian": [
            {"name": "hr-HR-GabrijelaNeural", "gender": "👩Female", "display": "Gabrijela"},
            {"name": "hr-HR-SreckoNeural", "gender": "🤵Male", "display": "Srećko"}
        ],

        "Slovak": [
            {"name": "sk-SK-ViktoriaNeural", "gender": "👩Female", "display": "Viktória"},
            {"name": "sk-SK-LukasNeural", "gender": "🤵Male", "display": "Lukáš"}
        ],

        "Slovenian": [
            {"name": "sl-SI-PetraNeural", "gender": "👩Female", "display": "Petra"},
            {"name": "sl-SI-RokNeural", "gender": "🤵Male", "display": "Rok"}
        ],

        "Serbian": [
            {"name": "sr-RS-NicholasNeural", "gender": "🤵Male", "display": "Nicholas"},
            {"name": "sr-RS-SophieNeural", "gender": "👩Female", "display": "Sophie"}
        ],

        "Catalan": [
            {"name": "ca-ES-JoanaNeural", "gender": "👩Female", "display": "Joana"},
            {"name": "ca-ES-AlbaNeural", "gender": "👩Female", "display": "Alba"},
            {"name": "ca-ES-EnricNeural", "gender": "🤵Male", "display": "Enric"}
        ],

        "Estonian": [
            {"name": "et-EE-AnuNeural", "gender": "👩Female", "display": "Anu"},
            {"name": "et-EE-KertNeural", "gender": "🤵Male", "display": "Kert"}
        ],

        "Latvian": [
            {"name": "lv-LV-EveritaNeural", "gender": "👩Female", "display": "Everita"},
            {"name": "lv-LV-NilsNeural", "gender": "🤵Male", "display": "Nils"}
        ],

        "Lithuanian": [
            {"name": "lt-LT-OnaNeural", "gender": "👩Female", "display": "Ona"},
            {"name": "lt-LT-LeonasNeural", "gender": "🤵Male", "display": "Leonas"}
        ],

        "Maltese": [
            {"name": "mt-MT-GraceNeural", "gender": "👩Female", "display": "Grace"},
            {"name": "mt-MT-JosephNeural", "gender": "🤵Male", "display": "Joseph"}
        ],

        "Welsh": [
            {"name": "cy-GB-NiaNeural", "gender": "👩Female", "display": "Nia"},
            {"name": "cy-GB-AledNeural", "gender": "🤵Male", "display": "Aled"}
        ],

        "Icelandic": [
            {"name": "is-IS-GudrunNeural", "gender": "👩Female", "display": "Guðrún"},
            {"name": "is-IS-GunnarNeural", "gender": "🤵Male", "display": "Gunnar"}
        ],

        "Irish": [
            {"name": "ga-IE-OrlaNeural", "gender": "👩Female", "display": "Orla"},
            {"name": "ga-IE-ColmNeural", "gender": "🤵Male", "display": "Colm"}
        ],

        "Albanian": [
            {"name": "sq-AL-AnilaNeural", "gender": "👩Female", "display": "Anila"},
            {"name": "sq-AL-IlirNeural", "gender": "🤵Male", "display": "Ilir"}
        ],

        "Armenian": [
            {"name": "hy-AM-AnahitNeural", "gender": "👩Female", "display": "Անահիտ"},
            {"name": "hy-AM-HaykNeural", "gender": "🤵Male", "display": "Հայկ"}
        ],

        "Azerbaijani": [
            {"name": "az-AZ-BanuNeural", "gender": "👩Female", "display": "Banu"},
            {"name": "az-AZ-BabekNeural", "gender": "🤵Male", "display": "Babək"}
        ],

        "Bengali": [
            {"name": "bn-BD-NabanitaNeural", "gender": "👩Female", "display": "নবনীতা"},
            {"name": "bn-BD-PradeepNeural", "gender": "🤵Male", "display": "প্রদীপ"}
        ],

        "Georgian": [
            {"name": "ka-GE-EkaNeural", "gender": "👩Female", "display": "ეკა"},
            {"name": "ka-GE-GiorgiNeural", "gender": "🤵Male", "display": "გიორგი"}
        ],

        "Kazakh": [
            {"name": "kk-KZ-AigulNeural", "gender": "👩Female", "display": "Айгүл"},
            {"name": "kk-KZ-DauletNeural", "gender": "🤵Male", "display": "Дәулет"}
        ],

        "Khmer": [
            {"name": "km-KH-SreymomNeural", "gender": "👩Female", "display": "ស្រីមុំ"},
            {"name": "km-KH-PisethNeural", "gender": "🤵Male", "display": "ពិសិដ្ឋ"}
        ],

        "Lao": [
            {"name": "lo-LA-KeomanyNeural", "gender": "👩Female", "display": "ແກ້ວມະນີ"},
            {"name": "lo-LA-ChanthavongNeural", "gender": "🤵Male", "display": "ຈັນທະວົງ"}
        ],

        "Mongolian": [
            {"name": "mn-MN-YesuiNeural", "gender": "👩Female", "display": "Есүй"},
            {"name": "mn-MN-BataaNeural", "gender": "🤵Male", "display": "Батаа"}
        ],

        "Nepali": [
            {"name": "ne-NP-HemkalaNeural", "gender": "👩Female", "display": "हेमकला"},
            {"name": "ne-NP-SagarNeural", "gender": "🤵Male", "display": "सागर"}
        ],

        "Sinhala": [
            {"name": "si-LK-ThiliniNeural", "gender": "👩Female", "display": "තිලිනි"},
            {"name": "si-LK-SameeraNeural", "gender": "🤵Male", "display": "සමීර"}
        ],

        "Tamil": [
            {"name": "ta-IN-PallaviNeural", "gender": "👩Female", "display": "பல்லவி"},
            {"name": "ta-IN-ValluvarNeural", "gender": "🤵Male", "display": "வள்ளுவர்"}
        ],

        "Telugu": [
            {"name": "te-IN-ShrutiNeural", "gender": "👩Female", "display": "శ్రుతి"},
            {"name": "te-IN-MohanNeural", "gender": "🤵Male", "display": "మోహన్"}
        ],

        "Urdu": [
            {"name": "ur-PK-UzmaNeural", "gender": "👩Female", "display": "عظمیٰ"},
            {"name": "ur-PK-AsadNeural", "gender": "🤵Male", "display": "اسد"}
        ],

        "Persian": [
            {"name": "fa-IR-DilaraNeural", "gender": "👩Female", "display": "دلارا"},
            {"name": "fa-IR-FaridNeural", "gender": "🤵Male", "display": "فرید"}
        ],

        "Afrikaans": [
            {"name": "af-ZA-AdriNeural", "gender": "👩Female", "display": "Adri"},
            {"name": "af-ZA-WillemNeural", "gender": "🤵Male", "display": "Willem"}
        ],

        "Swahili": [
            {"name": "sw-KE-ZuriNeural", "gender": "👩Female", "display": "Zuri"},
            {"name": "sw-KE-RafikiNeural", "gender": "🤵Male", "display": "Rafiki"}
        ],

        "Yoruba": [
            {"name": "yo-NG-AdeolaNeural", "gender": "👩Female", "display": "Adeola"},
            {"name": "yo-NG-AremuNeural", "gender": "🤵Male", "display": "Aremu"}
        ],

        "Zulu": [
            {"name": "zu-ZA-ThandoNeural", "gender": "👩Female", "display": "Thando"},
            {"name": "zu-ZA-ThembaNeural", "gender": "🤵Male", "display": "Themba"}
        ],

        "Hausa": [
            {"name": "ha-NG-AishaNeural", "gender": "👩Female", "display": "Aisha"},
            {"name": "ha-NG-AbdullahiNeural", "gender": "🤵Male", "display": "Abdullahi"}
        ],

        "Igbo": [
            {"name": "ig-NG-EbeleNeural", "gender": "👩Female", "display": "Ebele"},
            {"name": "ig-NG-ChineduNeural", "gender": "🤵Male", "display": "Chinedu"}
        ],

        "Somali": [
            {"name": "so-SO-UbaxNeural", "gender": "👩Female", "display": "Ubax"},
            {"name": "so-SO-MuuseNeural", "gender": "🤵Male", "display": "Muuse"}
        ]
    }
    
    OUTPUT_FORMATS = ["mp3", "wav"]
    
    # Subscription plans
    SUBSCRIPTION_PLANS = {
        "free": {
            "name": "Free",
            "price": "$0",
            "characters_per_week": 30000,
            "features": ["Single Voice TTS", "Basic Audio Effects", "30000 characters/week"],
            "limitations": ["No Multi-Voice", "No Q&A Dialogue", "Weekly limit"]
        },
        "premium": {
            "name": "Premium",
            "price": "$9.99/month",
            "characters_per_month": 1000000,
            "features": ["All Voices", "Multi-Voice TTS", "Q&A Dialogue", "1M characters/month"],
            "limitations": ["Monthly subscription"]
        },
        "pro": {
            "name": "Pro",
            "price": "$29.99/month",
            "characters_per_month": "Unlimited",
            "features": ["Unlimited Characters", "All Features", "Priority Support"],
            "limitations": []
        }
    }
    
    # Default pause settings (in milliseconds)
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
    
    def create_task(self, task_id: str, task_type: str, username: str):
        self.tasks[task_id] = {
            "id": task_id,
            "type": task_type,
            "username": username,
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
    
    def get_user_tasks(self, username: str):
        """Get all tasks for a specific user"""
        user_tasks = {}
        for task_id, task_data in self.tasks.items():
            if task_data.get("username") == username:
                user_tasks[task_id] = task_data
        return user_tasks
    
    def cleanup_old_tasks(self, hours_old: int = 1):
        """Cleanup tasks older than specified hours"""
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
    def count_characters(text: str) -> int:
        """Count characters in text (excluding spaces)"""
        return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean text"""
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
    
    @staticmethod
    def _process_special_cases(text: str) -> str:
        """Pipeline xử lý đặc biệt với thứ tự tối ưu"""
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
        """Process emails with correct English pronunciation"""
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
        """Process websites with correct English pronunciation"""
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
    def _process_temperatures(text: str) -> str:
        """Process temperatures and cardinal directions"""
        def temp_to_words(temp, unit):
            temp_text = TextProcessor._number_to_words(temp)
            unit = unit.upper() if unit else ''
            
            unit_map = {
                'C': 'degrees Celsius',
                'F': 'degrees Fahrenheit',
                'N': 'degrees north',
                'S': 'degrees south',
                'E': 'degrees east', 
                'W': 'degrees west',
                '': 'degrees'
            }
            unit_text = unit_map.get(unit, f'degrees {unit}')
            
            return f"{temp_text} {unit_text}"
        
        text = re.sub(
            r'(-?\d+)°([NSEWCFnsewcf]?)',
            lambda m: temp_to_words(m.group(1), m.group(2)),
            text,
            flags=re.IGNORECASE
        )
        
        text = re.sub(r'°', ' degrees ', text)
        return text

    @staticmethod
    def _process_measurements(text: str) -> str:
        """Xử lý đơn vị đo lường"""
        units_map = {
            'km/h': 'kilometers per hour',
            'mph': 'miles per hour',
            'kg': 'kilograms',
            'g': 'grams',
            'cm': 'centimeters',
            'm': 'meter',
            'mm': 'millimeters',
            'L': 'liter',
            'l': 'liter',
            'ml': 'milliliter',
            'mL': 'milliliter',
            'h': 'hour',
            'min': 'minute',
            's': 'second'
        }
    
        plural_units = {'L', 'l', 'mL', 'ml'}
    
        def measurement_to_words(value, unit):
            try:
                unit_lower = unit.lower()
                unit_text = units_map.get(unit, units_map.get(unit_lower, unit))
    
                if '.' in value:
                    integer, decimal = value.split('.')
                    value_text = (
                        f"{TextProcessor._number_to_words(integer)} "
                        f"point {' '.join(TextProcessor._digit_to_word(d) for d in decimal)}"
                    )
                else:
                    value_text = TextProcessor._number_to_words(value)
    
                if float(value) != 1 and unit in units_map and unit not in plural_units:
                    unit_text += 's'
    
                return f"{value_text} {unit_text}"
            except:
                return f"{value}{unit}"
    
        text = re.sub(
            r'(-?\d+\.?\d*)\s*({})s?\b'.format('|'.join(re.escape(key) for key in units_map.keys())),
            lambda m: measurement_to_words(m.group(1), m.group(2)),
            text,
            flags=re.IGNORECASE
        )
        return text
    
    @staticmethod
    def _process_currency(text: str) -> str:
        """Xử lý tiền tệ"""
        currency_map = {
            '$': 'dollars',
            '€': 'euros',
            '£': 'pounds',
            '¥': 'yen',
            '₩': 'won',
            '₽': 'rubles'
        }
    
        def currency_to_words(value, symbol):
            if value.endswith('.'):
                value = value[:-1]
                return f"{TextProcessor._number_to_words(value)} {currency_map.get(symbol, '')}."
    
            if '.' in value:
                integer_part, decimal_part = value.split('.')
                decimal_part = decimal_part.ljust(2, '0')
                return (
                    f"{TextProcessor._number_to_words(integer_part)} {currency_map.get(symbol, '')} "
                    f"and {TextProcessor._number_to_words(decimal_part)} cents"
                )
    
            return f"{TextProcessor._number_to_words(value)} {currency_map.get(symbol, '')}"
    
        text = re.sub(
            r'([$€£¥₩₽])(\d+(?:\.\d+)?)(?=\s|$|\.|,|;)',
            lambda m: currency_to_words(m.group(2), m.group(1)),
            text
        )
    
        return text

    @staticmethod
    def _process_percentages(text: str) -> str:
        """Xử lý phần trăm"""
        text = re.sub(
            r'(\d+\.?\d*)%',
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} percent",
            text
        )
        return text

    @staticmethod
    def _process_math_operations(text: str) -> str:
        """Xử lý các phép toán và khoảng số"""
        math_map = {
            '+': 'plus',
            '-': 'minus',
            '×': 'times',
            '*': 'times',
            '÷': 'divided by',
            '/': 'divided by',
            '=': 'equals',
            '>': 'is greater than',
            '<': 'is less than'
        }
    
        text = re.sub(
            r'(\d+)\s*-\s*(\d+)(?!\s*[=+×*÷/><])',
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} to {TextProcessor._number_to_words(m.group(2))}",
            text
        )
    
        text = re.sub(
            r'(\d+)\s*-\s*(\d+)(?=\s*[=+×*÷/><])',
            lambda m: f"{TextProcessor._number_to_words(m.group(1))} minus {TextProcessor._number_to_words(m.group(2))}",
            text
        )
    
        text = re.sub(
            r'(\d+)\s*([+×*÷/=><])\s*(\d+)',
            lambda m: (f"{TextProcessor._number_to_words(m.group(1))} "
                      f"{math_map.get(m.group(2), m.group(2))} "
                      f"{TextProcessor._number_to_words(m.group(3))}"),
            text
        )
    
        text = re.sub(
            r'(\d+)/(\d+)',
            lambda m: (f"{TextProcessor._number_to_words(m.group(1))} "
                      f"divided by {TextProcessor._number_to_words(m.group(2))}"),
            text
        )
    
        return text

    @staticmethod
    def _process_special_symbols(text: str) -> str:
        """Xử lý các ký hiệu đặc biệt"""
        symbol_map = {
            '@': 'at',
            '#': 'number',
            '&': 'and',
            '_': 'underscore'
        }

        text = re.sub(
            r'@(\w+)',
            lambda m: f"at {m.group(1)}",
            text
        )

        text = re.sub(
            r'#(\d+)',
            lambda m: f"number {TextProcessor._number_to_words(m.group(1))}",
            text
        )

        for symbol, replacement in symbol_map.items():
            text = text.replace(symbol, f' {replacement} ')

        return text

    @staticmethod
    def _process_times(text: str) -> str:
        """Xử lý thời gian"""
        text = re.sub(
            r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM|am|pm)?\b',
            lambda m: TextProcessor._time_to_words(m.group(1), m.group(2), m.group(3), m.group(4)),
            text
        )
        return text
    
    @staticmethod
    def _time_to_words(hour: str, minute: str, second: str = None, period: str = None) -> str:
        hour_int = int(hour)
        minute_int = int(minute)
        
        period_text = f" {period.upper()}" if period else ""
        hour_12 = hour_int % 12
        hour_text = "twelve" if hour_12 == 0 else TextProcessor._number_to_words(str(hour_12))
        
        minute_text = " \u200Bo'clock\u200B " if minute_int == 0 else \
                     f"oh {TextProcessor._number_to_words(minute)}" if minute_int < 10 else \
                     TextProcessor._number_to_words(minute)
        
        second_text = ""
        if second and int(second) > 0:
            second_text = f" and {TextProcessor._number_to_words(second)} seconds"
        
        if minute_int == 0 and not second_text:
            return f"{hour_text}{minute_text}{period_text}"
        else:
            return f"{hour_text} {minute_text}{second_text}{period_text}"

    @staticmethod
    def _process_years(text: str) -> str:
        """Xử lý các năm"""
        text = re.sub(
            r'\b(1[0-9]{3}|2[0-9]{3})\b',
            lambda m: TextProcessor._year_to_words(m.group(1)),
            text
        )
    
        text = re.sub(
            r'\b([0-9]{2})\b',
            lambda m: TextProcessor._two_digit_year_to_words(m.group(1)),
            text
        )
    
        return text

    @staticmethod
    def _year_to_words(year: str) -> str:
        if len(year) != 4:
            return year
    
        if year.startswith('20'):
            return f"twenty {TextProcessor._two_digit_year_to_words(year[2:])}"
    
        return TextProcessor._number_to_words(year)

    @staticmethod
    def _two_digit_year_to_words(num: str) -> str:
        if len(num) != 2:
            return num
    
        num_int = int(num)
        if num_int == 0:
            return "zero zero"
        if num_int < 10:
            return f"oh {TextProcessor._digit_to_word(num[1])}"
    
        ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
                'seventeen', 'eighteen', 'nineteen']
        tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 
               'eighty', 'ninety']
    
        if num_int < 20:
            return ones[num_int]
    
        ten, one = divmod(num_int, 10)
        if one == 0:
            return tens[ten]
        return f"{tens[ten]} {ones[one]}"        

    @staticmethod
    def _process_phone_numbers(text: str) -> str:
        """Xử lý số điện thoại"""
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

    @staticmethod
    def parse_dialogues(text: str, prefixes: List[str]) -> List[Tuple[str, str]]:
        """Phân tích nội dung hội thoại với các prefix chỉ định"""
        dialogues = []
        current = None
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            found_prefix = None
            for prefix in prefixes:
                if line.lower().startswith(prefix.lower() + ':'):
                    found_prefix = prefix
                    break
                    
            if found_prefix:
                if current:
                    processed_content = TextProcessor._process_special_cases(current[1])
                    dialogues.append((current[0], processed_content))
                
                speaker = found_prefix
                content = line[len(found_prefix)+1:].strip()
                current = (speaker, content)
            elif current:
                current = (current[0], current[1] + ' ' + line)
                
        if current:
            processed_content = TextProcessor._process_special_cases(current[1])
            dialogues.append((current[0], processed_content))
            
        return dialogues

# ==================== AUDIO CACHE MANAGER ====================
class AudioCacheManager:
    def __init__(self):
        self.cache_dir = "audio_cache"
        self.max_cache_size = 50
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_cache_key(self, text: str, voice_id: str, rate: int, pitch: int, volume: int) -> str:
        """Tạo cache key từ các tham số"""
        import hashlib
        key_string = f"{text}_{voice_id}_{rate}_{pitch}_{volume}"
        return hashlib.md5(key_string.encode()).hexdigest()[:12]
    
    def get_cached_audio(self, cache_key: str) -> Optional[str]:
        """Lấy file audio từ cache nếu tồn tại"""
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        if os.path.exists(cache_file):
            # Kiểm tra thời gian cache (không quá 1 ngày)
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 86400:  # 24 giờ
                return cache_file
        return None
    
    def save_to_cache(self, cache_key: str, audio_file: str):
        """Lưu audio vào cache"""
        try:
            # Giới hạn số file trong cache
            cache_files = os.listdir(self.cache_dir)
            if len(cache_files) >= self.max_cache_size:
                # Xóa file cũ nhất
                oldest_file = min(
                    [os.path.join(self.cache_dir, f) for f in cache_files],
                    key=os.path.getmtime
                )
                try:
                    os.remove(oldest_file)
                except:
                    pass
            
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
            shutil.copy(audio_file, cache_file)
            return cache_file
        except Exception as e:
            print(f"Error saving to cache: {e}")
            return None
    
    def clear_cache(self):
        """Xóa toàn bộ cache"""
        try:
            if os.path.exists(self.cache_dir):
                shutil.rmtree(self.cache_dir)
            os.makedirs(self.cache_dir, exist_ok=True)
            return True
        except Exception as e:
            print(f"Error clearing cache: {e}")
            return False

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.cache_manager = AudioCacheManager()
        self.settings = database.load_settings()
        self.initialize_directories()
    
    def initialize_directories(self):
        """Khởi tạo các thư mục cần thiết"""
        directories = ["outputs", "temp", "audio_cache", "static", "templates"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def load_settings(self):
        self.settings = database.load_settings()
    
    def save_settings(self):
        database.save_settings(self.settings)
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, pitch: int = 0, volume: int = 100, task_id: str = None):
        """Generate speech using edge-tts with cache optimization"""
        try:
            # Kiểm tra cache trước
            cache_key = self.cache_manager.get_cache_key(text, voice_id, rate, pitch, volume)
            cached_file = self.cache_manager.get_cached_audio(cache_key)
            
            if cached_file:
                # Tạo file tạm từ cache
                temp_file = f"temp/cache_{uuid.uuid4().hex[:8]}.mp3"
                shutil.copy(cached_file, temp_file)
                return temp_file, []
            
            # Tạo unique ID để tránh cache
            unique_id = uuid.uuid4().hex[:8]
            
            # Format parameters
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"+{pitch}Hz" if pitch >= 0 else f"{pitch}Hz"
            
            # Tạo communicate object
            communicate = edge_tts.Communicate(
                text, 
                voice_id, 
                rate=rate_str, 
                pitch=pitch_str
            )
            
            audio_chunks = []
            subtitles = []
            
            # Stream audio data
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
            
            # Lưu audio vào file tạm
            audio_data = b"".join(audio_chunks)
            temp_file = f"temp/audio_{unique_id}_{int(time.time())}.mp3"
            
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Xử lý audio
            try:
                audio = AudioSegment.from_file(temp_file)
                
                # Điều chỉnh volume
                volume_adjustment = min(max(volume - 100, -50), 10)
                audio = audio + volume_adjustment
                
                # Áp dụng các hiệu ứng audio cơ bản
                audio = normalize(audio)
                audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
                
                # Xuất với chất lượng cao
                audio.export(temp_file, format="mp3", bitrate="256k")
                
                # Lưu vào cache
                self.cache_manager.save_to_cache(cache_key, temp_file)
                
                return temp_file, subtitles
            except Exception as e:
                print(f"Error processing audio: {e}")
                # Trả về file gốc nếu xử lý lỗi
                return temp_file, subtitles
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None, []
    
    def generate_srt(self, subtitles: List[dict], output_path: str):
        """Generate SRT file from subtitles"""
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
                                 volume: int, pause: int, output_format: str = "mp3", task_id: str = None, username: str = None):
        """Process text with single voice - Optimized version"""
        # Xóa cache và file cũ trước khi bắt đầu
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/{username}/single_{timestamp}" if username else f"outputs/single_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Count characters for usage tracking
        characters_used = TextProcessor.count_characters(text)
        
        # Xử lý text
        sentences = self.text_processor.split_sentences(text)
        
        # Giới hạn số lượng câu để xử lý nhanh hơn
        MAX_SENTENCES = 50
        if len(sentences) > MAX_SENTENCES:
            sentences = sentences[:MAX_SENTENCES]
            print(f"Processing {MAX_SENTENCES} sentences only for performance")
        
        # Tạo semaphore để giới hạn concurrent requests
        SEMAPHORE = asyncio.Semaphore(2)
        
        async def bounded_generate(sentence, index):
            async with SEMAPHORE:
                # Cập nhật progress nếu có task_id
                if task_id and task_manager:
                    progress = int((index / len(sentences)) * 90)
                    task_manager.update_task(task_id, progress=progress, 
                                           message=f"Processing sentence {index+1}/{len(sentences)}")
                
                return await self.generate_speech(sentence, voice_id, rate, pitch, volume)
        
        # Xử lý các câu theo batch
        audio_segments = []
        all_subtitles = []
        
        for i in range(0, len(sentences), 2):  # Batch size = 2
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
                            
                            # Điều chỉnh thời gian cho subtitles
                            current_time = sum(len(a) for a in audio_segments[:-1])
                            for sub in subs:
                                if isinstance(sub, dict):
                                    sub["start"] += current_time
                                    sub["end"] += current_time
                                    all_subtitles.append(sub)
                            
                            # Xóa file tạm ngay
                            try:
                                os.remove(temp_file)
                            except:
                                pass
                        except Exception as e:
                            print(f"Error processing audio segment: {e}")
        
        if not audio_segments:
            return None, None, characters_used
        
        # Kết hợp các audio segment với pause
        combined = AudioSegment.empty()
        current_time = 0
        
        for i, audio in enumerate(audio_segments):
            audio = audio.fade_in(50).fade_out(50)
            combined += audio
            current_time += len(audio)
            
            if i < len(audio_segments) - 1:
                combined += AudioSegment.silent(duration=pause)
                current_time += pause
        
        # Xuất file audio
        output_file = os.path.join(output_dir, f"single_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        # Tạo file subtitle
        srt_file = self.generate_srt(all_subtitles, output_file)
        
        # Cập nhật progress hoàn thành
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, 
                                   message="Audio generation completed")
        
        return output_file, srt_file, characters_used
    
    async def process_multi_voice(self, text: str, voices_config: dict, pause: int, 
                                repeat: int, output_format: str = "mp3", task_id: str = None, username: str = None):
        """Process text with multiple voices"""
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/{username}/multi_{timestamp}" if username else f"outputs/multi_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Count characters for usage tracking
        characters_used = TextProcessor.count_characters(text)
        
        # Phân tích dialogue
        dialogues = []
        current_char = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            char_match = re.match(r'^(CHAR\d+|NARRATOR):\s*(.+)', line, re.IGNORECASE)
            if char_match:
                if current_char:
                    dialogues.append((current_char, ' '.join(current_text)))
                current_char = char_match.group(1).upper()
                current_text = [char_match.group(2)]
            elif current_char:
                current_text.append(line)
        
        if current_char:
            dialogues.append((current_char, ' '.join(current_text)))
        
        if not dialogues:
            return None, None, characters_used
        
        # Giới hạn số dialogues
        MAX_DIALOGUES = 20
        if len(dialogues) > MAX_DIALOGUES:
            dialogues = dialogues[:MAX_DIALOGUES]
        
        # Tạo audio cho mỗi dialogue
        audio_segments = []
        all_subtitles = []
        
        for i, (char, dialogue_text) in enumerate(dialogues):
            if task_id and task_manager:
                progress = int((i / len(dialogues)) * 90)
                task_manager.update_task(task_id, progress=progress,
                                       message=f"Processing {char}: {i+1}/{len(dialogues)}")
            
            if char == "CHAR1":
                config = voices_config["char1"]
            elif char == "CHAR2":
                config = voices_config["char2"]
            else:  # NARRATOR or others
                config = voices_config["char1"]
            
            temp_file, subs = await self.generate_speech(
                dialogue_text, 
                config["voice"], 
                config["rate"], 
                config["pitch"], 
                config["volume"]
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append((char, audio))
                
                for sub in subs:
                    sub["speaker"] = char
                    all_subtitles.append(sub)
                
                os.remove(temp_file)
        
        if not audio_segments:
            return None, None, characters_used
        
        # Kết hợp với repetition
        combined = AudioSegment.empty()
        
        for rep in range(min(repeat, 2)):  # Giới hạn repeat
            if task_id and task_manager:
                task_manager.update_task(task_id, message=f"Combining repetition {rep+1}/{repeat}")
            
            for i, (char, audio) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            
            if rep < min(repeat, 2) - 1:
                combined += AudioSegment.silent(duration=pause * 2)
        
        # Xuất file
        output_file = os.path.join(output_dir, f"multi_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        # Tạo SRT với speaker labels
        if all_subtitles:
            srt_content = []
            for i, sub in enumerate(all_subtitles, start=1):
                start = timedelta(milliseconds=sub["start"])
                end = timedelta(milliseconds=sub["end"])
                
                start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                
                text = f"{sub['speaker']}: {sub['text']}"
                srt_content.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
            
            srt_file = os.path.join(output_dir, f"multi_voice.srt")
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
        else:
            srt_file = None
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, message="Multi-voice audio generated")
        
        return output_file, srt_file, characters_used
    
    async def process_qa_dialogue(self, text: str, qa_config: dict, pause_q: int, 
                                pause_a: int, repeat: int, output_format: str = "mp3", task_id: str = None, username: str = None):
        """Process Q&A dialogue"""
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/{username}/qa_{timestamp}" if username else f"outputs/qa_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Count characters for usage tracking
        characters_used = TextProcessor.count_characters(text)
        
        # Phân tích Q&A
        dialogues = []
        current_speaker = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            speaker_match = re.match(r'^(Q|A):\s*(.+)', line, re.IGNORECASE)
            if speaker_match:
                if current_speaker:
                    dialogues.append((current_speaker, ' '.join(current_text)))
                current_speaker = speaker_match.group(1).upper()
                current_text = [speaker_match.group(2)]
            elif current_speaker:
                current_text.append(line)
        
        if current_speaker:
            dialogues.append((current_speaker, ' '.join(current_text)))
        
        if not dialogues:
            return None, None, characters_used
        
        # Giới hạn số dialogues
        MAX_DIALOGUES = 10
        if len(dialogues) > MAX_DIALOGUES:
            dialogues = dialogues[:MAX_DIALOGUES]
        
        # Tạo audio
        audio_segments = []
        all_subtitles = []
        
        for i, (speaker, dialogue_text) in enumerate(dialogues):
            if task_id and task_manager:
                progress = int((i / len(dialogues)) * 90)
                task_manager.update_task(task_id, progress=progress,
                                       message=f"Processing {speaker}: {i+1}/{len(dialogues)}")
            
            if speaker == "Q":
                config = qa_config["question"]
                pause = pause_q
            else:
                config = qa_config["answer"]
                pause = pause_a
            
            temp_file, subs = await self.generate_speech(
                dialogue_text,
                config["voice"],
                config["rate"],
                config["pitch"],
                config["volume"]
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append((speaker, audio, pause))
                
                for sub in subs:
                    sub["speaker"] = speaker
                    all_subtitles.append(sub)
                
                os.remove(temp_file)
        
        if not audio_segments:
            return None, None, characters_used
        
        # Kết hợp với repetition
        combined = AudioSegment.empty()
        
        for rep in range(min(repeat, 2)):  # Giới hạn repeat
            if task_id and task_manager:
                task_manager.update_task(task_id, message=f"Combining repetition {rep+1}/{repeat}")
            
            for i, (speaker, audio, pause) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            
            if rep < min(repeat, 2) - 1:
                combined += AudioSegment.silent(duration=pause_a * 2)
        
        # Xuất file
        output_file = os.path.join(output_dir, f"qa_dialogue.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        # Tạo SRT
        if all_subtitles:
            srt_content = []
            for i, sub in enumerate(all_subtitles, start=1):
                start = timedelta(milliseconds=sub["start"])
                end = timedelta(milliseconds=sub["end"])
                
                start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                
                text = f"{sub['speaker']}: {sub['text']}"
                srt_content.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
            
            srt_file = os.path.join(output_dir, f"qa_dialogue.srt")
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
        else:
            srt_file = None
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, message="Q&A audio generated")
        
        return output_file, srt_file, characters_used
    
    def cleanup_temp_files(self):
        """Dọn dẹp file tạm"""
        try:
            temp_files = glob.glob("temp/*.mp3")
            for file in temp_files:
                try:
                    if os.path.exists(file):
                        file_age = time.time() - os.path.getmtime(file)
                        if file_age > 3600:  # Xóa file cũ hơn 1 giờ
                            os.remove(file)
                except:
                    pass
        except Exception as e:
            print(f"Error cleaning temp files: {e}")
    
    def cleanup_old_outputs(self, hours_old: int = 24):
        """Dọn dẹp outputs cũ"""
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
    """Lifespan event handler thay thế cho on_event"""
    # Startup
    print("Starting up Professional TTS Generator with User Management...")
    
    # Initialize TTS processor
    global tts_processor, task_manager
    tts_processor = TTSProcessor()
    task_manager = TaskManager()
    
    # Cleanup old files on startup
    tts_processor.cleanup_temp_files()
    tts_processor.cleanup_old_outputs(24)
    task_manager.cleanup_old_tasks(1)
    
    # Create template files if not exists
    create_template_files()
    
    yield
    
    # Shutdown
    print("Shutting down TTS Generator...")
    tts_processor.cleanup_temp_files()
    if hasattr(task_manager, 'executor'):
        task_manager.executor.shutdown(wait=False)

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="Professional TTS Generator with User Management", 
    version="3.0.0",
    lifespan=lifespan
)

# Global instances (sẽ được khởi tạo trong lifespan)
tts_processor = None
task_manager = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/api/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Login API"""
    try:
        user_data = database.authenticate_user(username, password)
        if not user_data:
            return JSONResponse(
                {"success": False, "message": "Invalid username or password"},
                status_code=401
            )
        
        session_token = database.create_session(username)
        
        response = JSONResponse({
            "success": True,
            "message": "Login successful",
            "user": {
                "username": user_data["username"],
                "full_name": user_data.get("full_name", ""),
                "role": user_data["role"]
            }
        })
        
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            max_age=86400,
            secure=False,
            samesite="lax"
        )
        
        return response
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Login error: {str(e)}"},
            status_code=500
        )

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Register page"""
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/api/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(...),
    full_name: str = Form("")
):
    """Register API"""
    try:
        if len(password) < 6:
            return JSONResponse(
                {"success": False, "message": "Password must be at least 6 characters"},
                status_code=400
            )
        
        success, message = database.create_user(username, password, email, full_name)
        if not success:
            return JSONResponse(
                {"success": False, "message": message},
                status_code=400
            )
        
        return JSONResponse({"success": True, "message": message})
        
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Registration error: {str(e)}"},
            status_code=500
        )

@app.get("/logout")
async def logout(request: Request):
    """Logout"""
    session_token = request.cookies.get("session_token")
    if session_token:
        database.delete_session(session_token)
    
    response = RedirectResponse("/")
    response.delete_cookie("session_token")
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page"""
    try:
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login")
        
        # Calculate usage percentage
        subscription = user["subscription"]
        usage = user["usage"]
        
        if subscription["plan"] == "free":
            usage_percentage = (usage["characters_used"] / subscription["characters_limit"]) * 100
            usage_text = f"{usage['characters_used']:,}/{subscription['characters_limit']:,} characters this week"
        else:
            usage_percentage = 0
            usage_text = f"{usage['characters_used']:,} characters used"
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user": user,
            "usage_percentage": min(usage_percentage, 100),
            "usage_text": usage_text,
            "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS,
            "languages": TTSConfig.LANGUAGES,
            "formats": TTSConfig.OUTPUT_FORMATS
        })
        
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        return RedirectResponse("/login")

@app.get("/tts", response_class=HTMLResponse)
async def tts_page(request: Request):
    """TTS page"""
    try:
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login")
        
        can_access, message = database.can_user_use_feature(user["username"], "single")
        
        return templates.TemplateResponse("tts.html", {
            "request": request,
            "user": user,
            "languages": TTSConfig.LANGUAGES,
            "formats": TTSConfig.OUTPUT_FORMATS,
            "can_access": can_access,
            "access_message": message if not can_access else ""
        })
        
    except Exception as e:
        print(f"TTS page error: {str(e)}")
        return RedirectResponse("/login")

@app.get("/multi-tts", response_class=HTMLResponse)
async def multi_tts_page(request: Request):
    """Multi-Voice TTS page"""
    try:
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login")
        
        can_access, message = database.can_user_use_feature(user["username"], "multi")
        
        return templates.TemplateResponse("multi_tts.html", {
            "request": request,
            "user": user,
            "languages": TTSConfig.LANGUAGES,
            "formats": TTSConfig.OUTPUT_FORMATS,
            "can_access": can_access,
            "access_message": message if not can_access else ""
        })
        
    except Exception as e:
        print(f"Multi-TTS page error: {str(e)}")
        return RedirectResponse("/login")

@app.get("/qa-tts", response_class=HTMLResponse)
async def qa_tts_page(request: Request):
    """Q&A TTS page"""
    try:
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login")
        
        can_access, message = database.can_user_use_feature(user["username"], "qa")
        
        return templates.TemplateResponse("qa_tts.html", {
            "request": request,
            "user": user,
            "languages": TTSConfig.LANGUAGES,
            "formats": TTSConfig.OUTPUT_FORMATS,
            "can_access": can_access,
            "access_message": message if not can_access else ""
        })
        
    except Exception as e:
        print(f"Q&A TTS page error: {str(e)}")
        return RedirectResponse("/login")

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Profile page"""
    try:
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login")
        
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user
        })
        
    except Exception as e:
        print(f"Profile page error: {str(e)}")
        return RedirectResponse("/login")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin page"""
    try:
        user = await require_admin(request)
        
        all_users = database.get_all_users()
        user_count = len(all_users)
        
        # Calculate total usage
        total_characters = sum(user_data["usage"]["characters_used"] for user_data in all_users.values())
        total_requests = sum(user_data["usage"]["total_requests"] for user_data in all_users.values())
        
        return templates.TemplateResponse("admin.html", {
            "request": request,
            "user": user,
            "all_users": all_users,
            "user_count": user_count,
            "total_characters": total_characters,
            "total_requests": total_requests
        })
        
    except HTTPException as e:
        if e.status_code == 403:
            return RedirectResponse("/dashboard")
        raise

@app.get("/upgrade", response_class=HTMLResponse)
async def upgrade_page(request: Request):
    """Upgrade subscription page"""
    try:
        user = await get_current_user(request)
        if not user:
            return RedirectResponse("/login")
        
        return templates.TemplateResponse("upgrade.html", {
            "request": request,
            "user": user,
            "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS
        })
        
    except Exception as e:
        print(f"Upgrade page error: {str(e)}")
        return RedirectResponse("/login")

@app.get("/api/languages")
async def get_languages(request: Request = None):
    """Get all available languages"""
    try:
        # Allow this endpoint to be accessed without authentication for initial page load
        if request:
            user = await get_current_user(request)
            if not user:
                # Still return languages for public access
                pass
        
        languages = list(TTSConfig.LANGUAGES.keys())
        return JSONResponse({"languages": languages})
        
    except Exception as e:
        print(f"Get languages error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.get("/api/voices")
async def get_voices(language: str = None, request: Request = None):
    """Get available voices"""
    try:
        # Allow this endpoint to be accessed without authentication for initial page load
        if request:
            user = await get_current_user(request)
            if not user:
                # Still return voices for public access
                pass
        
        if language and language in TTSConfig.LANGUAGES:
            voices = TTSConfig.LANGUAGES[language]
        else:
            # Return all voices
            voices = []
            for lang_voices in TTSConfig.LANGUAGES.values():
                voices.extend(lang_voices)
        
        return JSONResponse({"voices": voices})
        
    except Exception as e:
        print(f"Get voices error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.post("/api/generate/single")
async def generate_single_voice(
    request: Request,
    text: str = Form(...),
    voice_id: str = Form(...),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3")
):
    """Generate single voice TTS with task system"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Check if user can use the feature
        can_access, message = database.can_user_use_feature(user["username"], "single")
        if not can_access:
            return JSONResponse(
                {"success": False, "message": message},
                status_code=403
            )
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        if not voice_id:
            raise HTTPException(status_code=400, detail="Voice is required")
        
        # Tạo task ID
        task_id = f"single_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "single_voice", user["username"])
        
        # Lưu settings
        tts_processor.settings["single_voice"] = {
            "voice": voice_id,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "pause": pause
        }
        tts_processor.save_settings()
        
        # Chạy trong background
        async def background_task():
            try:
                audio_file, srt_file, characters_used = await tts_processor.process_single_voice(
                    text, voice_id, rate, pitch, volume, pause, output_format, task_id, user["username"]
                )
                
                if audio_file:
                    # Record usage
                    database.record_usage(user["username"], characters_used)
                    
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "characters_used": characters_used,
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
        
        # Start background task
        asyncio.create_task(background_task())
        
        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": "Audio generation started. Check task status."
        })
        
    except Exception as e:
        print(f"Generation error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Generation error: {str(e)}"},
            status_code=500
        )

@app.post("/api/generate/multi")
async def generate_multi_voice(
    request: Request,
    text: str = Form(...),
    char1_language: str = Form(...),
    char1_voice: str = Form(...),
    char1_rate: int = Form(0),
    char1_pitch: int = Form(0),
    char1_volume: int = Form(100),
    char2_language: str = Form(...),
    char2_voice: str = Form(...),
    char2_rate: int = Form(-10),
    char2_pitch: int = Form(0),
    char2_volume: int = Form(100),
    pause: int = Form(500),
    repeat: int = Form(1),
    output_format: str = Form("mp3")
):
    """Generate multi-voice TTS"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Check if user can use the feature
        can_access, message = database.can_user_use_feature(user["username"], "multi")
        if not can_access:
            return JSONResponse(
                {"success": False, "message": message},
                status_code=403
            )
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Tạo task ID
        task_id = f"multi_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "multi_voice", user["username"])
        
        voices_config = {
            "char1": {
                "language": char1_language,
                "voice": char1_voice,
                "rate": char1_rate,
                "pitch": char1_pitch,
                "volume": char1_volume
            },
            "char2": {
                "language": char2_language,
                "voice": char2_voice,
                "rate": char2_rate,
                "pitch": char2_pitch,
                "volume": char2_volume
            }
        }
        
        # Lưu settings
        tts_processor.settings["multi_voice"] = {
            "char1": voices_config["char1"],
            "char2": voices_config["char2"],
            "pause": pause,
            "repeat": repeat
        }
        tts_processor.save_settings()
        
        # Background task
        async def background_task():
            try:
                audio_file, srt_file, characters_used = await tts_processor.process_multi_voice(
                    text, voices_config, pause, repeat, output_format, task_id, user["username"]
                )
                
                if audio_file:
                    # Record usage
                    database.record_usage(user["username"], characters_used)
                    
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "characters_used": characters_used,
                        "message": "Multi-voice audio generated successfully"
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
        
        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": "Multi-voice audio generation started"
        })
        
    except Exception as e:
        print(f"Generation error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Generation error: {str(e)}"},
            status_code=500
        )

@app.post("/api/generate/qa")
async def generate_qa_dialogue(
    request: Request,
    text: str = Form(...),
    question_language: str = Form(...),
    question_voice: str = Form(...),
    question_rate: int = Form(0),
    question_pitch: int = Form(0),
    question_volume: int = Form(100),
    answer_language: str = Form(...),
    answer_voice: str = Form(...),
    answer_rate: int = Form(-10),
    answer_pitch: int = Form(0),
    answer_volume: int = Form(100),
    pause_q: int = Form(200),
    pause_a: int = Form(500),
    repeat: int = Form(2),
    output_format: str = Form("mp3")
):
    """Generate Q&A dialogue TTS"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Check if user can use the feature
        can_access, message = database.can_user_use_feature(user["username"], "qa")
        if not can_access:
            return JSONResponse(
                {"success": False, "message": message},
                status_code=403
            )
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Tạo task ID
        task_id = f"qa_{int(time.time())}_{random.randint(1000, 9999)}"
        task_manager.create_task(task_id, "qa_dialogue", user["username"])
        
        qa_config = {
            "question": {
                "language": question_language,
                "voice": question_voice,
                "rate": question_rate,
                "pitch": question_pitch,
                "volume": question_volume
            },
            "answer": {
                "language": answer_language,
                "voice": answer_voice,
                "rate": answer_rate,
                "pitch": answer_pitch,
                "volume": answer_volume
            }
        }
        
        # Lưu settings
        tts_processor.settings["qa_voice"] = {
            "question": qa_config["question"],
            "answer": qa_config["answer"],
            "pause_q": pause_q,
            "pause_a": pause_a,
            "repeat": repeat
        }
        tts_processor.save_settings()
        
        # Background task
        async def background_task():
            try:
                audio_file, srt_file, characters_used = await tts_processor.process_qa_dialogue(
                    text, qa_config, pause_q, pause_a, repeat, output_format, task_id, user["username"]
                )
                
                if audio_file:
                    # Record usage
                    database.record_usage(user["username"], characters_used)
                    
                    result = {
                        "success": True,
                        "audio_url": f"/download/{os.path.basename(audio_file)}",
                        "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
                        "characters_used": characters_used,
                        "message": "Q&A dialogue audio generated successfully"
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
        
        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "message": "Q&A audio generation started"
        })
        
    except Exception as e:
        print(f"Generation error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Generation error: {str(e)}"},
            status_code=500
        )

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """Get task status"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        task = task_manager.get_task(task_id)
        if not task:
            return JSONResponse(
                {"success": False, "message": "Task not found"},
                status_code=404
            )
        
        # Check if user owns this task or is admin
        if task["username"] != user["username"] and user["role"] != "admin":
            return JSONResponse(
                {"success": False, "message": "Access denied"},
                status_code=403
            )
        
        return JSONResponse({
            "success": True,
            "task_id": task_id,
            "status": task["status"],
            "progress": task["progress"],
            "message": task["message"],
            "result": task.get("result"),
            "created_at": task["created_at"].isoformat(),
            "updated_at": task["updated_at"].isoformat()
        })
        
    except Exception as e:
        print(f"Get task status error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.get("/api/tasks")
async def get_user_tasks(request: Request):
    """Get all tasks for current user"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        tasks = task_manager.get_user_tasks(user["username"])
        
        # Convert tasks to serializable format
        serializable_tasks = {}
        for task_id, task_data in tasks.items():
            serializable_tasks[task_id] = {
                "id": task_data["id"],
                "type": task_data["type"],
                "status": task_data["status"],
                "progress": task_data["progress"],
                "message": task_data["message"],
                "created_at": task_data["created_at"].isoformat(),
                "updated_at": task_data["updated_at"].isoformat()
            }
        
        return JSONResponse({
            "success": True,
            "tasks": serializable_tasks
        })
        
    except Exception as e:
        print(f"Get user tasks error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.get("/download/{filename}")
async def download_file(filename: str, request: Request):
    """Download generated files"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        file_path = None
        
        # Tìm file trong outputs directory
        for root, dirs, files in os.walk("outputs"):
            if filename in files:
                file_path = os.path.join(root, filename)
                break
        
        if not file_path or not os.path.exists(file_path):
            return JSONResponse(
                {"success": False, "message": "File not found"},
                status_code=404
            )
        
        # Check if user has access to this file
        # For now, allow access if file exists
        # In production, you should add proper authorization checks
        
        return FileResponse(
            file_path,
            filename=filename,
            media_type="application/octet-stream"
        )
        
    except Exception as e:
        print(f"Download error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Download error: {str(e)}"},
            status_code=500
        )

@app.get("/api/user/info")
async def get_user_info(request: Request):
    """Get current user info"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        return JSONResponse({
            "success": True,
            "user": {
                "username": user["username"],
                "email": user["email"],
                "full_name": user.get("full_name", ""),
                "role": user["role"],
                "subscription": user["subscription"],
                "usage": user["usage"]
            }
        })
        
    except Exception as e:
        print(f"Get user info error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.post("/api/user/update")
async def update_user(
    request: Request,
    full_name: str = Form(None),
    email: str = Form(None)
):
    """Update user profile"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        users = database.load_users()
        if user["username"] not in users:
            return JSONResponse(
                {"success": False, "message": "User not found"},
                status_code=404
            )
        
        user_data = users[user["username"]]
        
        if full_name is not None:
            user_data["full_name"] = full_name
        
        if email is not None:
            user_data["email"] = email
        
        database.save_users(users)
        
        return JSONResponse({
            "success": True,
            "message": "Profile updated successfully"
        })
        
    except Exception as e:
        print(f"Update user error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.post("/api/user/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...)
):
    """Change user password"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Verify current password
        if not database.verify_password(current_password, user["password"]):
            return JSONResponse(
                {"success": False, "message": "Current password is incorrect"},
                status_code=400
            )
        
        if len(new_password) < 6:
            return JSONResponse(
                {"success": False, "message": "New password must be at least 6 characters"},
                status_code=400
            )
        
        users = database.load_users()
        if user["username"] not in users:
            return JSONResponse(
                {"success": False, "message": "User not found"},
                status_code=404
            )
        
        user_data = users[user["username"]]
        user_data["password"] = database.hash_password(new_password)
        
        database.save_users(users)
        
        return JSONResponse({
            "success": True,
            "message": "Password changed successfully"
        })
        
    except Exception as e:
        print(f"Change password error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.post("/api/admin/update-subscription")
async def update_subscription(
    request: Request,
    username: str = Form(...),
    plan: str = Form(...),
    days: int = Form(30)
):
    """Update user subscription (admin only)"""
    try:
        admin_user = await require_admin(request)
        
        success = database.update_subscription(username, plan, days)
        if not success:
            return JSONResponse(
                {"success": False, "message": "Failed to update subscription"},
                status_code=400
            )
        
        return JSONResponse({
            "success": True,
            "message": f"Subscription updated to {plan} for {username}"
        })
        
    except HTTPException as e:
        if e.status_code == 403:
            return JSONResponse(
                {"success": False, "message": "Admin privileges required"},
                status_code=403
            )
        raise
    except Exception as e:
        print(f"Update subscription error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.get("/api/settings")
async def get_settings(request: Request):
    """Get current TTS settings"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        settings = database.load_settings()
        return JSONResponse({
            "success": True,
            "settings": settings
        })
        
    except Exception as e:
        print(f"Get settings error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.post("/api/cleanup")
async def cleanup_files(request: Request):
    """Cleanup temporary and old files"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Only allow cleanup for users with proper permissions
        if user["role"] != "admin":
            return JSONResponse(
                {"success": False, "message": "Admin privileges required"},
                status_code=403
            )
        
        # Cleanup tasks
        task_manager.cleanup_old_tasks(1)
        
        # Cleanup files
        tts_processor.cleanup_temp_files()
        tts_processor.cleanup_old_outputs(1)  # 1 hour
        
        # Clear audio cache
        tts_processor.cache_manager.clear_cache()
        
        return JSONResponse({"success": True, "message": "Cleanup completed"})
        
    except Exception as e:
        print(f"Cleanup error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.post("/api/cleanup/all")
async def cleanup_all(request: Request):
    """Cleanup all temporary files and cache completely"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Only allow cleanup for users with proper permissions
        if user["role"] != "admin":
            return JSONResponse(
                {"success": False, "message": "Admin privileges required"},
                status_code=403
            )
        
        # Xóa toàn bộ temp
        if os.path.exists("temp"):
            shutil.rmtree("temp")
            os.makedirs("temp")
        
        # Xóa toàn bộ outputs (giữ lại cấu trúc)
        if os.path.exists("outputs"):
            shutil.rmtree("outputs")
            os.makedirs("outputs")
        
        # Xóa toàn bộ cache
        tts_processor.cache_manager.clear_cache()
        
        # Xóa task cache
        task_manager.tasks.clear()
        
        return JSONResponse({
            "success": True, 
            "message": "All cache and temporary files cleared"
        })
        
    except Exception as e:
        print(f"Cleanup all error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Error: {str(e)}"},
            status_code=500
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ==================== TEMPLATE CREATION ====================
def create_template_files():
    """Create all template files"""
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create index.html
    index_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .container {
            max-width: 500px;
        }
        .card {
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card p-5">
            <div class="text-center mb-4">
                <h2>🎤 TTS Generator</h2>
                <p class="text-muted">Convert text to natural speech</p>
            </div>
            <div class="text-center">
                <a href="/login" class="btn btn-primary btn-lg w-100 mb-3">Login</a>
                <a href="/register" class="btn btn-outline-primary btn-lg w-100">Register</a>
            </div>
            <div class="mt-4 text-center">
                <small class="text-muted">Start with 30,000 free characters per week!</small>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    
    # Create login.html
    login_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .container {
            max-width: 400px;
        }
        .card {
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .alert {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card p-4">
            <div class="text-center mb-4">
                <h2>Login</h2>
                <p class="text-muted">Enter your credentials</p>
            </div>
            
            <form id="loginForm">
                <div class="mb-3">
                    <label class="form-label">Username</label>
                    <input type="text" class="form-control" id="username" required>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Password</label>
                    <input type="password" class="form-control" id="password" required>
                </div>
                
                <button type="submit" class="btn btn-primary w-100">Login</button>
            </form>
            
            <div class="mt-3 text-center">
                <a href="/register" class="text-decoration-none">Create account</a>
                <span class="mx-2">•</span>
                <a href="/" class="text-decoration-none">Back to home</a>
            </div>
            
            <div class="alert mt-3" id="message"></div>
        </div>
    </div>
    
    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            
            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                const messageDiv = document.getElementById('message');
                messageDiv.style.display = 'block';
                
                if (result.success) {
                    messageDiv.className = 'alert alert-success';
                    messageDiv.textContent = 'Login successful! Redirecting...';
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1000);
                } else {
                    messageDiv.className = 'alert alert-danger';
                    messageDiv.textContent = result.message || 'Login failed';
                }
            } catch (error) {
                const messageDiv = document.getElementById('message');
                messageDiv.style.display = 'block';
                messageDiv.className = 'alert alert-danger';
                messageDiv.textContent = 'Network error. Please try again.';
            }
        });
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "login.html"), "w", encoding="utf-8") as f:
        f.write(login_html)
    
    # Create register.html
    register_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
        }
        .container {
            max-width: 500px;
        }
        .card {
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .alert {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card p-4">
            <div class="text-center mb-4">
                <h2>Create Account</h2>
                <p class="text-muted">Start with 30,000 free characters per week!</p>
            </div>
            
            <form id="registerForm">
                <div class="mb-3">
                    <label class="form-label">Username *</label>
                    <input type="text" class="form-control" id="username" required>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Email *</label>
                    <input type="email" class="form-control" id="email" required>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Password *</label>
                    <input type="password" class="form-control" id="password" required>
                    <small class="text-muted">Minimum 6 characters</small>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Confirm Password *</label>
                    <input type="password" class="form-control" id="confirm_password" required>
                </div>
                
                <button type="submit" class="btn btn-primary w-100">Create Account</button>
            </form>
            
            <div class="mt-3 text-center">
                <a href="/login" class="text-decoration-none">Already have an account? Login</a>
                <span class="mx-2">•</span>
                <a href="/" class="text-decoration-none">Back to home</a>
            </div>
            
            <div class="alert mt-3" id="message"></div>
        </div>
    </div>
    
    <script>
        document.getElementById('registerForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            const email = document.getElementById('email').value;
            
            // Validation
            if (password.length < 6) {
                showMessage('Password must be at least 6 characters', 'danger');
                return;
            }
            
            if (password !== confirmPassword) {
                showMessage('Passwords do not match', 'danger');
                return;
            }
            
            const formData = new FormData();
            formData.append('username', username);
            formData.append('password', password);
            formData.append('email', email);
            formData.append('full_name', '');
            
            try {
                const response = await fetch('/api/register', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showMessage('Account created! Redirecting to login...', 'success');
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 2000);
                } else {
                    showMessage(result.message || 'Registration failed', 'danger');
                }
            } catch (error) {
                showMessage('Network error. Please try again.', 'danger');
            }
        });
        
        function showMessage(text, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.style.display = 'block';
            messageDiv.className = `alert alert-${type}`;
            messageDiv.textContent = text;
        }
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "register.html"), "w", encoding="utf-8") as f:
        f.write(register_html)
    
    # Create dashboard.html
    dashboard_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
            font-family: Arial, sans-serif;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-bottom: 20px;
            transition: transform 0.3s;
        }
        .card:hover {
            transform: translateY(-5px);
        }
        .progress {
            height: 10px;
        }
        .feature-card {
            border-left: 4px solid #4361ee;
        }
        .stats-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex align-items-center">
                <span class="me-3">Welcome, {{ user.username }}!</span>
                <div class="dropdown">
                    <button class="btn btn-outline-secondary dropdown-toggle" type="button" id="userMenu" data-bs-toggle="dropdown">
                        <i class="fas fa-user"></i>
                    </button>
                    <ul class="dropdown-menu dropdown-menu-end">
                        <li><a class="dropdown-item" href="/profile"><i class="fas fa-user-circle me-2"></i>Profile</a></li>
                        <li><hr class="dropdown-divider"></li>
                        <li><a class="dropdown-item" href="/logout"><i class="fas fa-sign-out-alt me-2"></i>Logout</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8">
                <h2>Dashboard</h2>
                <p class="text-muted">Manage your TTS projects and settings</p>
            </div>
            <div class="col-md-4 text-end">
                <a href="/upgrade" class="btn btn-warning">
                    <i class="fas fa-crown me-2"></i>Upgrade Plan
                </a>
                {% if user.role == 'admin' %}
                <a href="/admin" class="btn btn-danger ms-2">
                    <i class="fas fa-shield-alt me-2"></i>Admin Panel
                </a>
                {% endif %}
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card stats-card">
                    <div class="card-body">
                        <h5 class="card-title">Current Plan: {{ user.subscription.plan|upper }}</h5>
                        <p class="card-text">{{ usage_text }}</p>
                        <div class="progress bg-white bg-opacity-25">
                            <div class="progress-bar" style="width: {{ usage_percentage }}%"></div>
                        </div>
                        <small>{{ usage_percentage|round(1) }}% used</small>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Quick Stats</h5>
                        <div class="row text-center">
                            <div class="col-6">
                                <h3>{{ user.usage.characters_used|number_format }}</h3>
                                <small class="text-muted">Characters Used</small>
                            </div>
                            <div class="col-6">
                                <h3>{{ user.usage.total_requests }}</h3>
                                <small class="text-muted">Total Requests</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="card feature-card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-user me-2"></i>Single Voice</h5>
                        <p class="card-text">Convert text to speech with a single voice.</p>
                        <a href="/tts" class="btn btn-primary w-100">Start Now</a>
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card feature-card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-users me-2"></i>Multi-Voice</h5>
                        <p class="card-text">Create dialogues with multiple characters.</p>
                        {% if 'multi' in user.subscription.features %}
                        <a href="/multi-tts" class="btn btn-primary w-100">Start Now</a>
                        {% else %}
                        <button class="btn btn-secondary w-100" disabled>Upgrade Required</button>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <div class="col-md-4">
                <div class="card feature-card">
                    <div class="card-body">
                        <h5 class="card-title"><i class="fas fa-comments me-2"></i>Q&A Dialogue</h5>
                        <p class="card-text">Generate question and answer dialogues.</p>
                        {% if 'qa' in user.subscription.features %}
                        <a href="/qa-tts" class="btn btn-primary w-100">Start Now</a>
                        {% else %}
                        <button class="btn btn-secondary w-100" disabled>Upgrade Required</button>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card mt-4">
            <div class="card-body">
                <h5 class="card-title">Account Information</h5>
                <table class="table">
                    <tr>
                        <th>Username:</th>
                        <td>{{ user.username }}</td>
                    </tr>
                    <tr>
                        <th>Email:</th>
                        <td>{{ user.email }}</td>
                    </tr>
                    <tr>
                        <th>Full Name:</th>
                        <td>{{ user.full_name or 'Not set' }}</td>
                    </tr>
                    <tr>
                        <th>Role:</th>
                        <td>{{ user.role|title }}</td>
                    </tr>
                    <tr>
                        <th>Plan:</th>
                        <td>{{ user.subscription.plan|title }}</td>
                    </tr>
                    <tr>
                        <th>Expires:</th>
                        <td>{{ user.subscription.expires_at|datetimeformat }}</td>
                    </tr>
                </table>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Simple datetime formatter
        function formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
        
        // Number formatter
        function formatNumber(num) {
            return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        
        // Apply formatting
        document.addEventListener('DOMContentLoaded', function() {
            // Format numbers
            document.querySelectorAll('h3').forEach(el => {
                if (el.textContent.match(/^\d+$/)) {
                    el.textContent = formatNumber(parseInt(el.textContent));
                }
            });
            
            // Format dates
            document.querySelectorAll('td').forEach(el => {
                if (el.textContent.match(/\d{4}-\d{2}-\d{2}T/)) {
                    el.textContent = formatDate(el.textContent);
                }
            });
        });
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(dashboard_html)
    
    # Create tts.html (single voice TTS page)
    tts_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Single Voice TTS - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .container {
            max-width: 1000px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 20px;
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
            border-top: 5px solid #4361ee;
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
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h2><i class="fas fa-user me-2"></i>Single Voice TTS</h2>
        
        {% if not can_access %}
        <div class="alert alert-danger">
            {{ access_message }}
        </div>
        {% endif %}
        
        <div class="card">
            <div class="card-body">
                <form id="ttsForm">
                    <div class="mb-3">
                        <label class="form-label">Text to Convert</label>
                        <textarea class="form-control" id="text" rows="6" required></textarea>
                        <div class="mt-1 text-end">
                            <small id="charCount">0 characters</small>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Language</label>
                            <select class="form-select" id="language" required>
                                <option value="">Select Language</option>
                                {% for language in languages %}
                                <option value="{{ language }}">{{ language }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Voice</label>
                            <select class="form-select" id="voice" required disabled>
                                <option value="">Select Voice</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="row mb-3">
                        <div class="col-md-3">
                            <label class="form-label">Speed: <span id="rateValue">0%</span></label>
                            <input type="range" class="form-range" id="rate" min="-30" max="30" value="0">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Pitch: <span id="pitchValue">0Hz</span></label>
                            <input type="range" class="form-range" id="pitch" min="-30" max="30" value="0">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Volume: <span id="volumeValue">100%</span></label>
                            <input type="range" class="form-range" id="volume" min="50" max="150" value="100">
                        </div>
                        <div class="col-md-3">
                            <label class="form-label">Pause: <span id="pauseValue">500ms</span></label>
                            <input type="range" class="form-range" id="pause" min="100" max="2000" value="500">
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Output Format</label>
                        <select class="form-select" id="format">
                            {% for format in formats %}
                            <option value="{{ format }}">{{ format|upper }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100" {% if not can_access %}disabled{% endif %}>
                        <i class="fas fa-play-circle me-2"></i>Generate Audio
                    </button>
                </form>
                
                <div class="mt-3 text-center">
                    <small class="text-muted">Processing may take a few moments</small>
                </div>
                
                <div class="task-status" id="taskStatus">
                    <div class="progress-container">
                        <div class="progress">
                            <div class="progress-bar" id="progressBar" style="width: 0%"></div>
                        </div>
                        <div class="text-center mt-2" id="progressText">0%</div>
                    </div>
                    <div id="taskMessage"></div>
                </div>
                
                <div id="result" class="mt-3" style="display: none;">
                    <h5>Generated Audio</h5>
                    <audio controls class="w-100" id="audioPlayer"></audio>
                    <div class="mt-2">
                        <a href="#" class="btn btn-success me-2" id="downloadBtn">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="downloadSubtitleBtn" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
    </div>
    
    <div class="toast-container"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentTaskId = null;
        let taskCheckInterval = null;
        
        // Load languages and voices
        async function loadLanguages() {
            try {
                const response = await fetch('/api/languages');
                const data = await response.json();
                
                const languageSelect = document.getElementById('language');
                data.languages.forEach(language => {
                    const option = document.createElement('option');
                    option.value = language;
                    option.textContent = language;
                    languageSelect.appendChild(option);
                });
                
                // Auto-select first language
                if (data.languages.length > 0) {
                    languageSelect.value = data.languages[0];
                    loadVoices(data.languages[0]);
                }
            } catch (error) {
                console.error('Error loading languages:', error);
                showToast('Error loading languages', 'error');
            }
        }
        
        // Load voices for selected language
        async function loadVoices(language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('voice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                voiceSelect.disabled = false;
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Auto-select first voice
                if (data.voices.length > 0) {
                    voiceSelect.value = data.voices[0].name;
                }
            } catch (error) {
                console.error('Error loading voices:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Update character count
        function updateCharCount() {
            const text = document.getElementById('text').value;
            const charCount = text.replace(/\s/g, '').length;
            document.getElementById('charCount').textContent = `${charCount} characters`;
        }
        
        // Initialize range displays
        function initRangeDisplays() {
            const ranges = [
                { id: 'rate', display: 'rateValue', suffix: '%' },
                { id: 'pitch', display: 'pitchValue', suffix: 'Hz' },
                { id: 'volume', display: 'volumeValue', suffix: '%' },
                { id: 'pause', display: 'pauseValue', suffix: 'ms' }
            ];
            
            ranges.forEach(range => {
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
        
        // Form submission
        document.getElementById('ttsForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const text = document.getElementById('text').value;
            const voice = document.getElementById('voice').value;
            const format = document.getElementById('format').value;
            const rate = document.getElementById('rate').value;
            const pitch = document.getElementById('pitch').value;
            const volume = document.getElementById('volume').value;
            const pause = document.getElementById('pause').value;
            
            if (!text.trim()) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!voice) {
                showToast('Please select a voice', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', rate);
            formData.append('pitch', pitch);
            formData.append('volume', volume);
            formData.append('pause', pause);
            formData.append('output_format', format);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus(result.task_id);
                    showToast('Audio generation started', 'success');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        });
        
        // Show task status and poll for updates
        function showTaskStatus(taskId) {
            const statusDiv = document.getElementById('taskStatus');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const taskMessage = document.getElementById('taskMessage');
            
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
                    
                    if (task.success) {
                        progressBar.style.width = `${task.progress}%`;
                        progressText.textContent = `${task.progress}%`;
                        taskMessage.textContent = task.message;
                        
                        if (task.status === 'completed') {
                            clearInterval(taskCheckInterval);
                            
                            if (task.result && task.result.success) {
                                showToast(task.result.message, 'success');
                                
                                // Show output
                                showOutput(task.result);
                            }
                            
                            // Hide status after 5 seconds
                            setTimeout(() => {
                                statusDiv.style.display = 'none';
                            }, 5000);
                        } else if (task.status === 'failed') {
                            clearInterval(taskCheckInterval);
                            showToast(task.message, 'error');
                            
                            // Hide status after 3 seconds
                            setTimeout(() => {
                                statusDiv.style.display = 'none';
                            }, 3000);
                        }
                    }
                } catch (error) {
                    console.error('Error checking task status:', error);
                }
            }, 2000);
        }
        
        // Show output
        function showOutput(result) {
            const resultDiv = document.getElementById('result');
            const audioPlayer = document.getElementById('audioPlayer');
            const downloadBtn = document.getElementById('downloadBtn');
            const downloadSubtitleBtn = document.getElementById('downloadSubtitleBtn');
            
            // Add timestamp to avoid cache
            const timestamp = new Date().getTime();
            const audioUrl = `${result.audio_url}?t=${timestamp}`;
            
            audioPlayer.innerHTML = `
                <source src="${audioUrl}" type="audio/mpeg">
                Your browser does not support the audio element.
            `;
            audioPlayer.load();
            
            downloadBtn.href = result.audio_url;
            downloadBtn.download = `tts_audio_${Date.now()}.mp3`;
            
            if (result.srt_url) {
                downloadSubtitleBtn.href = result.srt_url;
                downloadSubtitleBtn.download = `tts_subtitle_${Date.now()}.srt`;
                downloadSubtitleBtn.style.display = 'inline-block';
            } else {
                downloadSubtitleBtn.style.display = 'none';
            }
            
            resultDiv.style.display = 'block';
            
            // Scroll to output
            resultDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Event listeners
        document.getElementById('language').addEventListener('change', function() {
            loadVoices(this.value);
        });
        
        document.getElementById('text').addEventListener('input', updateCharCount);
        
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
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            loadLanguages();
            initRangeDisplays();
            updateCharCount();
            
            // Auto-select Vietnamese
            const languageSelect = document.getElementById('language');
            const viOption = Array.from(languageSelect.options).find(opt => opt.text.includes('Vietnamese'));
            if (viOption) {
                languageSelect.value = viOption.value;
                languageSelect.dispatchEvent(new Event('change'));
            }
        });
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "tts.html"), "w", encoding="utf-8") as f:
        f.write(tts_html)
    
    # Create multi_tts.html (multi-voice TTS page)
    multi_tts_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Voice TTS - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .container {
            max-width: 1200px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
        .voice-card {
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f8f9fa;
        }
        .character-tag {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .char1-tag { background: #e3f2fd; color: #1976d2; }
        .char2-tag { background: #f3e5f5; color: #7b1fa2; }
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
            border-top: 5px solid #4361ee;
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
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/tts" class="btn btn-outline-secondary btn-sm me-2">Single Voice</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h2><i class="fas fa-users me-2"></i>Multi-Voice TTS</h2>
        
        {% if not can_access %}
        <div class="alert alert-danger">
            {{ access_message }}
        </div>
        {% endif %}
        
        <div class="card">
            <div class="card-body">
                <form id="multiTTSForm">
                    <div class="mb-3">
                        <label class="form-label">Dialogue Content</label>
                        <textarea class="form-control" id="text" rows="8" 
                                  placeholder="CHAR1: Dialogue for character 1&#10;CHAR2: Dialogue for character 2&#10;NARRATOR: Narration text"></textarea>
                        <small class="text-muted">Use CHAR1:, CHAR2:, or NARRATOR: prefixes. Maximum 20 dialogues.</small>
                        <div class="mt-1 text-end">
                            <small id="charCount">0 characters</small>
                        </div>
                    </div>
                    
                    <div class="row">
                        <!-- Character 1 Settings -->
                        <div class="col-md-6">
                            <div class="voice-card">
                                <h5><span class="character-tag char1-tag">CHARACTER 1</span></h5>
                                
                                <div class="mb-3">
                                    <label class="form-label">Language</label>
                                    <select class="form-select" id="char1Language" required>
                                        <option value="">Select Language</option>
                                        {% for language in languages %}
                                        <option value="{{ language }}">{{ language }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Voice</label>
                                    <select class="form-select" id="char1Voice" required disabled>
                                        <option value="">Select Voice</option>
                                    </select>
                                </div>
                                
                                <div class="row">
                                    <div class="col-4">
                                        <label class="form-label small">Speed</label>
                                        <input type="range" class="form-range" id="char1Rate" min="-30" max="30" value="0">
                                        <small class="d-block text-center"><span id="char1RateValue">0%</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Pitch</label>
                                        <input type="range" class="form-range" id="char1Pitch" min="-30" max="30" value="0">
                                        <small class="d-block text-center"><span id="char1PitchValue">0Hz</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Volume</label>
                                        <input type="range" class="form-range" id="char1Volume" min="50" max="150" value="100">
                                        <small class="d-block text-center"><span id="char1VolumeValue">100%</span></small>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Character 2 Settings -->
                        <div class="col-md-6">
                            <div class="voice-card">
                                <h5><span class="character-tag char2-tag">CHARACTER 2</span></h5>
                                
                                <div class="mb-3">
                                    <label class="form-label">Language</label>
                                    <select class="form-select" id="char2Language" required>
                                        <option value="">Select Language</option>
                                        {% for language in languages %}
                                        <option value="{{ language }}">{{ language }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Voice</label>
                                    <select class="form-select" id="char2Voice" required disabled>
                                        <option value="">Select Voice</option>
                                    </select>
                                </div>
                                
                                <div class="row">
                                    <div class="col-4">
                                        <label class="form-label small">Speed</label>
                                        <input type="range" class="form-range" id="char2Rate" min="-30" max="30" value="-10">
                                        <small class="d-block text-center"><span id="char2RateValue">-10%</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Pitch</label>
                                        <input type="range" class="form-range" id="char2Pitch" min="-30" max="30" value="0">
                                        <small class="d-block text-center"><span id="char2PitchValue">0Hz</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Volume</label>
                                        <input type="range" class="form-range" id="char2Volume" min="50" max="150" value="100">
                                        <small class="d-block text-center"><span id="char2VolumeValue">100%</span></small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- General Settings -->
                    <div class="row mt-3">
                        <div class="col-md-4">
                            <label class="form-label">
                                Pause Between Dialogues: <span id="pauseValue">500ms</span>
                            </label>
                            <input type="range" class="form-range" id="pause" min="100" max="2000" value="500">
                        </div>
                        
                        <div class="col-md-4">
                            <label class="form-label">
                                Repeat Times: <span id="repeatValue">1</span>
                            </label>
                            <input type="range" class="form-range" id="repeat" min="1" max="5" value="1">
                        </div>
                        
                        <div class="col-md-4">
                            <label class="form-label">Output Format</label>
                            <select class="form-select" id="format">
                                {% for format in formats %}
                                <option value="{{ format }}">{{ format|upper }}</option>
                                {% endfor %}
                            </select>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100 mt-3" {% if not can_access %}disabled{% endif %}>
                        <i class="fas fa-play-circle me-2"></i>Generate Multi-Voice Audio
                    </button>
                </form>
                
                <div class="mt-3 text-center">
                    <small class="text-muted">Processing may take a few moments</small>
                </div>
                
                <div class="task-status" id="taskStatus">
                    <div class="progress-container">
                        <div class="progress">
                            <div class="progress-bar" id="progressBar" style="width: 0%"></div>
                        </div>
                        <div class="text-center mt-2" id="progressText">0%</div>
                    </div>
                    <div id="taskMessage"></div>
                </div>
                
                <div id="result" class="mt-3" style="display: none;">
                    <h5>Generated Multi-Voice Audio</h5>
                    <audio controls class="w-100" id="audioPlayer"></audio>
                    <div class="mt-2">
                        <a href="#" class="btn btn-success me-2" id="downloadBtn">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="downloadSubtitleBtn" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
    </div>
    
    <div class="toast-container"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentTaskId = null;
        let taskCheckInterval = null;
        
        // Load voices for character 1
        async function loadChar1Voices(language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('char1Voice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                voiceSelect.disabled = false;
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Auto-select Vietnamese female voice if available
                const viVoice = data.voices.find(v => v.name === 'vi-VN-HoaiMyNeural');
                if (viVoice) {
                    voiceSelect.value = viVoice.name;
                }
            } catch (error) {
                console.error('Error loading voices for character 1:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Load voices for character 2
        async function loadChar2Voices(language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('char2Voice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                voiceSelect.disabled = false;
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Auto-select Vietnamese male voice if available
                const viVoice = data.voices.find(v => v.name === 'vi-VN-NamMinhNeural');
                if (viVoice) {
                    voiceSelect.value = viVoice.name;
                }
            } catch (error) {
                console.error('Error loading voices for character 2:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Update character count
        function updateCharCount() {
            const text = document.getElementById('text').value;
            const charCount = text.replace(/\s/g, '').length;
            document.getElementById('charCount').textContent = `${charCount} characters`;
        }
        
        // Initialize range displays
        function initRangeDisplays() {
            // Character 1 ranges
            const char1Ranges = [
                { id: 'char1Rate', display: 'char1RateValue', suffix: '%' },
                { id: 'char1Pitch', display: 'char1PitchValue', suffix: 'Hz' },
                { id: 'char1Volume', display: 'char1VolumeValue', suffix: '%' }
            ];
            
            char1Ranges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // Character 2 ranges
            const char2Ranges = [
                { id: 'char2Rate', display: 'char2RateValue', suffix: '%' },
                { id: 'char2Pitch', display: 'char2PitchValue', suffix: 'Hz' },
                { id: 'char2Volume', display: 'char2VolumeValue', suffix: '%' }
            ];
            
            char2Ranges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // General ranges
            const generalRanges = [
                { id: 'pause', display: 'pauseValue', suffix: 'ms' },
                { id: 'repeat', display: 'repeatValue', suffix: 'x' }
            ];
            
            generalRanges.forEach(range => {
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
        
        // Form submission
        document.getElementById('multiTTSForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const text = document.getElementById('text').value;
            const char1Language = document.getElementById('char1Language').value;
            const char1Voice = document.getElementById('char1Voice').value;
            const char2Language = document.getElementById('char2Language').value;
            const char2Voice = document.getElementById('char2Voice').value;
            const format = document.getElementById('format').value;
            
            if (!text.trim()) {
                showToast('Please enter dialogue text', 'error');
                return;
            }
            
            if (!char1Language || !char1Voice) {
                showToast('Please select language and voice for Character 1', 'error');
                return;
            }
            
            if (!char2Language || !char2Voice) {
                showToast('Please select language and voice for Character 2', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('char1_language', char1Language);
            formData.append('char1_voice', char1Voice);
            formData.append('char1_rate', document.getElementById('char1Rate').value);
            formData.append('char1_pitch', document.getElementById('char1Pitch').value);
            formData.append('char1_volume', document.getElementById('char1Volume').value);
            formData.append('char2_language', char2Language);
            formData.append('char2_voice', char2Voice);
            formData.append('char2_rate', document.getElementById('char2Rate').value);
            formData.append('char2_pitch', document.getElementById('char2Pitch').value);
            formData.append('char2_volume', document.getElementById('char2Volume').value);
            formData.append('pause', document.getElementById('pause').value);
            formData.append('repeat', document.getElementById('repeat').value);
            formData.append('output_format', format);
            
            try {
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus(result.task_id);
                    showToast('Multi-voice audio generation started', 'success');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        });
        
        // Show task status and poll for updates
        function showTaskStatus(taskId) {
            const statusDiv = document.getElementById('taskStatus');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const taskMessage = document.getElementById('taskMessage');
            
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
                    
                    if (task.success) {
                        progressBar.style.width = `${task.progress}%`;
                        progressText.textContent = `${task.progress}%`;
                        taskMessage.textContent = task.message;
                        
                        if (task.status === 'completed') {
                            clearInterval(taskCheckInterval);
                            
                            if (task.result && task.result.success) {
                                showToast(task.result.message, 'success');
                                
                                // Show output
                                showOutput(task.result);
                            }
                            
                            // Hide status after 5 seconds
                            setTimeout(() => {
                                statusDiv.style.display = 'none';
                            }, 5000);
                        } else if (task.status === 'failed') {
                            clearInterval(taskCheckInterval);
                            showToast(task.message, 'error');
                            
                            // Hide status after 3 seconds
                            setTimeout(() => {
                                statusDiv.style.display = 'none';
                            }, 3000);
                        }
                    }
                } catch (error) {
                    console.error('Error checking task status:', error);
                }
            }, 2000);
        }
        
        // Show output
        function showOutput(result) {
            const resultDiv = document.getElementById('result');
            const audioPlayer = document.getElementById('audioPlayer');
            const downloadBtn = document.getElementById('downloadBtn');
            const downloadSubtitleBtn = document.getElementById('downloadSubtitleBtn');
            
            // Add timestamp to avoid cache
            const timestamp = new Date().getTime();
            const audioUrl = `${result.audio_url}?t=${timestamp}`;
            
            audioPlayer.innerHTML = `
                <source src="${audioUrl}" type="audio/mpeg">
                Your browser does not support the audio element.
            `;
            audioPlayer.load();
            
            downloadBtn.href = result.audio_url;
            downloadBtn.download = `tts_multi_audio_${Date.now()}.mp3`;
            
            if (result.srt_url) {
                downloadSubtitleBtn.href = result.srt_url;
                downloadSubtitleBtn.download = `tts_multi_subtitle_${Date.now()}.srt`;
                downloadSubtitleBtn.style.display = 'inline-block';
            } else {
                downloadSubtitleBtn.style.display = 'none';
            }
            
            resultDiv.style.display = 'block';
            
            // Scroll to output
            resultDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Event listeners
        document.getElementById('char1Language').addEventListener('change', function() {
            loadChar1Voices(this.value);
        });
        
        document.getElementById('char2Language').addEventListener('change', function() {
            loadChar2Voices(this.value);
        });
        
        document.getElementById('text').addEventListener('input', updateCharCount);
        
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
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initRangeDisplays();
            updateCharCount();
            
            // Auto-select Vietnamese for both characters
            const viLanguage = 'Vietnamese';
            document.getElementById('char1Language').value = viLanguage;
            document.getElementById('char2Language').value = viLanguage;
            
            // Load voices
            loadChar1Voices(viLanguage);
            loadChar2Voices(viLanguage);
        });
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "multi_tts.html"), "w", encoding="utf-8") as f:
        f.write(multi_tts_html)
    
    # Create qa_tts.html (Q&A TTS page) - similar structure to multi_tts.html
    # Create profile.html
    profile_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Profile - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
        .profile-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px 10px 0 0;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="card">
            <div class="profile-header">
                <h2><i class="fas fa-user-circle me-2"></i>Profile</h2>
                <p class="mb-0">Manage your account settings</p>
            </div>
            
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <h4>Account Information</h4>
                        <form id="profileForm">
                            <div class="mb-3">
                                <label class="form-label">Username</label>
                                <input type="text" class="form-control" value="{{ user.username }}" readonly>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Email Address</label>
                                <input type="email" class="form-control" id="email" value="{{ user.email }}">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Full Name</label>
                                <input type="text" class="form-control" id="full_name" value="{{ user.full_name or '' }}">
                            </div>
                            
                            <button type="submit" class="btn btn-primary">Update Profile</button>
                        </form>
                    </div>
                    
                    <div class="col-md-6">
                        <h4>Change Password</h4>
                        <form id="passwordForm">
                            <div class="mb-3">
                                <label class="form-label">Current Password</label>
                                <input type="password" class="form-control" id="current_password" required>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">New Password</label>
                                <input type="password" class="form-control" id="new_password" required>
                                <small class="text-muted">Minimum 6 characters</small>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Confirm New Password</label>
                                <input type="password" class="form-control" id="confirm_password" required>
                            </div>
                            
                            <button type="submit" class="btn btn-warning">Change Password</button>
                        </form>
                    </div>
                </div>
                
                <hr class="my-4">
                
                <div class="row">
                    <div class="col-md-6">
                        <h4>Subscription Information</h4>
                        <table class="table">
                            <tr>
                                <th>Current Plan:</th>
                                <td>{{ user.subscription.plan|title }}</td>
                            </tr>
                            <tr>
                                <th>Expiration Date:</th>
                                <td>{{ user.subscription.expires_at|datetimeformat }}</td>
                            </tr>
                            <tr>
                                <th>Characters Used:</th>
                                <td>{{ user.usage.characters_used }}</td>
                            </tr>
                            <tr>
                                <th>Total Requests:</th>
                                <td>{{ user.usage.total_requests }}</td>
                            </tr>
                        </table>
                        <a href="/upgrade" class="btn btn-success">Upgrade Plan</a>
                    </div>
                    
                    <div class="col-md-6">
                        <h4>Account Actions</h4>
                        <div class="d-grid gap-2">
                            <a href="/dashboard" class="btn btn-outline-primary">
                                <i class="fas fa-tachometer-alt me-2"></i>Back to Dashboard
                            </a>
                            <a href="/tts" class="btn btn-outline-secondary">
                                <i class="fas fa-user me-2"></i>Single Voice TTS
                            </a>
                            {% if 'multi' in user.subscription.features %}
                            <a href="/multi-tts" class="btn btn-outline-secondary">
                                <i class="fas fa-users me-2"></i>Multi-Voice TTS
                            </a>
                            {% endif %}
                            {% if 'qa' in user.subscription.features %}
                            <a href="/qa-tts" class="btn btn-outline-secondary">
                                <i class="fas fa-comments me-2"></i>Q&A TTS
                            </a>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast-container position-fixed top-0 end-0 p-3"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Profile form submission
        document.getElementById('profileForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const full_name = document.getElementById('full_name').value;
            
            const formData = new FormData();
            formData.append('email', email);
            formData.append('full_name', full_name);
            
            try {
                const response = await fetch('/api/user/update', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Profile updated successfully', 'success');
                } else {
                    showToast(result.message || 'Update failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Update failed: ' + error.message, 'error');
            }
        });
        
        // Password form submission
        document.getElementById('passwordForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const current_password = document.getElementById('current_password').value;
            const new_password = document.getElementById('new_password').value;
            const confirm_password = document.getElementById('confirm_password').value;
            
            // Validation
            if (new_password.length < 6) {
                showToast('New password must be at least 6 characters', 'error');
                return;
            }
            
            if (new_password !== confirm_password) {
                showToast('Passwords do not match', 'error');
                return;
            }
            
            const formData = new FormData();
            formData.append('current_password', current_password);
            formData.append('new_password', new_password);
            
            try {
                const response = await fetch('/api/user/change-password', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast('Password changed successfully', 'success');
                    // Clear form
                    document.getElementById('passwordForm').reset();
                } else {
                    showToast(result.message || 'Password change failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Password change failed: ' + error.message, 'error');
            }
        });
        
        // Format date
        function formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
        
        // Apply date formatting
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('td').forEach(el => {
                if (el.textContent.match(/\d{4}-\d{2}-\d{2}T/)) {
                    el.textContent = formatDate(el.textContent);
                }
            });
        });
        
        // Toast function
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
    
    with open(os.path.join(templates_dir, "profile.html"), "w", encoding="utf-8") as f:
        f.write(profile_html)
    
    # Create admin.html
    admin_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
        .admin-header {
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
            color: white;
            padding: 2rem;
            border-radius: 10px 10px 0 0;
        }
        .stats-card {
            background: linear-gradient(135deg, #4361ee 0%, #3a0ca3 100%);
            color: white;
        }
        .user-row:hover {
            background-color: #f8f9fa;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <div class="card">
            <div class="admin-header">
                <h2><i class="fas fa-shield-alt me-2"></i>Admin Panel</h2>
                <p class="mb-0">System administration and user management</p>
            </div>
            
            <div class="card-body">
                <!-- Statistics -->
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>{{ user_count }}</h3>
                                <p class="mb-0">Total Users</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>{{ total_characters|number_format }}</h3>
                                <p class="mb-0">Total Characters</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>{{ total_requests }}</h3>
                                <p class="mb-0">Total Requests</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card stats-card">
                            <div class="card-body text-center">
                                <h3>{{ (total_characters / 1000)|round(1) }}K</h3>
                                <p class="mb-0">Characters (K)</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- User Management -->
                <h4 class="mb-3">User Management</h4>
                <div class="table-responsive">
                    <table class="table table-hover">
                        <thead>
                            <tr>
                                <th>Username</th>
                                <th>Email</th>
                                <th>Role</th>
                                <th>Plan</th>
                                <th>Characters Used</th>
                                <th>Total Requests</th>
                                <th>Created</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for username, user_data in all_users.items() %}
                            <tr class="user-row">
                                <td>
                                    {{ username }}
                                    {% if user_data.role == 'admin' %}
                                    <span class="badge bg-danger ms-1">Admin</span>
                                    {% endif %}
                                </td>
                                <td>{{ user_data.email }}</td>
                                <td>{{ user_data.role|title }}</td>
                                <td>
                                    <span class="badge bg-{% if user_data.subscription.plan == 'pro' %}warning{% elif user_data.subscription.plan == 'premium' %}info{% else %}secondary{% endif %}">
                                        {{ user_data.subscription.plan|title }}
                                    </span>
                                </td>
                                <td>{{ user_data.usage.characters_used }}</td>
                                <td>{{ user_data.usage.total_requests }}</td>
                                <td>{{ user_data.created_at|datetimeformat }}</td>
                                <td>
                                    <div class="dropdown">
                                        <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown">
                                            Actions
                                        </button>
                                        <ul class="dropdown-menu">
                                            <li>
                                                <a class="dropdown-item" href="#" onclick="updateSubscription('{{ username }}', 'free')">
                                                    <i class="fas fa-user me-2"></i>Set to Free
                                                </a>
                                            </li>
                                            <li>
                                                <a class="dropdown-item" href="#" onclick="updateSubscription('{{ username }}', 'premium')">
                                                    <i class="fas fa-crown me-2"></i>Set to Premium
                                                </a>
                                            </li>
                                            <li>
                                                <a class="dropdown-item" href="#" onclick="updateSubscription('{{ username }}', 'pro')">
                                                    <i class="fas fa-gem me-2"></i>Set to Pro
                                                </a>
                                            </li>
                                            <li><hr class="dropdown-divider"></li>
                                            <li>
                                                <a class="dropdown-item text-danger" href="#" onclick="resetUsage('{{ username }}')">
                                                    <i class="fas fa-redo me-2"></i>Reset Usage
                                                </a>
                                            </li>
                                        </ul>
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
                
                <!-- System Actions -->
                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title"><i class="fas fa-broom me-2"></i>System Cleanup</h5>
                                <p class="card-text">Clean temporary files and cache to free up disk space.</p>
                                <button class="btn btn-warning me-2" onclick="cleanupFiles()">
                                    <i class="fas fa-trash-alt me-2"></i>Cleanup Files
                                </button>
                                <button class="btn btn-danger" onclick="cleanupAll()">
                                    <i class="fas fa-bomb me-2"></i>Cleanup All
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-body">
                                <h5 class="card-title"><i class="fas fa-info-circle me-2"></i>System Information</h5>
                                <ul class="list-unstyled">
                                    <li><i class="fas fa-server me-2"></i> Server Time: <span id="serverTime"></span></li>
                                    <li><i class="fas fa-hdd me-2"></i> Disk Usage: <span id="diskUsage">Checking...</span></li>
                                    <li><i class="fas fa-memory me-2"></i> Memory Usage: <span id="memoryUsage">Checking...</span></li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast-container position-fixed top-0 end-0 p-3"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Update subscription
        async function updateSubscription(username, plan) {
            if (!confirm(`Change ${username}'s subscription to ${plan}?`)) {
                return;
            }
            
            const formData = new FormData();
            formData.append('username', username);
            formData.append('plan', plan);
            formData.append('days', 30);
            
            try {
                const response = await fetch('/api/admin/update-subscription', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                    setTimeout(() => {
                        location.reload();
                    }, 2000);
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Update failed: ' + error.message, 'error');
            }
        }
        
        // Reset usage
        async function resetUsage(username) {
            if (!confirm(`Reset usage statistics for ${username}?`)) {
                return;
            }
            
            // This would require an API endpoint
            showToast('Feature coming soon', 'info');
        }
        
        // Cleanup files
        async function cleanupFiles() {
            if (!confirm('Cleanup temporary files and cache?')) {
                return;
            }
            
            try {
                const response = await fetch('/api/cleanup', {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Cleanup failed: ' + error.message, 'error');
            }
        }
        
        // Cleanup all
        async function cleanupAll() {
            if (!confirm('WARNING: This will delete ALL temporary files and cache. Continue?')) {
                return;
            }
            
            try {
                const response = await fetch('/api/cleanup/all', {
                    method: 'POST'
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast(result.message, 'success');
                } else {
                    showToast(result.message, 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Cleanup failed: ' + error.message, 'error');
            }
        }
        
        // Format date
        function formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
        
        // Format number
        function formatNumber(num) {
            return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        }
        
        // Update system info
        function updateSystemInfo() {
            // Server time
            const now = new Date();
            document.getElementById('serverTime').textContent = now.toLocaleString();
            
            // Simulate disk and memory usage (in a real app, you'd fetch this from an API)
            const diskUsage = Math.floor(Math.random() * 30) + 10;
            const memoryUsage = Math.floor(Math.random() * 40) + 20;
            
            document.getElementById('diskUsage').textContent = `${diskUsage}%`;
            document.getElementById('memoryUsage').textContent = `${memoryUsage}%`;
        }
        
        // Apply formatting
        document.addEventListener('DOMContentLoaded', function() {
            // Format numbers
            document.querySelectorAll('h3').forEach(el => {
                if (el.textContent.match(/^\d+$/)) {
                    el.textContent = formatNumber(parseInt(el.textContent));
                }
            });
            
            // Format dates
            document.querySelectorAll('td').forEach(el => {
                if (el.textContent.match(/\d{4}-\d{2}-\d{2}T/)) {
                    el.textContent = formatDate(el.textContent);
                }
            });
            
            // Update system info
            updateSystemInfo();
            setInterval(updateSystemInfo, 60000); // Update every minute
        });
        
        // Toast function
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
    
    with open(os.path.join(templates_dir, "admin.html"), "w", encoding="utf-8") as f:
        f.write(admin_html)
    
    # Create upgrade.html
    upgrade_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upgrade Plan - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .pricing-card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            transition: transform 0.3s;
            margin-bottom: 20px;
        }
        .pricing-card:hover {
            transform: translateY(-10px);
        }
        .pricing-header {
            padding: 2rem;
            border-radius: 10px 10px 0 0;
            color: white;
        }
        .free-header {
            background: linear-gradient(135deg, #6c757d 0%, #495057 100%);
        }
        .premium-header {
            background: linear-gradient(135deg, #4361ee 0%, #3a0ca3 100%);
        }
        .pro-header {
            background: linear-gradient(135deg, #f72585 0%, #b5179e 100%);
        }
        .feature-list {
            list-style: none;
            padding: 0;
        }
        .feature-list li {
            padding: 0.5rem 0;
            border-bottom: 1px solid #dee2e6;
        }
        .feature-list li:last-child {
            border-bottom: none;
        }
        .feature-list li i {
            margin-right: 0.5rem;
        }
        .feature-available {
            color: #28a745;
        }
        .feature-unavailable {
            color: #dc3545;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h2 class="text-center mb-4">Upgrade Your Plan</h2>
        <p class="text-center text-muted mb-5">Choose the plan that's right for you</p>
        
        <div class="row">
            <!-- Free Plan -->
            <div class="col-md-4">
                <div class="pricing-card">
                    <div class="pricing-header free-header text-center">
                        <h3>Free</h3>
                        <h2>$0</h2>
                        <p class="mb-0">Forever</p>
                    </div>
                    <div class="card-body">
                        <ul class="feature-list">
                            <li><i class="fas fa-check feature-available"></i> Single Voice TTS</li>
                            <li><i class="fas fa-check feature-available"></i> Basic Audio Effects</li>
                            <li><i class="fas fa-check feature-available"></i> 30,000 characters/week</li>
                            <li><i class="fas fa-times feature-unavailable"></i> Multi-Voice TTS</li>
                            <li><i class="fas fa-times feature-unavailable"></i> Q&A Dialogue</li>
                            <li><i class="fas fa-times feature-unavailable"></i> Priority Support</li>
                        </ul>
                        {% if user.subscription.plan == 'free' %}
                        <button class="btn btn-outline-secondary w-100" disabled>Current Plan</button>
                        {% else %}
                        <button class="btn btn-outline-secondary w-100" onclick="downgradeToFree()">Select Free</button>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <!-- Premium Plan -->
            <div class="col-md-4">
                <div class="pricing-card">
                    <div class="pricing-header premium-header text-center">
                        <h3>Premium</h3>
                        <h2>$9.99</h2>
                        <p class="mb-0">per month</p>
                    </div>
                    <div class="card-body">
                        <ul class="feature-list">
                            <li><i class="fas fa-check feature-available"></i> All Voices</li>
                            <li><i class="fas fa-check feature-available"></i> Multi-Voice TTS</li>
                            <li><i class="fas fa-check feature-available"></i> Q&A Dialogue</li>
                            <li><i class="fas fa-check feature-available"></i> 1M characters/month</li>
                            <li><i class="fas fa-check feature-available"></i> Advanced Audio Effects</li>
                            <li><i class="fas fa-times feature-unavailable"></i> Unlimited Characters</li>
                        </ul>
                        {% if user.subscription.plan == 'premium' %}
                        <button class="btn btn-primary w-100" disabled>Current Plan</button>
                        {% else %}
                        <button class="btn btn-primary w-100" onclick="upgradeToPremium()">Upgrade to Premium</button>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <!-- Pro Plan -->
            <div class="col-md-4">
                <div class="pricing-card">
                    <div class="pricing-header pro-header text-center">
                        <h3>Pro</h3>
                        <h2>$29.99</h2>
                        <p class="mb-0">per month</p>
                    </div>
                    <div class="card-body">
                        <ul class="feature-list">
                            <li><i class="fas fa-check feature-available"></i> Unlimited Characters</li>
                            <li><i class="fas fa-check feature-available"></i> All Features</li>
                            <li><i class="fas fa-check feature-available"></i> Priority Support</li>
                            <li><i class="fas fa-check feature-available"></i> Advanced Audio Processing</li>
                            <li><i class="fas fa-check feature-available"></i> Batch Processing</li>
                            <li><i class="fas fa-check feature-available"></i> Custom Voice Training</li>
                        </ul>
                        {% if user.subscription.plan == 'pro' %}
                        <button class="btn btn-danger w-100" disabled>Current Plan</button>
                        {% else %}
                        <button class="btn btn-danger w-100" onclick="upgradeToPro()">Upgrade to Pro</button>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
        
        <div class="card mt-5">
            <div class="card-body">
                <h4 class="card-title">Current Plan Details</h4>
                <table class="table">
                    <tr>
                        <th>Current Plan:</th>
                        <td>{{ user.subscription.plan|title }}</td>
                    </tr>
                    <tr>
                        <th>Expires:</th>
                        <td>{{ user.subscription.expires_at|datetimeformat }}</td>
                    </tr>
                    <tr>
                        <th>Characters Used:</th>
                        <td>{{ user.usage.characters_used }} / {{ user.subscription.characters_limit }}</td>
                    </tr>
                    <tr>
                        <th>Available Features:</th>
                        <td>
                            {% for feature in user.subscription.features %}
                            <span class="badge bg-success me-1">{{ feature|title }}</span>
                            {% endfor %}
                        </td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div class="text-center mt-4">
            <a href="/dashboard" class="btn btn-outline-secondary">
                <i class="fas fa-arrow-left me-2"></i>Back to Dashboard
            </a>
        </div>
    </div>
    
    <div class="toast-container position-fixed top-0 end-0 p-3"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Upgrade functions
        async function upgradeToPremium() {
            if (!confirm('Upgrade to Premium plan for $9.99/month?')) {
                return;
            }
            
            // In a real application, you would integrate with a payment gateway
            // For now, we'll show a message
            showToast('Payment integration coming soon. Contact admin to upgrade.', 'info');
        }
        
        async function upgradeToPro() {
            if (!confirm('Upgrade to Pro plan for $29.99/month?')) {
                return;
            }
            
            // In a real application, you would integrate with a payment gateway
            // For now, we'll show a message
            showToast('Payment integration coming soon. Contact admin to upgrade.', 'info');
        }
        
        async function downgradeToFree() {
            if (!confirm('Downgrade to Free plan? You will lose premium features.')) {
                return;
            }
            
            // In a real application, you would handle downgrade
            // For now, we'll show a message
            showToast('Contact admin to downgrade your plan.', 'info');
        }
        
        // Format date
        function formatDate(dateString) {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        }
        
        // Apply date formatting
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('td').forEach(el => {
                if (el.textContent.match(/\d{4}-\d{2}-\d{2}T/)) {
                    el.textContent = formatDate(el.textContent);
                }
            });
        });
        
        // Toast function
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
    
    with open(os.path.join(templates_dir, "upgrade.html"), "w", encoding="utf-8") as f:
        f.write(upgrade_html)
    
    # Create qa_tts.html (similar to multi_tts.html but for Q&A)
    qa_tts_html = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Q&A TTS - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .container {
            max-width: 1200px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
        .voice-card {
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: #f8f9fa;
        }
        .character-tag {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        .q-tag { background: #e8f5e9; color: #388e3c; }
        .a-tag { background: #fff3e0; color: #f57c00; }
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
            border-top: 5px solid #4361ee;
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
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">
                <i class="fas fa-microphone-alt me-2"></i>TTS Generator
            </a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/tts" class="btn btn-outline-secondary btn-sm me-2">Single Voice</a>
                <a href="/multi-tts" class="btn btn-outline-secondary btn-sm me-2">Multi-Voice</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h2><i class="fas fa-comments me-2"></i>Q&A Dialogue TTS</h2>
        
        {% if not can_access %}
        <div class="alert alert-danger">
            {{ access_message }}
        </div>
        {% endif %}
        
        <div class="card">
            <div class="card-body">
                <form id="qaTTSForm">
                    <div class="mb-3">
                        <label class="form-label">Q&A Content</label>
                        <textarea class="form-control" id="text" rows="8" 
                                  placeholder="Q: Question text&#10;A: Answer text&#10;Q: Next question&#10;A: Next answer"></textarea>
                        <small class="text-muted">Use Q: for questions and A: for answers. Maximum 10 Q&A pairs.</small>
                        <div class="mt-1 text-end">
                            <small id="charCount">0 characters</small>
                        </div>
                    </div>
                    
                    <div class="row">
                        <!-- Question Settings -->
                        <div class="col-md-6">
                            <div class="voice-card">
                                <h5><span class="character-tag q-tag">QUESTION</span></h5>
                                
                                <div class="mb-3">
                                    <label class="form-label">Language</label>
                                    <select class="form-select" id="questionLanguage" required>
                                        <option value="">Select Language</option>
                                        {% for language in languages %}
                                        <option value="{{ language }}">{{ language }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Voice</label>
                                    <select class="form-select" id="questionVoice" required disabled>
                                        <option value="">Select Voice</option>
                                    </select>
                                </div>
                                
                                <div class="row">
                                    <div class="col-4">
                                        <label class="form-label small">Speed</label>
                                        <input type="range" class="form-range" id="questionRate" min="-30" max="30" value="0">
                                        <small class="d-block text-center"><span id="questionRateValue">0%</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Pitch</label>
                                        <input type="range" class="form-range" id="questionPitch" min="-30" max="30" value="0">
                                        <small class="d-block text-center"><span id="questionPitchValue">0Hz</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Volume</label>
                                        <input type="range" class="form-range" id="questionVolume" min="50" max="150" value="100">
                                        <small class="d-block text-center"><span id="questionVolumeValue">100%</span></small>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Answer Settings -->
                        <div class="col-md-6">
                            <div class="voice-card">
                                <h5><span class="character-tag a-tag">ANSWER</span></h5>
                                
                                <div class="mb-3">
                                    <label class="form-label">Language</label>
                                    <select class="form-select" id="answerLanguage" required>
                                        <option value="">Select Language</option>
                                        {% for language in languages %}
                                        <option value="{{ language }}">{{ language }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Voice</label>
                                    <select class="form-select" id="answerVoice" required disabled>
                                        <option value="">Select Voice</option>
                                    </select>
                                </div>
                                
                                <div class="row">
                                    <div class="col-4">
                                        <label class="form-label small">Speed</label>
                                        <input type="range" class="form-range" id="answerRate" min="-30" max="30" value="-10">
                                        <small class="d-block text-center"><span id="answerRateValue">-10%</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Pitch</label>
                                        <input type="range" class="form-range" id="answerPitch" min="-30" max="30" value="0">
                                        <small class="d-block text-center"><span id="answerPitchValue">0Hz</span></small>
                                    </div>
                                    <div class="col-4">
                                        <label class="form-label small">Volume</label>
                                        <input type="range" class="form-range" id="answerVolume" min="50" max="150" value="100">
                                        <small class="d-block text-center"><span id="answerVolumeValue">100%</span></small>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Q&A Settings -->
                    <div class="row mt-3">
                        <div class="col-md-4">
                            <label class="form-label">
                                Pause After Question: <span id="pauseQValue">200ms</span>
                            </label>
                            <input type="range" class="form-range" id="pauseQ" min="100" max="1000" value="200">
                        </div>
                        
                        <div class="col-md-4">
                            <label class="form-label">
                                Pause After Answer: <span id="pauseAValue">500ms</span>
                            </label>
                            <input type="range" class="form-range" id="pauseA" min="100" max="2000" value="500">
                        </div>
                        
                        <div class="col-md-4">
                            <label class="form-label">
                                Repeat Times: <span id="repeatValue">2</span>
                            </label>
                            <input type="range" class="form-range" id="repeat" min="1" max="5" value="2">
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Output Format</label>
                        <select class="form-select" id="format">
                            {% for format in formats %}
                            <option value="{{ format }}">{{ format|upper }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100" {% if not can_access %}disabled{% endif %}>
                        <i class="fas fa-play-circle me-2"></i>Generate Q&A Audio
                    </button>
                </form>
                
                <div class="mt-3 text-center">
                    <small class="text-muted">Processing may take a few moments</small>
                </div>
                
                <div class="task-status" id="taskStatus">
                    <div class="progress-container">
                        <div class="progress">
                            <div class="progress-bar" id="progressBar" style="width: 0%"></div>
                        </div>
                        <div class="text-center mt-2" id="progressText">0%</div>
                    </div>
                    <div id="taskMessage"></div>
                </div>
                
                <div id="result" class="mt-3" style="display: none;">
                    <h5>Generated Q&A Audio</h5>
                    <audio controls class="w-100" id="audioPlayer"></audio>
                    <div class="mt-2">
                        <a href="#" class="btn btn-success me-2" id="downloadBtn">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="downloadSubtitleBtn" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
    </div>
    
    <div class="toast-container"></div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentTaskId = null;
        let taskCheckInterval = null;
        
        // Load voices for questions
        async function loadQuestionVoices(language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('questionVoice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                voiceSelect.disabled = false;
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Auto-select Vietnamese female voice if available
                const viVoice = data.voices.find(v => v.name === 'vi-VN-HoaiMyNeural');
                if (viVoice) {
                    voiceSelect.value = viVoice.name;
                }
            } catch (error) {
                console.error('Error loading voices for questions:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Load voices for answers
        async function loadAnswerVoices(language) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const voiceSelect = document.getElementById('answerVoice');
                voiceSelect.innerHTML = '<option value="">Select Voice</option>';
                voiceSelect.disabled = false;
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender})`;
                    voiceSelect.appendChild(option);
                });
                
                // Auto-select Vietnamese male voice if available
                const viVoice = data.voices.find(v => v.name === 'vi-VN-NamMinhNeural');
                if (viVoice) {
                    voiceSelect.value = viVoice.name;
                }
            } catch (error) {
                console.error('Error loading voices for answers:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Update character count
        function updateCharCount() {
            const text = document.getElementById('text').value;
            const charCount = text.replace(/\s/g, '').length;
            document.getElementById('charCount').textContent = `${charCount} characters`;
        }
        
        // Initialize range displays
        function initRangeDisplays() {
            // Question ranges
            const questionRanges = [
                { id: 'questionRate', display: 'questionRateValue', suffix: '%' },
                { id: 'questionPitch', display: 'questionPitchValue', suffix: 'Hz' },
                { id: 'questionVolume', display: 'questionVolumeValue', suffix: '%' }
            ];
            
            questionRanges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // Answer ranges
            const answerRanges = [
                { id: 'answerRate', display: 'answerRateValue', suffix: '%' },
                { id: 'answerPitch', display: 'answerPitchValue', suffix: 'Hz' },
                { id: 'answerVolume', display: 'answerVolumeValue', suffix: '%' }
            ];
            
            answerRanges.forEach(range => {
                const input = document.getElementById(range.id);
                const display = document.getElementById(range.display);
                
                if (input && display) {
                    display.textContent = input.value + range.suffix;
                    input.addEventListener('input', () => {
                        display.textContent = input.value + range.suffix;
                    });
                }
            });
            
            // Q&A ranges
            const qaRanges = [
                { id: 'pauseQ', display: 'pauseQValue', suffix: 'ms' },
                { id: 'pauseA', display: 'pauseAValue', suffix: 'ms' },
                { id: 'repeat', display: 'repeatValue', suffix: 'x' }
            ];
            
            qaRanges.forEach(range => {
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
        
        // Form submission
        document.getElementById('qaTTSForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const text = document.getElementById('text').value;
            const questionLanguage = document.getElementById('questionLanguage').value;
            const questionVoice = document.getElementById('questionVoice').value;
            const answerLanguage = document.getElementById('answerLanguage').value;
            const answerVoice = document.getElementById('answerVoice').value;
            const format = document.getElementById('format').value;
            
            if (!text.trim()) {
                showToast('Please enter Q&A text', 'error');
                return;
            }
            
            if (!questionLanguage || !questionVoice) {
                showToast('Please select language and voice for Questions', 'error');
                return;
            }
            
            if (!answerLanguage || !answerVoice) {
                showToast('Please select language and voice for Answers', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('question_language', questionLanguage);
            formData.append('question_voice', questionVoice);
            formData.append('question_rate', document.getElementById('questionRate').value);
            formData.append('question_pitch', document.getElementById('questionPitch').value);
            formData.append('question_volume', document.getElementById('questionVolume').value);
            formData.append('answer_language', answerLanguage);
            formData.append('answer_voice', answerVoice);
            formData.append('answer_rate', document.getElementById('answerRate').value);
            formData.append('answer_pitch', document.getElementById('answerPitch').value);
            formData.append('answer_volume', document.getElementById('answerVolume').value);
            formData.append('pause_q', document.getElementById('pauseQ').value);
            formData.append('pause_a', document.getElementById('pauseA').value);
            formData.append('repeat', document.getElementById('repeat').value);
            formData.append('output_format', format);
            
            try {
                const response = await fetch('/api/generate/qa', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    currentTaskId = result.task_id;
                    showTaskStatus(result.task_id);
                    showToast('Q&A audio generation started', 'success');
                } else {
                    showToast(result.message || 'Generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        });
        
        // Show task status and poll for updates
        function showTaskStatus(taskId) {
            const statusDiv = document.getElementById('taskStatus');
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const taskMessage = document.getElementById('taskMessage');
            
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
                    
                    if (task.success) {
                        progressBar.style.width = `${task.progress}%`;
                        progressText.textContent = `${task.progress}%`;
                        taskMessage.textContent = task.message;
                        
                        if (task.status === 'completed') {
                            clearInterval(taskCheckInterval);
                            
                            if (task.result && task.result.success) {
                                showToast(task.result.message, 'success');
                                
                                // Show output
                                showOutput(task.result);
                            }
                            
                            // Hide status after 5 seconds
                            setTimeout(() => {
                                statusDiv.style.display = 'none';
                            }, 5000);
                        } else if (task.status === 'failed') {
                            clearInterval(taskCheckInterval);
                            showToast(task.message, 'error');
                            
                            // Hide status after 3 seconds
                            setTimeout(() => {
                                statusDiv.style.display = 'none';
                            }, 3000);
                        }
                    }
                } catch (error) {
                    console.error('Error checking task status:', error);
                }
            }, 2000);
        }
        
        // Show output
        function showOutput(result) {
            const resultDiv = document.getElementById('result');
            const audioPlayer = document.getElementById('audioPlayer');
            const downloadBtn = document.getElementById('downloadBtn');
            const downloadSubtitleBtn = document.getElementById('downloadSubtitleBtn');
            
            // Add timestamp to avoid cache
            const timestamp = new Date().getTime();
            const audioUrl = `${result.audio_url}?t=${timestamp}`;
            
            audioPlayer.innerHTML = `
                <source src="${audioUrl}" type="audio/mpeg">
                Your browser does not support the audio element.
            `;
            audioPlayer.load();
            
            downloadBtn.href = result.audio_url;
            downloadBtn.download = `tts_qa_audio_${Date.now()}.mp3`;
            
            if (result.srt_url) {
                downloadSubtitleBtn.href = result.srt_url;
                downloadSubtitleBtn.download = `tts_qa_subtitle_${Date.now()}.srt`;
                downloadSubtitleBtn.style.display = 'inline-block';
            } else {
                downloadSubtitleBtn.style.display = 'none';
            }
            
            resultDiv.style.display = 'block';
            
            // Scroll to output
            resultDiv.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Event listeners
        document.getElementById('questionLanguage').addEventListener('change', function() {
            loadQuestionVoices(this.value);
        });
        
        document.getElementById('answerLanguage').addEventListener('change', function() {
            loadAnswerVoices(this.value);
        });
        
        document.getElementById('text').addEventListener('input', updateCharCount);
        
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
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            initRangeDisplays();
            updateCharCount();
            
            // Auto-select Vietnamese for both
            const viLanguage = 'Vietnamese';
            document.getElementById('questionLanguage').value = viLanguage;
            document.getElementById('answerLanguage').value = viLanguage;
            
            // Load voices
            loadQuestionVoices(viLanguage);
            loadAnswerVoices(viLanguage);
        });
    </script>
</body>
</html>"""
    
    with open(os.path.join(templates_dir, "qa_tts.html"), "w", encoding="utf-8") as f:
        f.write(qa_tts_html)
    
    print("All template files created successfully")

# ==================== RUN APPLICATION ====================
if __name__ == "__main__":
    # Create required directories
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("audio_cache", exist_ok=True)
    
    # Get port from environment variable
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("PROFESSIONAL TTS GENERATOR WITH USER MANAGEMENT")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Admin credentials: admin / admin123")
    print(f"Open http://localhost:{port} in your browser")
    print("=" * 60)
    
    # Run with uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
