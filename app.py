# app.py
import asyncio
import json
import os
import random
import re
import time
import zipfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import edge_tts
from pydub import AudioSegment
from pydub.effects import normalize, compress_dynamic_range, low_pass_filter, high_pass_filter
import webvtt
import natsort
import uvicorn

# ==================== SYSTEM CONFIGURATION ====================
class TTSConfig:
    SETTINGS_FILE = "tts_settings.json"
    
    LANGUAGES = {
        "Tiếng Việt": [
            {"name": "vi-VN-HoaiMyNeural", "gender": "Nữ", "display": "Hoài My"},
            {"name": "vi-VN-NamMinhNeural", "gender": "Nam", "display": "Nam Minh"}
        ],
        "English (US)": [
            {"name": "en-US-GuyNeural", "gender": "Nam"},
            {"name": "en-US-JennyNeural", "gender": "Nữ"},
            {"name": "en-US-AvaNeural", "gender": "Nữ"},
            {"name": "en-US-AndrewNeural", "gender": "Nam"},
            {"name": "en-US-EmmaNeural", "gender": "Nữ"},
            {"name": "en-US-BrianNeural", "gender": "Nam"},
            {"name": "en-US-AnaNeural", "gender": "Nữ"},
            {"name": "en-US-AndrewMultilingualNeural", "gender": "Nam"},
            {"name": "en-US-AriaNeural", "gender": "Nữ"},
            {"name": "en-US-AvaMultilingualNeural", "gender": "Nữ"},
            {"name": "en-US-BrianMultilingualNeural", "gender": "Nam"},
            {"name": "en-US-ChristopherNeural", "gender": "Nam"},
            {"name": "en-US-EmmaMultilingualNeural", "gender": "Nữ"},
            {"name": "en-US-EricNeural", "gender": "Nam"},
            {"name": "en-US-MichelleNeural", "gender": "Nữ"},
            {"name": "en-US-RogerNeural", "gender": "Nam"},
            {"name": "en-US-SteffanNeural", "gender": "Nam"}
        ],
        "English (UK)": [
            {"name": "en-GB-LibbyNeural", "gender": "Nữ"},
            {"name": "en-GB-MiaNeural", "gender": "Nữ"},
            {"name": "en-GB-RyanNeural", "gender": "Nam"},
            {"name": "en-GB-MaisieNeural", "gender": "Nữ"},
            {"name": "en-GB-SoniaNeural", "gender": "Nữ"},
            {"name": "en-GB-ThomasNeural", "gender": "Nam"}
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

# ==================== TTS PROCESSOR ====================
class TTSProcessor:
    def __init__(self):
        self.text_processor = TextProcessor()
        self.load_settings()
        
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
                    "char1": {
                        "language": "Tiếng Việt",
                        "voice": "vi-VN-HoaiMyNeural", 
                        "rate": 0, 
                        "pitch": 0, 
                        "volume": 100
                    },
                    "char2": {
                        "language": "Tiếng Việt",
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
                        "language": "Tiếng Việt",
                        "voice": "vi-VN-HoaiMyNeural", 
                        "rate": 0, 
                        "pitch": 0, 
                        "volume": 100
                    },
                    "answer": {
                        "language": "Tiếng Việt",
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
        """Generate speech using edge-tts"""
        try:
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            rate_str = f"{rate}%" if rate != 0 else "+0%"
            pitch_str = f"+{pitch}Hz" if pitch >=0 else f"{pitch}Hz"
            
            communicate = edge_tts.Communicate(text, voice_id, rate=rate_str, pitch=pitch_str)
            
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
                                 volume: int, pause: int, output_format: str = "mp3"):
        """Process text with single voice"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/single_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        sentences = self.text_processor.split_sentences(text)
        audio_segments = []
        all_subtitles = []
        
        for i, sentence in enumerate(sentences):
            temp_file, subs = await self.generate_speech(sentence, voice_id, rate, pitch, volume)
            if temp_file:
                audio = AudioSegment.from_file(temp_file)
                audio_segments.append(audio)
                all_subtitles.extend(subs)
                os.remove(temp_file)
        
        if not audio_segments:
            return None, None
        
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
        
        return output_file, srt_file
    
    async def process_multi_voice(self, text: str, voices_config: dict, pause: int, 
                                repeat: int, output_format: str = "mp3"):
        """Process text with multiple voices"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/multi_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Parse character dialogues
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
            return None, None
        
        # Generate audio for each dialogue
        audio_segments = []
        all_subtitles = []
        
        for char, dialogue_text in dialogues:
            if char == "CHAR1":
                config = voices_config["char1"]
            elif char == "CHAR2":
                config = voices_config["char2"]
            else:  # NARRATOR or others
                config = voices_config["char1"]  # Default to char1
            
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
            return None, None
        
        # Combine with repetition
        combined = AudioSegment.empty()
        for _ in range(repeat):
            for i, (char, audio) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            combined += AudioSegment.silent(duration=pause * 2)  # Longer pause between repetitions
        
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
        
        return output_file, srt_file
    
    async def process_qa_dialogue(self, text: str, qa_config: dict, pause_q: int, 
                                pause_a: int, repeat: int, output_format: str = "mp3"):
        """Process Q&A dialogue"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"outputs/qa_{timestamp}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Parse Q&A
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
            return None, None
        
        # Generate audio
        audio_segments = []
        all_subtitles = []
        
        for speaker, dialogue_text in dialogues:
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
            return None, None
        
        # Combine with repetition
        combined = AudioSegment.empty()
        for _ in range(repeat):
            for i, (speaker, audio, pause) in enumerate(audio_segments):
                audio = audio.fade_in(50).fade_out(50)
                combined += audio
                if i < len(audio_segments) - 1:
                    combined += AudioSegment.silent(duration=pause)
            combined += AudioSegment.silent(duration=pause_a * 2)  # Longer pause between repetitions
        
        # Export
        output_file = os.path.join(output_dir, f"qa_dialogue.{output_format}")
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
            
            srt_file = os.path.join(output_dir, f"qa_dialogue.srt")
            with open(srt_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(srt_content))
        else:
            srt_file = None
        
        return output_file, srt_file

# ==================== FASTAPI APPLICATION ====================
app = FastAPI(title="Professional TTS Generator", version="1.0.0")

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

# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "languages": TTSConfig.LANGUAGES,
        "formats": TTSConfig.OUTPUT_FORMATS
    })

@app.get("/api/languages")
async def get_languages():
    """Get all available languages"""
    languages = list(TTSConfig.LANGUAGES.keys())
    return {"languages": languages}

@app.get("/api/voices")
async def get_voices(language: str = None):
    """Get available voices"""
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
    output_format: str = Form("mp3")
):
    """Generate single voice TTS"""
    try:
        audio_file, srt_file = await tts_processor.process_single_voice(
            text, voice_id, rate, pitch, volume, pause, output_format
        )
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        # Save settings
        tts_processor.settings["single_voice"] = {
            "voice": voice_id,
            "rate": rate,
            "pitch": pitch,
            "volume": volume,
            "pause": pause
        }
        tts_processor.save_settings()
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(audio_file)}",
            "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
            "message": "Audio generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/multi")
async def generate_multi_voice(
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
        
        audio_file, srt_file = await tts_processor.process_multi_voice(
            text, voices_config, pause, repeat, output_format
        )
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        # Save settings
        tts_processor.settings["multi_voice"] = {
            "char1": voices_config["char1"],
            "char2": voices_config["char2"],
            "pause": pause,
            "repeat": repeat
        }
        tts_processor.save_settings()
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(audio_file)}",
            "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
            "message": "Multi-voice audio generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate/qa")
async def generate_qa_dialogue(
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
        
        audio_file, srt_file = await tts_processor.process_qa_dialogue(
            text, qa_config, pause_q, pause_a, repeat, output_format
        )
        
        if not audio_file:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        # Save settings
        tts_processor.settings["qa_voice"] = {
            "question": qa_config["question"],
            "answer": qa_config["answer"],
            "pause_q": pause_q,
            "pause_a": pause_a,
            "repeat": repeat
        }
        tts_processor.save_settings()
        
        return {
            "success": True,
            "audio_url": f"/download/{os.path.basename(audio_file)}",
            "srt_url": f"/download/{os.path.basename(srt_file)}" if srt_file else None,
            "message": "Q&A dialogue audio generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

# ==================== HTML TEMPLATES ====================
# Create templates directory and HTML files
os.makedirs("templates", exist_ok=True)

# index.html template
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
            --border-color: #dee2e6;
        }
        
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .navbar-brand {
            font-weight: 700;
            font-size: 1.5rem;
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
            border-bottom: 2px solid var(--border-color);
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
        
        .form-label {
            font-weight: 600;
            color: var(--dark-bg);
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
        
        .audio-player {
            background: var(--light-bg);
            border-radius: 10px;
            padding: 1rem;
            margin-top: 1rem;
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
        
        .voice-card {
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 1rem;
            margin-bottom: 1rem;
            transition: all 0.3s;
        }
        
        .voice-card:hover {
            border-color: var(--primary-color);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .preview-btn {
            margin-top: 0.5rem;
        }
        
        .output-card {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            border-radius: 10px;
            padding: 1.5rem;
            margin-top: 2rem;
        }
        
        .accordion-button:not(.collapsed) {
            background-color: rgba(67, 97, 238, 0.1);
            color: var(--primary-color);
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
        .q-tag { background: #e8f5e9; color: #388e3c; }
        .a-tag { background: #fff3e0; color: #f57c00; }
        
        .language-selector {
            margin-bottom: 0.75rem;
        }
        
        .voice-selector {
            margin-bottom: 0.75rem;
        }
    </style>
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-microphone-alt me-2"></i>
                Professional TTS Generator
            </a>
            <div class="navbar-text">
                <span id="current-time" class="text-light"></span>
            </div>
        </div>
    </nav>

    <!-- Main Container -->
    <div class="container main-container">
        <!-- Tabs -->
        <ul class="nav nav-tabs" id="ttsTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="single-tab" data-bs-toggle="tab" data-bs-target="#single" type="button">
                    <i class="fas fa-user me-2"></i>Single Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="multi-tab" data-bs-toggle="tab" data-bs-target="#multi" type="button">
                    <i class="fas fa-users me-2"></i>Multi-Voice
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="qa-tab" data-bs-toggle="tab" data-bs-target="#qa" type="button">
                    <i class="fas fa-comments me-2"></i>Q&A Dialogue
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="ttsTabsContent">
            <!-- Single Voice Tab -->
            <div class="tab-pane fade show active" id="single" role="tabpanel">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label for="singleText" class="form-label">Text Content</label>
                            <textarea class="form-control" id="singleText" rows="10" 
                                      placeholder="Enter your text here..."></textarea>
                            <div class="mt-2">
                                <small class="text-muted">
                                    <i class="fas fa-info-circle me-1"></i>
                                    Text will be automatically processed for proper pronunciation
                                </small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <!-- Voice Selection -->
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
                        <div class="accordion mb-3" id="singleSettings">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#singleVoiceSettings">
                                        <i class="fas fa-sliders-h me-2"></i>Voice Settings
                                    </button>
                                </h2>
                                <div id="singleVoiceSettings" class="accordion-collapse collapse show">
                                    <div class="accordion-body">
                                        <div class="mb-3">
                                            <label for="singleRate" class="form-label">
                                                Speed: <span id="singleRateValue">0%</span>
                                            </label>
                                            <input type="range" class="form-range" id="singleRate" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label for="singlePitch" class="form-label">
                                                Pitch: <span id="singlePitchValue">0Hz</span>
                                            </label>
                                            <input type="range" class="form-range" id="singlePitch" min="-30" max="30" value="0">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label for="singleVolume" class="form-label">
                                                Volume: <span id="singleVolumeValue">100%</span>
                                            </label>
                                            <input type="range" class="form-range" id="singleVolume" min="50" max="150" value="100">
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label for="singlePause" class="form-label">
                                                Pause Duration: <span id="singlePauseValue">500ms</span>
                                            </label>
                                            <input type="range" class="form-range" id="singlePause" min="100" max="2000" step="50" value="500">
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
                        
                        <button class="btn btn-primary w-100" id="singleGenerateBtn">
                            <i class="fas fa-play-circle me-2"></i>Generate Audio
                        </button>
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
            <div class="tab-pane fade" id="multi" role="tabpanel">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label for="multiText" class="form-label">Dialogue Content</label>
                            <textarea class="form-control" id="multiText" rows="10" 
                                      placeholder="CHAR1: Dialogue for character 1&#10;CHAR2: Dialogue for character 2&#10;NARRATOR: Narration text"></textarea>
                            <div class="mt-2">
                                <small class="text-muted">
                                    <i class="fas fa-info-circle me-1"></i>
                                    Use CHAR1:, CHAR2:, or NARRATOR: prefixes for different characters
                                </small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <!-- Character 1 Settings -->
                        <div class="voice-card">
                            <h6><span class="character-tag char1-tag">CHARACTER 1</span></h6>
                            
                            <!-- Language Selector for Character 1 -->
                            <div class="language-selector">
                                <label class="form-label small">Language</label>
                                <select class="form-select multiLanguage" data-char="1">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <!-- Voice Selector for Character 1 -->
                            <div class="voice-selector">
                                <label class="form-label small">Voice</label>
                                <select class="form-select multiVoice" data-char="1">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-char="1" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="rate" data-char="1">0%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-char="1" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-char="1">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-char="1" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-char="1">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Character 2 Settings -->
                        <div class="voice-card">
                            <h6><span class="character-tag char2-tag">CHARACTER 2</span></h6>
                            
                            <!-- Language Selector for Character 2 -->
                            <div class="language-selector">
                                <label class="form-label small">Language</label>
                                <select class="form-select multiLanguage" data-char="2">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <!-- Voice Selector for Character 2 -->
                            <div class="voice-selector">
                                <label class="form-label small">Voice</label>
                                <select class="form-select multiVoice" data-char="2">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-char="2" min="-30" max="30" value="-10">
                                    <small class="d-block text-center"><span data-value="rate" data-char="2">-10%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-char="2" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-char="2">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-char="2" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-char="2">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- General Settings -->
                        <div class="mb-3">
                            <label for="multiPause" class="form-label">
                                Pause Between Dialogues: <span id="multiPauseValue">500ms</span>
                            </label>
                            <input type="range" class="form-range" id="multiPause" min="100" max="2000" step="50" value="500">
                        </div>
                        
                        <div class="mb-3">
                            <label for="multiRepeat" class="form-label">
                                Repeat Times: <span id="multiRepeatValue">1</span>
                            </label>
                            <input type="range" class="form-range" id="multiRepeat" min="1" max="5" value="1">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Output Format</label>
                            <select class="form-select" id="multiFormat">
                                {% for format in formats %}
                                <option value="{{ format }}">{{ format|upper }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <button class="btn btn-primary w-100" id="multiGenerateBtn">
                            <i class="fas fa-users me-2"></i>Generate Multi-Voice Audio
                        </button>
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

            <!-- Q&A Dialogue Tab -->
            <div class="tab-pane fade" id="qa" role="tabpanel">
                <div class="row">
                    <div class="col-md-8">
                        <div class="mb-3">
                            <label for="qaText" class="form-label">Q&A Content</label>
                            <textarea class="form-control" id="qaText" rows="10" 
                                      placeholder="Q: Question text&#10;A: Answer text&#10;Q: Next question&#10;A: Next answer"></textarea>
                            <div class="mt-2">
                                <small class="text-muted">
                                    <i class="fas fa-info-circle me-1"></i>
                                    Use Q: for questions and A: for answers
                                </small>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <!-- Question Settings -->
                        <div class="voice-card">
                            <h6><span class="character-tag q-tag">QUESTION</span></h6>
                            
                            <!-- Language Selector for Question -->
                            <div class="language-selector">
                                <label class="form-label small">Language</label>
                                <select class="form-select qaLanguage" data-type="question">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <!-- Voice Selector for Question -->
                            <div class="voice-selector">
                                <label class="form-label small">Voice</label>
                                <select class="form-select qaVoice" data-type="question">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-type="question" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="rate" data-type="question">0%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-type="question" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-type="question">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-type="question" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-type="question">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Answer Settings -->
                        <div class="voice-card">
                            <h6><span class="character-tag a-tag">ANSWER</span></h6>
                            
                            <!-- Language Selector for Answer -->
                            <div class="language-selector">
                                <label class="form-label small">Language</label>
                                <select class="form-select qaLanguage" data-type="answer">
                                    <option value="">Select Language</option>
                                    {% for language in languages %}
                                    <option value="{{ language }}">{{ language }}</option>
                                    {% endfor %}
                                </select>
                            </div>
                            
                            <!-- Voice Selector for Answer -->
                            <div class="voice-selector">
                                <label class="form-label small">Voice</label>
                                <select class="form-select qaVoice" data-type="answer">
                                    <option value="">Select Voice</option>
                                </select>
                            </div>
                            
                            <div class="row">
                                <div class="col-4">
                                    <label class="form-label small">Speed</label>
                                    <input type="range" class="form-range" data-setting="rate" data-type="answer" min="-30" max="30" value="-10">
                                    <small class="d-block text-center"><span data-value="rate" data-type="answer">-10%</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Pitch</label>
                                    <input type="range" class="form-range" data-setting="pitch" data-type="answer" min="-30" max="30" value="0">
                                    <small class="d-block text-center"><span data-value="pitch" data-type="answer">0Hz</span></small>
                                </div>
                                <div class="col-4">
                                    <label class="form-label small">Volume</label>
                                    <input type="range" class="form-range" data-setting="volume" data-type="answer" min="50" max="150" value="100">
                                    <small class="d-block text-center"><span data-value="volume" data-type="answer">100%</span></small>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Q&A Settings -->
                        <div class="mb-3">
                            <label for="qaPauseQ" class="form-label">
                                Pause After Question: <span id="qaPauseQValue">200ms</span>
                            </label>
                            <input type="range" class="form-range" id="qaPauseQ" min="100" max="1000" step="50" value="200">
                        </div>
                        
                        <div class="mb-3">
                            <label for="qaPauseA" class="form-label">
                                Pause After Answer: <span id="qaPauseAValue">500ms</span>
                            </label>
                            <input type="range" class="form-range" id="qaPauseA" min="100" max="2000" step="50" value="500">
                        </div>
                        
                        <div class="mb-3">
                            <label for="qaRepeat" class="form-label">
                                Repeat Times: <span id="qaRepeatValue">2</span>
                            </label>
                            <input type="range" class="form-range" id="qaRepeat" min="1" max="5" value="2">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Output Format</label>
                            <select class="form-select" id="qaFormat">
                                {% for format in formats %}
                                <option value="{{ format }}">{{ format|upper }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        
                        <button class="btn btn-primary w-100" id="qaGenerateBtn">
                            <i class="fas fa-comments me-2"></i>Generate Q&A Audio
                        </button>
                    </div>
                </div>
                
                <!-- Output Section -->
                <div class="output-card mt-4" id="qaOutput" style="display: none;">
                    <h5><i class="fas fa-comments me-2"></i>Generated Q&A Audio</h5>
                    <div class="audio-player" id="qaAudioPlayer"></div>
                    <div class="mt-3">
                        <a href="#" class="btn btn-success me-2" id="qaDownloadAudio">
                            <i class="fas fa-download me-2"></i>Download Audio
                        </a>
                        <a href="#" class="btn btn-info" id="qaDownloadSubtitle" style="display: none;">
                            <i class="fas fa-file-alt me-2"></i>Download Subtitles
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
        // Current time display
        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = 
                now.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
        }
        setInterval(updateTime, 1000);
        updateTime();

        // Voice data cache
        let voicesCache = {};
        
        // Load voices for a language
        async function loadVoices(language, targetSelect) {
            try {
                const response = await fetch(`/api/voices?language=${encodeURIComponent(language)}`);
                const data = await response.json();
                
                if (targetSelect) {
                    targetSelect.innerHTML = '<option value="">Select Voice</option>';
                    
                    data.voices.forEach(voice => {
                        const option = document.createElement('option');
                        option.value = voice.name;
                        option.textContent = `${voice.display} (${voice.gender})`;
                        targetSelect.appendChild(option);
                    });
                    
                    // Cache voices
                    voicesCache[language] = data.voices;
                }
                return data.voices;
            } catch (error) {
                console.error('Error loading voices:', error);
                showToast('Error loading voices', 'error');
                return [];
            }
        }

        // Show toast notification
        function showToast(message, type = 'info') {
            const toastContainer = document.querySelector('.toast-container');
            const toastId = 'toast-' + Date.now();
            
            const toastHtml = `
                <div id="${toastId}" class="toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'success'} border-0" role="alert">
                    <div class="d-flex">
                        <div class="toast-body">
                            <i class="fas ${type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle'} me-2"></i>
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

        // Show loading overlay
        function showLoading() {
            document.getElementById('loadingOverlay').style.display = 'flex';
        }

        // Hide loading overlay
        function hideLoading() {
            document.getElementById('loadingOverlay').style.display = 'none';
        }

        // Update range value display
        function updateRangeDisplay(inputId, valueId, suffix = '') {
            const input = document.getElementById(inputId);
            const display = document.getElementById(valueId);
            
            if (input && display) {
                input.addEventListener('input', () => {
                    display.textContent = input.value + suffix;
                });
                display.textContent = input.value + suffix;
            }
        }

        // Initialize range displays
        updateRangeDisplay('singleRate', 'singleRateValue', '%');
        updateRangeDisplay('singlePitch', 'singlePitchValue', 'Hz');
        updateRangeDisplay('singleVolume', 'singleVolumeValue', '%');
        updateRangeDisplay('singlePause', 'singlePauseValue', 'ms');
        updateRangeDisplay('multiPause', 'multiPauseValue', 'ms');
        updateRangeDisplay('multiRepeat', 'multiRepeatValue', 'x');
        updateRangeDisplay('qaPauseQ', 'qaPauseQValue', 'ms');
        updateRangeDisplay('qaPauseA', 'qaPauseAValue', 'ms');
        updateRangeDisplay('qaRepeat', 'qaRepeatValue', 'x');

        // Update multi-voice range displays
        document.querySelectorAll('[data-value][data-char]').forEach(span => {
            const char = span.dataset.char;
            const setting = span.dataset.value;
            const input = document.querySelector(`[data-setting="${setting}"][data-char="${char}"]`);
            
            if (input && span) {
                const suffix = setting === 'rate' ? '%' : setting === 'pitch' ? 'Hz' : '%';
                span.textContent = input.value + suffix;
                
                input.addEventListener('input', () => {
                    span.textContent = input.value + suffix;
                });
            }
        });

        // Update Q&A range displays
        document.querySelectorAll('[data-value][data-type]').forEach(span => {
            const type = span.dataset.type;
            const setting = span.dataset.value;
            const input = document.querySelector(`[data-setting="${setting}"][data-type="${type}"]`);
            
            if (input && span) {
                const suffix = setting === 'rate' ? '%' : setting === 'pitch' ? 'Hz' : '%';
                span.textContent = input.value + suffix;
                
                input.addEventListener('input', () => {
                    span.textContent = input.value + suffix;
                });
            }
        });

        // Load voices when language changes (Single Voice)
        document.getElementById('singleLanguage').addEventListener('change', async function() {
            if (this.value) {
                await loadVoices(this.value, document.getElementById('singleVoice'));
            } else {
                document.getElementById('singleVoice').innerHTML = '<option value="">Select Voice</option>';
            }
        });

        // Load voices when language changes (Multi-Voice)
        document.querySelectorAll('.multiLanguage').forEach(select => {
            select.addEventListener('change', async function() {
                const char = this.dataset.char;
                const targetVoiceSelect = document.querySelector(`.multiVoice[data-char="${char}"]`);
                
                if (this.value) {
                    await loadVoices(this.value, targetVoiceSelect);
                } else {
                    targetVoiceSelect.innerHTML = '<option value="">Select Voice</option>';
                }
            });
        });

        // Load voices when language changes (Q&A)
        document.querySelectorAll('.qaLanguage').forEach(select => {
            select.addEventListener('change', async function() {
                const type = this.dataset.type;
                const targetVoiceSelect = document.querySelector(`.qaVoice[data-type="${type}"]`);
                
                if (this.value) {
                    await loadVoices(this.value, targetVoiceSelect);
                } else {
                    targetVoiceSelect.innerHTML = '<option value="">Select Voice</option>';
                }
            });
        });

        // Load default voices on page load
        window.addEventListener('DOMContentLoaded', async () => {
            // Load Vietnamese voices by default for all tabs
            const defaultLanguage = 'Tiếng Việt';
            
            // Single Voice Tab
            document.getElementById('singleLanguage').value = defaultLanguage;
            await loadVoices(defaultLanguage, document.getElementById('singleVoice'));
            
            // Multi-Voice Tab
            const multiLanguageSelects = document.querySelectorAll('.multiLanguage');
            multiLanguageSelects.forEach(select => {
                select.value = defaultLanguage;
            });
            
            const multiVoiceSelects = document.querySelectorAll('.multiVoice');
            for (const select of multiVoiceSelects) {
                await loadVoices(defaultLanguage, select);
            }
            
            // Q&A Tab
            const qaLanguageSelects = document.querySelectorAll('.qaLanguage');
            qaLanguageSelects.forEach(select => {
                select.value = defaultLanguage;
            });
            
            const qaVoiceSelects = document.querySelectorAll('.qaVoice');
            for (const select of qaVoiceSelects) {
                await loadVoices(defaultLanguage, select);
            }
            
            // Load saved settings
            try {
                const response = await fetch('/api/settings');
                const settings = await response.json();
                
                // Apply single voice settings
                if (settings.single_voice) {
                    const sv = settings.single_voice;
                    document.getElementById('singleRate').value = sv.rate;
                    document.getElementById('singlePitch').value = sv.pitch;
                    document.getElementById('singleVolume').value = sv.volume;
                    document.getElementById('singlePause').value = sv.pause;
                    
                    // Trigger updates
                    document.getElementById('singleRate').dispatchEvent(new Event('input'));
                    document.getElementById('singlePitch').dispatchEvent(new Event('input'));
                    document.getElementById('singleVolume').dispatchEvent(new Event('input'));
                    document.getElementById('singlePause').dispatchEvent(new Event('input'));
                }
                
                // Apply multi-voice settings
                if (settings.multi_voice) {
                    const mv = settings.multi_voice;
                    
                    // Character 1 settings
                    if (mv.char1) {
                        document.querySelector('.multiLanguage[data-char="1"]').value = mv.char1.language || 'Tiếng Việt';
                        document.querySelector('.multiVoice[data-char="1"]').value = mv.char1.voice;
                        document.querySelector('[data-setting="rate"][data-char="1"]').value = mv.char1.rate;
                        document.querySelector('[data-setting="pitch"][data-char="1"]').value = mv.char1.pitch;
                        document.querySelector('[data-setting="volume"][data-char="1"]').value = mv.char1.volume;
                    }
                    
                    // Character 2 settings
                    if (mv.char2) {
                        document.querySelector('.multiLanguage[data-char="2"]').value = mv.char2.language || 'Tiếng Việt';
                        document.querySelector('.multiVoice[data-char="2"]').value = mv.char2.voice;
                        document.querySelector('[data-setting="rate"][data-char="2"]').value = mv.char2.rate;
                        document.querySelector('[data-setting="pitch"][data-char="2"]').value = mv.char2.pitch;
                        document.querySelector('[data-setting="volume"][data-char="2"]').value = mv.char2.volume;
                    }
                    
                    document.getElementById('multiPause').value = mv.pause;
                    document.getElementById('multiRepeat').value = mv.repeat;
                    
                    document.getElementById('multiPause').dispatchEvent(new Event('input'));
                    document.getElementById('multiRepeat').dispatchEvent(new Event('input'));
                }
                
                // Apply Q&A settings
                if (settings.qa_voice) {
                    const qv = settings.qa_voice;
                    
                    // Question settings
                    if (qv.question) {
                        document.querySelector('.qaLanguage[data-type="question"]').value = qv.question.language || 'Tiếng Việt';
                        document.querySelector('.qaVoice[data-type="question"]').value = qv.question.voice;
                        document.querySelector('[data-setting="rate"][data-type="question"]').value = qv.question.rate;
                        document.querySelector('[data-setting="pitch"][data-type="question"]').value = qv.question.pitch;
                        document.querySelector('[data-setting="volume"][data-type="question"]').value = qv.question.volume;
                    }
                    
                    // Answer settings
                    if (qv.answer) {
                        document.querySelector('.qaLanguage[data-type="answer"]').value = qv.answer.language || 'Tiếng Việt';
                        document.querySelector('.qaVoice[data-type="answer"]').value = qv.answer.voice;
                        document.querySelector('[data-setting="rate"][data-type="answer"]').value = qv.answer.rate;
                        document.querySelector('[data-setting="pitch"][data-type="answer"]').value = qv.answer.pitch;
                        document.querySelector('[data-setting="volume"][data-type="answer"]').value = qv.answer.volume;
                    }
                    
                    document.getElementById('qaPauseQ').value = qv.pause_q;
                    document.getElementById('qaPauseA').value = qv.pause_a;
                    document.getElementById('qaRepeat').value = qv.repeat;
                    
                    document.getElementById('qaPauseQ').dispatchEvent(new Event('input'));
                    document.getElementById('qaPauseA').dispatchEvent(new Event('input'));
                    document.getElementById('qaRepeat').dispatchEvent(new Event('input'));
                }
            } catch (error) {
                console.error('Error loading settings:', error);
            }
        });

        // Generate single voice audio
        document.getElementById('singleGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('singleText').value.trim();
            const voice = document.getElementById('singleVoice').value;
            const language = document.getElementById('singleLanguage').value;
            
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
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('voice_id', voice);
            formData.append('rate', document.getElementById('singleRate').value);
            formData.append('pitch', document.getElementById('singlePitch').value);
            formData.append('volume', document.getElementById('singleVolume').value);
            formData.append('pause', document.getElementById('singlePause').value);
            formData.append('output_format', document.getElementById('singleFormat').value);
            
            try {
                const response = await fetch('/api/generate/single', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show audio player
                    const audioPlayer = document.getElementById('singleAudioPlayer');
                    audioPlayer.innerHTML = `
                        <audio controls class="w-100">
                            <source src="${result.audio_url}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                    `;
                    
                    // Show download buttons
                    document.getElementById('singleDownloadAudio').href = result.audio_url;
                    if (result.srt_url) {
                        document.getElementById('singleDownloadSubtitle').href = result.srt_url;
                        document.getElementById('singleDownloadSubtitle').style.display = 'inline-block';
                    }
                    
                    // Show output section
                    document.getElementById('singleOutput').style.display = 'block';
                    
                    showToast(result.message);
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

        // Generate multi-voice audio
        document.getElementById('multiGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('multiText').value.trim();
            
            if (!text) {
                showToast('Please enter dialogue text', 'error');
                return;
            }
            
            // Get character 1 settings
            const char1LanguageSelect = document.querySelector('.multiLanguage[data-char="1"]');
            const char1VoiceSelect = document.querySelector('.multiVoice[data-char="1"]');
            const char1Language = char1LanguageSelect.value;
            const char1Voice = char1VoiceSelect.value;
            
            if (!char1Language) {
                showToast('Please select language for Character 1', 'error');
                return;
            }
            
            if (!char1Voice) {
                showToast('Please select voice for Character 1', 'error');
                return;
            }
            
            // Get character 2 settings
            const char2LanguageSelect = document.querySelector('.multiLanguage[data-char="2"]');
            const char2VoiceSelect = document.querySelector('.multiVoice[data-char="2"]');
            const char2Language = char2LanguageSelect.value;
            const char2Voice = char2VoiceSelect.value;
            
            if (!char2Language) {
                showToast('Please select language for Character 2', 'error');
                return;
            }
            
            if (!char2Voice) {
                showToast('Please select voice for Character 2', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('char1_language', char1Language);
            formData.append('char1_voice', char1Voice);
            formData.append('char1_rate', document.querySelector('[data-setting="rate"][data-char="1"]').value);
            formData.append('char1_pitch', document.querySelector('[data-setting="pitch"][data-char="1"]').value);
            formData.append('char1_volume', document.querySelector('[data-setting="volume"][data-char="1"]').value);
            formData.append('char2_language', char2Language);
            formData.append('char2_voice', char2Voice);
            formData.append('char2_rate', document.querySelector('[data-setting="rate"][data-char="2"]').value);
            formData.append('char2_pitch', document.querySelector('[data-setting="pitch"][data-char="2"]').value);
            formData.append('char2_volume', document.querySelector('[data-setting="volume"][data-char="2"]').value);
            formData.append('pause', document.getElementById('multiPause').value);
            formData.append('repeat', document.getElementById('multiRepeat').value);
            formData.append('output_format', document.getElementById('multiFormat').value);
            
            try {
                const response = await fetch('/api/generate/multi', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show audio player
                    const audioPlayer = document.getElementById('multiAudioPlayer');
                    audioPlayer.innerHTML = `
                        <audio controls class="w-100">
                            <source src="${result.audio_url}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                    `;
                    
                    // Show download buttons
                    document.getElementById('multiDownloadAudio').href = result.audio_url;
                    if (result.srt_url) {
                        document.getElementById('multiDownloadSubtitle').href = result.srt_url;
                        document.getElementById('multiDownloadSubtitle').style.display = 'inline-block';
                    }
                    
                    // Show output section
                    document.getElementById('multiOutput').style.display = 'block';
                    
                    showToast(result.message);
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

        // Generate Q&A audio
        document.getElementById('qaGenerateBtn').addEventListener('click', async function() {
            const text = document.getElementById('qaText').value.trim();
            
            if (!text) {
                showToast('Please enter Q&A text', 'error');
                return;
            }
            
            // Get question settings
            const questionLanguageSelect = document.querySelector('.qaLanguage[data-type="question"]');
            const questionVoiceSelect = document.querySelector('.qaVoice[data-type="question"]');
            const questionLanguage = questionLanguageSelect.value;
            const questionVoice = questionVoiceSelect.value;
            
            if (!questionLanguage) {
                showToast('Please select language for Questions', 'error');
                return;
            }
            
            if (!questionVoice) {
                showToast('Please select voice for Questions', 'error');
                return;
            }
            
            // Get answer settings
            const answerLanguageSelect = document.querySelector('.qaLanguage[data-type="answer"]');
            const answerVoiceSelect = document.querySelector('.qaVoice[data-type="answer"]');
            const answerLanguage = answerLanguageSelect.value;
            const answerVoice = answerVoiceSelect.value;
            
            if (!answerLanguage) {
                showToast('Please select language for Answers', 'error');
                return;
            }
            
            if (!answerVoice) {
                showToast('Please select voice for Answers', 'error');
                return;
            }
            
            showLoading();
            
            const formData = new FormData();
            formData.append('text', text);
            formData.append('question_language', questionLanguage);
            formData.append('question_voice', questionVoice);
            formData.append('question_rate', document.querySelector('[data-setting="rate"][data-type="question"]').value);
            formData.append('question_pitch', document.querySelector('[data-setting="pitch"][data-type="question"]').value);
            formData.append('question_volume', document.querySelector('[data-setting="volume"][data-type="question"]').value);
            formData.append('answer_language', answerLanguage);
            formData.append('answer_voice', answerVoice);
            formData.append('answer_rate', document.querySelector('[data-setting="rate"][data-type="answer"]').value);
            formData.append('answer_pitch', document.querySelector('[data-setting="pitch"][data-type="answer"]').value);
            formData.append('answer_volume', document.querySelector('[data-setting="volume"][data-type="answer"]').value);
            formData.append('pause_q', document.getElementById('qaPauseQ').value);
            formData.append('pause_a', document.getElementById('qaPauseA').value);
            formData.append('repeat', document.getElementById('qaRepeat').value);
            formData.append('output_format', document.getElementById('qaFormat').value);
            
            try {
                const response = await fetch('/api/generate/qa', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show audio player
                    const audioPlayer = document.getElementById('qaAudioPlayer');
                    audioPlayer.innerHTML = `
                        <audio controls class="w-100">
                            <source src="${result.audio_url}" type="audio/mpeg">
                            Your browser does not support the audio element.
                        </audio>
                    `;
                    
                    // Show download buttons
                    document.getElementById('qaDownloadAudio').href = result.audio_url;
                    if (result.srt_url) {
                        document.getElementById('qaDownloadSubtitle').href = result.srt_url;
                        document.getElementById('qaDownloadSubtitle').style.display = 'inline-block';
                    }
                    
                    // Show output section
                    document.getElementById('qaOutput').style.display = 'block';
                    
                    showToast(result.message);
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

        // Auto-cleanup on page load
        window.addEventListener('load', () => {
            fetch('/api/cleanup', { method: 'POST' }).catch(console.error);
        });
    </script>
</body>
</html>
"""

# Create the HTML file
with open("templates/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)

# Create static directory for additional assets
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

# Create simple CSS file
css_content = """
/* Additional custom styles */
.voice-preview {
    border-left: 4px solid #4361ee;
    padding-left: 1rem;
    margin: 1rem 0;
}

.voice-preview audio {
    width: 100%;
    margin-top: 0.5rem;
}

.settings-group {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
}

.output-stats {
    background: #e9ecef;
    border-radius: 8px;
    padding: 1rem;
    margin-top: 1rem;
    font-size: 0.875rem;
}

@media (max-width: 768px) {
    .main-container {
        margin: 1rem;
        border-radius: 10px;
    }
    
    .nav-tabs .nav-link {
        padding: 0.75rem 1rem;
        font-size: 0.875rem;
    }
    
    .tab-content {
        padding: 1rem;
    }
}
"""

with open("static/css/custom.css", "w", encoding="utf-8") as f:
    f.write(css_content)

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
    
    print(f"Starting Professional TTS Generator on port {port}")
    print(f"Open http://localhost:{port} in your browser")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
