# app.py - Professional TTS Generator with User Management
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
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range
import webvtt
import natsort
import uvicorn
import glob
import shutil
import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from sqlitedict import SqliteDict

# ==================== DATABASE CONFIGURATION ====================
class Database:
    def __init__(self):
        self.users_db = SqliteDict("users.db", autocommit=True)
        self.sessions_db = SqliteDict("sessions.db", autocommit=True)
        self.usage_db = SqliteDict("usage.db", autocommit=True)
    
    def init_admin_user(self):
        """Initialize admin user if not exists"""
        if "admin" not in self.users_db:
            admin_user = {
                "username": "admin",
                "password": self.hash_password("admin123"),
                "email": "admin@tts.com",
                "full_name": "Administrator",
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "subscription": {
                    "plan": "premium",
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
            self.users_db["admin"] = admin_user
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA256 with salt"""
        salt = "tts_system_2024"
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password) == hashed_password
    
    def create_user(self, username: str, password: str, email: str, full_name: str = ""):
        """Create new user"""
        if username in self.users_db:
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
                "features": ["single"]  # Only single voice for free tier
            },
            "usage": {
                "characters_used": 0,
                "last_reset": datetime.now().isoformat(),
                "total_requests": 0
            }
        }
        
        self.users_db[username] = user_data
        return True, "User created successfully"
    
    def authenticate_user(self, username: str, password: str):
        """Authenticate user"""
        if username not in self.users_db:
            return None
        
        user_data = self.users_db[username]
        if self.verify_password(password, user_data["password"]):
            return user_data
        return None
    
    def create_session(self, username: str) -> str:
        """Create session token"""
        session_token = secrets.token_urlsafe(32)
        session_data = {
            "username": username,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        self.sessions_db[session_token] = session_data
        return session_token
    
    def validate_session(self, session_token: str):
        """Validate session token"""
        if session_token not in self.sessions_db:
            return None
        
        session_data = self.sessions_db[session_token]
        # Check if session is expired (24 hours)
        created_at = datetime.fromisoformat(session_data["created_at"])
        if datetime.now() - created_at > timedelta(hours=24):
            del self.sessions_db[session_token]
            return None
        
        # Update last activity
        session_data["last_activity"] = datetime.now().isoformat()
        self.sessions_db[session_token] = session_data
        
        return session_data["username"]
    
    def delete_session(self, session_token: str):
        """Delete session"""
        if session_token in self.sessions_db:
            del self.sessions_db[session_token]
    
    def get_user(self, username: str):
        """Get user data"""
        return self.users_db.get(username)
    
    def update_user(self, username: str, user_data: dict):
        """Update user data"""
        if username in self.users_db:
            self.users_db[username] = user_data
            return True
        return False
    
    def record_usage(self, username: str, characters_used: int):
        """Record usage for user"""
        if username in self.users_db:
            user_data = self.users_db[username]
            
            # Reset weekly usage if needed
            last_reset = datetime.fromisoformat(user_data["usage"]["last_reset"])
            if datetime.now() - last_reset > timedelta(days=7):
                user_data["usage"]["characters_used"] = 0
                user_data["usage"]["last_reset"] = datetime.now().isoformat()
            
            # Update usage
            user_data["usage"]["characters_used"] += characters_used
            user_data["usage"]["total_requests"] += 1
            
            self.users_db[username] = user_data
    
    def can_user_use_feature(self, username: str, feature: str) -> Tuple[bool, str]:
        """Check if user can use a feature"""
        if username not in self.users_db:
            return False, "User not found"
        
        user_data = self.users_db[username]
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
        return {username: self.users_db[username] for username in self.users_db.keys()}
    
    def update_subscription(self, username: str, plan: str, days: int = 30):
        """Update user subscription"""
        if username not in self.users_db:
            return False
        
        user_data = self.users_db[username]
        
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
        
        self.users_db[username] = user_data
        return True
    
    def close(self):
        """Close database connections"""
        self.users_db.close()
        self.sessions_db.close()
        self.usage_db.close()

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
        raise HTTPException(status_code=403, detail="Admin access required")
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
        self.executor = ThreadPoolExecutor(max_workers=2)  # Giảm workers cho Render
    
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
        key_string = f"{text}_{voice_id}_{rate}_{pitch}_{volume}"
        return hashlib.md5(key_string.encode()).hexdigest()[:12]
    
    def get_cached_audio(self, cache_key: str) -> Optional[str]:
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.mp3")
        if os.path.exists(cache_file):
            file_age = time.time() - os.path.getmtime(cache_file)
            if file_age < 86400:
                return cache_file
        return None
    
    def save_to_cache(self, cache_key: str, audio_file: str):
        try:
            cache_files = os.listdir(self.cache_dir)
            if len(cache_files) >= self.max_cache_size:
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
            self.save_settings()
    
    def save_settings(self):
        with open(TTSConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, pitch: int = 0, volume: int = 100):
        """Generate speech using edge-tts with cache optimization"""
        try:
            cache_key = self.cache_manager.get_cache_key(text, voice_id, rate, pitch, volume)
            cached_file = self.cache_manager.get_cached_audio(cache_key)
            
            if cached_file:
                temp_file = f"temp/cache_{uuid.uuid4().hex[:8]}.mp3"
                shutil.copy(cached_file, temp_file)
                return temp_file, []
            
            unique_id = uuid.uuid4().hex[:8]
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
            temp_file = f"temp/audio_{unique_id}_{int(time.time())}.mp3"
            
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            try:
                audio = AudioSegment.from_file(temp_file)
                volume_adjustment = min(max(volume - 100, -50), 10)
                audio = audio + volume_adjustment
                audio = normalize(audio)
                audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
                audio.export(temp_file, format="mp3", bitrate="256k")
                
                self.cache_manager.save_to_cache(cache_key, temp_file)
                
                return temp_file, subtitles
            except Exception as e:
                print(f"Error processing audio: {e}")
                return temp_file, subtitles
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None, []
    
    async def process_single_voice(self, text: str, voice_id: str, rate: int, pitch: int, 
                                 volume: int, pause: int, output_format: str = "mp3", task_id: str = None):
        """Process text with single voice"""
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_dir = f"outputs/single_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        sentences = self.text_processor.split_sentences(text)
        MAX_SENTENCES = 50
        if len(sentences) > MAX_SENTENCES:
            sentences = sentences[:MAX_SENTENCES]
        
        audio_segments = []
        all_subtitles = []
        
        for i, sentence in enumerate(sentences):
            if task_id and task_manager:
                progress = int((i / len(sentences)) * 90)
                task_manager.update_task(task_id, progress=progress, 
                                       message=f"Processing sentence {i+1}/{len(sentences)}")
            
            temp_file, subs = await self.generate_speech(sentence, voice_id, rate, pitch, volume)
            
            if temp_file:
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
        
        output_file = os.path.join(output_dir, f"single_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        srt_file = self.generate_srt(all_subtitles, output_file)
        
        if task_id and task_manager:
            task_manager.update_task(task_id, progress=100, 
                                   message="Audio generation completed")
        
        return output_file, srt_file
    
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
    
    def cleanup_temp_files(self):
        """Clean temporary files"""
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

# ==================== APPLICATION INITIALIZATION ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    print("Starting up TTS Generator with User Management...")
    
    global tts_processor, task_manager
    tts_processor = TTSProcessor()
    task_manager = TaskManager()
    
    tts_processor.cleanup_temp_files()
    task_manager.cleanup_old_tasks(1)
    
    create_template_file()
    
    yield
    
    print("Shutting down TTS Generator...")
    tts_processor.cleanup_temp_files()
    if hasattr(task_manager, 'executor'):
        task_manager.executor.shutdown(wait=False)
    database.close()

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="Professional TTS Generator with User Management", 
    version="3.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """Home page - redirects to dashboard if logged in"""
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
    user_data = database.authenticate_user(username, password)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
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
        max_age=86400,  # 24 hours
        secure=False,  # Set to True in production with HTTPS
        samesite="lax"
    )
    
    return response

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
    success, message = database.create_user(username, password, email, full_name)
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}

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
    user = await require_login(request)
    
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
        "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS
    })

@app.get("/tts", response_class=HTMLResponse)
async def tts_page(request: Request):
    """Main TTS page with tabs"""
    user = await require_login(request)
    
    # Check if user can access TTS features
    can_access, message = database.can_user_use_feature(user["username"], "single")
    
    return templates.TemplateResponse("tts.html", {
        "request": request,
        "user": user,
        "languages": TTSConfig.LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS,
        "can_access": can_access,
        "access_message": message if not can_access else ""
    })

@app.get("/multi-voice", response_class=HTMLResponse)
async def multi_voice_page(request: Request):
    """Multi-voice page"""
    user = await require_login(request)
    
    # Check if user can access multi-voice
    can_access, message = database.can_user_use_feature(user["username"], "multi")
    
    if not can_access:
        return templates.TemplateResponse("upgrade.html", {
            "request": request,
            "user": user,
            "feature": "Multi-Voice TTS",
            "message": message,
            "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS
        })
    
    return templates.TemplateResponse("multi_voice.html", {
        "request": request,
        "user": user,
        "languages": TTSConfig.LANGUAGES
    })

@app.get("/qa-dialogue", response_class=HTMLResponse)
async def qa_dialogue_page(request: Request):
    """Q&A Dialogue page"""
    user = await require_login(request)
    
    # Check if user can access Q&A dialogue
    can_access, message = database.can_user_use_feature(user["username"], "qa")
    
    if not can_access:
        return templates.TemplateResponse("upgrade.html", {
            "request": request,
            "user": user,
            "feature": "Q&A Dialogue TTS",
            "message": message,
            "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS
        })
    
    return templates.TemplateResponse("qa_dialogue.html", {
        "request": request,
        "user": user,
        "languages": TTSConfig.LANGUAGES
    })

@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """User profile page"""
    user = await require_login(request)
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS
    })

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """Admin dashboard"""
    admin_user = await require_admin(request)
    
    all_users = database.get_all_users()
    total_users = len(all_users)
    
    # Calculate statistics
    free_users = sum(1 for user in all_users.values() if user["subscription"]["plan"] == "free")
    premium_users = sum(1 for user in all_users.values() if user["subscription"]["plan"] == "premium")
    pro_users = sum(1 for user in all_users.values() if user["subscription"]["plan"] == "pro")
    
    total_characters = sum(user["usage"]["characters_used"] for user in all_users.values())
    total_requests = sum(user["usage"]["total_requests"] for user in all_users.values())
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "admin": admin_user,
        "users": all_users,
        "stats": {
            "total_users": total_users,
            "free_users": free_users,
            "premium_users": premium_users,
            "pro_users": pro_users,
            "total_characters": total_characters,
            "total_requests": total_requests
        }
    })

# ==================== TTS API ENDPOINTS ====================
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
    """Generate single voice TTS"""
    user = await require_login(request)
    
    # Count characters
    characters_used = TextProcessor.count_characters(text)
    
    # Check if user can use the feature and has enough quota
    can_access, message = database.can_user_use_feature(user["username"], "single")
    if not can_access:
        raise HTTPException(status_code=403, detail=message)
    
    # Record usage
    database.record_usage(user["username"], characters_used)
    
    # Create task
    task_id = f"single_{int(time.time())}_{random.randint(1000, 9999)}"
    task_manager.create_task(task_id, "single_voice", user["username"])
    
    # Save settings
    tts_processor.settings["single_voice"] = {
        "voice": voice_id,
        "rate": rate,
        "pitch": pitch,
        "volume": volume,
        "pause": pause
    }
    tts_processor.save_settings()
    
    # Background task
    async def background_task():
        try:
            audio_file, srt_file = await tts_processor.process_single_voice(
                text, voice_id, rate, pitch, volume, pause, output_format, task_id
            )
            
            if audio_file:
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
    
    asyncio.create_task(background_task())
    
    return {
        "success": True,
        "task_id": task_id,
        "characters_used": characters_used,
        "message": "Audio generation started. Check task status."
    }

@app.post("/api/generate/multi")
async def generate_multi_voice(
    request: Request,
    text: str = Form(...),
    char1_voice: str = Form(...),
    char2_voice: str = Form(...),
    pause: int = Form(500),
    repeat: int = Form(1),
    output_format: str = Form("mp3")
):
    """Generate multi-voice TTS"""
    user = await require_login(request)
    
    # Check if user can access multi-voice
    can_access, message = database.can_user_use_feature(user["username"], "multi")
    if not can_access:
        raise HTTPException(status_code=403, detail=message)
    
    # Count characters
    characters_used = TextProcessor.count_characters(text)
    
    # Record usage
    database.record_usage(user["username"], characters_used)
    
    # Create task
    task_id = f"multi_{int(time.time())}_{random.randint(1000, 9999)}"
    task_manager.create_task(task_id, "multi_voice", user["username"])
    
    # This is a simplified version - you should expand it to handle actual multi-voice
    async def background_task():
        try:
            # For now, just use single voice generation
            # You should implement actual multi-voice generation here
            audio_file, srt_file = await tts_processor.process_single_voice(
                text, char1_voice, 0, 0, 100, pause, output_format, task_id
            )
            
            if audio_file:
                result = {
                    "success": True,
                    "audio_url": f"/download/{os.path.basename(audio_file)}",
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
    
    return {
        "success": True,
        "task_id": task_id,
        "characters_used": characters_used,
        "message": "Multi-voice audio generation started"
    }

# ==================== USER MANAGEMENT API ====================
@app.get("/api/user/info")
async def get_user_info(request: Request):
    """Get current user info"""
    user = await require_login(request)
    return {
        "success": True,
        "user": {
            "username": user["username"],
            "email": user["email"],
            "full_name": user.get("full_name", ""),
            "role": user["role"],
            "subscription": user["subscription"],
            "usage": user["usage"]
        }
    }

@app.post("/api/user/update-profile")
async def update_profile(
    request: Request,
    full_name: str = Form(None),
    email: str = Form(None)
):
    """Update user profile"""
    user = await require_login(request)
    username = user["username"]
    
    if full_name:
        user["full_name"] = full_name
    if email:
        user["email"] = email
    
    database.update_user(username, user)
    
    return {"success": True, "message": "Profile updated successfully"}

@app.post("/api/user/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...)
):
    """Change user password"""
    user = await require_login(request)
    username = user["username"]
    
    # Verify current password
    if not database.verify_password(current_password, user["password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Update password
    user["password"] = database.hash_password(new_password)
    database.update_user(username, user)
    
    return {"success": True, "message": "Password changed successfully"}

# ==================== ADMIN API ====================
@app.post("/api/admin/update-subscription")
async def admin_update_subscription(
    request: Request,
    username: str = Form(...),
    plan: str = Form(...),
    days: int = Form(30)
):
    """Admin: Update user subscription"""
    admin_user = await require_admin(request)
    
    if plan not in ["free", "premium", "pro"]:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    success = database.update_subscription(username, plan, days)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "message": f"Subscription updated to {plan}"}

@app.post("/api/admin/reset-usage")
async def admin_reset_usage(
    request: Request,
    username: str = Form(...)
):
    """Admin: Reset user usage"""
    admin_user = await require_admin(request)
    
    user = database.get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user["usage"]["characters_used"] = 0
    user["usage"]["last_reset"] = datetime.now().isoformat()
    database.update_user(username, user)
    
    return {"success": True, "message": "Usage reset successfully"}

# ==================== UTILITY ENDPOINTS ====================
@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str, request: Request):
    """Get task status"""
    user = await require_login(request)
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Only allow user to see their own tasks (or admin)
    if user["role"] != "admin" and task["username"] != user["username"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
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
async def download_file(filename: str, request: Request):
    """Download generated files"""
    user = await require_login(request)
    
    file_path = None
    for root, dirs, files in os.walk("outputs"):
        if filename in files:
            file_path = os.path.join(root, filename)
            break
    
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.get("/api/languages")
async def get_languages(request: Request):
    """Get all available languages"""
    user = await require_login(request)
    languages = list(TTSConfig.LANGUAGES.keys())
    return {"languages": languages}

@app.get("/api/voices")
async def get_voices(language: str = None, request: Request = None):
    """Get available voices"""
    user = await get_current_user(request) if request else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    if language and language in TTSConfig.LANGUAGES:
        voices = TTSConfig.LANGUAGES[language]
    else:
        voices = []
        for lang_voices in TTSConfig.LANGUAGES.values():
            voices.extend(lang_voices)
    
    return {"voices": voices}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# ==================== HTML TEMPLATE CREATION ====================
def create_template_file():
    """Create HTML template files"""
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create index.html
    index_html = """
<!DOCTYPE html>
<html lang="vi">
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
        
        .hero-section {
            padding: 100px 0;
            color: white;
            text-align: center;
        }
        
        .hero-section h1 {
            font-size: 3.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
        }
        
        .hero-section p {
            font-size: 1.2rem;
            opacity: 0.9;
            margin-bottom: 2rem;
        }
        
        .feature-card {
            background: white;
            border-radius: 15px;
            padding: 2rem;
            margin: 1rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
        }
        
        .feature-card i {
            font-size: 2.5rem;
            color: var(--primary-color);
            margin-bottom: 1rem;
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
        
        .auth-buttons {
            position: absolute;
            top: 20px;
            right: 20px;
        }
    </style>
</head>
<body>
    <div class="auth-buttons">
        <a href="/login" class="btn btn-light me-2">Login</a>
        <a href="/register" class="btn btn-primary">Register</a>
    </div>
    
    <div class="hero-section">
        <div class="container">
            <h1><i class="fas fa-microphone-alt me-3"></i>Professional TTS Generator</h1>
            <p class="lead">Convert text to natural-sounding speech with multiple voices and languages</p>
            
            <div class="row mt-5">
                <div class="col-md-4">
                    <div class="feature-card">
                        <i class="fas fa-user"></i>
                        <h4>Single Voice</h4>
                        <p>Convert text to speech with a single natural voice</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <i class="fas fa-users"></i>
                        <h4>Multi-Voice</h4>
                        <p>Create dialogues with multiple characters (Premium)</p>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="feature-card">
                        <i class="fas fa-comments"></i>
                        <h4>Q&A Dialogue</h4>
                        <p>Generate question and answer conversations (Premium)</p>
                    </div>
                </div>
            </div>
            
            <div class="mt-5">
                <h3>Start with 30,000 free characters per week!</h3>
                <a href="/register" class="btn btn-primary btn-lg mt-3">
                    <i class="fas fa-rocket me-2"></i>Get Started Free
                </a>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
    """
    
    with open(os.path.join(templates_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    
    # Create login.html
    login_html = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .login-container {
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 400px;
            width: 100%;
            margin: 0 auto;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .login-header i {
            font-size: 3rem;
            color: #4361ee;
            margin-bottom: 1rem;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #4361ee, #3a0ca3);
            border: none;
            padding: 0.75rem;
            font-weight: 600;
            width: 100%;
        }
        
        .form-control:focus {
            border-color: #4361ee;
            box-shadow: 0 0 0 0.2rem rgba(67, 97, 238, 0.25);
        }
        
        .register-link {
            text-align: center;
            margin-top: 1.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="login-container">
            <div class="login-header">
                <i class="fas fa-microphone-alt"></i>
                <h2>Login to TTS Generator</h2>
                <p class="text-muted">Enter your credentials to continue</p>
            </div>
            
            <form id="loginForm">
                <div class="mb-3">
                    <label for="username" class="form-label">Username</label>
                    <input type="text" class="form-control" id="username" required>
                </div>
                
                <div class="mb-3">
                    <label for="password" class="form-label">Password</label>
                    <input type="password" class="form-control" id="password" required>
                </div>
                
                <button type="submit" class="btn btn-primary">
                    <i class="fas fa-sign-in-alt me-2"></i>Login
                </button>
            </form>
            
            <div class="register-link">
                <p class="mb-0">Don't have an account? <a href="/register">Register here</a></p>
                <p class="mt-2"><a href="/">Back to Home</a></p>
            </div>
            
            <div id="message" class="mt-3"></div>
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
                
                if (result.success) {
                    window.location.href = '/dashboard';
                } else {
                    document.getElementById('message').innerHTML = `
                        <div class="alert alert-danger">${result.message || 'Login failed'}</div>
                    `;
                }
            } catch (error) {
                document.getElementById('message').innerHTML = `
                    <div class="alert alert-danger">Network error: ${error.message}</div>
                `;
            }
        });
    </script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
    """
    
    with open(os.path.join(templates_dir, "login.html"), "w", encoding="utf-8") as f:
        f.write(login_html)
    
    # Create register.html (similar structure to login.html)
    # Create dashboard.html
    dashboard_html = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --primary-color: #4361ee;
            --secondary-color: #3a0ca3;
        }
        
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .sidebar {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            min-height: calc(100vh - 56px);
            padding-top: 2rem;
        }
        
        .sidebar a {
            color: rgba(255,255,255,0.8);
            padding: 0.75rem 1.5rem;
            display: block;
            text-decoration: none;
            transition: all 0.3s;
        }
        
        .sidebar a:hover, .sidebar a.active {
            background: rgba(255,255,255,0.1);
            color: white;
            padding-left: 2rem;
        }
        
        .sidebar a i {
            width: 20px;
            margin-right: 10px;
        }
        
        .main-content {
            padding: 2rem;
            background: #f8f9fa;
            min-height: calc(100vh - 56px);
        }
        
        .stat-card {
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }
        
        .stat-card i {
            font-size: 2.5rem;
            color: var(--primary-color);
            margin-bottom: 1rem;
        }
        
        .progress {
            height: 10px;
            margin-top: 10px;
        }
        
        .feature-card {
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            transition: transform 0.3s;
        }
        
        .feature-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }
        
        .feature-card.disabled {
            opacity: 0.6;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            border: none;
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
                <span class="me-3">Welcome, {{ user.username }}</span>
                <a href="/profile" class="btn btn-outline-primary btn-sm me-2">
                    <i class="fas fa-user"></i>
                </a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">
                    <i class="fas fa-sign-out-alt"></i>
                </a>
            </div>
        </div>
    </nav>
    
    <div class="container-fluid">
        <div class="row">
            <div class="col-md-3 col-lg-2 sidebar">
                <a href="/dashboard" class="active">
                    <i class="fas fa-home"></i> Dashboard
                </a>
                <a href="/tts">
                    <i class="fas fa-user"></i> Single Voice
                </a>
                <a href="/multi-voice">
                    <i class="fas fa-users"></i> Multi-Voice
                </a>
                <a href="/qa-dialogue">
                    <i class="fas fa-comments"></i> Q&A Dialogue
                </a>
                {% if user.role == 'admin' %}
                <a href="/admin">
                    <i class="fas fa-cog"></i> Admin Panel
                </a>
                {% endif %}
            </div>
            
            <div class="col-md-9 col-lg-10 main-content">
                <h2 class="mb-4">Dashboard</h2>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="stat-card">
                            <i class="fas fa-chart-bar"></i>
                            <h5>Usage Statistics</h5>
                            <p>{{ usage_text }}</p>
                            <div class="progress">
                                <div class="progress-bar bg-success" style="width: {{ usage_percentage }}%"></div>
                            </div>
                            <small>{{ usage_percentage|round(1) }}% used</small>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="stat-card">
                            <i class="fas fa-crown"></i>
                            <h5>Current Plan: {{ user.subscription.plan|title }}</h5>
                            <p>Expires: {{ user.subscription.expires_at[:10] }}</p>
                            <a href="/profile" class="btn btn-primary btn-sm">Upgrade Plan</a>
                        </div>
                    </div>
                </div>
                
                <h4 class="mt-4 mb-3">Available Features</h4>
                <div class="row">
                    <div class="col-md-4">
                        <div class="feature-card">
                            <h5><i class="fas fa-user text-primary me-2"></i>Single Voice</h5>
                            <p class="text-muted">Convert text to speech with a single voice</p>
                            <a href="/tts" class="btn btn-primary">Use Feature</a>
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="feature-card {% if 'multi' not in user.subscription.features %}disabled{% endif %}">
                            <h5><i class="fas fa-users {% if 'multi' in user.subscription.features %}text-primary{% else %}text-muted{% endif %} me-2"></i>Multi-Voice</h5>
                            <p class="text-muted">Create dialogues with multiple characters</p>
                            {% if 'multi' in user.subscription.features %}
                            <a href="/multi-voice" class="btn btn-primary">Use Feature</a>
                            {% else %}
                            <a href="/profile" class="btn btn-outline-primary">Upgrade to Use</a>
                            {% endif %}
                        </div>
                    </div>
                    
                    <div class="col-md-4">
                        <div class="feature-card {% if 'qa' not in user.subscription.features %}disabled{% endif %}">
                            <h5><i class="fas fa-comments {% if 'qa' in user.subscription.features %}text-primary{% else %}text-muted{% endif %} me-2"></i>Q&A Dialogue</h5>
                            <p class="text-muted">Generate question and answer conversations</p>
                            {% if 'qa' in user.subscription.features %}
                            <a href="/qa-dialogue" class="btn btn-primary">Use Feature</a>
                            {% else %}
                            <a href="/profile" class="btn btn-outline-primary">Upgrade to Use</a>
                            {% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
    """
    
    with open(os.path.join(templates_dir, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(dashboard_html)
    
    # Create tts.html (similar to single voice tab from original)
    # Create profile.html
    # Create admin.html
    # Create upgrade.html
    
    print("Templates created successfully")

# ==================== RUN APPLICATION ====================
def create_requirements_txt():
    """Create requirements.txt file"""
    requirements = """fastapi==0.104.1
uvicorn[standard]==0.24.0
edge-tts==6.1.9
pydub==0.25.1
webvtt-py==0.4.6
natsort==8.4.0
python-multipart==0.0.6
sqlitedict==2.1.0
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    print("requirements.txt created")

def create_runtime_txt():
    """Create runtime.txt for Python version"""
    runtime = "python-3.10.0"
    
    with open("runtime.txt", "w") as f:
        f.write(runtime)
    
    print("runtime.txt created")

if __name__ == "__main__":
    # Create necessary files for deployment
    create_requirements_txt()
    create_runtime_txt()
    
    # Get port from environment variable
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("PROFESSIONAL TTS GENERATOR WITH USER MANAGEMENT v3.0")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Open http://localhost:{port} in your browser")
    print("Admin credentials: admin / admin123")
    print("=" * 60)
    
    # Run with uvicorn with debug
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="debug",  # Thay đổi từ "info" thành "debug"
        reload=True,  # Bật reload để dễ debug
        access_log=True  # Bật access log
    ))
