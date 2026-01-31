import asyncio
import json
import os
import random
import re
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import webvtt
import natsort
import uvicorn
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import threading

# ==================== SYSTEM CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    # Expanded languages with more voices
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
    
    # All available voices for dropdowns
    ALL_VOICES = []
    for lang_voices in LANGUAGES.values():
        ALL_VOICES.extend(lang_voices)
    
    OUTPUT_FORMATS = ["mp3", "wav", "ogg", "m4a"]
    
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
    
    # Dialogue formats
    DIALOGUE_FORMATS = {
        "single": ["TEXT"],
        "multi": ["CHAR1:", "CHAR2:", "NARRATOR:", "CHAR3:", "CHAR4:"],
        "qa": ["Q:", "A:"],
        "script": ["[SCENE]", "[ACTION]", "CHARACTER:", "(parenthesis)"]
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
    
    @staticmethod
    def parse_custom_dialogues(text: str, character_map: Dict[str, str]) -> List[Tuple[str, str]]:
        """Parse dialogues with custom character mappings"""
        dialogues = []
        lines = text.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
                
            # Check for character prefix
            found_character = None
            for char_prefix in character_map.keys():
                if line.startswith(char_prefix + ':'):
                    found_character = character_map[char_prefix]
                    content = line[len(char_prefix)+1:].strip()
                    break
            
            if found_character:
                # Collect multi-line content
                j = i + 1
                while j < len(lines) and lines[j].strip() and not any(lines[j].strip().startswith(c + ':') for c in character_map.keys()):
                    content += ' ' + lines[j].strip()
                    j += 1
                
                dialogues.append((found_character, TextProcessor._process_special_cases(content)))
                i = j
            else:
                i += 1
        
        return dialogues

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.load_settings()
        self.progress_queue = queue.Queue()
        self.progress_listeners = {}
        
    def load_settings(self):
        if os.path.exists(TTSConfig.SETTINGS_FILE):
            with open(TTSConfig.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        else:
            self.settings = {
                "single_voice": {
                    "language": "Tiếng Việt",
                    "voice": "vi-VN-HoaiMyNeural",
                    "rate": 0,
                    "pitch": 0,
                    "volume": 100,
                    "pause": 500
                },
                "multi_voice": {
                    "characters": [
                        {"name": "CHAR1", "voice": "vi-VN-HoaiMyNeural", "rate": 0, "pitch": 0, "volume": 100},
                        {"name": "CHAR2", "voice": "vi-VN-NamMinhNeural", "rate": -10, "pitch": 0, "volume": 100}
                    ],
                    "pause": 500,
                    "repeat": 1,
                    "format": "CHAR1:"
                },
                "qa_voice": {
                    "question": {"voice": "vi-VN-HoaiMyNeural", "rate": 0, "pitch": 0, "volume": 100},
                    "answer": {"voice": "vi-VN-NamMinhNeural", "rate": -10, "pitch": 0, "volume": 100},
                    "pause_q": 200,
                    "pause_a": 500,
                    "repeat": 2
                },
                "dialogue_voice": {
                    "characters": [
                        {"name": "NARRATOR", "voice": "vi-VN-HoaiMyNeural", "rate": 0, "pitch": 0, "volume": 100},
                        {"name": "CHAR1", "voice": "vi-VN-NamMinhNeural", "rate": -10, "pitch": 0, "volume": 100}
                    ],
                    "pause": 300,
                    "repeat": 1,
                    "format": "NARRATOR:"
                }
            }
            self.save_settings()
    
    def save_settings(self):
        with open(TTSConfig.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=2, ensure_ascii=False)
    
    def update_progress(self, task_id: str, progress: int, message: str = ""):
        """Update progress for a task"""
        self.progress_queue.put({
            "task_id": task_id,
            "progress": progress,
            "message": message
        })
    
    async def generate_speech(self, text: str, voice_id: str, rate: int = 0, pitch: int = 0, volume: int = 100, task_id: str = None):
        """Generate speech using edge-tts with progress tracking"""
        try:
            if task_id:
                self.update_progress(task_id, 10, "Starting speech generation...")
            
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"+{pitch}Hz" if pitch >=0 else f"{pitch}Hz"
            
            if task_id:
                self.update_progress(task_id, 20, "Initializing TTS engine...")
            
            communicate = edge_tts.Communicate(text, voice_id, rate=rate_str, pitch=pitch_str)
            
            audio_chunks = []
            subtitles = []
            
            if task_id:
                self.update_progress(task_id, 30, "Generating audio...")
            
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
                if task_id:
                    self.update_progress(task_id, 100, "Failed to generate audio")
                return None, []
            
            if task_id:
                self.update_progress(task_id, 60, "Processing audio...")
            
            # Combine audio chunks
            audio_data = b"".join(audio_chunks)
            
            # Process audio
            temp_file = f"temp_{int(time.time())}_{random.randint(1000, 9999)}.mp3"
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            audio = AudioSegment.from_file(temp_file)
            
            # Apply volume adjustment
            volume_adjustment = min(max(volume - 100, -50), 10)
            audio = audio + volume_adjustment
            
            # Apply audio processing
            audio = normalize(audio)
            audio = compress_dynamic_range(audio, threshold=-20.0, ratio=4.0)
            audio = low_pass_filter(audio, 14000)
            audio = high_pass_filter(audio, 100)
            
            audio.export(temp_file, format="mp3", bitrate="256k")
            
            if task_id:
                self.update_progress(task_id, 90, "Finalizing...")
            
            return temp_file, subtitles
            
        except Exception as e:
            print(f"Error generating speech: {e}")
            if task_id:
                self.update_progress(task_id, 100, f"Error: {str(e)}")
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
                                 volume: int, pause: int, output_format: str = "mp3", task_id: str = None):
        """Process text with single voice"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/single_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        if task_id:
            self.update_progress(task_id, 5, "Splitting text into sentences...")
        
        sentences = self.text_processor.split_sentences(text)
        audio_segments = []
        all_subtitles = []
        
        total_sentences = len(sentences)
        
        for i, sentence in enumerate(sentences):
            if task_id:
                progress = 5 + int((i / total_sentences) * 85)
                self.update_progress(task_id, progress, f"Processing sentence {i+1}/{total_sentences}...")
            
            temp_file, subs = await self.generate_speech(sentence, voice_id, rate, pitch, volume, task_id)
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append(audio)
                all_subtitles.extend(subs)
                os.remove(temp_file)
        
        if not audio_segments:
            if task_id:
                self.update_progress(task_id, 100, "No audio generated")
            return None, None
        
        if task_id:
            self.update_progress(task_id, 95, "Combining audio segments...")
        
        # Combine audio with pauses
        combined = AudioSegment.empty()
        for i, audio in enumerate(audio_segments):
            audio = audio.fade_in(50).fade_out(50)
            combined += audio
            if i < len(audio_segments) - 1:
                combined += AudioSegment.silent(duration=pause)
        
        # Export combined audio
        output_file = os.path.join(output_dir, f"single_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="256k")
        
        # Generate SRT
        srt_file = self.generate_srt(all_subtitles, output_file)
        
        if task_id:
            self.update_progress(task_id, 100, "Audio generation complete!")
        
        return output_file, srt_file
    
    async def process_multi_voice(self, text: str, voices_config: dict, pause: int, 
                                repeat: int, output_format: str = "mp3", task_id: str = None):
        """Process text with multiple voices"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/multi_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        if task_id:
            self.update_progress(task_id, 5, "Parsing dialogue...")
        
        # Parse character dialogues
        dialogues = []
        current_char = None
        current_text = []
        
        for line in text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            char_match = re.match(r'^(CHAR\d+|NARRATOR|Q|A|[\w\s]+):\s*(.+)', line, re.IGNORECASE)
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
            if task_id:
                self.update_progress(task_id, 100, "No dialogue found")
            return None, None
        
        # Generate audio for each dialogue
        audio_segments = []
        all_subtitles = []
        
        total_dialogues = len(dialogues)
        
        for idx, (char, dialogue_text) in enumerate(dialogues):
            if task_id:
                progress = 5 + int((idx / total_dialogues) * 85)
                self.update_progress(task_id, progress, f"Processing {char}: {dialogue_text[:50]}...")
            
            # Find voice config for character
            config = None
            for voice_config in voices_config["characters"]:
                if voice_config["name"].upper() == char.upper():
                    config = voice_config
                    break
            
            if not config:
                # Use first character as default
                config = voices_config["characters"][0]
            
            temp_file, subs = await self.generate_speech(
                dialogue_text, 
                config["voice"], 
                config["rate"], 
                config["pitch"], 
                config["volume"],
                task_id
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append((char, audio))
                
                for sub in subs:
                    sub["speaker"] = char
                    all_subtitles.append(sub)
                
                os.remove(temp_file)
        
        if not audio_segments:
            if task_id:
                self.update_progress(task_id, 100, "No audio generated")
            return None, None
        
        if task_id:
            self.update_progress(task_id, 95, "Combining audio segments...")
        
        # Combine with repetition
        combined = AudioSegment.empty()
        for rep in range(repeat):
            if task_id:
                self.update_progress(task_id, 95, f"Combining repetition {rep+1}/{repeat}...")
            
            for i, (char, audio) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            if rep < repeat - 1:
                combined += AudioSegment.silent(duration=pause * 2)
        
        # Export
        output_file = os.path.join(output_dir, f"multi_voice.{output_format}")
        combined.export(output_file, format=output_format, bitrate="256k")
        
        # Generate SRT with speaker labels
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
        
        if task_id:
            self.update_progress(task_id, 100, "Audio generation complete!")
        
        return output_file, srt_file
    
    async def process_custom_dialogue(self, text: str, characters: List[Dict], pause: int,
                                    repeat: int, output_format: str = "mp3", task_id: str = None):
        """Process custom dialogue format"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/dialogue_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        if task_id:
            self.update_progress(task_id, 5, "Parsing dialogue content...")
        
        # Create character map
        character_map = {char["name"]: char for char in characters}
        
        # Parse dialogues
        dialogues = self.text_processor.parse_custom_dialogues(text, {char["name"]: char["name"] for char in characters})
        
        if not dialogues:
            if task_id:
                self.update_progress(task_id, 100, "No dialogue content found")
            return None, None
        
        # Generate audio for each dialogue
        audio_segments = []
        all_subtitles = []
        
        total_dialogues = len(dialogues)
        
        for idx, (char_name, dialogue_text) in enumerate(dialogues):
            if task_id:
                progress = 5 + int((idx / total_dialogues) * 85)
                self.update_progress(task_id, progress, f"Processing {char_name}: {dialogue_text[:50]}...")
            
            char_config = character_map.get(char_name)
            if not char_config:
                # Use first character as default
                char_config = characters[0]
            
            temp_file, subs = await self.generate_speech(
                dialogue_text,
                char_config["voice"],
                char_config["rate"],
                char_config["pitch"],
                char_config["volume"],
                task_id
            )
            
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append((char_name, audio))
                
                for sub in subs:
                    sub["speaker"] = char_name
                    all_subtitles.append(sub)
                
                os.remove(temp_file)
        
        if not audio_segments:
            if task_id:
                self.update_progress(task_id, 100, "No audio generated")
            return None, None
        
        if task_id:
            self.update_progress(task_id, 95, "Combining audio segments...")
        
        # Combine audio
        combined = AudioSegment.empty()
        for rep in range(repeat):
            for i, (char_name, audio) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            if rep < repeat - 1:
                combined += AudioSegment.silent(duration=pause * 2)
        
        # Export
        output_file = os.path.join(output_dir, f"dialogue.{output_format}")
        combined.export(output_file, format=output_format, bitrate="256k")
        
        # Generate SRT
        if all_subtitles:
            srt_content = []
            for i, sub in enumerate(all_subtitles, start=1):
                start = timedelta(milliseconds=sub["start"])
                end = timedelta(milliseconds=sub["end"])
                
                start_str = f"{start.total_seconds() // 3600:02.0f}:{(start.total_seconds() % 3600) // 60:02.0f}:{start.total_seconds() % 60:06.3f}".replace('.', ',')
                end_str = f"{end.total_seconds() // 3600:02.0f}:{(end.total_seconds() % 3600) // 60:02.0f}:{end.total_seconds() % 60:06.3f}".replace('.', ',')
                
                text = f"{sub['speaker']}: {sub['text']}"
                srt_content.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")
            
            srt_file = os.path.join(output_dir, f"dialogue.srt")
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
        else:
            srt_file = None
        
        if task_id:
            self.update_progress(task_id, 100, "Dialogue audio generated successfully!")
        
        return output_file, srt_file

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(title="Professional TTS Generator Pro", version="2.0.0")

# Create necessary directories
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("temp", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# TTS Processor instance
tts_processor = TTSProcessor()

# WebSocket connections
active_connections = {}

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index_pro.html", {
        "request": request,
        "languages": TTSConfig.LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS,
        "all_voices": TTSConfig.ALL_VOICES,
        "dialogue_formats": TTSConfig.DIALOGUE_FORMATS
    })

@app.get("/api/voices")
async def get_voices(language: str = None):
    """Get available voices"""
    if language and language in TTSConfig.LANGUAGES:
        voices = TTSConfig.LANGUAGES[language]
    else:
        voices = TTSConfig.ALL_VOICES
    
    return {"voices": voices}

@app.get("/api/languages")
async def get_languages():
    """Get all available languages"""
    languages = list(TTSConfig.LANGUAGES.keys())
    return {"languages": languages}

@app.post("/api/generate/single")
async def generate_single_voice(
    text: str = Form(...),
    voice_id: str = Form(...),
    language: str = Form(None),
    rate: int = Form(0),
    pitch: int = Form(0),
    volume: int = Form(100),
    pause: int = Form(500),
    output_format: str = Form("mp3"),
    task_id: str = Form(None)
):
    """Generate single voice TTS"""
    try:
        if not task_id:
            task_id = f"single_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Start generation in background
        asyncio.create_task(
            tts_processor.process_single_voice(
                text, voice_id, rate, pitch, volume, pause, output_format, task_id
            )
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Generation started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/multi")
async def generate_multi_voice(
    text: str = Form(...),
    characters: str = Form(...),  # JSON string of characters
    pause: int = Form(500),
    repeat: int = Form(1),
    output_format: str = Form("mp3"),
    task_id: str = Form(None)
):
    """Generate multi-voice TTS"""
    try:
        if not task_id:
            task_id = f"multi_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Parse characters
        characters_data = json.loads(characters)
        
        # Create voices config
        voices_config = {
            "characters": characters_data
        }
        
        # Start generation in background
        asyncio.create_task(
            tts_processor.process_multi_voice(
                text, voices_config, pause, repeat, output_format, task_id
            )
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Multi-voice generation started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/dialogue")
async def generate_dialogue(
    text: str = Form(...),
    characters: str = Form(...),
    pause: int = Form(300),
    repeat: int = Form(1),
    output_format: str = Form("mp3"),
    task_id: str = Form(None)
):
    """Generate dialogue TTS"""
    try:
        if not task_id:
            task_id = f"dialogue_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Parse characters
        characters_data = json.loads(characters)
        
        # Start generation in background
        asyncio.create_task(
            tts_processor.process_custom_dialogue(
                text, characters_data, pause, repeat, output_format, task_id
            )
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "message": "Dialogue generation started"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/task/{task_id}/result")
async def get_task_result(task_id: str):
    """Get result of a generation task"""
    # This would check if the task is complete and return the result
    # For simplicity, we'll just return a placeholder
    # In a real implementation, you'd track task completion and results
    
    # Check if output files exist
    for root, dirs, files in os.walk("outputs"):
        for dir_name in dirs:
            if task_id in dir_name:
                dir_path = os.path.join(root, dir_name)
                for file in os.listdir(dir_path):
                    if file.endswith(('.mp3', '.wav', '.ogg', '.m4a')):
                        audio_file = os.path.join(dir_path, file)
                        srt_file = audio_file.replace('.mp3', '.srt').replace('.wav', '.srt').replace('.ogg', '.srt').replace('.m4a', '.srt')
                        
                        if os.path.exists(srt_file):
                            return {
                                "success": True,
                                "complete": True,
                                "audio_url": f"/download/{os.path.basename(audio_file)}",
                                "srt_url": f"/download/{os.path.basename(srt_file)}",
                                "message": "Generation complete"
                            }
                        else:
                            return {
                                "success": True,
                                "complete": True,
                                "audio_url": f"/download/{os.path.basename(audio_file)}",
                                "message": "Generation complete"
                            }
    
    return {
        "success": True,
        "complete": False,
        "message": "Task in progress"
    }

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated files"""
    file_path = None
    
    # Search in outputs directory
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

@app.get("/api/settings")
async def get_settings():
    """Get current settings"""
    return tts_processor.settings

@app.post("/api/settings")
async def save_settings(settings: dict):
    """Save settings"""
    try:
        tts_processor.settings.update(settings)
        tts_processor.save_settings()
        return {"success": True, "message": "Settings saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/cleanup")
async def cleanup_old_files():
    """Cleanup old generated files (older than 1 hour)"""
    try:
        now = time.time()
        deleted = 0
        
        for root, dirs, files in os.walk("outputs"):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getmtime(file_path) < now - 3600:  # 1 hour
                    os.remove(file_path)
                    deleted += 1
        
        # Clean temp directory
        for file in os.listdir("temp"):
            file_path = os.path.join("temp", file)
            if os.path.isfile(file_path):
                os.remove(file_path)
        
        return {"success": True, "deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# WebSocket for progress updates
@app.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    active_connections[task_id] = websocket
    
    try:
        while True:
            # Send progress updates
            try:
                if not tts_processor.progress_queue.empty():
                    progress_data = tts_processor.progress_queue.get()
                    if progress_data["task_id"] == task_id:
                        await websocket.send_json(progress_data)
            except:
                pass
            
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        if task_id in active_connections:
            del active_connections[task_id]

# ==================== HTML TEMPLATE ====================
index_pro_html = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Professional TTS Generator Pro</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet">
    <style>
        :root {
            --primary: #4361ee;
            --primary-dark: #3a0ca3;
            --secondary: #4cc9f0;
            --success: #06d6a0;
            --danger: #ef476f;
            --warning: #ffd166;
            --dark: #212529;
            --light: #f8f9fa;
            --gray: #6c757d;
            --border: #dee2e6;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow-x: hidden;
        }
        
        .glass-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .nav-tabs.glass {
            background: rgba(248, 249, 250, 0.8);
            border-bottom: 2px solid var(--border);
            padding: 0.5rem;
        }
        
        .nav-tabs.glass .nav-link {
            border: none;
            border-radius: 10px;
            padding: 0.75rem 1.5rem;
            margin: 0 0.25rem;
            font-weight: 600;
            color: var(--gray);
            transition: all 0.3s ease;
        }
        
        .nav-tabs.glass .nav-link:hover {
            background: rgba(255, 255, 255, 0.5);
            transform: translateY(-2px);
        }
        
        .nav-tabs.glass .nav-link.active {
            background: var(--primary);
            color: white;
            box-shadow: 0 5px 15px rgba(67, 97, 238, 0.4);
        }
        
        .btn-gradient {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border: none;
            color: white;
            font-weight: 600;
            padding: 0.75rem 2rem;
            border-radius: 10px;
            transition: all 0.3s ease;
        }
        
        .btn-gradient:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(67, 97, 238, 0.4);
        }
        
        .progress-ring {
            position: relative;
            width: 120px;
            height: 120px;
        }
        
        .progress-ring__circle {
            transform: rotate(-90deg);
            transform-origin: 50% 50%;
        }
        
        .voice-card {
            background: white;
            border-radius: 15px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border: 2px solid transparent;
            transition: all 0.3s ease;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }
        
        .voice-card:hover {
            border-color: var(--primary);
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(67, 97, 238, 0.1);
        }
        
        .voice-card.active {
            border-color: var(--primary);
            background: linear-gradient(135deg, rgba(67, 97, 238, 0.05), rgba(67, 97, 238, 0.1));
        }
        
        .character-badge {
            display: inline-block;
            padding: 0.25rem 1rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            margin-right: 0.5rem;
            margin-bottom: 0.5rem;
        }
        
        .lang-select {
            width: 100%;
            padding: 0.5rem;
            border: 2px solid var(--border);
            border-radius: 10px;
            background: white;
            font-weight: 500;
        }
        
        .select2-container--default .select2-selection--single {
            border: 2px solid var(--border);
            border-radius: 10px;
            height: 42px;
            padding: 5px;
        }
        
        .select2-container--default .select2-selection--single .select2-selection__rendered {
            line-height: 30px;
        }
        
        .textarea-autosize {
            min-height: 200px;
            resize: vertical;
            border: 2px solid var(--border);
            border-radius: 10px;
            padding: 1rem;
            font-size: 1rem;
            transition: border-color 0.3s;
        }
        
        .textarea-autosize:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 0.25rem rgba(67, 97, 238, 0.25);
            outline: none;
        }
        
        .output-panel {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 15px;
            padding: 2rem;
            margin-top: 2rem;
            display: none;
        }
        
        .progress-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            backdrop-filter: blur(5px);
        }
        
        .progress-modal-content {
            background: white;
            border-radius: 20px;
            padding: 2rem;
            width: 90%;
            max-width: 500px;
            text-align: center;
        }
        
        .audio-wave {
            display: flex;
            align-items: flex-end;
            height: 60px;
            gap: 2px;
            margin: 1rem 0;
        }
        
        .audio-wave-bar {
            flex: 1;
            background: var(--primary);
            border-radius: 2px;
            animation: wave 1s ease-in-out infinite;
        }
        
        @keyframes wave {
            0%, 100% { height: 20%; }
            50% { height: 100%; }
        }
        
        .settings-slider {
            -webkit-appearance: none;
            width: 100%;
            height: 8px;
            border-radius: 4px;
            background: linear-gradient(to right, #dee2e6, var(--primary));
            outline: none;
        }
        
        .settings-slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: var(--primary);
            cursor: pointer;
            border: 3px solid white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        .tab-icon {
            font-size: 1.2rem;
            margin-right: 0.5rem;
        }
        
        .character-settings {
            background: rgba(248, 249, 250, 0.5);
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        
        @media (max-width: 768px) {
            .glass-card {
                margin: 1rem;
                border-radius: 15px;
            }
            
            .nav-tabs.glass .nav-link {
                padding: 0.5rem 1rem;
                font-size: 0.875rem;
            }
            
            .progress-modal-content {
                width: 95%;
                padding: 1.5rem;
            }
        }
        
        /* Toast notifications */
        .toast-container {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
        }
        
        .custom-toast {
            background: white;
            border-left: 5px solid var(--primary);
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            padding: 1rem;
            margin-bottom: 1rem;
            animation: slideInRight 0.3s ease;
        }
        
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        .preview-btn {
            position: absolute;
            right: 1rem;
            top: 1rem;
            background: rgba(67, 97, 238, 0.1);
            border: none;
            color: var(--primary);
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .preview-btn:hover {
            background: var(--primary);
            color: white;
            transform: scale(1.1);
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark py-3">
        <div class="container">
            <a class="navbar-brand d-flex align-items-center" href="#">
                <div class="bg-white rounded-circle p-2 me-3">
                    <i class="fas fa-microphone-alt text-primary" style="font-size: 1.5rem;"></i>
                </div>
                <div>
                    <h4 class="mb-0 fw-bold">TTS Pro</h4>
                    <small class="text-light opacity-75">Professional Text-to-Speech Generator</small>
                </div>
            </a>
            <div class="navbar-text">
                <div class="d-flex align-items-center">
                    <i class="fas fa-globe me-2 text-light"></i>
                    <select class="form-select form-select-sm bg-transparent text-light border-light" style="width: auto;" id="globalLanguage">
                        <option value="vi">🇻🇳 Tiếng Việt</option>
                        <option value="en">🇺🇸 English</option>
                        <option value="zh">🇨🇳 中文</option>
                        <option value="ja">🇯🇵 日本語</option>
                        <option value="ko">🇰🇷 한국어</option>
                    </select>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container py-4">
        <div class="glass-card">
            <!-- Tabs -->
            <ul class="nav nav-tabs glass justify-content-center" id="ttsTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single">
                        <i class="fas fa-user tab-icon"></i>Single Voice
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="dialogue-tab" data-bs-toggle="tab" data-bs-target="#dialogue">
                        <i class="fas fa-comments tab-icon"></i>Dialogue
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="multi-tab" data-bs-toggle="tab" data-bs-target="#multi">
                        <i class="fas fa-users tab-icon"></i>Multi-Character
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="batch-tab" data-bs-toggle="tab" data-bs-target="#batch">
                        <i class="fas fa-layer-group tab-icon"></i>Batch
                    </button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="settings-tab" data-bs-toggle="tab" data-bs-target="#settings">
                        <i class="fas fa-cog tab-icon"></i>Settings
                    </button>
                </li>
            </ul>

            <!-- Tab Content -->
            <div class="tab-content p-4" id="ttsTabsContent">
                <!-- Single Voice Tab -->
                <div class="tab-pane fade show active" id="single" role="tabpanel">
                    <div class="row">
                        <div class="col-lg-8">
                            <div class="mb-4">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-align-left me-2"></i>Text Content
                                </label>
                                <textarea class="textarea-autosize w-100" id="singleText" 
                                          placeholder="Enter your text here...&#10;The system will automatically process numbers, dates, and special characters for proper pronunciation."></textarea>
                                <div class="mt-2 d-flex justify-content-between">
                                    <small class="text-muted">
                                        <i class="fas fa-info-circle me-1"></i>
                                        Supports smart text processing
                                    </small>
                                    <small class="text-muted" id="singleCharCount">0 characters</small>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <!-- Language Selection -->
                            <div class="mb-4">
                                <label class="form-label fw-bold">
                                    <i class="fas fa-language me-2"></i>Language
                                </label>
                                <select class="lang-select" id="singleLanguage">
                                    {% for language in languages %}
                                    <option value="{{ language }}" {% if language == 'Tiếng Việt' %}selected{% endif %}>
                                        {{ language }}
                                    </option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <!-- Voice Selection -->
                            <div class="mb-4">
                                <label class="form-label fw-bold">
                                    <i class="fas fa-microphone me-2"></i>Voice
                                </label>
                                <select class="form-select" id="singleVoice">
                                    <option value="">Select a voice...</option>
                                </select>
                                <div class="mt-2" id="singleVoiceInfo"></div>
                            </div>
                            
                            <!-- Voice Settings -->
                            <div class="accordion mb-4" id="singleSettings">
                                <div class="accordion-item border-0">
                                    <h2 class="accordion-header">
                                        <button class="accordion-button collapsed bg-light rounded" type="button" 
                                                data-bs-toggle="collapse" data-bs-target="#singleVoiceSettings">
                                            <i class="fas fa-sliders-h me-2"></i>Voice Settings
                                        </button>
                                    </h2>
                                    <div id="singleVoiceSettings" class="accordion-collapse collapse">
                                        <div class="accordion-body p-3">
                                            <!-- Speed -->
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-tachometer-alt me-2"></i>Speed</span>
                                                    <span class="text-primary fw-bold" id="singleRateValue">0%</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="singleRate" 
                                                       min="-50" max="50" value="0">
                                                <div class="d-flex justify-content-between mt-1">
                                                    <small class="text-muted">Slower</small>
                                                    <small class="text-muted">Faster</small>
                                                </div>
                                            </div>
                                            
                                            <!-- Pitch -->
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-wave-square me-2"></i>Pitch</span>
                                                    <span class="text-primary fw-bold" id="singlePitchValue">0Hz</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="singlePitch" 
                                                       min="-100" max="100" value="0">
                                                <div class="d-flex justify-content-between mt-1">
                                                    <small class="text-muted">Lower</small>
                                                    <small class="text-muted">Higher</small>
                                                </div>
                                            </div>
                                            
                                            <!-- Volume -->
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-volume-up me-2"></i>Volume</span>
                                                    <span class="text-primary fw-bold" id="singleVolumeValue">100%</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="singleVolume" 
                                                       min="50" max="150" value="100">
                                                <div class="d-flex justify-content-between mt-1">
                                                    <small class="text-muted">Quieter</small>
                                                    <small class="text-muted">Louder</small>
                                                </div>
                                            </div>
                                            
                                            <!-- Pause -->
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-pause me-2"></i>Pause Duration</span>
                                                    <span class="text-primary fw-bold" id="singlePauseValue">500ms</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="singlePause" 
                                                       min="100" max="2000" step="50" value="500">
                                            </div>
                                            
                                            <!-- Format -->
                                            <div class="mb-3">
                                                <label class="form-label">
                                                    <i class="fas fa-file-audio me-2"></i>Output Format
                                                </label>
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
                            
                            <!-- Generate Button -->
                            <button class="btn btn-gradient w-100 py-3 fw-bold" id="singleGenerateBtn">
                                <i class="fas fa-play-circle me-2"></i>Generate Audio
                            </button>
                            
                            <!-- Preview Button -->
                            <button class="btn btn-outline-primary w-100 mt-3" id="singlePreviewBtn">
                                <i class="fas fa-play me-2"></i>Preview Voice
                            </button>
                        </div>
                    </div>
                    
                    <!-- Output Section -->
                    <div class="output-panel" id="singleOutput">
                        <h4 class="fw-bold mb-4">
                            <i class="fas fa-music me-2"></i>Generated Audio
                        </h4>
                        <div class="row">
                            <div class="col-md-8">
                                <div class="audio-player bg-white rounded p-3 shadow-sm">
                                    <audio controls class="w-100" id="singleAudioElement"></audio>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="d-grid gap-2">
                                    <a href="#" class="btn btn-success" id="singleDownloadAudio">
                                        <i class="fas fa-download me-2"></i>Download Audio
                                    </a>
                                    <a href="#" class="btn btn-info" id="singleDownloadSubtitle" style="display: none;">
                                        <i class="fas fa-file-alt me-2"></i>Download Subtitles
                                    </a>
                                    <button class="btn btn-outline-primary" id="singleNewGeneration">
                                        <i class="fas fa-redo me-2"></i>New Generation
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Dialogue Tab -->
                <div class="tab-pane fade" id="dialogue" role="tabpanel">
                    <div class="row">
                        <div class="col-lg-8">
                            <div class="mb-4">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-comment-dots me-2"></i>Dialogue Format
                                </label>
                                <select class="form-select mb-3" id="dialogueFormat">
                                    <option value="multi">CHAR1: Dialogue for character 1</option>
                                    <option value="qa">Q: Question text</option>
                                    <option value="script">[SCENE] Scene description</option>
                                </select>
                                
                                <textarea class="textarea-autosize w-100" id="dialogueText" rows="10"
                                          placeholder="CHAR1: Hello, how are you?&#10;CHAR2: I'm fine, thank you! And you?&#10;CHAR1: I'm doing great!&#10;&#10;NARRATOR: They continued their conversation..."></textarea>
                                <div class="mt-2 d-flex justify-content-between">
                                    <small class="text-muted">
                                        <i class="fas fa-info-circle me-1"></i>
                                        Use prefixes like CHAR1:, CHAR2:, NARRATOR:, Q:, A:
                                    </small>
                                    <small class="text-muted" id="dialogueCharCount">0 characters</small>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <!-- Character Management -->
                            <div class="mb-4">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <label class="form-label fw-bold mb-0">
                                        <i class="fas fa-user-friends me-2"></i>Characters
                                    </label>
                                    <button class="btn btn-sm btn-primary" id="addCharacterBtn">
                                        <i class="fas fa-plus me-1"></i>Add
                                    </button>
                                </div>
                                <div id="characterList">
                                    <!-- Characters will be added here -->
                                </div>
                            </div>
                            
                            <!-- Dialogue Settings -->
                            <div class="accordion mb-4" id="dialogueSettings">
                                <div class="accordion-item border-0">
                                    <h2 class="accordion-header">
                                        <button class="accordion-button collapsed bg-light rounded" type="button" 
                                                data-bs-toggle="collapse" data-bs-target="#dialogueVoiceSettings">
                                            <i class="fas fa-cog me-2"></i>Dialogue Settings
                                        </button>
                                    </h2>
                                    <div id="dialogueVoiceSettings" class="accordion-collapse collapse">
                                        <div class="accordion-body p-3">
                                            <!-- Pause -->
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-pause me-2"></i>Pause Between Lines</span>
                                                    <span class="text-primary fw-bold" id="dialoguePauseValue">300ms</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="dialoguePause" 
                                                       min="100" max="1000" step="50" value="300">
                                            </div>
                                            
                                            <!-- Repeat -->
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-redo me-2"></i>Repeat Times</span>
                                                    <span class="text-primary fw-bold" id="dialogueRepeatValue">1x</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="dialogueRepeat" 
                                                       min="1" max="5" value="1">
                                            </div>
                                            
                                            <!-- Format -->
                                            <div class="mb-3">
                                                <label class="form-label">
                                                    <i class="fas fa-file-audio me-2"></i>Output Format
                                                </label>
                                                <select class="form-select" id="dialogueFormatSelect">
                                                    {% for format in formats %}
                                                    <option value="{{ format }}">{{ format|upper }}</option>
                                                    {% endfor %}
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Generate Button -->
                            <button class="btn btn-gradient w-100 py-3 fw-bold" id="dialogueGenerateBtn">
                                <i class="fas fa-play-circle me-2"></i>Generate Dialogue Audio
                            </button>
                        </div>
                    </div>
                    
                    <!-- Output Section -->
                    <div class="output-panel" id="dialogueOutput">
                        <h4 class="fw-bold mb-4">
                            <i class="fas fa-comments me-2"></i>Generated Dialogue Audio
                        </h4>
                        <div class="row">
                            <div class="col-md-8">
                                <div class="audio-player bg-white rounded p-3 shadow-sm">
                                    <audio controls class="w-100" id="dialogueAudioElement"></audio>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="d-grid gap-2">
                                    <a href="#" class="btn btn-success" id="dialogueDownloadAudio">
                                        <i class="fas fa-download me-2"></i>Download Audio
                                    </a>
                                    <a href="#" class="btn btn-info" id="dialogueDownloadSubtitle" style="display: none;">
                                        <i class="fas fa-file-alt me-2"></i>Download Subtitles
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Multi-Character Tab -->
                <div class="tab-pane fade" id="multi" role="tabpanel">
                    <div class="row">
                        <div class="col-lg-8">
                            <div class="mb-4">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-theater-masks me-2"></i>Script Content
                                </label>
                                <div class="bg-light rounded p-3 mb-3">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <label class="form-label">Number of Characters</label>
                                            <input type="range" class="settings-slider" id="characterCount" min="2" max="8" value="2">
                                            <div class="text-center mt-2">
                                                <span class="badge bg-primary" id="characterCountValue">2 Characters</span>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label">Script Template</label>
                                            <select class="form-select" id="scriptTemplate">
                                                <option value="conversation">Conversation</option>
                                                <option value="interview">Interview</option>
                                                <option value="story">Story Narration</option>
                                                <option value="presentation">Presentation</option>
                                            </select>
                                        </div>
                                    </div>
                                </div>
                                
                                <textarea class="textarea-autosize w-100" id="multiText" rows="12"
                                          placeholder="Character 1: Hello everyone!&#10;Character 2: Hi there!&#10;Character 1: Today we're going to discuss...&#10;Character 2: That sounds interesting!"></textarea>
                                <div class="mt-2 d-flex justify-content-between">
                                    <small class="text-muted">
                                        <i class="fas fa-info-circle me-1"></i>
                                        Assign voices to each character below
                                    </small>
                                    <small class="text-muted" id="multiCharCount">0 characters</small>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <!-- Character Voices -->
                            <div class="mb-4">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-microphone-alt me-2"></i>Character Voices
                                </label>
                                <div id="multiCharacterVoices">
                                    <!-- Character voice settings will be added here -->
                                </div>
                            </div>
                            
                            <!-- Multi Settings -->
                            <div class="accordion mb-4" id="multiSettings">
                                <div class="accordion-item border-0">
                                    <h2 class="accordion-header">
                                        <button class="accordion-button collapsed bg-light rounded" type="button" 
                                                data-bs-toggle="collapse" data-bs-target="#multiVoiceSettings">
                                            <i class="fas fa-cog me-2"></i>Settings
                                        </button>
                                    </h2>
                                    <div id="multiVoiceSettings" class="accordion-collapse collapse">
                                        <div class="accordion-body p-3">
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-pause me-2"></i>Pause Between Characters</span>
                                                    <span class="text-primary fw-bold" id="multiPauseValue">500ms</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="multiPause" 
                                                       min="100" max="2000" step="50" value="500">
                                            </div>
                                            
                                            <div class="mb-3">
                                                <label class="form-label d-flex justify-content-between">
                                                    <span><i class="fas fa-redo me-2"></i>Repeat Times</span>
                                                    <span class="text-primary fw-bold" id="multiRepeatValue">1x</span>
                                                </label>
                                                <input type="range" class="settings-slider" id="multiRepeat" 
                                                       min="1" max="5" value="1">
                                            </div>
                                            
                                            <div class="mb-3">
                                                <label class="form-label">
                                                    <i class="fas fa-file-audio me-2"></i>Output Format
                                                </label>
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
                            
                            <!-- Generate Button -->
                            <button class="btn btn-gradient w-100 py-3 fw-bold" id="multiGenerateBtn">
                                <i class="fas fa-users me-2"></i>Generate Multi-Character Audio
                            </button>
                        </div>
                    </div>
                    
                    <!-- Output Section -->
                    <div class="output-panel" id="multiOutput">
                        <h4 class="fw-bold mb-4">
                            <i class="fas fa-users me-2"></i>Generated Multi-Character Audio
                        </h4>
                        <div class="row">
                            <div class="col-md-8">
                                <div class="audio-player bg-white rounded p-3 shadow-sm">
                                    <audio controls class="w-100" id="multiAudioElement"></audio>
                                </div>
                            </div>
                            <div class="col-md-4">
                                <div class="d-grid gap-2">
                                    <a href="#" class="btn btn-success" id="multiDownloadAudio">
                                        <i class="fas fa-download me-2"></i>Download Audio
                                    </a>
                                    <a href="#" class="btn btn-info" id="multiDownloadSubtitle" style="display: none;">
                                        <i class="fas fa-file-alt me-2"></i>Download Subtitles
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Batch Tab -->
                <div class="tab-pane fade" id="batch" role="tabpanel">
                    <div class="row">
                        <div class="col-lg-8">
                            <div class="mb-4">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-layer-group me-2"></i>Batch Processing
                                </label>
                                <div class="bg-light rounded p-4 mb-4">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <h5><i class="fas fa-upload me-2"></i>Import Options</h5>
                                            <div class="d-grid gap-2">
                                                <button class="btn btn-outline-primary" id="importTxtBtn">
                                                    <i class="fas fa-file-alt me-2"></i>Import TXT File
                                                </button>
                                                <button class="btn btn-outline-primary" id="importJsonBtn">
                                                    <i class="fas fa-code me-2"></i>Import JSON Data
                                                </button>
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <h5><i class="fas fa-list me-2"></i>Current Items</h5>
                                            <div class="alert alert-info">
                                                <i class="fas fa-info-circle me-2"></i>
                                                <span id="batchItemCount">0 items ready</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="table-responsive">
                                    <table class="table table-hover" id="batchTable">
                                        <thead>
                                            <tr>
                                                <th>#</th>
                                                <th>Text Content</th>
                                                <th>Voice</th>
                                                <th>Status</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <!-- Batch items will be added here -->
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <!-- Batch Settings -->
                            <div class="mb-4">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-sliders-h me-2"></i>Batch Settings
                                </label>
                                
                                <div class="mb-3">
                                    <label class="form-label">Default Voice</label>
                                    <select class="form-select" id="batchDefaultVoice">
                                        <option value="">Select default voice...</option>
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Output Format</label>
                                    <select class="form-select" id="batchFormat">
                                        {% for format in formats %}
                                        <option value="{{ format }}">{{ format|upper }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label">Output Directory</label>
                                    <input type="text" class="form-control" id="batchOutputDir" value="batch_output">
                                </div>
                            </div>
                            
                            <!-- Batch Actions -->
                            <div class="d-grid gap-2">
                                <button class="btn btn-primary" id="addBatchItemBtn">
                                    <i class="fas fa-plus me-2"></i>Add Item
                                </button>
                                <button class="btn btn-success" id="startBatchBtn">
                                    <i class="fas fa-play me-2"></i>Start Batch Processing
                                </button>
                                <button class="btn btn-warning" id="clearBatchBtn">
                                    <i class="fas fa-trash me-2"></i>Clear All
                                </button>
                            </div>
                            
                            <!-- Batch Progress -->
                            <div class="mt-4" id="batchProgress" style="display: none;">
                                <label class="form-label fw-bold mb-3">
                                    <i class="fas fa-tasks me-2"></i>Processing Progress
                                </label>
                                <div class="progress" style="height: 10px;">
                                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                                         id="batchProgressBar" style="width: 0%"></div>
                                </div>
                                <div class="text-center mt-2">
                                    <small id="batchProgressText">0/0 items processed</small>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Settings Tab -->
                <div class="tab-pane fade" id="settings" role="tabpanel">
                    <div class="row">
                        <div class="col-lg-8">
                            <div class="mb-4">
                                <h4 class="fw-bold mb-4">
                                    <i class="fas fa-cog me-2"></i>Application Settings
                                </h4>
                                
                                <div class="accordion" id="settingsAccordion">
                                    <!-- Audio Settings -->
                                    <div class="accordion-item">
                                        <h2 class="accordion-header">
                                            <button class="accordion-button" type="button" 
                                                    data-bs-toggle="collapse" data-bs-target="#audioSettings">
                                                <i class="fas fa-volume-up me-2"></i>Audio Settings
                                            </button>
                                        </h2>
                                        <div id="audioSettings" class="accordion-collapse collapse show">
                                            <div class="accordion-body">
                                                <div class="row">
                                                    <div class="col-md-6">
                                                        <div class="mb-3">
                                                            <label class="form-label">Default Bitrate</label>
                                                            <select class="form-select" id="defaultBitrate">
                                                                <option value="128">128 kbps</option>
                                                                <option value="192" selected>192 kbps</option>
                                                                <option value="256">256 kbps</option>
                                                                <option value="320">320 kbps</option>
                                                            </select>
                                                        </div>
                                                        
                                                        <div class="mb-3">
                                                            <label class="form-label">Audio Effects</label>
                                                            <div class="form-check">
                                                                <input class="form-check-input" type="checkbox" id="enableNormalization" checked>
                                                                <label class="form-check-label" for="enableNormalization">
                                                                    Enable Normalization
                                                                </label>
                                                            </div>
                                                            <div class="form-check">
                                                                <input class="form-check-input" type="checkbox" id="enableCompression" checked>
                                                                <label class="form-check-label" for="enableCompression">
                                                                    Enable Compression
                                                                </label>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <div class="col-md-6">
                                                        <div class="mb-3">
                                                            <label class="form-label">Default Pause Duration</label>
                                                            <input type="range" class="settings-slider" id="defaultPause" 
                                                                   min="100" max="2000" step="50" value="500">
                                                            <div class="text-center mt-2">
                                                                <span class="badge bg-primary" id="defaultPauseValue">500ms</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <!-- Text Processing -->
                                    <div class="accordion-item">
                                        <h2 class="accordion-header">
                                            <button class="accordion-button collapsed" type="button" 
                                                    data-bs-toggle="collapse" data-bs-target="#textProcessing">
                                                <i class="fas fa-text-height me-2"></i>Text Processing
                                            </button>
                                        </h2>
                                        <div id="textProcessing" class="accordion-collapse collapse">
                                            <div class="accordion-body">
                                                <div class="mb-3">
                                                    <label class="form-label">Smart Text Processing</label>
                                                    <div class="form-check">
                                                        <input class="form-check-input" type="checkbox" id="processNumbers" checked>
                                                        <label class="form-check-label" for="processNumbers">
                                                            Convert numbers to words
                                                        </label>
                                                    </div>
                                                    <div class="form-check">
                                                        <input class="form-check-input" type="checkbox" id="processDates" checked>
                                                        <label class="form-check-label" for="processDates">
                                                            Process dates and times
                                                        </label>
                                                    </div>
                                                    <div class="form-check">
                                                        <input class="form-check-input" type="checkbox" id="processCurrency" checked>
                                                        <label class="form-check-label" for="processCurrency">
                                                            Process currency symbols
                                                        </label>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    <!-- Export Settings -->
                                    <div class="accordion-item">
                                        <h2 class="accordion-header">
                                            <button class="accordion-button collapsed" type="button" 
                                                    data-bs-toggle="collapse" data-bs-target="#exportSettings">
                                                <i class="fas fa-download me-2"></i>Export Settings
                                            </button>
                                        </h2>
                                        <div id="exportSettings" class="accordion-collapse collapse">
                                            <div class="accordion-body">
                                                <div class="mb-3">
                                                    <label class="form-label">Default Export Location</label>
                                                    <input type="text" class="form-control" id="exportLocation" value="outputs">
                                                </div>
                                                
                                                <div class="mb-3">
                                                    <label class="form-label">Auto-cleanup Files Older Than</label>
                                                    <select class="form-select" id="cleanupInterval">
                                                        <option value="1">1 hour</option>
                                                        <option value="6">6 hours</option>
                                                        <option value="24" selected>24 hours</option>
                                                        <option value="168">1 week</option>
                                                    </select>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-lg-4">
                            <!-- Quick Actions -->
                            <div class="mb-4">
                                <h5 class="fw-bold mb-3">
                                    <i class="fas fa-bolt me-2"></i>Quick Actions
                                </h5>
                                <div class="d-grid gap-2">
                                    <button class="btn btn-outline-primary" id="exportSettingsBtn">
                                        <i class="fas fa-save me-2"></i>Export Settings
                                    </button>
                                    <button class="btn btn-outline-primary" id="importSettingsBtn">
                                        <i class="fas fa-folder-open me-2"></i>Import Settings
                                    </button>
                                    <button class="btn btn-outline-warning" id="resetSettingsBtn">
                                        <i class="fas fa-undo me-2"></i>Reset to Defaults
                                    </button>
                                    <button class="btn btn-outline-danger" id="clearCacheBtn">
                                        <i class="fas fa-trash me-2"></i>Clear Cache
                                    </button>
                                </div>
                            </div>
                            
                            <!-- System Info -->
                            <div class="card">
                                <div class="card-body">
                                    <h5 class="card-title">
                                        <i class="fas fa-info-circle me-2"></i>System Information
                                    </h5>
                                    <ul class="list-unstyled">
                                        <li class="mb-2">
                                            <small class="text-muted">Version:</small>
                                            <div class="fw-bold">TTS Pro 2.0.0</div>
                                        </li>
                                        <li class="mb-2">
                                            <small class="text-muted">Voices Available:</small>
                                            <div class="fw-bold">{{ all_voices|length }}+ voices</div>
                                        </li>
                                        <li class="mb-2">
                                            <small class="text-muted">Languages:</small>
                                            <div class="fw-bold">{{ languages|length }}+ languages</div>
                                        </li>
                                        <li>
                                            <small class="text-muted">Last Updated:</small>
                                            <div class="fw-bold" id="lastUpdated">Just now</div>
                                        </li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Progress Modal -->
    <div class="progress-modal" id="progressModal">
        <div class="progress-modal-content">
            <div class="progress-ring mb-4">
                <svg width="120" height="120" viewBox="0 0 120 120">
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#e9ecef" stroke-width="12"/>
                    <circle cx="60" cy="60" r="54" fill="none" stroke="#4361ee" stroke-width="12" 
                            stroke-linecap="round" stroke-dasharray="339" stroke-dashoffset="339" 
                            class="progress-ring__circle" id="progressCircle"/>
                </svg>
                <div class="position-absolute top-50 start-50 translate-middle">
                    <h2 class="mb-0 fw-bold" id="progressPercent">0%</h2>
                </div>
            </div>
            
            <h4 class="fw-bold mb-3" id="progressTitle">Generating Audio...</h4>
            <p class="text-muted mb-4" id="progressMessage">Initializing...</p>
            
            <div class="audio-wave">
                <div class="audio-wave-bar"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.1s"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.2s"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.3s"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.4s"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.5s"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.6s"></div>
                <div class="audio-wave-bar" style="animation-delay: 0.7s"></div>
            </div>
            
            <button class="btn btn-outline-danger mt-4" id="cancelGenerationBtn">
                <i class="fas fa-times me-2"></i>Cancel
            </button>
        </div>
    </div>

    <!-- Toast Container -->
    <div class="toast-container" id="toastContainer"></div>

    <!-- Scripts -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
    <script>
        // Global variables
        let currentTaskId = null;
        let progressWebSocket = null;
        let batchItems = [];
        let characters = [];
        
        // Initialize Select2
        $(document).ready(function() {
            $('.form-select').select2({
                theme: 'bootstrap-5',
                width: '100%'
            });
        });
        
        // Character counter
        function updateCharCount(textareaId, counterId) {
            const textarea = document.getElementById(textareaId);
            const counter = document.getElementById(counterId);
            
            textarea.addEventListener('input', function() {
                counter.textContent = this.value.length + ' characters';
            });
            
            counter.textContent = textarea.value.length + ' characters';
        }
        
        // Update all character counters
        updateCharCount('singleText', 'singleCharCount');
        updateCharCount('dialogueText', 'dialogueCharCount');
        updateCharCount('multiText', 'multiCharCount');
        
        // Show toast notification
        function showToast(message, type = 'info', duration = 3000) {
            const toastContainer = document.getElementById('toastContainer');
            const toastId = 'toast-' + Date.now();
            
            const icon = {
                'success': 'fa-check-circle',
                'error': 'fa-exclamation-circle',
                'warning': 'fa-exclamation-triangle',
                'info': 'fa-info-circle'
            }[type] || 'fa-info-circle';
            
            const color = {
                'success': 'var(--success)',
                'error': 'var(--danger)',
                'warning': 'var(--warning)',
                'info': 'var(--primary)'
            }[type] || 'var(--primary)';
            
            const toast = document.createElement('div');
            toast.className = 'custom-toast';
            toast.id = toastId;
            toast.style.borderLeftColor = color;
            toast.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="fas ${icon} me-3" style="color: ${color}; font-size: 1.2rem;"></i>
                    <div class="flex-grow-1">
                        <div class="fw-bold">${message}</div>
                    </div>
                    <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
                </div>
            `;
            
            toastContainer.appendChild(toast);
            
            setTimeout(() => {
                if (document.getElementById(toastId)) {
                    toast.remove();
                }
            }, duration);
        }
        
        // Show progress modal
        function showProgressModal(title = 'Generating Audio...') {
            document.getElementById('progressTitle').textContent = title;
            document.getElementById('progressModal').style.display = 'flex';
        }
        
        // Hide progress modal
        function hideProgressModal() {
            document.getElementById('progressModal').style.display = 'none';
            if (progressWebSocket) {
                progressWebSocket.close();
                progressWebSocket = null;
            }
            currentTaskId = null;
        }
        
        // Update progress
        function updateProgress(percent, message) {
            const circle = document.getElementById('progressCircle');
            const radius = 54;
            const circumference = 2 * Math.PI * radius;
            const offset = circumference - (percent / 100) * circumference;
            
            circle.style.strokeDashoffset = offset;
            document.getElementById('progressPercent').textContent = percent + '%';
            document.getElementById('progressMessage').textContent = message;
        }
        
        // Load voices for language
        async function loadVoices(language, targetSelectId) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                const select = document.getElementById(targetSelectId);
                select.innerHTML = '<option value="">Select a voice...</option>';
                
                data.voices.forEach(voice => {
                    const option = document.createElement('option');
                    option.value = voice.name;
                    option.textContent = `${voice.display} (${voice.gender}) - ${voice.name}`;
                    select.appendChild(option);
                });
                
                $(select).trigger('change');
            } catch (error) {
                console.error('Error loading voices:', error);
                showToast('Error loading voices', 'error');
            }
        }
        
        // Initialize voice loading
        document.getElementById('singleLanguage').addEventListener('change', function() {
            loadVoices(this.value, 'singleVoice');
        });
        
        // Load default voices
        loadVoices('Tiếng Việt', 'singleVoice');
        
        // Update slider values
        function initSliders() {
            const sliders = document.querySelectorAll('.settings-slider');
            sliders.forEach(slider => {
                const valueId = slider.id + 'Value';
                const valueElement = document.getElementById(valueId);
                
                if (valueElement) {
                    const updateValue = () => {
                        const suffix = slider.id.includes('Pause') ? 'ms' : 
                                      slider.id.includes('Repeat') ? 'x' :
                                      slider.id.includes('Rate') ? '%' :
                                      slider.id.includes('Pitch') ? 'Hz' :
                                      slider.id.includes('Volume') ? '%' : '';
                        valueElement.textContent = slider.value + suffix;
                    };
                    
                    slider.addEventListener('input', updateValue);
                    updateValue();
                }
            });
        }
        
        initSliders();
        
        // Single voice generation
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
            
            currentTaskId = 'single_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            // Show progress modal
            showProgressModal('Generating Single Voice Audio...');
            updateProgress(0, 'Starting...');
            
            // Connect to WebSocket for progress updates
            progressWebSocket = new WebSocket(`ws://${window.location.host}/ws/progress/${currentTaskId}`);
            
            progressWebSocket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateProgress(data.progress, data.message);
                
                if (data.progress >= 100) {
                    setTimeout(() => {
                        checkTaskResult(currentTaskId);
                    }, 1000);
                }
            };
            
            progressWebSocket.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
            
            // Start generation
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', document.getElementById('singleRate').value);
            formData.append('pitch', document.getElementById('singlePitch').value);
            formData.append('volume', document.getElementById('singleVolume').value);
            formData.append('pause', document.getElementById('singlePause').value);
            formData.append('output_format', document.getElementById('singleFormat').value);
            formData.append('task_id', currentTaskId);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    showToast(result.message || 'Generation failed', 'error');
                    hideProgressModal();
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
                hideProgressModal();
            }
        });
        
        // Check task result
        async function checkTaskResult(taskId) {
            try {
                const response = await fetch(`/api/task/${taskId}/result`);
                const result = await response.json();
                
                if (result.complete) {
                    hideProgressModal();
                    
                    if (result.success) {
                        // Show output panel
                        const outputPanel = document.getElementById('singleOutput');
                        outputPanel.style.display = 'block';
                        
                        // Set audio player
                        const audioElement = document.getElementById('singleAudioElement');
                        audioElement.src = result.audio_url;
                        audioElement.load();
                        
                        // Set download links
                        document.getElementById('singleDownloadAudio').href = result.audio_url;
                        if (result.srt_url) {
                            document.getElementById('singleDownloadSubtitle').href = result.srt_url;
                            document.getElementById('singleDownloadSubtitle').style.display = 'inline-block';
                        }
                        
                        showToast('Audio generated successfully!', 'success');
                    } else {
                        showToast(result.message || 'Generation failed', 'error');
                    }
                } else {
                    // Check again after delay
                    setTimeout(() => checkTaskResult(taskId), 1000);
                }
            } catch (error) {
                console.error('Error checking task result:', error);
                hideProgressModal();
                showToast('Error checking generation status', 'error');
            }
        }
        
        // Character management for dialogue tab
        document.getElementById('addCharacterBtn').addEventListener('click', function() {
            const characterList = document.getElementById('characterList');
            const characterCount = characterList.children.length + 1;
            
            const characterDiv = document.createElement('div');
            characterDiv.className = 'character-settings';
            characterDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0 fw-bold">
                        <i class="fas fa-user me-2"></i>Character ${characterCount}
                    </h6>
                    <button type="button" class="btn btn-sm btn-outline-danger remove-character">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="row">
                    <div class="col-md-6 mb-2">
                        <input type="text" class="form-control form-control-sm character-name" 
                               placeholder="Character name" value="CHAR${characterCount}">
                    </div>
                    <div class="col-md-6 mb-2">
                        <select class="form-select form-select-sm character-voice">
                            <option value="">Select voice...</option>
                        </select>
                    </div>
                </div>
                <div class="row">
                    <div class="col-4">
                        <small class="d-block text-muted">Speed</small>
                        <input type="range" class="form-range form-range-sm character-rate" 
                               min="-50" max="50" value="0">
                        <small class="character-rate-value">0%</small>
                    </div>
                    <div class="col-4">
                        <small class="d-block text-muted">Pitch</small>
                        <input type="range" class="form-range form-range-sm character-pitch" 
                               min="-100" max="100" value="0">
                        <small class="character-pitch-value">0Hz</small>
                    </div>
                    <div class="col-4">
                        <small class="d-block text-muted">Volume</small>
                        <input type="range" class="form-range form-range-sm character-volume" 
                               min="50" max="150" value="100">
                        <small class="character-volume-value">100%</small>
                    </div>
                </div>
            `;
            
            characterList.appendChild(characterDiv);
            
            // Load voices for this character
            loadVoices('Tiếng Việt', characterDiv.querySelector('.character-voice').id);
            
            // Initialize sliders
            initCharacterSliders(characterDiv);
            
            // Add remove functionality
            characterDiv.querySelector('.remove-character').addEventListener('click', function() {
                characterDiv.remove();
                updateCharacterNumbers();
            });
        });
        
        // Initialize character sliders
        function initCharacterSliders(characterDiv) {
            const sliders = characterDiv.querySelectorAll('.form-range');
            sliders.forEach(slider => {
                const valueElement = slider.nextElementSibling;
                
                slider.addEventListener('input', function() {
                    const suffix = slider.classList.contains('character-rate') ? '%' :
                                  slider.classList.contains('character-pitch') ? 'Hz' :
                                  slider.classList.contains('character-volume') ? '%' : '';
                    valueElement.textContent = this.value + suffix;
                });
                
                // Trigger initial update
                slider.dispatchEvent(new Event('input'));
            });
        }
        
        // Update character numbers
        function updateCharacterNumbers() {
            const characterList = document.getElementById('characterList');
            const characters = characterList.children;
            
            for (let i = 0; i < characters.length; i++) {
                const characterDiv = characters[i];
                const title = characterDiv.querySelector('h6');
                title.innerHTML = `<i class="fas fa-user me-2"></i>Character ${i + 1}`;
            }
        }
        
        // Dialogue generation
        document.getElementById('dialogueGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('dialogueText').value.trim();
            
            if (!text) {
                showToast('Please enter dialogue text', 'error');
                return;
            }
            
            // Collect character data
            const characterElements = document.querySelectorAll('.character-settings');
            const characters = [];
            
            characterElements.forEach((element, index) => {
                const name = element.querySelector('.character-name').value || `CHAR${index + 1}`;
                const voice = element.querySelector('.character-voice').value;
                
                if (voice) {
                    characters.push({
                        name: name,
                        voice: voice,
                        rate: parseInt(element.querySelector('.character-rate').value),
                        pitch: parseInt(element.querySelector('.character-pitch').value),
                        volume: parseInt(element.querySelector('.character-volume').value)
                    });
                }
            });
            
            if (characters.length === 0) {
                showToast('Please add at least one character with voice', 'error');
                return;
            }
            
            currentTaskId = 'dialogue_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            showProgressModal('Generating Dialogue Audio...');
            updateProgress(0, 'Starting...');
            
            // Connect to WebSocket
            progressWebSocket = new WebSocket(`ws://${window.location.host}/ws/progress/${currentTaskId}`);
            
            progressWebSocket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateProgress(data.progress, data.message);
                
                if (data.progress >= 100) {
                    setTimeout(() => {
                        checkDialogueResult(currentTaskId);
                    }, 1000);
                }
            };
            
            // Start generation
            const formData = new FormData();
            formData.append('text', text);
            formData.append('characters', JSON.stringify(characters));
            formData.append('pause', document.getElementById('dialoguePause').value);
            formData.append('repeat', document.getElementById('dialogueRepeat').value);
            formData.append('output_format', document.getElementById('dialogueFormatSelect').value);
            formData.append('task_id', currentTaskId);
            
            try {
                const response = await fetch('/api/generate/dialogue', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    showToast(result.message || 'Generation failed', 'error');
                    hideProgressModal();
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
                hideProgressModal();
            }
        });
        
        // Check dialogue result
        async function checkDialogueResult(taskId) {
            try {
                const response = await fetch(`/api/task/${taskId}/result`);
                const result = await response.json();
                
                if (result.complete) {
                    hideProgressModal();
                    
                    if (result.success) {
                        // Show output panel
                        const outputPanel = document.getElementById('dialogueOutput');
                        outputPanel.style.display = 'block';
                        
                        // Set audio player
                        const audioElement = document.getElementById('dialogueAudioElement');
                        audioElement.src = result.audio_url;
                        audioElement.load();
                        
                        // Set download links
                        document.getElementById('dialogueDownloadAudio').href = result.audio_url;
                        if (result.srt_url) {
                            document.getElementById('dialogueDownloadSubtitle').href = result.srt_url;
                            document.getElementById('dialogueDownloadSubtitle').style.display = 'inline-block';
                        }
                        
                        showToast('Dialogue audio generated successfully!', 'success');
                    } else {
                        showToast(result.message || 'Generation failed', 'error');
                    }
                } else {
                    setTimeout(() => checkDialogueResult(taskId), 1000);
                }
            } catch (error) {
                console.error('Error checking dialogue result:', error);
                hideProgressModal();
                showToast('Error checking generation status', 'error');
            }
        }
        
        // Initialize with default character
        document.getElementById('addCharacterBtn').click();
        
        // Cancel generation
        document.getElementById('cancelGenerationBtn').addEventListener('click', function() {
            hideProgressModal();
            showToast('Generation cancelled', 'warning');
        });
        
        // New generation
        document.getElementById('singleNewGeneration').addEventListener('click', function() {
            document.getElementById('singleOutput').style.display = 'none';
            document.getElementById('singleText').value = '';
            document.getElementById('singleText').focus();
        });
        
        // Auto-cleanup on load
        window.addEventListener('load', () => {
            fetch('/api/cleanup', { method: 'POST' }).catch(console.error);
            
            // Update last updated time
            document.getElementById('lastUpdated').textContent = 
                new Date().toLocaleString('vi-VN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
        });
        
        // Voice preview
        document.getElementById('singlePreviewBtn').addEventListener('click', async function() {
            const voice = document.getElementById('singleVoice').value;
            const text = "This is a preview of the selected voice. Hello, how are you today?";
            
            if (!voice) {
                showToast('Please select a voice first', 'error');
                return;
            }
            
            showProgressModal('Generating Preview...');
            updateProgress(0, 'Generating preview audio...');
            
            const tempTaskId = 'preview_' + Date.now();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', document.getElementById('singleRate').value);
            formData.append('pitch', document.getElementById('singlePitch').value);
            formData.append('volume', document.getElementById('singleVolume').value);
            formData.append('pause', 300);
            formData.append('output_format', 'mp3');
            formData.append('task_id', tempTaskId);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Poll for result
                    const checkPreview = setInterval(async () => {
                        try {
                            const resultResponse = await fetch(`/api/task/${tempTaskId}/result`);
                            const previewResult = await resultResponse.json();
                            
                            if (previewResult.complete && previewResult.success) {
                                clearInterval(checkPreview);
                                hideProgressModal();
                                
                                // Play preview
                                const audio = new Audio(previewResult.audio_url);
                                audio.play();
                                
                                showToast('Preview playing...', 'success');
                            }
                        } catch (error) {
                            console.error('Error checking preview:', error);
                            clearInterval(checkPreview);
                            hideProgressModal();
                        }
                    }, 500);
                } else {
                    hideProgressModal();
                    showToast('Preview generation failed', 'error');
                }
            } catch (error) {
                console.error('Error:', error);
                hideProgressModal();
                showToast('Preview generation failed', 'error');
            }
        });
        
        // Initialize multi-character tab
        document.getElementById('characterCount').addEventListener('input', function() {
            const value = this.value;
            document.getElementById('characterCountValue').textContent = value + ' Characters';
            updateMultiCharacterVoices(value);
        });
        
        function updateMultiCharacterVoices(count) {
            const container = document.getElementById('multiCharacterVoices');
            container.innerHTML = '';
            
            for (let i = 1; i <= count; i++) {
                const characterDiv = document.createElement('div');
                characterDiv.className = 'character-settings mb-3';
                characterDiv.innerHTML = `
                    <h6 class="fw-bold mb-2">
                        <i class="fas fa-user me-2"></i>Character ${i}
                    </h6>
                    <div class="row">
                        <div class="col-md-6 mb-2">
                            <input type="text" class="form-control form-control-sm" 
                                   placeholder="Character name" value="Character ${i}">
                        </div>
                        <div class="col-md-6 mb-2">
                            <select class="form-select form-select-sm multi-character-voice">
                                <option value="">Select voice...</option>
                            </select>
                        </div>
                    </div>
                `;
                container.appendChild(characterDiv);
                
                // Load voices
                loadVoices('Tiếng Việt', characterDiv.querySelector('.multi-character-voice').id);
            }
        }
        
        // Initialize with 2 characters
        updateMultiCharacterVoices(2);
        
        // Multi-character generation
        document.getElementById('multiGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('multiText').value.trim();
            
            if (!text) {
                showToast('Please enter script text', 'error');
                return;
            }
            
            // Collect character data
            const characterElements = document.querySelectorAll('#multiCharacterVoices .character-settings');
            const characters = [];
            
            characterElements.forEach((element, index) => {
                const name = element.querySelector('input[type="text"]').value || `Character ${index + 1}`;
                const voice = element.querySelector('.multi-character-voice').value;
                
                if (voice) {
                    characters.push({
                        name: name.toUpperCase().replace(/\s+/g, '_'),
                        voice: voice,
                        rate: 0,
                        pitch: 0,
                        volume: 100
                    });
                }
            });
            
            if (characters.length === 0) {
                showToast('Please select voices for characters', 'error');
                return;
            }
            
            currentTaskId = 'multi_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            
            showProgressModal('Generating Multi-Character Audio...');
            updateProgress(0, 'Starting...');
            
            // Connect to WebSocket
            progressWebSocket = new WebSocket(`ws://${window.location.host}/ws/progress/${currentTaskId}`);
            
            progressWebSocket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateProgress(data.progress, data.message);
                
                if (data.progress >= 100) {
                    setTimeout(() => {
                        checkMultiResult(currentTaskId);
                    }, 1000);
                }
            };
            
            // Format text with character names
            let formattedText = text;
            characters.forEach(char => {
                const regex = new RegExp(`${char.name.replace('_', '\\s*')}:`, 'gi');
                formattedText = formattedText.replace(regex, `${char.name}:`);
            });
            
            // Start generation
            const formData = new FormData();
            formData.append('text', formattedText);
            formData.append('characters', JSON.stringify({
                characters: characters
            }));
            formData.append('pause', document.getElementById('multiPause').value);
            formData.append('repeat', document.getElementById('multiRepeat').value);
            formData.append('output_format', document.getElementById('multiFormat').value);
            formData.append('task_id', currentTaskId);
            
            try {
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (!result.success) {
                    showToast(result.message || 'Generation failed', 'error');
                    hideProgressModal();
                }
            } catch (error) {
                console.error('Error:', error);
                showToast('Generation failed: ' + error.message, 'error');
                hideProgressModal();
            }
        });
        
        // Check multi result
        async function checkMultiResult(taskId) {
            try {
                const response = await fetch(`/api/task/${taskId}/result`);
                const result = await response.json();
                
                if (result.complete) {
                    hideProgressModal();
                    
                    if (result.success) {
                        // Show output panel
                        const outputPanel = document.getElementById('multiOutput');
                        outputPanel.style.display = 'block';
                        
                        // Set audio player
                        const audioElement = document.getElementById('multiAudioElement');
                        audioElement.src = result.audio_url;
                        audioElement.load();
                        
                        // Set download links
                        document.getElementById('multiDownloadAudio').href = result.audio_url;
                        if (result.srt_url) {
                            document.getElementById('multiDownloadSubtitle').href = result.srt_url;
                            document.getElementById('multiDownloadSubtitle').style.display = 'inline-block';
                        }
                        
                        showToast('Multi-character audio generated successfully!', 'success');
                    } else {
                        showToast(result.message || 'Generation failed', 'error');
                    }
                } else {
                    setTimeout(() => checkMultiResult(taskId), 1000);
                }
            } catch (error) {
                console.error('Error checking multi result:', error);
                hideProgressModal();
                showToast('Error checking generation status', 'error');
            }
        }
    </script>
</body>
</html>
"""

# Create the HTML file
with open("templates/index_pro.html", "w", encoding="utf-8") as f:
    f.write(index_pro_html)

# Create static directory for additional assets
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# Create enhanced CSS file
enhanced_css = """
/* Additional custom styles for TTS Pro */
.select2-container--bootstrap-5 .select2-selection {
    border: 2px solid #dee2e6;
    border-radius: 10px;
    transition: all 0.3s;
}

.select2-container--bootstrap-5.select2-container--focus .select2-selection {
    border-color: #4361ee;
    box-shadow: 0 0 0 0.25rem rgba(67, 97, 238, 0.25);
}

.select2-container--bootstrap-5 .select2-selection--single {
    height: 42px;
    padding: 5px;
}

.select2-container--bootstrap-5 .select2-selection--single .select2-selection__rendered {
    line-height: 30px;
    padding-left: 0;
}

/* Animation for progress ring */
@keyframes progress-ring-fill {
    from {
        stroke-dashoffset: 339;
    }
    to {
        stroke-dashoffset: var(--progress-offset);
    }
}

/* Voice card animations */
.voice-card {
    animation: fadeInUp 0.5s ease;
}

@keyframes fadeInUp {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

/* Audio wave animation */
@keyframes wave-animation {
    0%, 100% {
        transform: scaleY(0.2);
    }
    50% {
        transform: scaleY(1);
    }
}

.audio-wave-bar {
    animation: wave-animation 1s ease-in-out infinite;
}

.audio-wave-bar:nth-child(2) { animation-delay: 0.1s; }
.audio-wave-bar:nth-child(3) { animation-delay: 0.2s; }
.audio-wave-bar:nth-child(4) { animation-delay: 0.3s; }
.audio-wave-bar:nth-child(5) { animation-delay: 0.4s; }
.audio-wave-bar:nth-child(6) { animation-delay: 0.5s; }
.audio-wave-bar:nth-child(7) { animation-delay: 0.6s; }
.audio-wave-bar:nth-child(8) { animation-delay: 0.7s; }

/* Character badges */
.character-badge {
    animation: badgePulse 2s infinite;
}

@keyframes badgePulse {
    0%, 100% {
        box-shadow: 0 0 0 0 rgba(67, 97, 238, 0.7);
    }
    50% {
        box-shadow: 0 0 0 10px rgba(67, 97, 238, 0);
    }
}

/* Settings slider customization */
.settings-slider::-webkit-slider-thumb {
    transition: all 0.2s;
}

.settings-slider::-webkit-slider-thumb:hover {
    transform: scale(1.1);
    box-shadow: 0 0 0 3px rgba(67, 97, 238, 0.2);
}

/* Responsive adjustments */
@media (max-width: 768px) {
    .glass-card {
        margin: 0.5rem;
        border-radius: 15px;
    }
    
    .nav-tabs.glass {
        overflow-x: auto;
        flex-wrap: nowrap;
    }
    
    .nav-tabs.glass .nav-link {
        white-space: nowrap;
        padding: 0.5rem 1rem;
        font-size: 0.875rem;
    }
    
    .progress-modal-content {
        width: 95%;
        margin: 0.5rem;
        padding: 1.5rem;
    }
    
    .textarea-autosize {
        min-height: 150px;
    }
}

/* Dark mode support */
@media (prefers-color-scheme: dark) {
    .glass-card {
        background: rgba(33, 37, 41, 0.95);
        color: #f8f9fa;
    }
    
    .voice-card {
        background: #2d3748;
        color: #f8f9fa;
    }
    
    .textarea-autosize {
        background: #2d3748;
        color: #f8f9fa;
        border-color: #4a5568;
    }
    
    .select2-container--bootstrap-5 .select2-selection {
        background: #2d3748;
        border-color: #4a5568;
        color: #f8f9fa;
    }
}

/* Print styles */
@media print {
    .glass-card {
        box-shadow: none;
        border: 1px solid #dee2e6;
    }
    
    .nav-tabs, 
    .progress-modal,
    .toast-container {
        display: none !important;
    }
}

/* Loading animations */
.loading-dots::after {
    content: '.';
    animation: dots 1.5s steps(4, end) infinite;
}

@keyframes dots {
    0%, 20% { content: '.'; }
    40% { content: '..'; }
    60% { content: '...'; }
    80%, 100% { content: ''; }
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 10px;
}

::-webkit-scrollbar-thumb {
    background: #4361ee;
    border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
    background: #3a0ca3;
}

/* Tooltip styling */
.custom-tooltip {
    position: relative;
    display: inline-block;
}

.custom-tooltip .tooltip-text {
    visibility: hidden;
    background-color: #333;
    color: #fff;
    text-align: center;
    border-radius: 6px;
    padding: 5px 10px;
    position: absolute;
    z-index: 1;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 0.875rem;
    white-space: nowrap;
}

.custom-tooltip:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}
"""

with open("static/css/enhanced.css", "w", encoding="utf-8") as f:
    f.write(enhanced_css)

# Create JavaScript file
enhanced_js = """
// Enhanced JavaScript for TTS Pro

// Global state
const appState = {
    currentTab: 'single',
    currentTaskId: null,
    activeWebSocket: null,
    batchItems: [],
    characters: [],
    settings: {}
};

// Initialize application
function initApp() {
    // Load saved settings
    loadSettings();
    
    // Initialize event listeners
    initEventListeners();
    
    // Initialize UI components
    initUIComponents();
    
    // Auto-cleanup old files
    performAutoCleanup();
}

// Load settings from server
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        appState.settings = settings;
        
        // Apply settings to UI
        applySettingsToUI(settings);
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

// Apply settings to UI
function applySettingsToUI(settings) {
    // Apply single voice settings
    if (settings.single_voice) {
        const sv = settings.single_voice;
        const elements = {
            'singleRate': sv.rate,
            'singlePitch': sv.pitch,
            'singleVolume': sv.volume,
            'singlePause': sv.pause
        };
        
        Object.entries(elements).forEach(([id, value]) => {
            const element = document.getElementById(id);
            if (element) {
                element.value = value;
                element.dispatchEvent(new Event('input'));
            }
        });
        
        // Set language and voice if available
        if (sv.language && document.getElementById('singleLanguage')) {
            document.getElementById('singleLanguage').value = sv.language;
            document.getElementById('singleLanguage').dispatchEvent(new Event('change'));
            
            // Need to wait for voices to load
            setTimeout(() => {
                if (sv.voice && document.getElementById('singleVoice')) {
                    document.getElementById('singleVoice').value = sv.voice;
                    $(document.getElementById('singleVoice')).trigger('change');
                }
            }, 500);
        }
    }
    
    // Apply other settings...
}

// Initialize event listeners
function initEventListeners() {
    // Tab switching
    const tabLinks = document.querySelectorAll('[data-bs-toggle="tab"]');
    tabLinks.forEach(tab => {
        tab.addEventListener('shown.bs.tab', function(event) {
            const activeTab = event.target.getAttribute('data-bs-target').replace('#', '');
            appState.currentTab = activeTab;
            updateTabSpecificUI(activeTab);
        });
    });
    
    // Global language selector
    const globalLangSelect = document.getElementById('globalLanguage');
    if (globalLangSelect) {
        globalLangSelect.addEventListener('change', function() {
            updateGlobalLanguage(this.value);
        });
    }
    
    // Cancel generation button
    const cancelBtn = document.getElementById('cancelGenerationBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', cancelCurrentGeneration);
    }
}

// Initialize UI components
function initUIComponents() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize character counters for all textareas
    document.querySelectorAll('textarea').forEach(textarea => {
        if (textarea.id && !textarea.id.includes('counter')) {
            initCharacterCounter(textarea.id);
        }
    });
}

// Initialize character counter for a textarea
function initCharacterCounter(textareaId) {
    const textarea = document.getElementById(textareaId);
    if (!textarea) return;
    
    // Create counter element if it doesn't exist
    const counterId = textareaId + 'Counter';
    if (!document.getElementById(counterId)) {
        const counter = document.createElement('div');
        counter.id = counterId;
        counter.className = 'text-muted text-end small mt-1';
        counter.style.fontSize = '0.75rem';
        textarea.parentNode.appendChild(counter);
    }
    
    const updateCounter = () => {
        const counter = document.getElementById(counterId);
        if (counter) {
            const count = textarea.value.length;
            const wordCount = textarea.value.trim().split(/\\s+/).filter(word => word.length > 0).length;
            counter.textContent = `${count} characters, ${wordCount} words`;
            
            // Add warning for long text
            if (count > 5000) {
                counter.classList.add('text-danger');
                counter.classList.remove('text-muted');
            } else {
                counter.classList.remove('text-danger');
                counter.classList.add('text-muted');
            }
        }
    };
    
    textarea.addEventListener('input', updateCounter);
    updateCounter(); // Initial update
}

// Update tab-specific UI
function updateTabSpecificUI(tabId) {
    switch (tabId) {
        case 'single':
            // Ensure voice list is loaded
            const langSelect = document.getElementById('singleLanguage');
            if (langSelect && !langSelect.hasAttribute('data-loaded')) {
                langSelect.dispatchEvent(new Event('change'));
            }
            break;
            
        case 'dialogue':
            // Ensure at least one character exists
            if (document.querySelectorAll('.character-settings').length === 0) {
                document.getElementById('addCharacterBtn').click();
            }
            break;
            
        case 'multi':
            // Initialize multi-character voices if needed
            const voiceSelects = document.querySelectorAll('.multi-character-voice');
            if (voiceSelects.length === 0) {
                document.getElementById('characterCount').dispatchEvent(new Event('input'));
            }
            break;
    }
}

// Update global language
function updateGlobalLanguage(langCode) {
    // This would update the UI language in a real implementation
    console.log('Global language changed to:', langCode);
    
    // Update all language selectors to match
    const langSelectors = document.querySelectorAll('select[id$="Language"]');
    langSelectors.forEach(select => {
        // Find matching language based on code
        // This is simplified - in real app you'd have a mapping
        if (langCode === 'vi') {
            select.value = 'Tiếng Việt';
        } else if (langCode === 'en') {
            select.value = 'English (US)';
        }
        select.dispatchEvent(new Event('change'));
    });
}

// Cancel current generation
function cancelCurrentGeneration() {
    if (appState.activeWebSocket) {
        appState.activeWebSocket.close();
        appState.activeWebSocket = null;
    }
    
    if (appState.currentTaskId) {
        // In a real implementation, you'd send a cancellation request to the server
        console.log('Cancelling task:', appState.currentTaskId);
        appState.currentTaskId = null;
    }
    
    hideProgressModal();
    showToast('Generation cancelled', 'warning');
}

// Show toast notification
function showToast(message, type = 'info', duration = 3000) {
    const toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) return;
    
    const toastId = 'toast-' + Date.now();
    
    const icon = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'warning': 'fa-exclamation-triangle',
        'info': 'fa-info-circle'
    }[type] || 'fa-info-circle';
    
    const color = {
        'success': '#06d6a0',
        'error': '#ef476f',
        'warning': '#ffd166',
        'info': '#4361ee'
    }[type] || '#4361ee';
    
    const toast = document.createElement('div');
    toast.className = 'custom-toast';
    toast.id = toastId;
    toast.style.borderLeftColor = color;
    toast.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas ${icon} me-3" style="color: ${color}; font-size: 1.2rem;"></i>
            <div class="flex-grow-1">
                <div class="fw-bold">${message}</div>
            </div>
            <button type="button" class="btn-close" onclick="this.parentElement.parentElement.remove()"></button>
        </div>
    `;
    
    toastContainer.appendChild(toast);
    
    // Auto-remove after duration
    setTimeout(() => {
        if (document.getElementById(toastId)) {
            toast.remove();
        }
    }, duration);
}

// Show progress modal
function showProgressModal(title = 'Generating Audio...', showCancel = true) {
    const modal = document.getElementById('progressModal');
    const cancelBtn = document.getElementById('cancelGenerationBtn');
    
    if (modal) {
        document.getElementById('progressTitle').textContent = title;
        modal.style.display = 'flex';
        
        if (cancelBtn) {
            cancelBtn.style.display = showCancel ? 'block' : 'none';
        }
    }
}

// Hide progress modal
function hideProgressModal() {
    const modal = document.getElementById('progressModal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    if (appState.activeWebSocket) {
        appState.activeWebSocket.close();
        appState.activeWebSocket = null;
    }
    
    appState.currentTaskId = null;
}

// Update progress
function updateProgress(percent, message) {
    const circle = document.getElementById('progressCircle');
    const percentElement = document.getElementById('progressPercent');
    const messageElement = document.getElementById('progressMessage');
    
    if (circle) {
        const radius = 54;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference - (percent / 100) * circumference;
        circle.style.strokeDashoffset = offset;
    }
    
    if (percentElement) {
        percentElement.textContent = percent + '%';
    }
    
    if (messageElement) {
        messageElement.textContent = message;
    }
}

// Connect to progress WebSocket
function connectProgressWebSocket(taskId) {
    if (appState.activeWebSocket) {
        appState.activeWebSocket.close();
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/progress/${taskId}`;
    
    appState.activeWebSocket = new WebSocket(wsUrl);
    appState.currentTaskId = taskId;
    
    appState.activeWebSocket.onopen = function() {
        console.log('WebSocket connected for task:', taskId);
    };
    
    appState.activeWebSocket.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            updateProgress(data.progress, data.message);
            
            if (data.progress >= 100) {
                setTimeout(() => {
                    checkTaskResult(taskId);
                }, 1000);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    };
    
    appState.activeWebSocket.onerror = function(error) {
        console.error('WebSocket error:', error);
        showToast('Connection error', 'error');
    };
    
    appState.activeWebSocket.onclose = function() {
        console.log('WebSocket closed');
        appState.activeWebSocket = null;
    };
}

// Check task result
async function checkTaskResult(taskId) {
    try {
        const response = await fetch(`/api/task/${taskId}/result`);
        const result = await response.json();
        
        if (result.complete) {
            hideProgressModal();
            
            if (result.success) {
                // Determine which tab is active and show appropriate output
                const activeTab = appState.currentTab;
                showOutputResult(activeTab, result);
                showToast('Audio generated successfully!', 'success');
            } else {
                showToast(result.message || 'Generation failed', 'error');
            }
        } else {
            // Check again after delay
            setTimeout(() => checkTaskResult(taskId), 1000);
        }
    } catch (error) {
        console.error('Error checking task result:', error);
        hideProgressModal();
        showToast('Error checking generation status', 'error');
    }
}

// Show output result based on active tab
function showOutputResult(tabId, result) {
    const outputPanels = {
        'single': 'singleOutput',
        'dialogue': 'dialogueOutput',
        'multi': 'multiOutput'
    };
    
    const audioElements = {
        'single': 'singleAudioElement',
        'dialogue': 'dialogueAudioElement',
        'multi': 'multiAudioElement'
    };
    
    const downloadButtons = {
        'single': 'singleDownloadAudio',
        'dialogue': 'dialogueDownloadAudio',
        'multi': 'multiDownloadAudio'
    };
    
    const subtitleButtons = {
        'single': 'singleDownloadSubtitle',
        'dialogue': 'dialogueDownloadSubtitle',
        'multi': 'multiDownloadSubtitle'
    };
    
    const outputPanelId = outputPanels[tabId];
    if (!outputPanelId) return;
    
    const outputPanel = document.getElementById(outputPanelId);
    if (outputPanel) {
        outputPanel.style.display = 'block';
        
        // Scroll to output
        outputPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Set audio player
        const audioElementId = audioElements[tabId];
        if (audioElementId) {
            const audioElement = document.getElementById(audioElementId);
            if (audioElement) {
                audioElement.src = result.audio_url;
                audioElement.load();
                
                // Auto-play if user prefers
                const autoPlay = localStorage.getItem('autoPlayAudio') === 'true';
                if (autoPlay) {
                    audioElement.play().catch(e => console.log('Auto-play prevented:', e));
                }
            }
        }
        
        // Set download links
        const downloadButtonId = downloadButtons[tabId];
        if (downloadButtonId) {
            const downloadButton = document.getElementById(downloadButtonId);
            if (downloadButton) {
                downloadButton.href = result.audio_url;
                downloadButton.download = `tts_output_${Date.now()}.${result.audio_url.split('.').pop()}`;
            }
        }
        
        // Set subtitle download link if available
        const subtitleButtonId = subtitleButtons[tabId];
        if (subtitleButtonId && result.srt_url) {
            const subtitleButton = document.getElementById(subtitleButtonId);
            if (subtitleButton) {
                subtitleButton.href = result.srt_url;
                subtitleButton.style.display = 'inline-block';
                subtitleButton.download = `subtitles_${Date.now()}.srt`;
            }
        }
    }
}

// Perform auto-cleanup
async function performAutoCleanup() {
    try {
        await fetch('/api/cleanup', { method: 'POST' });
    } catch (error) {
        console.error('Auto-cleanup failed:', error);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);

// Export functions for global use
window.TTSPro = {
    showToast,
    showProgressModal,
    hideProgressModal,
    updateProgress,
    cancelCurrentGeneration
};
"""

with open("static/js/enhanced.js", "w", encoding="utf-8") as f:
    f.write(enhanced_js)

# ==================== START APPLICATION ====================
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    
    # Cleanup old temp files on startup
    for file in os.listdir("temp"):
        try:
            os.remove(os.path.join("temp", file))
        except:
            pass
    
    print("=" * 60)
    print("PROFESSIONAL TTS GENERATOR PRO v2.0.0")
    print("=" * 60)
    print(f"✓ Available Languages: {len(TTSConfig.LANGUAGES)}")
    print(f"✓ Total Voices: {len(TTSConfig.ALL_VOICES)}")
    print(f"✓ Output Formats: {', '.join(TTSConfig.OUTPUT_FORMATS)}")
    print(f"✓ Dialogue Formats: {', '.join(TTSConfig.DIALOGUE_FORMATS.keys())}")
    print("=" * 60)
    print(f"🚀 Starting server on port {port}")
    print(f"🌐 Open http://localhost:{port} in your browser")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
