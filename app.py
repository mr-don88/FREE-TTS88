# app.py - Professional TTS Generator with User Management (Fixed Version)
import asyncio
import json
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
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
import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor

# ==================== DATABASE SIMPLE (Using JSON files) ====================
class Database:
    def __init__(self):
        self.users_file = "users.json"
        self.sessions_file = "sessions.json"
        self.init_db()
    
    def init_db(self):
        """Initialize database files"""
        if not os.path.exists(self.users_file):
            with open(self.users_file, 'w') as f:
                json.dump({}, f)
        
        if not os.path.exists(self.sessions_file):
            with open(self.sessions_file, 'w') as f:
                json.dump({}, f)
    
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
            users["admin"] = admin_user
            self.save_users(users)

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

# ==================== TTS CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    # Giọng nói đơn giản hóa để test
    LANGUAGES = {
        "Vietnamese": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "👩Female", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "🤵Male", "display": "Nam Minh"}
        ],
        "English (US)": [
            {"name": "en-US-JennyNeural", "gender": "👩Female", "display": "Jenny (US)"},
            {"name": "en-US-GuyNeural", "gender": "🤵Male", "display": "Guy (US)"}
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
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences"""
        sentences = []
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped:
                sentences.append(stripped)
        return sentences

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.initialize_directories()
    
    def initialize_directories(self):
        """Initialize necessary directories"""
        directories = ["outputs", "temp", "static", "templates"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, pitch: int = 0, volume: int = 100):
        """Generate speech using edge-tts"""
        try:
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
            
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            if not audio_chunks:
                return None
            
            audio_data = b"".join(audio_chunks)
            temp_file = f"temp/audio_{unique_id}_{int(time.time())}.mp3"
            
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            return temp_file
            
        except Exception as e:
            print(f"Error generating speech: {str(e)}")
            return None
    
    async def process_single_voice(self, text: str, voice_id: str, rate: int, pitch: int, 
                                 volume: int, pause: int, output_format: str = "mp3"):
        """Process text with single voice"""
        # Clean up old temp files
        self.cleanup_temp_files()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/single_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        sentences = self.text_processor.split_sentences(text)
        
        audio_segments = []
        
        for sentence in sentences:
            temp_file = await self.generate_speech(sentence, voice_id, rate, pitch, volume)
            
            if temp_file:
                try:
                    audio = AudioSegment.from_file(temp_file)
                    audio_segments.append(audio)
                    
                    try:
                        os.remove(temp_file)
                    except:
                        pass
                except Exception as e:
                    print(f"Error processing audio segment: {str(e)}")
        
        if not audio_segments:
            return None
        
        # Combine audio segments
        combined = AudioSegment.empty()
        for i, audio in enumerate(audio_segments):
            combined += audio
            if i < len(audio_segments) - 1:
                combined += AudioSegment.silent(duration=pause)
        
        output_file = os.path.join(output_dir, f"single_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="192k")
        
        return output_file
    
    def cleanup_temp_files(self):
        """Clean temporary files"""
        try:
            temp_files = glob.glob("temp/*.mp3")
            for file in temp_files:
                try:
                    if os.path.exists(file):
                        os.remove(file)
                except:
                    pass
        except Exception as e:
            print(f"Error cleaning temp files: {str(e)}")

# ==================== LIFESPAN MANAGER ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    print("Starting up TTS Generator with User Management...")
    
    global tts_processor
    tts_processor = TTSProcessor()
    
    # Cleanup old files
    tts_processor.cleanup_temp_files()
    
    # Create template files
    create_template_files()
    
    yield
    
    print("Shutting down TTS Generator...")
    tts_processor.cleanup_temp_files()

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(
    title="Professional TTS Generator with User Management", 
    version="3.0.0",
    lifespan=lifespan
)

# Global instance
tts_processor = None

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==================== SIMPLE ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page"""
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
            "subscription_plans": TTSConfig.SUBSCRIPTION_PLANS
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
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
        # Count characters
        characters_used = TextProcessor.count_characters(text)
        
        # Check if user can use the feature
        can_access, message = database.can_user_use_feature(user["username"], "single")
        if not can_access:
            return JSONResponse(
                {"success": False, "message": message},
                status_code=403
            )
        
        # Record usage
        database.record_usage(user["username"], characters_used)
        
        # Generate audio
        audio_file = await tts_processor.process_single_voice(
            text, voice_id, rate, pitch, volume, pause, output_format
        )
        
        if audio_file:
            return JSONResponse({
                "success": True,
                "audio_url": f"/download/{os.path.basename(audio_file)}",
                "characters_used": characters_used,
                "message": "Audio generated successfully"
            })
        else:
            return JSONResponse({
                "success": False,
                "message": "Failed to generate audio"
            })
            
    except Exception as e:
        print(f"Generation error: {str(e)}")
        return JSONResponse(
            {"success": False, "message": f"Generation error: {str(e)}"},
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
        for root, dirs, files in os.walk("outputs"):
            if filename in files:
                file_path = os.path.join(root, filename)
                break
        
        if not file_path or not os.path.exists(file_path):
            return JSONResponse(
                {"success": False, "message": "File not found"},
                status_code=404
            )
        
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

@app.get("/api/languages")
async def get_languages(request: Request):
    """Get all available languages"""
    try:
        user = await get_current_user(request)
        if not user:
            return JSONResponse(
                {"success": False, "message": "Not authenticated"},
                status_code=401
            )
        
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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return JSONResponse({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ==================== TEMPLATE CREATION ====================
def create_template_files():
    """Create all template files"""
    templates_dir = "templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Create simple index.html
    index_html = """
<!DOCTYPE html>
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
</html>
    """
    
    with open(os.path.join(templates_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    
    # Create simple login.html
    login_html = """
<!DOCTYPE html>
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
</html>
    """
    
    with open(os.path.join(templates_dir, "login.html"), "w", encoding="utf-8") as f:
        f.write(login_html)
    
    # Create simple register.html
    register_html = """
<!DOCTYPE html>
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
</html>
    """
    
    with open(os.path.join(templates_dir, "register.html"), "w", encoding="utf-8") as f:
        f.write(register_html)
    
    # Create simple dashboard.html
    dashboard_html = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
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
        }
        .progress {
            height: 10px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">🎤 TTS Generator</a>
            <div class="d-flex">
                <span class="me-3">{{ user.username }}</span>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h2>Welcome, {{ user.username }}!</h2>
        
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Current Plan: {{ user.subscription.plan|upper }}</h5>
                        <p class="card-text">{{ usage_text }}</p>
                        <div class="progress">
                            <div class="progress-bar" style="width: {{ usage_percentage }}%"></div>
                        </div>
                        <small>{{ usage_percentage|round(1) }}% used</small>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Quick Actions</h5>
                        <a href="/tts" class="btn btn-primary w-100 mb-2">Single Voice TTS</a>
                        <a href="#" class="btn btn-outline-primary w-100 mb-2">Multi-Voice (Premium)</a>
                        <a href="#" class="btn btn-outline-primary w-100">Q&A Dialogue (Premium)</a>
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
                        <th>Plan:</th>
                        <td>{{ user.subscription.plan|title }}</td>
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
            </div>
        </div>
    </div>
</body>
</html>
    """
    
    with open(os.path.join(templates_dir, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(dashboard_html)
    
    # Create simple tts.html
    tts_html = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS - TTS Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: #f8f9fa;
        }
        .navbar {
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .container {
            max-width: 800px;
        }
        .card {
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light">
        <div class="container-fluid">
            <a class="navbar-brand" href="/dashboard">🎤 TTS Generator</a>
            <div class="d-flex">
                <a href="/dashboard" class="btn btn-outline-primary btn-sm me-2">Dashboard</a>
                <a href="/logout" class="btn btn-outline-danger btn-sm">Logout</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        <h2>Text to Speech Generator</h2>
        
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
                            </select>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label class="form-label">Voice</label>
                            <select class="form-select" id="voice" required disabled>
                                <option value="">Select Voice</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <label class="form-label">Output Format</label>
                        <select class="form-select" id="format">
                            <option value="mp3">MP3</option>
                            <option value="wav">WAV</option>
                        </select>
                    </div>
                    
                    <button type="submit" class="btn btn-primary w-100" {% if not can_access %}disabled{% endif %}>
                        Generate Audio
                    </button>
                </form>
                
                <div class="mt-3 text-center">
                    <small class="text-muted">Processing may take a few moments</small>
                </div>
                
                <div class="alert mt-3" id="message" style="display: none;"></div>
                
                <div id="result" class="mt-3" style="display: none;">
                    <h5>Generated Audio</h5>
                    <audio controls class="w-100" id="audioPlayer"></audio>
                    <div class="mt-2">
                        <a href="#" class="btn btn-success" id="downloadBtn">Download Audio</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Load languages
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
            }
        }
        
        // Update character count
        function updateCharCount() {
            const text = document.getElementById('text').value;
            const charCount = text.replace(/\s/g, '').length;
            document.getElementById('charCount').textContent = `${charCount} characters`;
        }
        
        // Form submission
        document.getElementById('ttsForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const text = document.getElementById('text').value;
            const voice = document.getElementById('voice').value;
            const format = document.getElementById('format').value;
            
            if (!text.trim()) {
                showMessage('Please enter text', 'danger');
                return;
            }
            
            if (!voice) {
                showMessage('Please select a voice', 'danger');
                return;
            }
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', '0');
            formData.append('pitch', '0');
            formData.append('volume', '100');
            formData.append('pause', '500');
            formData.append('output_format', format);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showMessage('Audio generated successfully!', 'success');
                    
                    // Show audio player
                    const audioPlayer = document.getElementById('audioPlayer');
                    audioPlayer.src = result.audio_url;
                    
                    // Set download link
                    const downloadBtn = document.getElementById('downloadBtn');
                    downloadBtn.href = result.audio_url;
                    downloadBtn.download = `tts_audio_${Date.now()}.${format}`;
                    
                    // Show result section
                    document.getElementById('result').style.display = 'block';
                } else {
                    showMessage(result.message || 'Generation failed', 'danger');
                }
            } catch (error) {
                showMessage('Network error. Please try again.', 'danger');
            }
        });
        
        // Event listeners
        document.getElementById('language').addEventListener('change', function() {
            loadVoices(this.value);
        });
        
        document.getElementById('text').addEventListener('input', updateCharCount);
        
        function showMessage(text, type) {
            const messageDiv = document.getElementById('message');
            messageDiv.style.display = 'block';
            messageDiv.className = `alert alert-${type}`;
            messageDiv.textContent = text;
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            loadLanguages();
            updateCharCount();
        });
    </script>
</body>
</html>
    """
    
    with open(os.path.join(templates_dir, "tts.html"), "w", encoding="utf-8") as f:
        f.write(tts_html)
    
    print("All template files created successfully")

# ==================== RUN APPLICATION ====================
if __name__ == "__main__":
    # Get port from environment variable
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 60)
    print("TTS GENERATOR WITH USER MANAGEMENT")
    print("=" * 60)
    print(f"Server starting on port: {port}")
    print(f"Admin credentials: admin / admin123")
    print("=" * 60)
    
    # Run with uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )
