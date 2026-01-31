import asyncio
import json
import os
import random
import re
import time
from datetime import datetime
from typing import List, Dict, Tuple
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import edge_tts
from pydub import AudioSegment
import uvicorn

# ==================== CONFIGURATION ====================
class Config:
    LANGUAGES = {
        "Tiếng Việt": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "Nữ", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "Nam", "display": "Nam Minh"},
            {"name": "vi-VN-HoaiMyNeural", "gender": "Nữ", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "Nam", "display": "Nam Minh"}
        ],
        "English (US)": [
            {"name": "en-US-GuyNeural", "gender": "Nam", "display": "Guy"},
            {"name": "en-US-JennyNeural", "gender": "Nữ", "display": "Jenny"},
            {"name": "en-US-AvaNeural", "gender": "Nữ", "display": "Ava"},
            {"name": "en-US-AndrewNeural", "gender": "Nam", "display": "Andrew"},
            {"name": "en-US-EmmaNeural", "gender": "Nữ", "display": "Emma"},
            {"name": "en-US-BrianNeural", "gender": "Nam", "display": "Brian"},
            {"name": "en-US-DavisNeural", "gender": "Nam", "display": "Davis"},
            {"name": "en-US-AmberNeural", "gender": "Nữ", "display": "Amber"},
            {"name": "en-US-AnaNeural", "gender": "Nữ", "display": "Ana"},
            {"name": "en-US-AshleyNeural", "gender": "Nữ", "display": "Ashley"}
        ],
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "Nữ", "display": "Libby"},
            {"name": "en-GB-MiaNeural", "gender": "Nữ", "display": "Mia"},
            {"name": "en-GB-RyanNeural", "gender": "Nam", "display": "Ryan"},
            {"name": "en-GB-SoniaNeural", "gender": "Nữ", "display": "Sonia"},
            {"name": "en-GB-ThomasNeural", "gender": "Nam", "display": "Thomas"},
            {"name": "en-GB-HollieNeural", "gender": "Nữ", "display": "Hollie"}
        ],
        "中文 (普通话)": [
            {"name": "zh-CN-XiaoxiaoNeural", "gender": "Nữ", "display": "晓晓"},
            {"name": "zh-CN-YunxiNeural", "gender": "Nam", "display": "云希"},
            {"name": "zh-CN-YunjianNeural", "gender": "Nam", "display": "云健"},
            {"name": "zh-CN-XiaoyiNeural", "gender": "Nữ", "display": "晓伊"},
            {"name": "zh-CN-XiaomoNeural", "gender": "Nữ", "display": "晓墨"},
            {"name": "zh-CN-XiaoxuanNeural", "gender": "Nữ", "display": "晓萱"}
        ],
        "中文 (台湾)": [
            {"name": "zh-TW-HsiaoChenNeural", "gender": "Nữ", "display": "曉臻"},
            {"name": "zh-TW-YunJheNeural", "gender": "Nam", "display": "雲哲"},
            {"name": "zh-TW-HsiaoYuNeural", "gender": "Nữ", "display": "曉雨"}
        ],
        "日本語": [
            {"name": "ja-JP-NanamiNeural", "gender": "Nữ", "display": "七海"},
            {"name": "ja-JP-KeitaNeural", "gender": "Nam", "display": "圭太"},
            {"name": "ja-JP-DaichiNeural", "gender": "Nam", "display": "大地"},
            {"name": "ja-JP-ShioriNeural", "gender": "Nữ", "display": "詩織"},
            {"name": "ja-JP-AoiNeural", "gender": "Nữ", "display": "葵"}
        ],
        "한국어": [
            {"name": "ko-KR-SunHiNeural", "gender": "Nữ", "display": "선희"},
            {"name": "ko-KR-InJoonNeural", "gender": "Nam", "display": "인준"},
            {"name": "ko-KR-BongJinNeural", "gender": "Nam", "display": "봉진"},
            {"name": "ko-KR-GookMinNeural", "gender": "Nam", "display": "국민"},
            {"name": "ko-KR-JiMinNeural", "gender": "Nữ", "display": "지민"}
        ],
        "Français": [
            {"name": "fr-FR-DeniseNeural", "gender": "Nữ", "display": "Denise"},
            {"name": "fr-FR-HenriNeural", "gender": "Nam", "display": "Henri"},
            {"name": "fr-FR-AlainNeural", "gender": "Nam", "display": "Alain"},
            {"name": "fr-FR-JacquelineNeural", "gender": "Nữ", "display": "Jacqueline"},
            {"name": "fr-FR-ClaudeNeural", "gender": "Nam", "display": "Claude"}
        ],
        "Español": [
            {"name": "es-ES-AlvaroNeural", "gender": "Nam", "display": "Álvaro"},
            {"name": "es-ES-ElviraNeural", "gender": "Nữ", "display": "Elvira"},
            {"name": "es-MX-DaliaNeural", "gender": "Nữ", "display": "Dalia"},
            {"name": "es-MX-JorgeNeural", "gender": "Nam", "display": "Jorge"},
            {"name": "es-ES-AbrilNeural", "gender": "Nữ", "display": "Abril"},
            {"name": "es-ES-ManuelNeural", "gender": "Nam", "display": "Manuel"}
        ],
        "Deutsch": [
            {"name": "de-DE-KatjaNeural", "gender": "Nữ", "display": "Katja"},
            {"name": "de-DE-ConradNeural", "gender": "Nam", "display": "Conrad"},
            {"name": "de-DE-AmalaNeural", "gender": "Nữ", "display": "Amala"},
            {"name": "de-DE-BerndNeural", "gender": "Nam", "display": "Bernd"},
            {"name": "de-DE-ChristophNeural", "gender": "Nam", "display": "Christoph"}
        ],
        "Italiano": [
            {"name": "it-IT-IsabellaNeural", "gender": "Nữ", "display": "Isabella"},
            {"name": "it-IT-DiegoNeural", "gender": "Nam", "display": "Diego"},
            {"name": "it-IT-BenignoNeural", "gender": "Nam", "display": "Benigno"},
            {"name": "it-IT-PalmiraNeural", "gender": "Nữ", "display": "Palmira"},
            {"name": "it-IT-CalimeroNeural", "gender": "Nam", "display": "Calimero"}
        ],
        "Português": [
            {"name": "pt-BR-FranciscaNeural", "gender": "Nữ", "display": "Francisca"},
            {"name": "pt-BR-AntonioNeural", "gender": "Nam", "display": "Antônio"},
            {"name": "pt-PT-DuarteNeural", "gender": "Nam", "display": "Duarte"},
            {"name": "pt-PT-RaquelNeural", "gender": "Nữ", "display": "Raquel"},
            {"name": "pt-BR-BrendaNeural", "gender": "Nữ", "display": "Brenda"}
        ],
        "Русский": [
            {"name": "ru-RU-SvetlanaNeural", "gender": "Nữ", "display": "Светлана"},
            {"name": "ru-RU-DmitryNeural", "gender": "Nam", "display": "Дмитрий"},
            {"name": "ru-RU-DariyaNeural", "gender": "Nữ", "display": "Дария"}
        ],
        "العربية": [
            {"name": "ar-SA-ZariyahNeural", "gender": "Nữ", "display": "زارية"},
            {"name": "ar-SA-HamedNeural", "gender": "Nam", "display": "حامد"},
            {"name": "ar-EG-SalmaNeural", "gender": "Nữ", "display": "سلمى"},
            {"name": "ar-EG-ShakirNeural", "gender": "Nam", "display": "شاكر"}
        ],
        "Nederlands": [
            {"name": "nl-NL-ColetteNeural", "gender": "Nữ", "display": "Colette"},
            {"name": "nl-NL-FennaNeural", "gender": "Nữ", "display": "Fenna"},
            {"name": "nl-NL-MaartenNeural", "gender": "Nam", "display": "Maarten"}
        ],
        "Polski": [
            {"name": "pl-PL-AgnieszkaNeural", "gender": "Nữ", "display": "Agnieszka"},
            {"name": "pl-PL-MarekNeural", "gender": "Nam", "display": "Marek"},
            {"name": "pl-PL-ZofiaNeural", "gender": "Nữ", "display": "Zofia"}
        ],
        "Türkçe": [
            {"name": "tr-TR-AhmetNeural", "gender": "Nam", "display": "Ahmet"},
            {"name": "tr-TR-EmelNeural", "gender": "Nữ", "display": "Emel"},
            {"name": "tr-TR-FatmaNeural", "gender": "Nữ", "display": "Fatma"}
        ],
        "ไทย": [
            {"name": "th-TH-PremwadeeNeural", "gender": "Nữ", "display": "เปรมวดี"},
            {"name": "th-TH-NiwatNeural", "gender": "Nam", "display": "นิวัฒน์"},
            {"name": "th-TH-AcharaNeural", "gender": "Nữ", "display": "อัจฉรา"}
        ],
        "हिन्दी": [
            {"name": "hi-IN-MadhurNeural", "gender": "Nam", "display": "मधुर"},
            {"name": "hi-IN-SwaraNeural", "gender": "Nữ", "display": "स्वरा"},
            {"name": "hi-IN-KiranNeural", "gender": "Nữ", "display": "किरण"}
        ]
    }
    
    OUTPUT_FORMATS = ["mp3", "wav"]
    
    SETTINGS_FILE = "tts_settings.json"

# ==================== TEXT PROCESSING ====================
class TextProcessor:
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()
    
    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """Split text into sentences"""
        sentences = []
        current = []
        
        for char in text:
            current.append(char)
            if char in '.!?。！？':
                sentence = ''.join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []
        
        # Add remaining text
        if current:
            sentence = ''.join(current).strip()
            if sentence:
                sentences.append(sentence)
        
        return sentences
    
    @staticmethod
    def parse_dialogue(text: str) -> List[Tuple[str, str]]:
        """Parse dialogue text into speaker-content pairs"""
        dialogues = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for speaker prefix
            match = re.match(r'^([A-Za-z0-9_]+)\s*[:：]\s*(.+)$', line)
            if match:
                speaker = match.group(1).strip()
                content = match.group(2).strip()
                dialogues.append((speaker, content))
            else:
                # If no speaker, add to last dialogue or use default
                if dialogues:
                    last_speaker, last_content = dialogues[-1]
                    dialogues[-1] = (last_speaker, last_content + ' ' + line)
                else:
                    dialogues.append(('NARRATOR', line))
        
        return dialogues

# ==================== TTS ENGINE ====================
class TTSEngine:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.settings = self.load_settings()
    
    def load_settings(self):
        """Load user settings"""
        if os.path.exists(Config.SETTINGS_FILE):
            try:
                with open(Config.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        # Default settings
        return {
            "single": {
                "language": "Tiếng Việt",
                "voice": "vi-VN-HoaiMyNeural",
                "speed": 0,
                "pitch": 0,
                "volume": 100
            },
            "dialogue": {
                "characters": {
                    "CHAR1": {"voice": "vi-VN-HoaiMyNeural", "speed": 0, "pitch": 0, "volume": 100},
                    "CHAR2": {"voice": "vi-VN-NamMinhNeural", "speed": 0, "pitch": 0, "volume": 100}
                },
                "pause": 500
            },
            "multi": {
                "voices": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"],
                "pause": 300
            }
        }
    
    def save_settings(self):
        """Save user settings"""
        try:
            with open(Config.SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    async def generate_speech(self, text: str, voice: str, speed: int = 0, pitch: int = 0, volume: int = 100) -> str:
        """Generate speech from text"""
        try:
            # Create output directory
            os.makedirs("outputs", exist_ok=True)
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"outputs/tts_{timestamp}.mp3"
            
            # Prepare parameters
            rate = f"{speed}%" if speed != 0 else "+0%"
            pitch = f"{pitch}Hz" if pitch != 0 else "+0Hz"
            
            # Generate speech
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            
            # Save to file
            await communicate.save(output_file)
            
            # Adjust volume if needed
            if volume != 100:
                audio = AudioSegment.from_file(output_file)
                volume_change = volume - 100
                audio = audio + volume_change
                audio.export(output_file, format="mp3")
            
            return output_file
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None
    
    async def generate_single(self, text: str, voice: str, speed: int, pitch: int, volume: int) -> str:
        """Generate single voice audio"""
        text = self.text_processor.clean_text(text)
        return await self.generate_speech(text, voice, speed, pitch, volume)
    
    async def generate_dialogue(self, text: str, characters: Dict[str, Dict], pause: int = 500) -> str:
        """Generate dialogue audio"""
        dialogues = self.text_processor.parse_dialogue(text)
        if not dialogues:
            return None
        
        # Generate audio for each dialogue
        audio_segments = []
        
        for speaker, content in dialogues:
            # Get voice settings for speaker
            if speaker in characters:
                voice_settings = characters[speaker]
            else:
                # Default to first character
                voice_settings = list(characters.values())[0]
            
            # Generate speech
            temp_file = await self.generate_speech(
                content, 
                voice_settings["voice"],
                voice_settings.get("speed", 0),
                voice_settings.get("pitch", 0),
                voice_settings.get("volume", 100)
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append(audio)
                
                # Add pause
                if len(audio_segments) > 1:
                    audio_segments.append(AudioSegment.silent(duration=pause))
                
                # Clean up temp file
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        if not audio_segments:
            return None
        
        # Combine audio segments
        combined = AudioSegment.empty()
        for segment in audio_segments:
            combined += segment
        
        # Save combined audio
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"outputs/dialogue_{timestamp}.mp3"
        combined.export(output_file, format="mp3")
        
        return output_file
    
    async def generate_multi(self, text: str, voices: List[str], pause: int = 300) -> str:
        """Generate multi-voice audio (alternating voices)"""
        sentences = self.text_processor.split_sentences(text)
        if not sentences:
            return None
        
        audio_segments = []
        
        for i, sentence in enumerate(sentences):
            # Cycle through voices
            voice_idx = i % len(voices)
            voice = voices[voice_idx]
            
            # Generate speech
            temp_file = await self.generate_speech(sentence, voice)
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append(audio)
                
                # Add pause between sentences
                if i < len(sentences) - 1:
                    audio_segments.append(AudioSegment.silent(duration=pause))
                
                # Clean up temp file
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        if not audio_segments:
            return None
        
        # Combine audio segments
        combined = AudioSegment.empty()
        for segment in audio_segments:
            combined += segment
        
        # Save combined audio
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"outputs/multi_{timestamp}.mp3"
        combined.export(output_file, format="mp3")
        
        return output_file

# ==================== FASTAPI APP ====================
app = FastAPI(title="TTS Generator", version="1.0.0")

# Create directories
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# TTS Engine
tts_engine = TTSEngine()

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "languages": Config.LANGUAGES,
        "formats": Config.OUTPUT_FORMATS,
        "settings": tts_engine.settings
    })

@app.get("/api/voices")
async def get_voices(language: str = None):
    """Get available voices"""
    if language and language in Config.LANGUAGES:
        voices = Config.LANGUAGES[language]
    else:
        # Return all voices
        voices = []
        for lang_voices in Config.LANGUAGES.values():
            voices.extend(lang_voices)
    
    return {"voices": voices}

@app.post("/api/generate/single")
async def generate_single(
    text: str = Form(...),
    voice: str = Form(...),
    speed: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100)
):
    """Generate single voice audio"""
    try:
        if not text or not voice:
            raise HTTPException(status_code=400, detail="Text and voice are required")
        
        # Save settings
        tts_engine.settings["single"].update({
            "voice": voice,
            "speed": speed,
            "pitch": pitch,
            "volume": volume
        })
        
        # Find language for this voice
        for lang, voices in Config.LANGUAGES.items():
            for v in voices:
                if v["id"] == voice:
                    tts_engine.settings["single"]["language"] = lang
                    break
        
        tts_engine.save_settings()
        
        # Generate audio
        audio_file = await tts_engine.generate_single(text, voice, speed, pitch, volume)
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(audio_file)}",
            "message": "Audio generated successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/dialogue")
async def generate_dialogue(
    text: str = Form(...),
    char1_voice: str = Form(...),
    char2_voice: str = Form(...),
    pause: int = Form(500)
):
    """Generate dialogue audio"""
    try:
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Prepare character settings
        characters = {
            "CHAR1": {"voice": char1_voice, "speed": 0, "pitch": 0, "volume": 100},
            "CHAR2": {"voice": char2_voice, "speed": 0, "pitch": 0, "volume": 100}
        }
        
        # Save settings
        tts_engine.settings["dialogue"]["characters"] = characters
        tts_engine.settings["dialogue"]["pause"] = pause
        tts_engine.save_settings()
        
        # Generate audio
        audio_file = await tts_engine.generate_dialogue(text, characters, pause)
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(audio_file)}",
            "message": "Dialogue audio generated successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/multi")
async def generate_multi(
    text: str = Form(...),
    voice1: str = Form(...),
    voice2: str = Form(...),
    pause: int = Form(300)
):
    """Generate multi-voice audio"""
    try:
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Prepare voices list
        voices = [voice1, voice2]
        
        # Save settings
        tts_engine.settings["multi"]["voices"] = voices
        tts_engine.settings["multi"]["pause"] = pause
        tts_engine.save_settings()
        
        # Generate audio
        audio_file = await tts_engine.generate_multi(text, voices, pause)
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(audio_file)}",
            "message": "Multi-voice audio generated successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated file"""
    filepath = f"outputs/{filename}"
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        filepath,
        filename=filename,
        media_type="audio/mpeg"
    )

@app.get("/api/settings")
async def get_settings():
    """Get current settings"""
    return tts_engine.settings

@app.post("/api/settings/save")
async def save_settings(settings: dict):
    """Save settings"""
    try:
        tts_engine.settings.update(settings)
        tts_engine.save_settings()
        return {"success": True, "message": "Settings saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cleanup")
async def cleanup_files():
    """Cleanup old files"""
    try:
        deleted = 0
        now = time.time()
        
        for filename in os.listdir("outputs"):
            filepath = os.path.join("outputs", filename)
            if os.path.isfile(filepath):
                # Delete files older than 1 hour
                if now - os.path.getmtime(filepath) > 3600:
                    os.remove(filepath)
                    deleted += 1
        
        return {"success": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== HTML TEMPLATE ====================
html_template = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS Generator Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .main-container {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            margin-top: 30px;
            margin-bottom: 30px;
            overflow: hidden;
        }
        
        .nav-tabs {
            border-bottom: 2px solid #dee2e6;
            background: #f8f9fa;
        }
        
        .nav-tabs .nav-link {
            border: none;
            border-radius: 0;
            padding: 15px 30px;
            font-weight: 600;
            color: #6c757d;
            transition: all 0.3s;
        }
        
        .nav-tabs .nav-link.active {
            background: white;
            color: #4361ee;
            border-bottom: 3px solid #4361ee;
        }
        
        .tab-content {
            padding: 30px;
        }
        
        .form-label {
            font-weight: 600;
            color: #212529;
            margin-bottom: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #4361ee, #3a0ca3);
            border: none;
            padding: 12px 30px;
            font-weight: 600;
            border-radius: 10px;
            transition: all 0.3s;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(67, 97, 238, 0.3);
        }
        
        .audio-player {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
            display: none;
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
        
        .loading-content {
            background: white;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            max-width: 400px;
            width: 90%;
        }
        
        .loading-spinner {
            width: 60px;
            height: 60px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid #4361ee;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .progress-bar {
            height: 10px;
            background: #4361ee;
            border-radius: 5px;
            margin-top: 10px;
            width: 0%;
            transition: width 0.3s;
        }
        
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            min-width: 300px;
        }
        
        .voice-card {
            border: 1px solid #dee2e6;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 15px;
            transition: all 0.3s;
        }
        
        .voice-card:hover {
            border-color: #4361ee;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .character-tag {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            margin-right: 10px;
            margin-bottom: 10px;
        }
        
        .char1-tag { background: #e3f2fd; color: #1976d2; }
        .char2-tag { background: #f3e5f5; color: #7b1fa2; }
        
        .range-value {
            display: inline-block;
            min-width: 50px;
            text-align: right;
            color: #4361ee;
            font-weight: 600;
        }
        
        @media (max-width: 768px) {
            .main-container {
                margin: 15px;
                border-radius: 15px;
            }
            
            .nav-tabs .nav-link {
                padding: 12px 20px;
                font-size: 14px;
            }
            
            .tab-content {
                padding: 20px;
            }
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-microphone-alt me-2"></i>
                TTS Generator Pro
            </a>
            <div class="navbar-text text-light">
                <i class="fas fa-globe me-2"></i>
                <span id="current-time">--:--</span>
            </div>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container">
        <div class="main-container">
            <!-- Tabs -->
            <ul class="nav nav-tabs" id="ttsTabs">
                <li class="nav-item">
                    <button class="nav-link active" data-bs-target="#single" data-bs-toggle="tab">
                        <i class="fas fa-user me-2"></i>Single Voice
                    </button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" data-bs-target="#dialogue" data-bs-toggle="tab">
                        <i class="fas fa-comments me-2"></i>Dialogue
                    </button>
                </li>
                <li class="nav-item">
                    <button class="nav-link" data-bs-target="#multi" data-bs-toggle="tab">
                        <i class="fas fa-users me-2"></i>Multi-Voice
                    </button>
                </li>
            </ul>

            <!-- Tab Content -->
            <div class="tab-content">
                <!-- Single Voice Tab -->
                <div class="tab-pane fade show active" id="single">
                    <div class="row">
                        <div class="col-md-8">
                            <div class="mb-4">
                                <label class="form-label">Text Content</label>
                                <textarea class="form-control" id="singleText" rows="10" 
                                          placeholder="Enter your text here..."></textarea>
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <i class="fas fa-info-circle me-1"></i>
                                        Supports multiple languages
                                    </small>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <!-- Language Selection -->
                            <div class="mb-3">
                                <label class="form-label">Language</label>
                                <select class="form-select" id="singleLanguage">
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <!-- Voice Selection -->
                            <div class="mb-3">
                                <label class="form-label">Voice</label>
                                <select class="form-select" id="singleVoice">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <!-- Voice Settings -->
                            <div class="mb-3">
                                <label class="form-label">
                                    Speed: <span class="range-value" id="singleSpeedValue">0%</span>
                                </label>
                                <input type="range" class="form-range" id="singleSpeed" min="-50" max="50" value="0">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">
                                    Pitch: <span class="range-value" id="singlePitchValue">0Hz</span>
                                </label>
                                <input type="range" class="form-range" id="singlePitch" min="-100" max="100" value="0">
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">
                                    Volume: <span class="range-value" id="singleVolumeValue">100%</span>
                                </label>
                                <input type="range" class="form-range" id="singleVolume" min="50" max="150" value="100">
                            </div>
                            
                            <!-- Generate Button -->
                            <button class="btn btn-primary w-100 mt-3" id="singleGenerateBtn">
                                <i class="fas fa-play-circle me-2"></i>Generate Audio
                            </button>
                            
                            <!-- Preview Button -->
                            <button class="btn btn-outline-primary w-100 mt-2" id="singlePreviewBtn">
                                <i class="fas fa-play me-2"></i>Preview
                            </button>
                        </div>
                    </div>
                    
                    <!-- Output -->
                    <div class="audio-player" id="singleOutput">
                        <h5><i class="fas fa-music me-2"></i>Generated Audio</h5>
                        <audio controls class="w-100" id="singleAudio"></audio>
                        <div class="mt-3">
                            <a href="#" class="btn btn-success" id="singleDownloadBtn">
                                <i class="fas fa-download me-2"></i>Download
                            </a>
                        </div>
                    </div>
                </div>

                <!-- Dialogue Tab -->
                <div class="tab-pane fade" id="dialogue">
                    <div class="row">
                        <div class="col-md-8">
                            <div class="mb-4">
                                <label class="form-label">Dialogue Content</label>
                                <textarea class="form-control" id="dialogueText" rows="10"
                                          placeholder="CHAR1: Hello, how are you?&#10;CHAR2: I'm fine, thank you!&#10;CHAR1: That's great to hear!"></textarea>
                                <div class="mt-2">
                                    <small class="text-muted">
                                        <i class="fas fa-info-circle me-1"></i>
                                        Use CHAR1:, CHAR2:, etc. as prefixes
                                    </small>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <!-- Character 1 -->
                            <div class="voice-card">
                                <h6><span class="character-tag char1-tag">CHARACTER 1</span></h6>
                                <div class="mb-2">
                                    <label class="form-label">Voice</label>
                                    <select class="form-select" id="char1Voice">
                                        <option value="">Select Voice</option>
                                    </select>
                                </div>
                            </div>
                            
                            <!-- Character 2 -->
                            <div class="voice-card">
                                <h6><span class="character-tag char2-tag">CHARACTER 2</span></h6>
                                <div class="mb-2">
                                    <label class="form-label">Voice</label>
                                    <select class="form-select" id="char2Voice">
                                        <option value="">Select Voice</option>
                                    </select>
                                </div>
                            </div>
                            
                            <!-- Settings -->
                            <div class="mb-3">
                                <label class="form-label">
                                    Pause Between Dialogues: <span class="range-value" id="dialoguePauseValue">500ms</span>
                                </label>
                                <input type="range" class="form-range" id="dialoguePause" min="100" max="2000" value="500" step="50">
                            </div>
                            
                            <!-- Generate Button -->
                            <button class="btn btn-primary w-100 mt-3" id="dialogueGenerateBtn">
                                <i class="fas fa-comments me-2"></i>Generate Dialogue
                            </button>
                        </div>
                    </div>
                    
                    <!-- Output -->
                    <div class="audio-player" id="dialogueOutput">
                        <h5><i class="fas fa-comments me-2"></i>Generated Dialogue</h5>
                        <audio controls class="w-100" id="dialogueAudio"></audio>
                        <div class="mt-3">
                            <a href="#" class="btn btn-success" id="dialogueDownloadBtn">
                                <i class="fas fa-download me-2"></i>Download
                            </a>
                        </div>
                    </div>
                </div>

                <!-- Multi-Voice Tab -->
                <div class="tab-pane fade" id="multi">
                    <div class="row">
                        <div class="col-md-8">
                            <div class="mb-4">
                                <label class="form-label">Text Content</label>
                                <textarea class="form-control" id="multiText" rows="10"
                                          placeholder="Enter text here... Each sentence will be spoken by alternating voices."></textarea>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <!-- Voice 1 -->
                            <div class="mb-3">
                                <label class="form-label">Voice 1</label>
                                <select class="form-select" id="voice1">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <!-- Voice 2 -->
                            <div class="mb-3">
                                <label class="form-label">Voice 2</label>
                                <select class="form-select" id="voice2">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <!-- Settings -->
                            <div class="mb-3">
                                <label class="form-label">
                                    Pause Between Sentences: <span class="range-value" id="multiPauseValue">300ms</span>
                                </label>
                                <input type="range" class="form-range" id="multiPause" min="100" max="1000" value="300" step="50">
                            </div>
                            
                            <!-- Generate Button -->
                            <button class="btn btn-primary w-100 mt-3" id="multiGenerateBtn">
                                <i class="fas fa-users me-2"></i>Generate Multi-Voice
                            </button>
                        </div>
                    </div>
                    
                    <!-- Output -->
                    <div class="audio-player" id="multiOutput">
                        <h5><i class="fas fa-users me-2"></i>Generated Multi-Voice</h5>
                        <audio controls class="w-100" id="multiAudio"></audio>
                        <div class="mt-3">
                            <a href="#" class="btn btn-success" id="multiDownloadBtn">
                                <i class="fas fa-download me-2"></i>Download
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Loading Overlay -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-content">
            <div class="loading-spinner"></div>
            <h5 id="loadingTitle">Generating Audio...</h5>
            <p id="loadingMessage">Please wait...</p>
            <div class="progress-bar" id="loadingProgress"></div>
            <button class="btn btn-outline-danger mt-3" id="cancelBtn" style="display: none;">
                <i class="fas fa-times me-2"></i>Cancel
            </button>
        </div>
    </div>

    <!-- Toast Container -->
    <div id="toastContainer"></div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Global variables
        let currentGeneration = null;
        let progressInterval = null;
        
        // Update time
        function updateTime() {
            const now = new Date();
            const timeString = now.toLocaleTimeString('vi-VN', {
                hour: '2-digit',
                minute: '2-digit'
            });
            document.getElementById('current-time').textContent = timeString;
        }
        setInterval(updateTime, 1000);
        updateTime();
        
        // Show toast
        function showToast(message, type = 'info') {
            const toastContainer = document.getElementById('toastContainer');
            const toastId = 'toast-' + Date.now();
            
            const bgColor = type === 'error' ? 'bg-danger' : 
                           type === 'success' ? 'bg-success' : 
                           type === 'warning' ? 'bg-warning' : 'bg-info';
            
            const toastHTML = `
                <div id="${toastId}" class="toast ${bgColor} text-white" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 
                                          type === 'success' ? 'fa-check-circle' : 
                                          type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'} me-2"></i>
                            ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                    </div>
                </div>
            `;
            
            toastContainer.insertAdjacentHTML('beforeend', toastHTML);
            const toast = new bootstrap.Toast(document.getElementById(toastId));
            toast.show();
            
            // Remove after hide
            document.getElementById(toastId).addEventListener('hidden.bs.toast', function() {
                this.remove();
            });
        }
        
        // Show loading
        function showLoading(title = 'Generating Audio...', message = 'Please wait...', showCancel = false) {
            document.getElementById('loadingTitle').textContent = title;
            document.getElementById('loadingMessage').textContent = message;
            document.getElementById('cancelBtn').style.display = showCancel ? 'block' : 'none';
            document.getElementById('loadingOverlay').style.display = 'flex';
            document.getElementById('loadingProgress').style.width = '0%';
            
            // Simulate progress
            let progress = 0;
            clearInterval(progressInterval);
            progressInterval = setInterval(() => {
                if (progress < 90) {
                    progress += 5;
                    document.getElementById('loadingProgress').style.width = progress + '%';
                }
            }, 500);
        }
        
        // Hide loading
        function hideLoading() {
            document.getElementById('loadingOverlay').style.display = 'none';
            clearInterval(progressInterval);
            document.getElementById('loadingProgress').style.width = '100%';
            setTimeout(() => {
                document.getElementById('loadingProgress').style.width = '0%';
            }, 300);
        }
        
        // Update range values
        function initRangeSliders() {
            // Single voice sliders
            const singleSpeed = document.getElementById('singleSpeed');
            const singlePitch = document.getElementById('singlePitch');
            const singleVolume = document.getElementById('singleVolume');
            const dialoguePause = document.getElementById('dialoguePause');
            const multiPause = document.getElementById('multiPause');
            
            function updateValue(input, displayId, suffix = '') {
                const display = document.getElementById(displayId);
                input.addEventListener('input', () => {
                    display.textContent = input.value + suffix;
                });
                display.textContent = input.value + suffix;
            }
            
            updateValue(singleSpeed, 'singleSpeedValue', '%');
            updateValue(singlePitch, 'singlePitchValue', 'Hz');
            updateValue(singleVolume, 'singleVolumeValue', '%');
            updateValue(dialoguePause, 'dialoguePauseValue', 'ms');
            updateValue(multiPause, 'multiPauseValue', 'ms');
        }
        
        // Load voices
        async function loadVoices(language, targetSelectId, defaultVoice = '') {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const select = document.getElementById(targetSelectId);
                select.innerHTML = '<option value="">Select Voice</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.id;
                    option.textContent = `${voice.name} (${voice.gender})`;
                    if (voice.id === defaultVoice) {
                        option.selected = true;
                    }
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('Error loading voices:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Initialize voices
        async function initVoices() {
            // Load settings
            let settings = {};
            try {
                const response = await fetch('/api/settings');
                settings = await response.json();
            } catch (error) {
                console.error('Error loading settings:', error);
            }
            
            // Single voice tab
            const singleLanguage = document.getElementById('singleLanguage');
            if (settings.single && settings.single.language) {
                singleLanguage.value = settings.single.language;
            }
            
            singleLanguage.addEventListener('change', async function() {
                await loadVoices(this.value, 'singleVoice', 
                    settings.single && settings.single.voice ? settings.single.voice : '');
            });
            
            // Trigger initial load
            await loadVoices(singleLanguage.value, 'singleVoice',
                settings.single && settings.single.voice ? settings.single.voice : '');
            
            // Dialogue tab
            const dialogueLanguage = 'Tiếng Việt'; // Default for dialogue
            await loadVoices(dialogueLanguage, 'char1Voice',
                settings.dialogue && settings.dialogue.characters && settings.dialogue.characters.CHAR1 ? 
                settings.dialogue.characters.CHAR1.voice : '');
            
            await loadVoices(dialogueLanguage, 'char2Voice',
                settings.dialogue && settings.dialogue.characters && settings.dialogue.characters.CHAR2 ? 
                settings.dialogue.characters.CHAR2.voice : '');
            
            // Multi-voice tab
            await loadVoices('Tiếng Việt', 'voice1',
                settings.multi && settings.multi.voices ? settings.multi.voices[0] : '');
            
            await loadVoices('Tiếng Việt', 'voice2',
                settings.multi && settings.multi.voices ? settings.multi.voices[1] : '');
        }
        
        // Generate single voice
        document.getElementById('singleGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('singleText').value.trim();
            const voice = document.getElementById('singleVoice').value;
            
            if (!text) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!voice) {
                showToast('Please select a voice', 'error');
                return;
            }
            
            showLoading('Generating Single Voice Audio...', 'Processing your text...', true);
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('voice', voice);
                formData.append('speed', document.getElementById('singleSpeed').value);
                formData.append('pitch', document.getElementById('singlePitch').value);
                formData.append('volume', document.getElementById('singleVolume').value);
                
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show audio player
                    const audioPlayer = document.getElementById('singleAudio');
                    audioPlayer.src = result.audio_url;
                    audioPlayer.load();
                    
                    // Show output panel
                    document.getElementById('singleOutput').style.display = 'block';
                    
                    // Set download link
                    document.getElementById('singleDownloadBtn').href = result.audio_url;
                    
                    showToast(result.message, 'success');
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
        
        // Generate dialogue
        document.getElementById('dialogueGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('dialogueText').value.trim();
            const char1Voice = document.getElementById('char1Voice').value;
            const char2Voice = document.getElementById('char2Voice').value;
            
            if (!text) {
                showToast('Please enter dialogue text', 'error');
                return;
            }
            
            if (!char1Voice || !char2Voice) {
                showToast('Please select voices for both characters', 'error');
                return;
            }
            
            showLoading('Generating Dialogue Audio...', 'Processing dialogue...', true);
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('char1_voice', char1Voice);
                formData.append('char2_voice', char2Voice);
                formData.append('pause', document.getElementById('dialoguePause').value);
                
                const response = await fetch('/api/generate/dialogue', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show audio player
                    const audioPlayer = document.getElementById('dialogueAudio');
                    audioPlayer.src = result.audio_url;
                    audioPlayer.load();
                    
                    // Show output panel
                    document.getElementById('dialogueOutput').style.display = 'block';
                    
                    // Set download link
                    document.getElementById('dialogueDownloadBtn').href = result.audio_url;
                    
                    showToast(result.message, 'success');
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
        
        // Generate multi-voice
        document.getElementById('multiGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('multiText').value.trim();
            const voice1 = document.getElementById('voice1').value;
            const voice2 = document.getElementById('voice2').value;
            
            if (!text) {
                showToast('Please enter text', 'error');
                return;
            }
            
            if (!voice1 || !voice2) {
                showToast('Please select both voices', 'error');
                return;
            }
            
            showLoading('Generating Multi-Voice Audio...', 'Processing text...', true);
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('voice1', voice1);
                formData.append('voice2', voice2);
                formData.append('pause', document.getElementById('multiPause').value);
                
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show audio player
                    const audioPlayer = document.getElementById('multiAudio');
                    audioPlayer.src = result.audio_url;
                    audioPlayer.load();
                    
                    // Show output panel
                    document.getElementById('multiOutput').style.display = 'block';
                    
                    // Set download link
                    document.getElementById('multiDownloadBtn').href = result.audio_url;
                    
                    showToast(result.message, 'success');
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
        
        // Preview single voice
        document.getElementById('singlePreviewBtn').addEventListener('click', async function() {
            const voice = document.getElementById('singleVoice').value;
            const text = "This is a preview of the selected voice. Hello, how are you today?";
            
            if (!voice) {
                showToast('Please select a voice first', 'error');
                return;
            }
            
            showLoading('Generating Preview...', 'Please wait...');
            
            try {
                const formData = new FormData();
                formData.append('text', text);
                formData.append('voice', voice);
                formData.append('speed', document.getElementById('singleSpeed').value);
                formData.append('pitch', document.getElementById('singlePitch').value);
                formData.append('volume', document.getElementById('singleVolume').value);
                
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Play preview
                    const audio = new Audio(result.audio_url);
                    audio.play();
                    
                    showToast('Preview playing...', 'success');
                } else {
                    showToast('Preview generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Preview generation failed', 'error');
            } finally {
                hideLoading();
            }
        });
        
        // Cancel button
        document.getElementById('cancelBtn').addEventListener('click', function() {
            hideLoading();
            showToast('Generation cancelled', 'warning');
        });
        
        // Initialize on load
        window.addEventListener('DOMContentLoaded', function() {
            initRangeSliders();
            initVoices();
            
            // Cleanup old files
            fetch('/api/cleanup', { method: 'POST' }).catch(console.error);
        });
    </script>
</body>
</html>
"""

# Create HTML file
with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(html_template)

# ==================== START SERVER ====================
if __name__ == "__main__":
    print("=" * 50)
    print("TTS GENERATOR PRO")
    print("=" * 50)
    print("Starting server...")
    print(f"Open http://localhost:8000 in your browser")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
