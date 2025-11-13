# ============================================
# ===       COMPLETE FINAL FIX (v31)       ===
# ============================================
# === (FEAT: Add More Episodes flow)       ===
# === (FEAT: Set Items per Page to 20)     ===
# === (FEAT: Sort anime by last_modified)  ===
# === (FEAT: Add 2 new fonts)              ===
# === (FIX: Back button logic for new flow)===
# ============================================
import os
import logging
import re # NAYA: Regex ke liye
import asyncio 
import threading 
import httpx 
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING 
from bson.objectid import ObjectId 
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, User, InputMediaPhoto
from telegram.constants import ParseMode # NAYA: HTML ke liye
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    Defaults
)
from telegram.error import BadRequest
# Flask server ke liye
from flask import Flask, request 
from waitress import serve 

# --- Font Manager (NAYA FEATURE) ---

# Har font ke liye Normal aur Bold map
FONT_MAPS = {
    'default': {},
    'small_caps': {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ',
        'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'Q', 'r': 'ʀ',
        's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
        'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F', 'G': 'G', 'H': 'H', 'I': 'I',
        'J': 'J', 'K': 'K', 'L': 'L', 'M': 'M', 'N': 'N', 'O': 'O', 'P': 'P', 'Q': 'Q', 'R': 'R',
        'S': 'S', 'T': 'T', 'U': 'U', 'V': 'V', 'W': 'W', 'X': 'X', 'Y': 'Y', 'Z': 'Z',
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
    },
    'sans_serif': {
        'a': '𝘢', 'b': '𝘣', 'c': '𝘤', 'd': '𝘥', 'e': '𝘦', 'f': '𝘧', 'g': '𝘨', 'h': '𝘩', 'i': '𝘪',
        'j': '𝘫', 'k': '𝘬', 'l': '𝘭', 'm': '𝘮', 'n': '𝘯', 'o': '𝘰', 'p': '𝘱', 'q': '𝘲', 'r': '𝘳',
        's': '𝘴', 't': '𝘵', 'u': '𝘶', 'v': '𝘷', 'w': '𝘸', 'x': '𝘹', 'y': '𝘺', 'z': '𝘻',
        'A': '𝘈', 'B': '𝘉', 'C': '𝘊', 'D': '𝘋', 'E': '𝘌', 'F': '𝘍', 'G': '𝘎', 'H': '𝘏', 'I': '𝘐',
        'J': '𝘑', 'K': '𝘒', 'L': '𝘓', 'M': '𝘔', 'N': '𝘕', 'O': '𝘖', 'P': '𝘗', 'Q': '𝘘', 'R': '𝘙', # <-- FIX
        'S': '𝘚', 'T': '𝘛', 'U': '𝘜', 'V': '𝘝', 'W': '𝘞', 'X': '𝘟', 'Y': '𝘠', 'Z': '𝘡',
        '0': '𝟢', '1': '𝟣', '2': '𝟤', '3': '𝟥', '4': '𝟦', '5': '𝟧', '6': '𝟨', '7': '𝟩', '8': '𝟪', '9': '𝟫'
    },
    'sans_serif_bold': {
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟', 'g': '𝐠', 'h': '𝐡', 'i': '𝐢',
        'j': '𝐣', 'k': '𝐤', 'l': '𝐥', 'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫',
        's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱', 'y': '𝐲', 'z': '𝐳',
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇', 'I': '𝐈',
        'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑',
        'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗'
    },
    # NAYA FONT 1: sans_serif_regular
    'sans_serif_regular': {
        'a': '𝖺', 'b': '𝖻', 'c': '𝖼', 'd': '𝖽', 'e': '𝖾', 'f': '𝖿', 'g': '𝗀', 'h': '𝗁', 'i': '𝗂',
        'j': '𝗃', 'k': '𝗄', 'l': '𝗅', 'm': '𝗆', 'n': '𝗇', 'o': '𝗈', 'p': '𝗉', 'q': '𝗊', 'r': '𝗋',
        's': '𝗌', 't': '𝗍', 'u': '𝗎', 'v': '𝗏', 'w': '𝗐', 'x': '𝗑', 'y': '𝗒', 'z': '𝗓',
        'A': '𝖠', 'B': '𝖡', 'C': '𝖢', 'D': '𝖣', 'E': '𝖤', 'F': '𝖥', 'G': '𝖦', 'H': '𝖧', 'I': '𝖨',
        'J': '𝖩', 'K': '𝖪', 'L': '𝖫', 'M': '𝖬', 'N': '𝖭', 'O': '𝖮', 'P': '𝖯', 'Q': '𝖰', 'R': '𝖱',
        'S': '𝖲', 'T': '𝖳', 'U': '𝖴', 'V': '𝖵', 'W': '𝖶', 'X': '𝖷', 'Y': '𝖸', 'Z': '𝖹',
        '0': '𝟢', '1': '𝟣', '2': '𝟤', '3': '𝟥', '4': '𝟦', '5': '𝟧', '6': '𝟨', '7': '𝟩', '8': '𝟪', '9': '𝟫'
    },
    # NAYA FONT 2: sans_serif_regular_bold
    'sans_serif_regular_bold': {
        'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 'i': '𝗶',
        'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿',
        's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
        'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜',
        'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥',
        'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
        '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'
    },
    'script': {
        'a': '𝒶', 'b': '𝒷', 'c': '𝒸', 'd': '𝒹', 'e': '𝑒', 'f': '𝒻', 'g': '𝑔', 'h': '𝒽', 'i': '𝒾',
        'j': '𝒿', 'k': '𝓀', 'l': '𝓁', 'm': '𝓂', 'n': '𝓃', 'o': '𝑜', 'p': '𝓅', 'q': '𝓆', 'r': '𝓇',
        's': '𝓈', 't': '𝓉', 'u': '𝓊', 'v': '𝓋', 'w': '𝓌', 'x': '𝓍', 'y': '𝓎', 'z': '𝓏',
        'A': '𝒜', 'B': '𝐵', 'C': '𝒞', 'D': '𝒟', 'E': '𝐸', 'F': '𝐹', 'G': '𝒢', 'H': '𝐻', 'I': '𝐼',
        'J': '𝒥', 'K': '𝒦', 'L': '𝐿', 'M': '𝑀', 'N': '𝒩', 'O': '𝒪', 'P': '𝒫', 'Q': '𝒬', 'R': '𝑅',
        'S': '𝒮', 'T': '𝒯', 'U': '𝒰', 'V': '𝒱', 'W': '𝒲', 'X': '𝒳', 'Y': '𝒴', 'Z': '𝒵',
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
    },
    'script_bold': {
        'a': '𝓪', 'b': '𝓫', 'c': '𝓬', 'd': '𝓭', 'e': '𝓮', 'f': '𝓯', 'g': '𝓰', 'h': '𝓱', 'i': '𝓲',
        'j': '𝓳', 'k': '𝓴', 'l': '𝓵', 'm': '𝓶', 'n': '𝓷', 'o': '𝓸', 'p': '𝓹', 'q': '𝓺', 'r': '𝓻',
        's': '𝓼', 't': '𝓽', 'u': '𝓾', 'v': '𝓿', 'w': '𝔀', 'x': '𝔁', 'y': '𝔂', 'z': '𝔃',
        'A': '𝓐', 'B': '𝓑', 'C': '𝓒', 'D': '𝓓', 'E': '𝓔', 'F': '𝓕', 'G': '𝓖', 'H': '𝓗', 'I': '𝓘',
        'J': '𝓙', 'K': '𝓚', 'L': '𝓛', 'M': '𝓜', 'N': '𝓝', 'O': '𝓞', 'P': '𝓟', 'Q': '𝓠', 'R': '𝓡',
        'S': '𝓢', 'T': '𝓣', 'U': '𝓤', 'V': '𝓥', 'W': '𝓦', 'X': '𝓧', 'Y': '𝓨', 'Z': '𝓩',
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
    },
    'monospace': {
        'a': '𝚊', 'b': '𝚋', 'c': '𝚌', 'd': '𝚍', 'e': '𝚎', 'f': '𝚏', 'g': '𝚐', 'h': '𝚑', 'i': '𝚒',
        'j': '𝚓', 'k': '𝚔', 'l': '𝚕', 'm': '𝚖', 'n': '𝚗', 'o': '𝚘', 'p': '𝚙', 'q': '𝚚', 'r': '𝚛',
        's': '𝚜', 't': '𝚝', 'u': '𝚞', 'v': '𝚟', 'w': '𝚠', 'x': '𝚡', 'y': '𝚢', 'z': '𝚣',
        'A': '𝙰', 'B': '𝙱', 'C': '𝙲', 'D': '𝙳', 'E': '𝙴', 'F': '𝙵', 'G': '𝙶', 'H': '𝙷', 'I': '𝙸',
        'J': '𝙹', 'K': '𝙺', 'L': '𝙻', 'M': '𝙼', 'N': '𝙽', 'O': '𝙾', 'P': '𝙿', 'Q': '𝚀', 'R': '𝚁',
        'S': '𝚂', 'T': '𝚃', 'U': '𝚄', 'V': '𝚅', 'W': '𝚆', 'X': '𝚇', 'Y': '𝚈', 'Z': '𝚉',
        '0': '𝟶', '1': '𝟷', '2': '𝟸', '3': '𝟹', '4': '𝟺', '5': '𝟻', '6': '𝟼', '7': '𝟽', '8': '𝟾', '9': '𝟿'
    },
    'serif': {
        'a': '𝘢', 'b': '𝘣', 'c': '𝘤', 'd': '𝘥', 'e': '𝘦', 'f': '𝘧', 'g': '𝘨', 'h': '𝘩', 'i': '𝘪',
        'j': '𝘫', 'k': '𝘬', 'l': '𝘭', 'm': '𝘮', 'n': '𝘯', 'o': '𝘰', 'p': '𝘱', 'q': '𝘲', 'r': '𝘳',
        's': '𝘴', 't': '𝘵', 'u': '𝘶', 'v': '𝘷', 'w': '𝘸', 'x': '𝘹', 'y': '𝘺', 'z': '𝘻',
        'A': '𝘈', 'B': '𝘉', 'C': '𝘊', 'D': '𝘋', 'E': '𝘌', 'F': '𝘍', 'G': '𝘎', 'H': '𝘏', 'I': '𝘐', # <-- FIX
        'J': '𝘑', 'K': '𝘒', 'L': '𝘓', 'M': '𝘔', 'N': '𝘕', 'O': '𝘖', 'P': '𝘗', 'Q': '𝘘', 'R': '𝘙', # <-- FIX
        'S': '𝘚', 'T': '𝘛', 'U': '𝘜', 'V': '𝘝', 'W': '𝘞', 'X': '𝘟', 'Y': '𝘠', 'Z': '𝘡',
        '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9'
    },
    'serif_bold': {
        'a': '𝐚', 'b': '𝐛', 'c': '𝐜', 'd': '𝐝', 'e': '𝐞', 'f': '𝐟', 'g': '𝐠', 'h': '𝐡', 'i': '𝐢',
        'j': '𝐣', 'k': '𝐤', 'l': '𝐥', 'm': '𝐦', 'n': '𝐧', 'o': '𝐨', 'p': '𝐩', 'q': '𝐪', 'r': '𝐫',
        's': '𝐬', 't': '𝐭', 'u': '𝐮', 'v': '𝐯', 'w': '𝐰', 'x': '𝐱', 'y': '𝐲', 'z': '𝐳',
        'A': '𝐀', 'B': '𝐁', 'C': '𝐂', 'D': '𝐃', 'E': '𝐄', 'F': '𝐅', 'G': '𝐆', 'H': '𝐇', 'I': '𝐈',
        'J': '𝐉', 'K': '𝐊', 'L': '𝐋', 'M': '𝐌', 'N': '𝐍', 'O': '𝐎', 'P': '𝐏', 'Q': '𝐐', 'R': '𝐑',
        'S': '𝐒', 'T': '𝐓', 'U': '𝐔', 'V': '𝐕', 'W': '𝐖', 'X': '𝐗', 'Y': '𝐘', 'Z': '𝐙',
        '0': '𝟎', '1': '𝟏', '2': '𝟐', '3': '𝟑', '4': '𝟒', '5': '𝟓', '6': '𝟔', '7': '𝟕', '8': '𝟖', '9': '𝟗'
    }
}
# Small Caps ko bold nahi hota, isliye uska bold map normal hi hai
FONT_MAPS['small_caps_bold'] = FONT_MAPS['small_caps']
# Monospace ka bold nahi hota
FONT_MAPS['monospace_bold'] = FONT_MAPS['monospace']
# Default ke liye bold (yeh sans_serif_regular_bold se alag hai)
FONT_MAPS['default_bold'] = {
    'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 'i': '𝗶',
    'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿',
    's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 'y': '𝘆', 'z': '𝘇',
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 'I': '𝗜',
    'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥',
    'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 'Y': '𝗬', 'Z': '𝗭',
    '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', '8': '𝟴', '9': '𝟵'
}


async def apply_font_formatting(raw_text: str, font_settings: dict) -> str:
    """
    <f>...</f> tags ke andar ke text ko font apply karega.
    (FIX v31: HTML tags jaise <b> ko ignore karega)
    """
    font = font_settings.get('font', 'default')
    style = font_settings.get('style', 'normal')
    
    if font == 'default' and style == 'normal':
        return raw_text.replace('<f>', '').replace('</f>', '') # Tags hata do

    # Sahi map select karo
    map_key = f"{font}_{style}" if style == 'bold' else font
    font_map = FONT_MAPS.get(map_key, {})
    
    if not font_map:
        # Fallback
        map_key = 'default_bold' if style == 'bold' else 'default'
        font_map = FONT_MAPS.get(map_key, {})
        if not font_map: # Agar default_bold bhi fail ho
             return raw_text.replace('<f>', '').replace('</f>', '')

    def replace_chars_html_safe(text_chunk):
        # Yeh function sirf plain text par chalega
        return "".join([font_map.get(char, char) for char in text_chunk])

    def process_tags(match):
        content = match.group(1) # <f> ke andar ka content
        
        # Content ko HTML tags aur text me todo
        # Yeh 'Salaam <b>Naam</b>' ko ['Salaam ', '<b>', 'Naam', '</b>', ''] me tod dega
        parts = re.split(r'(<[^>]+>)', content)
        
        processed_parts = []
        for part in parts:
            if re.match(r'<[^>]+>', part):
                # Yeh ek HTML tag hai (jaise <b>), isko chhedo mat
                processed_parts.append(part)
            else:
                # Yeh plain text hai, ispar font apply karo
                processed_parts.append(replace_chars_html_safe(part))
        
        return "".join(processed_parts)

    # <f> tag ke andar sab kuch process karo
    try:
        formatted_text = re.sub(r'<f>(.*?)</f>', process_tags, raw_text, flags=re.DOTALL)
        return formatted_text
    except Exception as e:
        logger.error(f"Font formatting me error: {e}")
        return raw_text.replace('<f>', '').replace('</f>', '')


# --- Baaki ka Bot Code ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Secrets Load Karo ---
try:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    MONGO_URI = os.getenv("MONGO_URI")
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
    LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID") 
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL') 
    
    if not BOT_TOKEN or not MONGO_URI or not ADMIN_ID or not LOG_CHANNEL_ID:
        logger.error("Error: Secrets missing. BOT_TOKEN, MONGO_URI, ADMIN_ID, aur LOG_CHANNEL_ID check karo.")
        exit()
    if not WEBHOOK_URL:
        logger.error("Error: WEBHOOK_URL missing! Render > Environment mein set karo.")
        exit()
except Exception as e:
    logger.error(f"Error reading secrets: {e}")
    exit()

# --- Database Connection ---
try:
    logger.info("MongoDB se connect karne ki koshish...")
    client = MongoClient(MONGO_URI)
    db = client['AnimeBotDB']
    users_collection = db['users']
    animes_collection = db['animes'] 
    config_collection = db['config'] 
    
    animes_collection.create_index([("name", ASCENDING)])
    animes_collection.create_index([("created_at", DESCENDING)]) 
    animes_collection.create_index([("last_modified", DESCENDING)]) # NAYA: Smart sort ke liye
    
    client.admin.command('ping') 
    logger.info("MongoDB se successfully connect ho gaya!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit()

ITEMS_PER_PAGE = 20 # NAYA: 8 se 20 kar diya

# --- NAYA: Admin & Co-Admin Checks ---
async def is_main_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

async def is_co_admin(user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    config = await get_config()
    return user_id in config.get("co_admins", [])


# --- NAYA: Message Formatting Helper ---
async def format_message(context: ContextTypes.DEFAULT_TYPE, key: str, variables: dict = None) -> str:
    """
    DB se message laayega, font apply karega, aur variables replace karega.
    """
    config = await get_config()
    
    # 1. Message template DB se laao
    default_messages = await get_default_messages() # Default list laao
    raw_text = config.get("messages", {}).get(key, default_messages.get(key, f"MISSING_KEY: {key}"))
    
    # 2. Font settings apply karo
    font_settings = config.get("appearance", {"font": "default", "style": "normal"})
    formatted_text = await apply_font_formatting(raw_text, font_settings)
    
    # 3. Variables (jaise {anime_name}) replace karo
    if variables:
        # Variables ko HTML-safe banao (agar woh text hain)
        safe_variables = {}
        for k, v in variables.items():
            if isinstance(v, str):
                safe_variables[k] = v.replace('<', '&lt;').replace('>', '&gt;')
            else:
                safe_variables[k] = v
        
        try:
            formatted_text = formatted_text.format(**safe_variables)
        except KeyError as e:
            logger.error(f"Message format karne me KeyError: {e} (Key: {key})")
            # Koshish karo ki problem waale variable ke bina format ho
            try:
                formatted_text = formatted_text.format_map(safe_variables)
            except:
                pass # Agar phir bhi fail ho, toh raw text hi bhej do
        except Exception as e:
             logger.error(f"Message format karne me error: {e} (Key: {key})")

    return formatted_text


# --- NAYA: Saare Default Messages Ek Jagah ---
async def get_default_messages():
    """
    Saare default messages ki list, <f> tags aur HTML ke saath.
    FIX: Saare <pre> tags hata diye jo spacing ke liye the.
    """
    # <pre>...</pre> tag commands (/cancel) ko clickable banaye rakhne ke liye zaroori hai
    return {
        # === Download Flow ===
        "user_dl_dm_alert": "✅ <f>Check your DM (private chat) with me!</f>",
        "user_dl_anime_not_found": "❌ <f>Error: Anime nahi mila.</f>",
        "user_dl_file_error": "❌ <f>Error! {quality} file nahi bhej paya. Please try again.</f>",
        "user_dl_blocked_error": "❌ <f>Error! File nahi bhej paya. Aapne bot ko block kiya hua hai.</f>",
        "user_dl_episodes_not_found": "❌ <f>Error: Is season ke liye episodes nahi mile.</f>",
        "user_dl_seasons_not_found": "❌ <f>Error: Is anime ke liye seasons nahi mile.</f>",
        "user_dl_general_error": "❌ <f>Error! Please try again.</f>",
        "user_dl_sending_files": "✅ <b>{anime_name}</b> | <b>S{season_name}</b> | <b>E{ep_num}</b>\n\n<f>Aapke saare files bhej raha hoon...</f>",
        "user_dl_select_episode": "<b>{anime_name}</b> | <b>Season {season_name}</b>\n\n<f>Episode select karein:</f>",
        "user_dl_select_season": "<b>{anime_name}</b>\n\n<f>Season select karein:</f>",
        "file_warning": "⚠️ <b><f>Yeh file {minutes} minute(s) mein automatically delete ho jaayegi.</f></b>",
        "user_dl_fetching": "⏳ <f>Fetching files...</f>",

        # === General User ===
        "user_menu_greeting": "<f>Salaam {full_name}! Ye raha aapka menu:</f>", # FIX: {full_name}
        "user_donate_qr_error": "❌ <f>Donation info abhi admin ne set nahi ki hai.</f>",
        "user_donate_qr_text": "❤️ <b><f>Support Us!</f></b>\n\n<f>Agar aapko hamara kaam pasand aata hai, toh aap humein support kar sakte hain.</f>",
        "donate_thanks": "❤️ <f>Support karne ke liye shukriya!</f>",
        "user_not_admin": "<f>Aap admin nahi hain.</f>",
        "user_welcome_admin": "<f>Salaam, Admin! Admin panel ke liye</f> /menu <f>use karein.</f>",
        "user_welcome_basic": "<f>Salaam, {full_name}! Apna user menu dekhne ke liye</f> /user <f>use karein.</f>", # FIX: {full_name}
        
        # === Post Generator ===
        "post_gen_anime_caption": "✅ <b>{anime_name}</b>\n\n<b><f>📖 Synopsis:</f></b>\n{description}\n\n<f>Neeche [Download] button dabake download karein!</f>",
        "post_gen_season_caption": "✅ <b>{anime_name}</b>\n<b>[ S{season_name} ]</b>\n\n<b><f>📖 Synopsis:</f></b>\n{description}\n\n<f>Neeche [Download] button dabake download karein!</f>",
        "post_gen_episode_caption": "✨ <b><f>Episode {ep_num} Added</f></b> ✨\n\n🎬 <b><f>Anime:</f></b> {anime_name}\n➡️ <b><f>Season:</f></b> {season_name}\n\n<f>Neeche [Download] button dabake download karein!</f>",

        # === Admin: General ===
        "admin_cancel": "<f>Operation cancel kar diya gaya hai.</f>",
        "admin_cancel_error_edit": "<f>Cancel me edit nahi kar paya: {e}</f>",
        "admin_cancel_error_general": "<f>Cancel me error: {e}</f>",
        "admin_panel_main": "👑 <b><f>Salaam, Admin Boss!</f></b> 👑\n<f>Aapka control panel taiyyar hai.</f>",
        "admin_panel_co": "👑 <b><f>Salaam, Co-Admin!</f></b> 👑\n<f>Aapka content panel taiyyar hai.</f>",

        # === Admin: Set Menu Photo ===
    "admin_set_menu_photo_start": "<f>User menu mein dikhaane ke liye <b>Photo</b> bhejo.</f>\n\n/skip - <f>Photo hata do.</f>\n/cancel - <f>Cancel.</f>",
    "admin_set_menu_photo_error": "<f>Ye photo nahi hai. Please ek photo bhejo ya</f> /skip <f>karein.</f>",
    "admin_set_menu_photo_success": "✅ <b><f>Success!</f></b> <f>Naya user menu photo set ho gaya hai.</f>",
    "admin_set_menu_photo_skip": "✅ <b><f>Success!</f></b> <f>User menu photo hata diya gaya hai.</f>",

        # === Admin: Add Content Menus ===
        "admin_menu_add_content": "➕ <b><f>Add Content</f></b> ➕\n\n<f>Aap kya add karna chahte hain?</f>",
        "admin_menu_manage_content": "🗑️ <b><f>Delete Content</f></b> 🗑️\n\n<f>Aap kya delete karna chahte hain?</f>",
        "admin_menu_edit_content": "✏️ <b><f>Edit Content</f></b> ✏️\n\n<f>Aap kya edit karna chahte hain?</f>",

        # === Admin: Add Anime ===
        "admin_add_anime_start": "<f>Salaam Admin! Anime ka <b>Naam</b> kya hai?</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_add_anime_get_name": "<f>Badhiya! Ab anime ka <b>Poster (Photo)</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_add_anime_get_poster_error": "Ye photo nahi hai. Please ek photo bhejo.",
        "admin_add_anime_get_poster": "<f>Poster mil gaya! Ab <b>Description (Synopsis)</b> bhejo.</f>\n\n/skip <f>ya</f> /cancel.",
        "admin_add_anime_confirm": "<b>{name}</b>\n\n{description}\n\n<f>--- Details Check Karo ---</f>",
        "admin_add_anime_confirm_error": "❌ <f>Error: Poster bhej nahi paya. Dobara try karein ya</f> /cancel.",
        "admin_add_anime_save_exists": "⚠️ <b><f>Error:</f></b> <f>Ye anime naam</f> '{name}' <f>pehle se hai.</f>",
        "admin_add_anime_save_success": "✅ <b><f>Success!</f></b> '{name}' <f>add ho gaya hai.</f>",
        "admin_add_anime_save_error": "❌ <b><f>Error!</f></b> <f>Database me save nahi kar paya.</f>",

        # === Admin: Add Season ===
        "admin_add_season_select_anime": "<f>Aap kis anime mein season add karna chahte hain?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_add_season_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai. Pehle 'Add Anime' se add karein.</f>",
        "admin_add_season_get_anime": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Ab is season ka <b>Number ya Naam</b> bhejo.</f>\n<f>(Jaise: 1, 2, Movie)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_add_season_get_anime_with_last": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n<f>Last added season:</f> <b>{last_season_name}</b>\n\n<f>Ab is season ka <b>Number ya Naam</b> bhejo.</f>\n<f>(Jaise: 1, 2, Movie)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_add_season_get_anime_no_last": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n<f>Is anime mein abhi koi season nahi hai.</f>\n\n<f>Ab is season ka <b>Number ya Naam</b> bhejo.</f>\n<f>(Jaise: 1, 2, Movie)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_add_season_get_number_error": "⚠️ <b><f>Error!</f></b> <f>Anime</f> '{anime_name}' <f>database mein nahi mila.</f> /cancel <f>karke dobara try karein.</f>",
        "admin_add_season_get_number_exists": "⚠️ <b><f>Error!</f></b> '{anime_name}' <f>mein 'Season {season_name}' pehle se hai.</f>\n\n<f>Koi doosra naam/number type karein ya</f> /cancel <f>karein.</f>",
        "admin_add_season_get_poster_prompt": "<f>Aapne Season</f> '{season_name}' <f>select kiya hai.</f>\n\n<f>Ab is season ka <b>Poster (Photo)</b> bhejo.</f>\n\n/skip - <f>Default anime poster use karo.</f>\n/cancel - <f>Cancel.</f>",
        "admin_add_season_get_poster_error": "<f>Ye photo nahi hai. Please ek photo bhejo.</f>",
        "admin_add_season_get_desc_prompt": "<f>Poster mil gaya! Ab is season ka <b>Description</b> bhejo.</f>\n<f>(Yeh post generator mein use hoga)</f>\n\n/skip <f>ya</f> /cancel.",
        "admin_add_season_skip_poster": "<f>Default poster set! Ab is season ka <b>Description</b> bhejo.</f>\n<f>(Yeh post generator mein use hoga)</f>\n\n/skip <f>ya</f> /cancel.",
        "admin_add_season_confirm": "<b><f>Confirm Karo:</f></b>\n<f>Anime:</f> <b>{anime_name}</b>\n<f>Naya Season:</f> <b>{season_name}</b>\n<f>Description:</f> {season_desc}\n\n<f>Save kar doon?</f>",
        "admin_add_season_save_success": "✅ <b><f>Success!</f></b>\n<b>{anime_name}</b> <f>mein</f> <b>Season {season_name}</b> <f>add ho gaya hai.</f>",
        "admin_add_season_save_error": "❌ <b><f>Error!</f></b> <f>Database me save nahi kar paya.</f>",
        "admin_add_season_ask_more": "✅ <f>Season</f> <b>{season_name}</b> <f>save ho gaya!</f>\n\n<f>Aap</f> <b>{anime_name}</b> <f>mein aur season add karna chahte hain?</f>", 
        "admin_add_season_next_prompt": "<f>Last Season:</f> <b>{season_name}</b>. <f>Anime:</f> <b>{anime_name}</b>\n\n<f>Ab agla <b>Season Number/Naam</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        
        # === Admin: Add Episode ===
        "admin_add_ep_select_anime": "<f>Aap kis anime mein episode add karna chahte hain?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_add_ep_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai. Pehle 'Add Anime' se add karein.</f>",
        "admin_add_ep_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>\n\n<f>Pehle</f> <code>➕ Add Season</code> <f>se season add karo.</f>",
        "admin_add_ep_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Ab <b>Season</b> select karein:</f>",
        # NEW
        "admin_add_ep_get_season_with_last": "<f>Aapne</f> <b>Season {season_name}</b> <f>select kiya hai.</f>\n<f>Last added episode:</f> <b>{last_ep_num}</b>\n\n<f>Ab <b>Episode Number</b> bhejo.</f>\n<f>(Jaise: 1, 2, 3...)</f>\n<f>(Agar yeh ek movie hai, toh</f> <code>1</code> <f>type karein.)</f>\n\n/cancel - <f>Cancel.</f>", # NAYA
        "admin_add_ep_get_season_no_last": "<f>Aapne</f> <b>Season {season_name}</b> <f>select kiya hai.</f>\n<f>Is season mein abhi koi episode nahi hai.</f>\n\n<f>Ab <b>Episode Number</b> bhejo.</f>\n<f>(Jaise: 1, 2, 3...)</f>\n<f>(Agar yeh ek movie hai, toh</f> <code>1</code> <f>type karein.)</f>\n\n/cancel - <f>Cancel.</f>", # NAYA
        "admin_add_ep_get_number": "<f>Aapne</f> <b>Episode {ep_num}</b> <f>select kiya hai.</f>\n\n<f>Ab <b>480p</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_get_number_exists": "⚠️ <b><f>Error!</f></b> '{anime_name}' - Season {season_name} - Episode {ep_num} <f>pehle se maujood hai. Please pehle isse delete karein ya koi doosra episode number dein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_add_ep_helper_invalid": "<f>Ye video file nahi hai. Please dobara video file bhejein ya</f> /skip <f>karein.</f>",
        "admin_add_ep_helper_success": "✅ <b>{quality}</b> <f>save ho gaya.</f>",
        "admin_add_ep_helper_error": "❌ <b><f>Error!</f></b> {quality} <f>save nahi kar paya. Logs check karein.</f>",
        "admin_add_ep_get_480p": "<f>Ab <b>720p</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_skip_480p": "✅ <f>480p skip kar diya.</f>\n\n<f>Ab <b>720p</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_get_720p": "<f>Ab <b>1080p</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_skip_720p": "✅ <f>720p skip kar diya.</f>\n\n<f>Ab <b>1080p</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_get_1080p": "<f>Ab <b>4K</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_skip_1080p": "✅ <f>1080p skip kar diya.</f>\n\n<f>Ab <b>4K</b> quality ki video file bhejein.</f>\n<f>Ya</f> /skip <f>type karein.</f>",
        "admin_add_ep_get_4k_success": "✅ <b><f>Success!</f></b> <f>Saari qualities save ho gayi hain.</f>",
        "admin_add_ep_skip_4k": "✅ <f>4K skip kar diya.</f>\n\n✅ <b><f>Success!</f></b> <f>Episode save ho gaya hai.</f>",
        "admin_add_ep_ask_more": "✅ <f>Ep</f> <b>{ep_num}</b> <f>save ho gaya!</f>\n\n<f>Aap</f> <b>S{season_name}</b> <f>mein aur episode add karna chahte hain?</f>", # NAYA
        "admin_add_ep_next_prompt": "<f>Last Ep:</f> <b>{ep_num}</b>. <f>Season:</f> <b>{season_name}</b>\n\n<f>Ab agla <b>Episode Number</b> bhejo.</f>\n<f>(Suggestion: {next_ep_num})</f>\n\n/cancel - <f>Cancel.</f>", # NAYA
        "admin_add_ep_next_prompt_no_suggestion": "<f>Last Ep:</f> <b>{ep_num}</b>. <f>Season:</f> <b>{season_name}</b>\n\n<f>Ab agla <b>Episode Number</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>", # NAYA
        
        # === Admin: Settings (Donate, Links, Delete Time) ===
        "admin_menu_donate": "❤️ <b><f>Donation Settings</f></b> ❤️\n\n<f>Sirf QR code se donation accept karein.</f>",
        "admin_set_donate_qr_start": "<f>Aapna <b>Donate QR Code</b> ki photo bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_set_donate_qr_error": "<f>Ye photo nahi hai. Please ek photo bhejo ya</f> /cancel <f>karein.</f>",
        "admin_set_donate_qr_success": "✅ <b><f>Success!</f></b> <f>Naya donate QR code set ho gaya hai.</f>",
        "admin_menu_links": "🔗 <b><f>Other Links</f></b> 🔗\n\n<f>Doosre links yahan set karein.</f>",
        "admin_set_link_backup": "<f>Aapke <b>Backup Channel</b> ka link bhejo.</f>\n<f>(Example: https://t.me/mychannel)</f>\n\n/skip - <f>Skip.</f>\n/cancel - <f>Cancel.</f>",
        "admin_set_link_download": "<f>Aapka global <b>Download Link</b> bhejo.</f>\n<f>(Yeh post generator mein use hoga)</f>\n\n/skip - <f>Skip.</f>\n/cancel - <f>Cancel.</f>",
        "admin_set_link_help": "<f>Aapke <b>Help/Support</b> ka link bhejo.</f>\n<f>(Example: https://t.me/mychannel)</f>\n\n/skip - <f>Skip.</f>\n/cancel - <f>Cancel.</f>", # NAYA
        "admin_set_link_invalid": "<f>Invalid button!</f>",
        "admin_set_link_success": "✅ <b><f>Success!</f></b> <f>Naya {link_type} link set ho gaya hai.</f>",
        "admin_set_link_skip": "✅ <b><f>Success!</f></b> {link_type} <f>link remove kar diya gaya hai.</f>",
        "admin_set_delete_time_start": "<f>Abhi file auto-delete</f> <b>{current_minutes} <f>minute(s)</f></b> ({current_seconds} <f>seconds</f>) <f>par set hai.</f>\n\n<f>Naya time <b>seconds</b> mein bhejo.</f>\n<f>(Example:</f> <code>300</code> <f>for 5 minutes)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_set_delete_time_low": "<f>Time 10 second se zyada hona chahiye.</f>",
        "admin_set_delete_time_success": "✅ <b><f>Success!</f></b> <f>Auto-delete time ab</f> <b>{seconds} <f>seconds</f></b> ({minutes} <f>min</f>) <f>par set ho gaya hai.</f>",
        "admin_set_delete_time_nan": "<f>Yeh number nahi hai. Please sirf seconds bhejein (jaise 180) ya</f> /cancel <f>karein.</f>",
        "admin_set_delete_time_error": "❌ <f>Error! Save nahi kar paya.</f>",

        # === Admin: Bot Messages Menu ===
        "admin_menu_messages_main": "⚙️ <b><f>Bot Messages</f></b> ⚙️\n\n<f>Aap bot ke replies ko edit karne ke liye category select karein.</f>",
        "admin_menu_messages_dl": "📥 <b><f>Download Flow Messages</f></b> 📥\n\n<f>Kaunsa message edit karna hai?</f>",
        "admin_menu_messages_gen": "⚙️ <b><f>General Messages</f></b> ⚙️\n\n<f>Kaunsa message edit karna hai?</f>",
        "admin_menu_messages_postgen": "✍️ <b><f>Post Generator Messages</f></b> ✍️\n\n<f>Kaunsa message edit karna hai?</f>",
        "admin_menu_messages_admin": "👑 <b><f>Admin Messages</f></b> 👑\n\n<f>Kaunsa message edit karna hai?</f>", # NAYA
        "admin_set_msg_start": "<b><f>Editing:</f></b> <code>{msg_key}</code>\n\n<b><f>Current Message:</f></b>\n<code>{current_msg}</code>\n\n<f>Naya message bhejo.</f>\n<f>Aap</f> <code>&lt;b&gt;bold&lt;/b&gt;</code>, <code>&lt;i&gt;italic&lt;/i&gt;</code>, <code>&lt;code&gt;code&lt;/code&gt;</code>, <f>aur</f> <code>&lt;blockquote&gt;quote&lt;/blockquote&gt;</code> <f>use kar sakte hain.</f>\n<f>Font apply karne ke liye</f> <code>&lt;f&gt;...&lt;/f&gt;</code> <f>use karein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_set_msg_success": "✅ <b><f>Success!</f></b> <f>Naya</f> '{msg_key}' <f>message set ho gaya hai.</f>",
        "admin_set_msg_error": "❌ <f>Error! Save nahi kar paya.</f>",

        # === Admin: Post Generator ===
        "admin_menu_post_gen": "✍️ <b><f>Post Generator</f></b> ✍️\n\n<f>Aap kis tarah ka post generate karna chahte hain?</f>",
        "admin_post_gen_select_anime": "<f>Kaunsa <b>Anime</b> select karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_post_gen_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_post_gen_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>",
        "admin_post_gen_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Ab <b>Season</b> select karein:</f>",
        "admin_post_gen_no_episode": "❌ <b><f>Error!</f></b> '{anime_name}' - Season {season_name} <f>mein koi episode nahi hai.</f>",
        "admin_post_gen_select_episode": "<f>Aapne</f> <b>Season {season_name}</b> <f>select kiya hai.</f>\n\n<f>Ab <b>Episode</b> select karein:</f>",
        "admin_post_gen_ask_shortlink": "✅ <b><f>Post Ready!</f></b>\n\n<f>Aapka original download link hai:</f>\n<code>{original_download_url}</code>\n\n<f>Please iska <b>shortened link</b> reply mein bhejein.</f>\n<f>(Agar link change nahi karna hai, toh upar waala link hi copy karke bhej dein.)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_post_gen_ask_chat": "✅ <b><f>Short Link Saved!</f></b>\n\n<f>Ab uss <b>Channel ka @username</b> ya <b>Group/Channel ki Chat ID</b> bhejo jahaan ye post karna hai.</f>\n<f>(Example: @MyAnimeChannel ya -100123456789)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_post_gen_success": "✅ <b><f>Success!</f></b>\n<f>Post ko</f> '{chat_id}' <f>par bhej diya gaya hai.</f>",
        "admin_post_gen_error": "❌ <b><f>Error!</f></b>\n<f>Post</f> '{chat_id}' <f>par nahi bhej paya. Check karo ki bot uss channel me admin hai ya ID sahi hai.</f>\n<f>Error:</f> {e}",
        "admin_post_gen_invalid_state": "❌ <f>Error! Invalid state. Please start over.</f>",
        "admin_post_gen_error_general": "❌ <b><f>Error!</f></b> <f>Post generate nahi ho paya. Logs check karein.</f>",
        
        # === Admin: Generate Link ===
        "admin_menu_gen_link": "🔗 <b><f>Generate Download Link</f></b> 🔗\n\n<f>Aap kis cheez ka link generate karna chahte hain?</f>",
        "admin_gen_link_select_anime": "<f>Kaunsa <b>Anime</b> select karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_gen_link_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_gen_link_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>",
        "admin_gen_link_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Ab <b>Season</b> select karein:</f>",
        "admin_gen_link_no_episode": "❌ <b><f>Error!</f></b> '{anime_name}' - Season {season_name} <f>mein koi episode nahi hai.</f>",
        "admin_gen_link_select_episode": "<f>Aapne</f> <b>Season {season_name}</b> <f>select kiya hai.</f>\n\n<f>Ab <b>Episode</b> select karein:</f>",
        "admin_gen_link_success": "✅ <b><f>Link Generated!</f></b>\n\n<b><f>Target:</f></b> {title}\n<b><f>Link:</f></b>\n<code>{final_link}</code>\n\n<f>Is link ko copy karke kahin bhi paste karein.</f>",
        "admin_gen_link_error": "❌ <b><f>Error!</f></b> <f>Link generate nahi ho paya. Logs check karein.</f>",

        # === Admin: Delete Anime ===
        "admin_del_anime_select": "<f>Kaunsa <b>Anime</b> delete karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_del_anime_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_del_anime_confirm": "⚠️ <b><f>FINAL WARNING</f></b> ⚠️\n\n<f>Aap</f> <b>{anime_name}</b> <f>ko delete karne wale hain. Iske saare seasons aur episodes delete ho jayenge.</f>\n\n<b><f>Are you sure?</f></b>",
        "admin_del_anime_success": "✅ <b><f>Success!</f></b>\n<f>Anime</f> '{anime_name}' <f>delete ho gaya hai.</f>",
        "admin_del_anime_error": "❌ <b><f>Error!</f></b> <f>Anime delete nahi ho paya.</f>",
        
        # === Admin: Delete Season ===
        "admin_del_season_select_anime": "<f>Kaunse <b>Anime</b> ka season delete karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_del_season_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_del_season_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>",
        "admin_del_season_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Kaunsa <b>Season</b> delete karna hai?</f>",
        "admin_del_season_confirm": "⚠️ <b><f>FINAL WARNING</f></b> ⚠️\n\n<f>Aap</f> <b>{anime_name}</b> <f>ka</f> <b>Season {season_name}</b> <f>delete karne wale hain. Iske saare episodes delete ho jayenge.</f>\n\n<b><f>Are you sure?</f></b>",
        "admin_del_season_success": "✅ <b><f>Success!</f></b>\n<f>Season</f> '{season_name}' <f>delete ho gaya hai.</f>",
        "admin_del_season_error": "❌ <b><f>Error!</f></b> <f>Season delete nahi ho paya.</f>",

        # === Admin: Delete Episode ===
        "admin_del_ep_select_anime": "<f>Kaunse <b>Anime</b> ka episode delete karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_del_ep_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_del_ep_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>",
        "admin_del_ep_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Kaunsa <b>Season</b> delete karna hai?</f>",
        "admin_del_ep_no_episode": "❌ <b><f>Error!</f></b> '{anime_name}' - Season {season_name} <f>mein koi episode nahi hai.</f>",
        "admin_del_ep_select_episode": "<f>Aapne</f> <b>Season {season_name}</b> <f>select kiya hai.</f>\n\n<f>Kaunsa <b>Episode</b> delete karna hai?</f>",
        "admin_del_ep_confirm": "⚠️ <b><f>FINAL WARNING</f></b> ⚠️\n\n<f>Aap</f> <b>{anime_name}</b> - <b>S{season_name}</b> - <b>Ep {ep_num}</b> <f>delete karne wale hain. Iske saare qualities delete ho jayenge.</f>\n\n<b><f>Are you sure?</f></b>",
        "admin_del_ep_success": "✅ <b><f>Success!</f></b>\n<f>Episode</f> '{ep_num}' <f>delete ho gaya hai.</f>",
        "admin_del_ep_error": "❌ <b><f>Error!</f></b> <f>Episode delete nahi ho paya.</f>",

        # === Admin: Update Photo ===
        "admin_update_photo_select_anime": "<f>Kaunse <b>Anime</b> ka poster update karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_update_photo_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_update_photo_select_target": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Aap iska <b>Main Poster</b> change karna chahte hain ya kisi <b>Season</b> ka?</f>",
        "admin_update_photo_get_poster": "<f>Aapne</f> <b>{target_name}</b> <f>select kiya hai.</f>\n\n<f>Ab naya <b>Poster (Photo)</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_update_photo_invalid": "<f>Ye photo nahi hai. Please ek photo bhejo ya</f> /cancel <f>karo.</f>",
        "admin_update_photo_save_error": "<f>Ye photo nahi hai. Please ek photo bhejo.</f>",
        "admin_update_photo_save_success_main": "✅ <b><f>Success!</f></b>\n{anime_name} <f>ka <b>Main Poster</b> change ho gaya hai.</f>",
        "admin_update_photo_save_success_season": "✅ <b><f>Success!</f></b>\n{anime_name} - <b>Season {season_name}</b> <f>ka poster change ho gaya hai.</f>",
        "admin_update_photo_save_error_db": "❌ <b><f>Error!</f></b> <f>Poster update nahi ho paya.</f>",

        # === Admin: Edit Anime ===
        "admin_edit_anime_select": "<f>Kaunsa <b>Anime</b> ka naam edit karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_edit_anime_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_edit_anime_get_name": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Ab iska <b>Naya Naam</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_edit_anime_save_exists": "⚠️ <b><f>Error!</f></b> <f>Naya naam</f> '{new_name}' <f>pehle se maujood hai. Koi doosra naam dein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_edit_anime_confirm": "<b><f>Confirm Karo:</f></b>\n\n<f>Purana Naam:</f> <code>{old_name}</code>\n<f>Naya Naam:</f> <code>{new_name}</code>\n\n<b><f>Are you sure?</f></b>",
        "admin_edit_anime_success": "✅ <b><f>Success!</f></b>\n<f>Anime</f> '{old_name}' <f>ka naam badal kar</f> '{new_name}' <f>ho gaya hai.</f>",
        "admin_edit_anime_error": "❌ <b><f>Error!</f></b> <f>Anime naam update nahi ho paya.</f>",
        
        # === Admin: Edit Season ===
        "admin_edit_season_select_anime": "<f>Kaunse <b>Anime</b> ka season edit karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_edit_season_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_edit_season_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>",
        "admin_edit_season_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Kaunsa <b>Season</b> ka naam edit karna hai?</f>",
        "admin_edit_season_get_name": "<f>Aapne</f> <b>{anime_name}</b> -> <b>Season {season_name}</b> <f>select kiya hai.</f>\n\n<f>Ab iska <b>Naya Naam/Number</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_edit_season_save_exists": "⚠️ <b><f>Error!</f></b> <f>Naya naam</f> '{new_name}' <f>is anime mein pehle se maujood hai. Koi doosra naam dein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_edit_season_confirm": "<b><f>Confirm Karo:</f></b>\n\n<f>Anime:</f> Code {anime_name}</code>\n<f>Purana Season:</f> <code>{old_name}</code>\n<f>Naya Season:</f> <code>{new_name}</code>\n\n<b><f>Are you sure?</f></b>",
        "admin_edit_season_success": "✅ <b><f>Success!</f></b>\n<f>Season</f> '{old_name}' <f>ka naam badal kar</f> '{new_name}' <f>ho gaya hai.</f>",
        "admin_edit_season_error": "❌ <b><f>Error!</f></b> <f>Season naam update nahi ho paya.</f>",

        # === Admin: Edit Episode ===
        "admin_edit_ep_select_anime": "<f>Kaunse <b>Anime</b> ka episode edit karna hai?</f>\n\n<b><f>Recently Updated First</f></b> <f>(Sabse naya pehle):</f>\n<f>(Page {page})</f>", # NAYA: Text change
        "admin_edit_ep_no_anime": "❌ <f>Error: Abhi koi anime add nahi hua hai.</f>",
        "admin_edit_ep_no_season": "❌ <b><f>Error!</f></b> '{anime_name}' <f>mein koi season nahi hai.</f>",
        "admin_edit_ep_select_season": "<f>Aapne</f> <b>{anime_name}</b> <f>select kiya hai.</f>\n\n<f>Kaunsa <b>Season</b> select karna hai?</f>",
        "admin_edit_ep_no_episode": "❌ <b><f>Error!</f></b> '{anime_name}' - Season {season_name} <f>mein koi episode nahi hai.</f>",
        "admin_edit_ep_select_episode": "<f>Aapne</f> <b>Season {season_name}</b> <f>select kiya hai.</f>\n\n<f>Kaunsa <b>Episode</b> ka number edit karna hai?</f>",
        "admin_edit_ep_get_num": "<f>Aapne</f> <b>{anime_name}</b> -> <b>S{season_name}</b> -> <b>Ep {ep_num}</b> <f>select kiya hai.</f>\n\n<f>Ab iska <b>Naya Number</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_edit_ep_save_exists": "⚠️ <b><f>Error!</f></b> <f>Naya number</f> '{new_num}' <f>is season mein pehle se maujood hai. Koi doosra number dein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_edit_ep_confirm": "<b><f>Confirm Karo:</f></b>\n\n<f>Anime:</f> <code>{anime_name}</code>\n<f>Season:</f> <code>{season_name}</code>\n<f>Purana Episode:</f> <code>{old_num}</code>\n<f>Naya Episode:</f> <code>{new_num}</code>\n\n<b><f>Are you sure?</f></b>",
        "admin_edit_ep_success": "✅ <b><f>Success!</f></b>\n<f>Episode</f> '{old_num}' <f>ka number badal kar</f> '{new_num}' <f>ho gaya hai.</f>",
        "admin_edit_ep_error": "❌ <b><f>Error!</f></b> <f>Episode number update nahi ho paya.</f>",

        # === Admin: Admin Settings (Co-Admin, Custom Post) ===
        "admin_menu_admin_settings": "🛠️ <b><f>Admin Settings</f></b> 🛠️\n\n<f>Yahan aap Co-Admins aur doosri advanced settings manage kar sakte hain.</f>",
        "admin_co_admin_add_start": "<f>Naye Co-Admin ki <b>Telegram User ID</b> bhejein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_co_admin_add_invalid_id": "<f>Yeh valid User ID nahi hai. Please sirf number bhejein.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_co_admin_add_is_main": "<f>Aap Main Admin hain, khud ko add nahi kar sakte.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_co_admin_add_exists": "<f>User</f> <code>{user_id}</code> <f>pehle se Co-Admin hai.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_co_admin_add_confirm": "<f>Aap user ID</f> Code {user_id}</code> <f>ko <b>Co-Admin</b> banane wale hain.</f>\n\n<f>Woh content add, remove, aur post generate kar payenge.</f>\n\n<b><f>Are you sure?</f></b>",
        "admin_co_admin_add_success": "✅ <b><f>Success!</f></b>\n<f>User ID</f> <code>{user_id}</code> <f>ab Co-Admin hai.</f>",
        "admin_co_admin_add_error": "❌ <b><f>Error!</f></b> <f>Co-Admin add nahi ho paya.</f>",
        "admin_co_admin_remove_no_co": "<f>Abhi koi Co-Admin nahi hai.</f>",
        "admin_co_admin_remove_start": "<f>Kis Co-Admin ko remove karna hai?</f>",
        "admin_co_admin_remove_confirm": "<f>Aap Co-Admin ID</f> <code>{user_id}</code> <f>ko remove karne wale hain.</f>\n\n<b><f>Are you sure?</f></b>",
        "admin_co_admin_remove_success": "✅ <b><f>Success!</f></b>\n<f>Co-Admin ID</f> <code>{user_id}</code> <f>remove ho gaya hai.</f>",
        "admin_co_admin_remove_error": "❌ <b><f>Error!</f></b> <f>Co-Admin remove nahi ho paya.</f>",
        "admin_co_admin_list_none": "<f>Abhi koi Co-Admin nahi hai.</f>",
        "admin_co_admin_list_header": "<b><f>List of Co-Admins:</f></b>\n", # <pre> hata diya
        "admin_custom_post_start": "🚀 <b><f>Custom Post Generator</f></b>\n\n<f>Ab uss <b>Channel ka @username</b> ya <b>Group/Channel ki Chat ID</b> bhejo jahaan ye post karna hai.</f>\n<f>(Example: @MyAnimeChannel ya -100123456789)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_custom_post_get_chat": "<f>Chat ID set! Ab post ka <b>Poster (Photo)</b> bhejo.</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_custom_post_get_poster_error": "<f>Ye photo nahi hai. Please ek photo bhejo.</f>",
        "admin_custom_post_get_poster": "<f>Poster set! Ab post ka <b>Caption</b> (text) bhejo.</f>\n<f>(Aap</f> <code>&lt;f&gt;...&lt;/f&gt;</code> <f>tags use kar sakte hain)</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_custom_post_get_caption": "<f>Caption set! Ab custom button ka <b>Text</b> bhejo.</f>\n<f>(Example: 'Join Now')</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_custom_post_get_btn_text": "<f>Button text set! Ab button ka <b>URL (Link)</b> bhejo.</f>\n<f>(Example: 'https://t.me/mychannel')</f>\n\n/cancel - <f>Cancel.</f>",
        "admin_custom_post_confirm": "<b><f>--- PREVIEW ---</f></b>\n\n{caption}\n\n<b><f>Target:</f></b> <code>{chat_id}</code>",
        "admin_custom_post_success": "✅ <b><f>Success!</f></b>\n<f>Post ko</f> '{chat_id}' <f>par bhej diya gaya hai.</f>",
        "admin_custom_post_error": "❌ <b><f>Error!</f></b>\n<f>Post</f> '{chat_id}' <f>par nahi bhej paya.</f>\n<f>Error:</f> {e}",
        
        # === Admin: Bot Appearance Menu (NAYA) ===
        "admin_menu_appearance": "🎨 <b><f>Bot Appearance</f></b> 🎨\n\n<f>Bot ke messages ka look aur feel yahaan change karein.</f>\n\n<f>Current Font:</f> <b>{font}</b>\n<f>Current Style:</f> <b>{style}</b>",
        "admin_appearance_select_font": "<f>Kaunsa font select karna hai?</f>\n\n<f>Current:</f> <b>{font}</b>",
        "admin_appearance_select_style": "<f>Kaunsa style select karna hai?</f>\n\n<f>Current:</f> <b>{style}</b>",
        "admin_appearance_set_font_success": "✅ <b><f>Success!</f></b> <f>Font ko</f> <b>{font}</b> <f>par set kar diya gaya hai.</f>",
        "admin_appearance_set_style_success": "✅ <b><f>Success!</f></b> <f>Style ko</f> <b>{style}</b> <f>par set kar diya gaya hai.</f>",
    }
# --- Config Helper (MAJOR REFACTOR) ---
async def get_config():
    """Database se bot config fetch karega"""
    config = config_collection.find_one({"_id": "bot_config"})
    
    default_messages = await get_default_messages()

    if not config:
        default_config = {
            "_id": "bot_config", "donate_qr_id": None, 
            "links": {"backup": None, "download": None, "help": None}, # NAYA: Help link
            "user_menu_photo_id": None, # NAYA: User Menu Photo
            "delete_seconds": 300, 
            "messages": default_messages,
            "co_admins": [],
            "appearance": {"font": "default", "style": "normal"}
        }
        config_collection.insert_one(default_config)
        return default_config
    
    # --- Compatibility aur Migration ---
    needs_update = False
    
    if "delete_seconds" not in config: 
        config["delete_seconds"] = 300 
        needs_update = True
    if "co_admins" not in config:
        config["co_admins"] = []
        needs_update = True
    if "appearance" not in config:
        config["appearance"] = {"font": "default", "style": "normal"}
        needs_update = True
    
    if "messages" not in config: 
        config["messages"] = {}
        needs_update = True
        
    if "links" not in config: # NAYA: Links check
        config["links"] = {"backup": None, "download": None, "help": None}
        needs_update = True
    elif "help" not in config["links"]: # NAYA: Help link check
        config["links"]["help"] = None
        needs_update = True

    # Check karo ki saare default messages config me hain ya nahi
    for key, value in default_messages.items():
        if key not in config["messages"]:
            config["messages"][key] = value
            needs_update = True
    
    # Purane messages remove karo
    messages_to_remove = [
        "user_sub_qr_error", "user_sub_qr_text", "user_sub_ss_prompt", "user_sub_ss_not_photo",
        "user_sub_ss_error", "sub_pending", "sub_approved", "sub_rejected", "user_sub_removed",
        "user_already_subscribed", "user_dl_unsubscribed_alert", "user_dl_unsubscribed_dm",
        "user_dl_checking_sub", "gen_link_caption_anime", "gen_link_caption_ep", "gen_link_caption_season"
    ]

    keys_to_actually_remove = []
    if "messages" in config:
        for key in messages_to_remove:
            if key in config["messages"]:
                keys_to_actually_remove.append(key)
                needs_update = True
    
    if keys_to_actually_remove:
        for key in keys_to_actually_remove:
            del config["messages"][key] 

    if needs_update:
        update_set = {
            "messages": config["messages"], 
            "user_menu_photo_id": config.get("user_menu_photo_id"), # NAYA
            "delete_seconds": config.get("delete_seconds", 300),
            "co_admins": config.get("co_admins", []),
            "appearance": config.get("appearance", {"font": "default", "style": "normal"}),
            "links": config.get("links", {"backup": None, "download": None, "help": None}) # NAYA
        }
        
        config_collection.update_one(
            {"_id": "bot_config"}, 
            {"$set": update_set}
        )
        
    if "donate" in config.get("links", {}): 
        config_collection.update_one({"_id": "bot_config"}, {"$unset": {"links.donate": ""}})
    
    if "links" in config:
        if "support" in config["links"]:
            config_collection.update_one({"_id": "bot_config"}, {"$unset": {"links.support": ""}})
        if "download" not in config["links"]:
            if "dl_link" in config["links"]: 
                 config_collection.update_one({"_id": "bot_config"}, {"$rename": {"links.dl_link": "links.download"}})
            else:
                 config_collection.update_one({"_id": "bot_config"}, {"$set": {"links.download": None}})

    return config

# NAYA FIX: 2x2 Grid Helper
def build_grid_keyboard(buttons, items_per_row=2):
    keyboard = []
    row = []
    for button in buttons:
        row.append(button)
        if len(row) == items_per_row:
            keyboard.append(row)
            row = []
    if row: 
        keyboard.append(row)
    return keyboard

# NAYA (v10): Pagination Helper
async def build_paginated_keyboard(
    collection, 
    page: int, 
    page_callback_prefix: str, 
    item_callback_prefix: str,
    back_callback: str,
    filter_query: dict = None
):
    if filter_query is None:
        filter_query = {}
        
    skip = page * ITEMS_PER_PAGE
    total_items = collection.count_documents(filter_query)
    
    # NAYA: Sort by last_modified (descending)
    items = list(collection.find(filter_query).sort("last_modified", DESCENDING).skip(skip).limit(ITEMS_PER_PAGE))
    
    if not items and page == 0:
        return None, InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_callback)]])

    buttons = []
    for item in items:
        if "name" in item:
            buttons.append(InlineKeyboardButton(item['name'], callback_data=f"{item_callback_prefix}{item['name']}"))
        elif "first_name" in item:
            user_id = item['_id']
            first_name = item.get('first_name', f"ID: {user_id}")
            buttons.append(InlineKeyboardButton(first_name, callback_data=f"{item_callback_prefix}{user_id}"))

    keyboard = build_grid_keyboard(buttons, items_per_row=2)
    
    page_buttons = []
    if page > 0:
        page_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{page_callback_prefix}{page - 1}"))
    if (page + 1) * ITEMS_PER_PAGE < total_items:
        page_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{page_callback_prefix}{page + 1}"))
        
    if page_buttons:
        keyboard.append(page_buttons)
        
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=back_callback)])
    
    return items, InlineKeyboardMarkup(keyboard)
# --- Job Queue Callbacks ---
async def send_donate_thank_you(context: ContextTypes.DEFAULT_TYPE):
    """1 min baad thank you message bhejega"""
    job = context.job
    try:
        msg = await format_message(context, "donate_thanks")
        await context.bot.send_message(chat_id=job.chat_id, text=msg, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.warning(f"Thank you message bhejte waqt error: {e}")

# FIX: Naya Auto-Delete Function (asyncio)
async def delete_message_later(bot, chat_id: int, message_id: int, seconds: int):
    """asyncio.sleep ka use karke message delete karega"""
    try:
        await asyncio.sleep(seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Auto-deleted message {message_id} for user {chat_id} (asyncio.sleep)")
    except Exception as e:
        logger.warning(f"Message (asyncio.sleep) delete karne me error: {e}")

# NAYA: Anime ka timestamp update karne ke liye helper
async def _update_anime_timestamp(anime_name: str):
    """
    Jab bhi koi anime/season/ep add/edit/delete hoga,
    toh iska 'last_modified' timestamp update karega.
    """
    try:
        animes_collection.update_one(
            {"name": anime_name},
            {"$set": {"last_modified": datetime.now()}}
        )
        logger.info(f"'{anime_name}' ka timestamp update ho gaya.")
    except Exception as e:
        logger.error(f"'{anime_name}' ka timestamp update karne me error: {e}")


# --- Conversation States ---
# NEW (SAHI) CODE
(A_GET_NAME, A_GET_POSTER, A_GET_DESC, A_CONFIRM) = range(4) # <-- YEH LINE MISS HO GAYI THI
(S_GET_ANIME, S_GET_NUMBER, S_GET_POSTER, S_GET_DESC, S_CONFIRM, S_ASK_MORE) = range(4, 10) # NAYA: S_ASK_MORE
(E_GET_ANIME, E_GET_SEASON, E_GET_NUMBER, E_GET_480P, E_GET_720P, E_GET_1080P, E_GET_4K, E_ASK_MORE) = range(10, 18) # 9->10, 17->18
(CD_GET_QR,) = range(18, 19) # 17->18, 18->19
(CL_GET_LINK,) = range(20, 21) # 19->20, 20->21
(PG_MENU, PG_GET_ANIME, PG_GET_SEASON, PG_GET_EPISODE, PG_GET_SHORT_LINK, PG_GET_CHAT) = range(23, 29) # 22->23, 28->29
(DA_GET_ANIME, DA_CONFIRM) = range(29, 31) # 28->29, 30->31
(DS_GET_ANIME, DS_GET_SEASON, DS_CONFIRM) = range(31, 34) # 30->31, 33->34
(DE_GET_ANIME, DE_GET_SEASON, DE_GET_EPISODE, DE_CONFIRM) = range(34, 38) # 33->34, 37->38
(M_GET_DONATE_THANKS, M_GET_FILE_WARNING) = range(40, 42) # 39->40, 41->42
(CS_GET_DELETE_TIME,) = range(45, 46) # 44->45, 45->46
(UP_GET_ANIME, UP_GET_TARGET, UP_GET_POSTER) = range(48, 51) # 47->48, 50->51
(CA_GET_ID, CA_CONFIRM) = range(51, 53) # 50->51, 52->53
(CR_GET_ID, CR_CONFIRM) = range(53, 55) # 52->53, 54->55
(CPOST_GET_CHAT, CPOST_GET_POSTER, CPOST_GET_CAPTION, CPOST_GET_BTN_TEXT, CPOST_GET_BTN_URL, CPOST_CONFIRM) = range(55, 61) # 54->55, 60->61
(EA_GET_ANIME, EA_GET_NEW_NAME, EA_CONFIRM) = range(61, 64) # 60->61, 63->64
(ES_GET_ANIME, ES_GET_SEASON, ES_GET_NEW_NAME, ES_CONFIRM) = range(64, 68) # 63->64, 67->68
(EE_GET_ANIME, EE_GET_SEASON, EE_GET_EPISODE, EE_GET_NEW_NUM, EE_CONFIRM) = range(68, 73) # 67->68, 72->73
(M_MENU_MAIN, M_MENU_DL, M_MENU_GEN, M_MENU_POSTGEN, M_GET_MSG, M_MENU_ADMIN) = range(73, 79) # 72->73, 78->79
(GL_MENU, GL_GET_ANIME, GL_GET_SEASON, GL_GET_EPISODE) = range(79, 83) # 78->79, 82->83
# NAYA: Bot Appearance States
(AP_MENU, AP_SET_FONT, AP_SET_STYLE) = range(83, 86) # 82->83, 85->86
(CS_GET_MENU_PHOTO,) = range(86, 87) # 85->86, 86->87


# --- NAYA: Global Cancel Function ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the current conversation."""
    user = update.effective_user
    logger.info(f"User {user.id} ne operation cancel kiya.")
    if context.user_data:
        context.user_data.clear()
    
    reply_text = await format_message(context, "admin_cancel")
    
    try:
        if update.message:
            await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            query = update.callback_query
            if not query.data.startswith("admin_menu_") and not query.data == "admin_menu":
                await query.answer("Canceled!")
                await query.edit_message_text(reply_text, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
                logger.warning(f"Cancel me edit nahi kar paya: {e}")
                reply_text = await format_message(context, "admin_cancel_error_edit", {"e": e})
                await query.edit_message_text(reply_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Cancel me error: {e}")
        reply_text = await format_message(context, "admin_cancel_error_general", {"e": e})
        await query.edit_message_text(reply_text, parse_mode=ParseMode.HTML)

    if await is_co_admin(user.id):
        await asyncio.sleep(0.1) 
        await admin_command(update, context, from_callback=(update.callback_query is not None))
    
    return ConversationHandler.END

# NAYA: 'Add Episode' flow ke liye special back/cancel
async def cancel_add_episode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add Episode flow ko cancel karke Add Content menu par bhejega."""
    if context.user_data:
        context.user_data.clear()
    
    await cancel(update, context) # Pehle normal cancel message dikhao
    await asyncio.sleep(0.1)
    
    if update.callback_query:
        await add_content_menu(update, context) # Phir Add Content menu dikhao
    
    return ConversationHandler.END

# NAYA: 'Add Season' flow ke liye special back/cancel
async def cancel_add_season(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add Season flow ko cancel karke Add Content menu par bhejega."""
    if context.user_data:
        context.user_data.clear()
    
    await cancel(update, context) # Pehle normal cancel message dikhao
    await asyncio.sleep(0.1)
    
    if update.callback_query:
        await add_content_menu(update, context) # Phir Add Content menu dikhao
    
    return ConversationHandler.END

# --- Common Conversation Fallbacks ---
async def back_to_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_command(update, context, from_callback=True)
    return ConversationHandler.END

async def back_to_add_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if context.user_data:
        context.user_data.clear() # NAYA: State clear karo
    await add_content_menu(update, context)
    return ConversationHandler.END

async def back_to_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await manage_content_menu(update, context)
    return ConversationHandler.END

async def back_to_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_content_menu(update, context)
    return ConversationHandler.END

async def back_to_sub_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_command(update, context, from_callback=True) 
    return ConversationHandler.END

async def back_to_donate_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await donate_settings_menu(update, context)
    return ConversationHandler.END

async def back_to_links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await other_links_menu(update, context)
    return ConversationHandler.END

async def back_to_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_user_menu(update, context, from_callback=True) 
    return ConversationHandler.END
    
async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} ne /user dabaya.")
    await show_user_menu(update, context)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"User {update.effective_user.id} ne /menu dabaya (Admin Panel).")
    await admin_command(update, context)
    
async def back_to_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await bot_messages_menu(update, context)
    return ConversationHandler.END

async def back_to_admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_settings_menu(update, context)
    return ConversationHandler.END

# NAYA: Appearance Menu Fallback
async def back_to_appearance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await appearance_menu_start(update, context)
    return AP_MENU
# --- Admin Conversations (Add, Delete, etc.) ---
# --- Conversation: Add Anime ---
async def add_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = await format_message(context, "admin_add_anime_start")
    await query.edit_message_text(text, parse_mode=ParseMode.HTML) 
    return A_GET_NAME

async def get_anime_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime_name'] = update.message.text
    text = await format_message(context, "admin_add_anime_get_name")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return A_GET_POSTER

async def get_anime_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        text = await format_message(context, "admin_add_anime_get_poster_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return A_GET_POSTER 
    context.user_data['anime_poster_id'] = update.message.photo[-1].file_id
    text = await format_message(context, "admin_add_anime_get_poster")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return A_GET_DESC

async def get_anime_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime_desc'] = update.message.text
    return await confirm_anime_details(update, context)

async def skip_anime_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime_desc'] = None 
    return await confirm_anime_details(update, context)

async def confirm_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data['anime_name']
    poster_id = context.user_data['anime_poster_id']
    desc = context.user_data['anime_desc']
    
    caption = await format_message(context, "admin_add_anime_confirm", {
        "name": name, 
        "description": desc if desc else ''
    })
    keyboard = [[InlineKeyboardButton("✅ Save", callback_data="save_anime")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    
    if update.message:
        try:
            await update.message.reply_photo(photo=poster_id, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Confirm anime details me error: {e}")
            text = await format_message(context, "admin_add_anime_confirm_error")
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            return A_GET_DESC 
    return A_CONFIRM

async def save_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    try:
        name = context.user_data['anime_name']
        if animes_collection.find_one({"name": name}):
            caption = await format_message(context, "admin_add_anime_save_exists", {"name": name})
            await query.edit_message_caption(caption=caption, parse_mode=ParseMode.HTML)
            await asyncio.sleep(3)
            await add_content_menu(update, context)
            return ConversationHandler.END
        
        anime_document = {
            "name": name, 
            "poster_id": context.user_data['anime_poster_id'], 
            "description": context.user_data['anime_desc'], 
            "seasons": {},
            "created_at": datetime.now(),
            "last_modified": datetime.now() # NAYA: Timestamp
        }
        animes_collection.insert_one(anime_document)
        caption = await format_message(context, "admin_add_anime_save_success", {"name": name})
        await query.edit_message_caption(caption=caption, parse_mode=ParseMode.HTML)
        await asyncio.sleep(3)
        await add_content_menu(update, context)
    except Exception as e:
        logger.error(f"Anime save karne me error: {e}")
        caption = await format_message(context, "admin_add_anime_save_error")
        await query.edit_message_caption(caption=caption, parse_mode=ParseMode.HTML)
    context.user_data.clear() 
    return ConversationHandler.END

# --- Conversation: Add Season ---
async def add_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await add_season_show_anime_list(update, context, page=0)

async def add_season_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("addseason_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page 
    
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="addseason_page_",
        item_callback_prefix="season_anime_",
        back_callback="back_to_add_content"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_add_season_no_anime")
    else:
        text = await format_message(context, "admin_add_season_select_anime", {"page": page + 1}) # NAYA: Text DB se aayega
    
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return S_GET_ANIME

async def get_anime_for_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("season_anime_", "")
    context.user_data['anime_name'] = anime_name
    
    # --- NAYA LOGIC (Last Season Check) START ---
    anime_doc = animes_collection.find_one({"name": anime_name})
    if not anime_doc:
        text = await format_message(context, "admin_add_season_get_number_error", {"anime_name": anime_name})
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    
    seasons = anime_doc.get("seasons", {})
    season_keys = list(seasons.keys()) # Yahan _ keys filter karne ki zaroorat nahi
    
    if not season_keys:
        text = await format_message(context, "admin_add_season_get_anime_no_last", {
            "anime_name": anime_name
        })
    else:
        try:
            # Seasons ko numerically sort karo
            sorted_seasons = sorted(season_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            last_season_name = sorted_seasons[-1]
            text = await format_message(context, "admin_add_season_get_anime_with_last", {
                "anime_name": anime_name,
                "last_season_name": last_season_name
            })
        except Exception as e:
            logger.warning(f"Last season find karne me error: {e}")
            # Error hone par fallback
            text = await format_message(context, "admin_add_season_get_anime_no_last", {
                "anime_name": anime_name
            })
    # --- NAYA LOGIC END ---

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return S_GET_NUMBER

async def get_season_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    season_name = update.message.text
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if not anime_doc:
            text = await format_message(context, "admin_add_season_get_number_error", {"anime_name": anime_name})
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            return ConversationHandler.END
            
    if season_name in anime_doc.get("seasons", {}):
        text = await format_message(context, "admin_add_season_get_number_exists", {
            "anime_name": anime_name, 
            "season_name": season_name
        })
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return S_GET_NUMBER

    text = await format_message(context, "admin_add_season_get_poster_prompt", {"season_name": season_name})
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return S_GET_POSTER

async def get_season_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        text = await format_message(context, "admin_add_season_get_poster_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return S_GET_POSTER
    context.user_data['season_poster_id'] = update.message.photo[-1].file_id
    text = await format_message(context, "admin_add_season_get_desc_prompt")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return S_GET_DESC

async def skip_season_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season_poster_id'] = None
    text = await format_message(context, "admin_add_season_skip_poster")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return S_GET_DESC

async def get_season_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season_desc'] = update.message.text
    return await confirm_season_details(update, context)

async def skip_season_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season_desc'] = None
    return await confirm_season_details(update, context)

async def confirm_season_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    season_poster_id = context.user_data.get('season_poster_id')
    season_desc = context.user_data.get('season_desc') 
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    poster_id_to_show = season_poster_id or anime_doc.get('poster_id')
    
    caption = await format_message(context, "admin_add_season_confirm", {
        "anime_name": anime_name,
        "season_name": season_name,
        "season_desc": season_desc or 'N/A'
    })
    keyboard = [[InlineKeyboardButton("✅ Haan, Save Karo", callback_data="save_season")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    
    await update.message.reply_photo(
        photo=poster_id_to_show,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML
    )
    return S_CONFIRM

async def save_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # "Save" button press ko acknowledge karo
    
    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        season_poster_id = context.user_data.get('season_poster_id')
        season_desc = context.user_data.get('season_desc') 
        
        season_data = {} 
        if season_poster_id:
            season_data["_poster_id"] = season_poster_id 
        if season_desc:
            season_data["_description"] = season_desc 
        
        # 1. Database update
        animes_collection.update_one(
            {"name": anime_name}, 
            {"$set": {
                f"seasons.{season_name}": season_data,
                "last_modified": datetime.now()
            }} 
        )
        
        # 2. "Yes/No" message format karo
        text = await format_message(context, "admin_add_season_ask_more", {
            "anime_name": anime_name,
            "season_name": season_name
        })
        keyboard = [
            [InlineKeyboardButton("✅ Yes (Add More)", callback_data="add_season_more_yes")],
            [InlineKeyboardButton("🚫 No (Back to Menu)", callback_data="add_season_more_no")]
        ]

        # 3. === NAYA FIX: Purana photo message delete karo ===
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"Purana photo message delete nahi kar paya: {e}")
            # Agar delete fail ho, toh purana (buggy) tareeka try karo
            await query.edit_message_caption(caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
            try:
                await query.message.delete_reply_markup() 
                await query.edit_message_media(None)
            except: pass
            return S_ASK_MORE

        # 4. === NAYA FIX: Naya text message bhejo ===
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        
        # 5. Agle state par jao
        return S_ASK_MORE 

    except Exception as e:
        logger.error(f"Season save karne me error: {e}")
        caption = await format_message(context, "admin_add_season_save_error")
        
        # Error aane par, purane photo message par hi error dikhao
        try:
            await query.edit_message_caption(caption=caption, parse_mode=ParseMode.HTML, reply_markup=None)
        except Exception as e2:
            logger.error(f"Error message bhi nahi dikha paya: {e2}")
            # Fallback
            await context.bot.send_message(chat_id=query.from_user.id, text=caption, parse_mode=ParseMode.HTML)

        # Conversation ko end karo
        context.user_data.clear()
        await asyncio.sleep(3) 
        await add_content_menu(update, context) 
        return ConversationHandler.END

    # === FIX 3: Woh 2 lines yahan se delete kar di hain ===

# NAYA: "Add More Seasons" flow
async def add_more_seasons_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User ne 'Yes (Add More)' dabaya. Agle season ka number maango.
    """
    query = update.callback_query
    await query.answer()
    
    last_season_name = context.user_data['season_name']
    anime_name = context.user_data['anime_name']
    
    text = await format_message(context, "admin_add_season_next_prompt", {
        "season_name": last_season_name,
        "anime_name": anime_name,
    })

    # Sirf 'season_name' aur related data ko context se clear karo
    context.user_data.pop('season_name', None)
    context.user_data.pop('season_poster_id', None)
    context.user_data.pop('season_desc', None)
    
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return S_GET_NUMBER # Wapas season number maangne wale state par bhej do

async def add_more_seasons_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User ne 'No (Back to Menu)' dabaya. Conversation end karo.
    """
    query = update.callback_query
    await query.answer()
    
    # Poora context clear karo
    context.user_data.clear()
    
    # Wapas 'Add Content' menu par bhej do
    await add_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Add Episode (Multi-Quality) ---
async def add_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await add_episode_show_anime_list(update, context, page=0)

async def add_episode_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("addep_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page 
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="addep_page_",
        item_callback_prefix="ep_anime_",
        back_callback="back_to_add_content"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_add_ep_no_anime")
    else:
        text = await format_message(context, "admin_add_ep_select_anime", {"page": page + 1}) # NAYA: Text DB se aayega

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return E_GET_ANIME

async def get_anime_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    
    if not seasons:
        text = await format_message(context, "admin_add_ep_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1) 
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"addep_page_{current_page}")])
    
    text = await format_message(context, "admin_add_ep_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return E_GET_SEASON

async def get_season_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("ep_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']

    # NEW CODE
    # NAYA: Last episode number check karo
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        text = await format_message(context, "admin_add_ep_get_season_no_last", {"season_name": season_name})
    else:
        # Last episode (numerically) find karo
        try:
            sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            last_ep_num = sorted_eps[-1]
            text = await format_message(context, "admin_add_ep_get_season_with_last", {
                "season_name": season_name,
                "last_ep_num": last_ep_num
            })
        except Exception as e:
            logger.warning(f"Last episode find karne me error (shayad non-numeric): {e}")
            text = await format_message(context, "admin_add_ep_get_season_no_last", {"season_name": season_name})

    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return E_GET_NUMBER

async def _save_episode_file_helper(update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
    file_id = None
    if update.message.video: file_id = update.message.video.file_id
    elif update.message.document and (update.message.document.mime_type and update.message.document.mime_type.startswith('video')): file_id = update.message.document.file_id
    
    if not file_id:
        if update.message.text and update.message.text.startswith('/'):
            return False 
        text = await format_message(context, "admin_add_ep_helper_invalid")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return False 

    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        ep_num = context.user_data['ep_num']
        
        dot_notation_key = f"seasons.{season_name}.{ep_num}.{quality}"
        
        # NAYA: File save karne ke saath timestamp update karo
        animes_collection.update_one(
            {"name": anime_name},
            {"$set": {
                dot_notation_key: file_id,
                "last_modified": datetime.now()
            }}
        )
        logger.info(f"Naya episode save ho gaya: {anime_name} S{season_name} E{ep_num} {quality}")
        
        text = await format_message(context, "admin_add_ep_helper_success", {"quality": quality})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        logger.error(f"Episode file save karne me error: {e}")
        text = await format_message(context, "admin_add_ep_helper_error", {"quality": quality})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return False

async def get_episode_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_num'] = update.message.text
    
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    ep_num = context.user_data['ep_num']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    existing_eps = anime_doc.get("seasons", {}).get(season_name, {})
    if ep_num in existing_eps:
        text = await format_message(context, "admin_add_ep_get_number_exists", {
            "anime_name": anime_name,
            "season_name": season_name,
            "ep_num": ep_num
        })
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return E_GET_NUMBER

    text = await format_message(context, "admin_add_ep_get_number", {"ep_num": ep_num})
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_480P

async def get_480p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _save_episode_file_helper(update, context, "480p"):
        return E_GET_480P 
    text = await format_message(context, "admin_add_ep_get_480p")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_720P

async def skip_480p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await format_message(context, "admin_add_ep_skip_480p")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_720P

async def get_720p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _save_episode_file_helper(update, context, "720p"):
        return E_GET_720P 
    text = await format_message(context, "admin_add_ep_get_720p")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_1080P

async def skip_720p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await format_message(context, "admin_add_ep_skip_720p")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_1080P

async def get_1080p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _save_episode_file_helper(update, context, "1080p"):
        return E_GET_1080P 
    text = await format_message(context, "admin_add_ep_get_1080p")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_4K

async def skip_1080p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await format_message(context, "admin_add_ep_skip_1080p")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return E_GET_4K

async def get_4k_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _save_episode_file_helper(update, context, "4K"):
        text = await format_message(context, "admin_add_ep_get_4k_success")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
        return E_GET_4K 
    
    return await ask_add_more_episodes(update, context) # NAYA

async def skip_4k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await format_message(context, "admin_add_ep_skip_4k")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    return await ask_add_more_episodes(update, context) # NAYA

# NAYA: "Add More Episodes" flow
async def ask_add_more_episodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ek episode save hone ke baad poochhega ki aur add karna hai ya nahi.
    """
    ep_num = context.user_data['ep_num']
    season_name = context.user_data['season_name']
    
    text = await format_message(context, "admin_add_ep_ask_more", {
        "ep_num": ep_num,
        "season_name": season_name
    })
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes (Add More)", callback_data="add_ep_more_yes")],
        [InlineKeyboardButton("🚫 No (Back to Menu)", callback_data="add_ep_more_no")]
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return E_ASK_MORE

async def add_more_episodes_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User ne 'Yes (Add More)' dabaya. Agle episode ka number maango.
    """
    query = update.callback_query
    await query.answer()
    
    last_ep_num = context.user_data['ep_num']
    season_name = context.user_data['season_name']
    
    # NAYA: Agle episode number ka suggestion
    try:
        next_ep_num = str(int(last_ep_num) + 1)
        text = await format_message(context, "admin_add_ep_next_prompt", {
            "ep_num": last_ep_num,
            "season_name": season_name,
            "next_ep_num": next_ep_num
        })
    except ValueError:
        # Agar pichla number 'Movie' ya 'OVA' jaisa tha
        text = await format_message(context, "admin_add_ep_next_prompt_no_suggestion", {
            "ep_num": last_ep_num,
            "season_name": season_name
        })

    # Sirf 'ep_num' ko context se clear karo, taaki naya set ho sake
    context.user_data.pop('ep_num', None)
    
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return E_GET_NUMBER # Wapas episode number maangne wale state par bhej do

async def add_more_episodes_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    User ne 'No (Back to Menu)' dabaya. Conversation end karo.
    """
    query = update.callback_query
    await query.answer()
    
    # Poora context clear karo
    context.user_data.clear()
    
    # Wapas 'Add Content' menu par bhej do
    await add_content_menu(update, context)
    return ConversationHandler.END


# --- Conversation: Set Auto-Delete Time ---
async def set_delete_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = await get_config()
    current_seconds = config.get("delete_seconds", 300) 
    current_minutes = current_seconds // 60
    
    text = await format_message(context, "admin_set_delete_time_start", {
        "current_minutes": current_minutes,
        "current_seconds": current_seconds
    })
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
    return CS_GET_DELETE_TIME

async def set_delete_time_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        seconds = int(update.message.text)
        if seconds <= 10:
                text = await format_message(context, "admin_set_delete_time_low")
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
                return CS_GET_DELETE_TIME
                
        config_collection.update_one({"_id": "bot_config"}, {"$set": {"delete_seconds": seconds}}, upsert=True)
        logger.info(f"Auto-delete time update ho gaya: {seconds} seconds")
        
        text = await format_message(context, "admin_set_delete_time_success", {
            "seconds": seconds,
            "minutes": seconds // 60
        })
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        await admin_command(update, context, from_callback=False) 
        return ConversationHandler.END
        
    except ValueError:
        text = await format_message(context, "admin_set_delete_time_nan")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CS_GET_DELETE_TIME
    except Exception as e:
        logger.error(f"Delete time save karte waqt error: {e}")
        text = await format_message(context, "admin_set_delete_time_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        context.user_data.clear()
        return ConversationHandler.END

# --- Conversation: Set Donate QR ---
async def set_donate_qr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = await format_message(context, "admin_set_donate_qr_start")
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_donate_settings")]]))
    return CD_GET_QR

async def set_donate_qr_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        text = await format_message(context, "admin_set_donate_qr_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CD_GET_QR
    qr_file_id = update.message.photo[-1].file_id
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"donate_qr_id": qr_file_id}}, upsert=True)
    logger.info(f"Donate QR code update ho gaya.")
    text = await format_message(context, "admin_set_donate_qr_success")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    await donate_settings_menu(update, context)
    return ConversationHandler.END
# --- Conversation: Set Links ---
async def set_links_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    link_type = query.data.replace("admin_set_", "") 
    
    if link_type == "backup_link":
        context.user_data['link_type'] = "backup"
        text = await format_message(context, "admin_set_link_backup")
        back_button = "back_to_links"
    elif link_type == "download_link":
        context.user_data['link_type'] = "download"
        text = await format_message(context, "admin_set_link_download")
        back_button = "back_to_links"
    elif link_type == "help_link": # NAYA
        context.user_data['link_type'] = "help"
        text = await format_message(context, "admin_set_link_help")
        back_button = "back_to_links"
    else:
        text = await format_message(context, "admin_set_link_invalid")
        await query.answer(text, show_alert=True)
        return ConversationHandler.END

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_button)]]))
    return CL_GET_LINK 

async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link_url = update.message.text
    link_type = context.user_data['link_type']
    config_collection.update_one({"_id": "bot_config"}, {"$set": {f"links.{link_type}": link_url}}, upsert=True)
    logger.info(f"{link_type} link update ho gaya: {link_url}")
    text = await format_message(context, "admin_set_link_success", {"link_type": link_type})
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    await other_links_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END

async def skip_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link_type = context.user_data['link_type']
    config_collection.update_one({"_id": "bot_config"}, {"$set": {f"links.{link_type}": None}}, upsert=True)
    logger.info(f"{link_type} link skip kiya (None set).")
    text = await format_message(context, "admin_set_link_skip", {"link_type": link_type})
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    await other_links_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END
# --- NAYA: Conversation: Set Custom Messages (PAGINATED) ---
async def set_msg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    msg_key = query.data.replace("msg_edit_", "")
    
    config = await get_config()
    current_msg = config.get("messages", {}).get(msg_key, "N/A")
    
    context.user_data['msg_key'] = msg_key
    
    # current_msg ko HTML se escape karo taaki <code> me sahi dikhe
    safe_current_msg = current_msg.replace('<', '&lt;').replace('>', '&gt;')
    
    text = await format_message(context, "admin_set_msg_start", {
        "msg_key": msg_key,
        "current_msg": safe_current_msg
    })
    
    if msg_key.startswith("user_dl_") or msg_key == "file_warning":
        back_cb = "msg_menu_dl"
    elif msg_key.startswith("post_gen_"):
        back_cb = "msg_menu_postgen"
    elif msg_key.startswith("admin_"): # NAYA
        back_cb = "msg_menu_admin"
    else:
        back_cb = "msg_menu_gen"
        
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_cb)]]))
    return M_GET_MSG

async def set_msg_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        msg_text = update.message.text # Ab raw text save hoga (jisme <b> <blockquote> etc. ho sakte hain)
        msg_key = context.user_data['msg_key']
        
        config_collection.update_one({"_id": "bot_config"}, {"$set": {f"messages.{msg_key}": msg_text}}, upsert=True)
        logger.info(f"{msg_key} message update ho gaya: {msg_text}")
        text = await format_message(context, "admin_set_msg_success", {"msg_key": msg_key})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        
        await bot_messages_menu(update, context) 
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Message save karne me error: {e}")
        text = await format_message(context, "admin_set_msg_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        context.user_data.clear()
        return ConversationHandler.END
    
# --- Conversation: Post Generator ---
async def post_gen_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("✍️ Complete Anime Post", callback_data="post_gen_anime")],
        [InlineKeyboardButton("✍️ Season Post", callback_data="post_gen_season")],
        [InlineKeyboardButton("✍️ Episode Post", callback_data="post_gen_episode")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_post_gen")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return PG_MENU

async def post_gen_select_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    post_type = query.data
    context.user_data['post_type'] = post_type
    
    return await post_gen_show_anime_list(update, context, page=0)

async def post_gen_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("postgen_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()

    context.user_data['current_page'] = page 
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="postgen_page_",
        item_callback_prefix="post_anime_",
        back_callback="admin_post_gen" 
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_post_gen_no_anime")
    else:
        text = await format_message(context, "admin_post_gen_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return PG_GET_ANIME

async def post_gen_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("post_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    
    if context.user_data['post_type'] == 'post_gen_anime':
        context.user_data['season_name'] = None
        context.user_data['ep_num'] = None 
        await generate_post_ask_chat(update, context) 
        return PG_GET_SHORT_LINK 
        
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        text = await format_message(context, "admin_post_gen_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"post_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"postgen_page_{current_page}")])

    text = await format_message(context, "admin_post_gen_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return PG_GET_SEASON

async def post_gen_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("post_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    if context.user_data['post_type'] == 'post_gen_season':
        context.user_data['ep_num'] = None 
        await generate_post_ask_chat(update, context) 
        return PG_GET_SHORT_LINK 
        
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        text = await format_message(context, "admin_post_gen_no_episode", {
            "anime_name": anime_name, 
            "season_name": season_name
        })
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"post_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"post_anime_{anime_name}")])

    text = await format_message(context, "admin_post_gen_select_episode", {"season_name": season_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return PG_GET_EPISODE

async def post_gen_final_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("post_ep_", "")
    context.user_data['ep_num'] = ep_num
    
    await generate_post_ask_chat(update, context) 
    return PG_GET_SHORT_LINK 

async def generate_post_ask_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        bot_username = (await context.bot.get_me()).username
        
        config = await get_config()
        anime_name = context.user_data['anime_name']
        season_name = context.user_data.get('season_name')
        ep_num = context.user_data.get('ep_num') 
        anime_doc = animes_collection.find_one({"name": anime_name})
        
        anime_id = str(anime_doc['_id'])
        
        post_type = context.user_data.get('post_type')
        
        dl_callback_data = f"dl{anime_id}" 
        
        if post_type == 'post_gen_anime':
            context.user_data['is_episode_post'] = False
            poster_id = anime_doc['poster_id']
            description = anime_doc.get('description', '')
            
            caption_template = await format_message(context, "post_gen_anime_caption") # NAYA
            caption = caption_template.format(anime_name=anime_name, description=description if description else "")
        
        elif not ep_num and season_name:
            context.user_data['is_episode_post'] = False
            dl_callback_data = f"dl{anime_id}__{season_name}" 
            
            season_data = anime_doc.get("seasons", {}).get(season_name, {})
            poster_id = season_data.get("_poster_id") or anime_doc['poster_id']
            description = season_data.get("_description") or anime_doc.get('description', '')
            
            caption_template = await format_message(context, "post_gen_season_caption") # NAYA
            caption = caption_template.format(anime_name=anime_name, season_name=season_name, description=description if description else "")
    
        elif ep_num:
            context.user_data['is_episode_post'] = True
            dl_callback_data = f"dl{anime_id}__{season_name}__{ep_num}" 
            
            caption_template = await format_message(context, "post_gen_episode_caption") # NAYA
            caption = caption_template.format(anime_name=anime_name, season_name=season_name, ep_num=ep_num)
            
            poster_id = None 
        
        else:
            logger.warning("Post generator me invalid state")
            text = await format_message(context, "admin_post_gen_invalid_state")
            await query.edit_message_text(text, parse_mode=ParseMode.HTML)
            return ConversationHandler.END
        
        links = config.get('links', {})
        backup_url = links.get('backup') or "https://t.me/"
        help_url = links.get('help') or "https://t.me/" # NAYA
        donate_url = f"https://t.me/{bot_username}?start=donate"
        
        original_download_url = f"https://t.me/{bot_username}?start={dl_callback_data}"
        
        btn_backup = InlineKeyboardButton("Backup", url=backup_url)
        btn_donate = InlineKeyboardButton("Donate", url=donate_url)
        btn_help = InlineKeyboardButton("🆘 Help", url=help_url) # NAYA

        context.user_data['post_caption_raw'] = caption # Raw caption (bina font)
        context.user_data['post_poster_id'] = poster_id 
        context.user_data['btn_backup'] = btn_backup
        context.user_data['btn_donate'] = btn_donate
        context.user_data['btn_help'] = btn_help # NAYA
        context.user_data['is_episode_post'] = context.user_data.get('is_episode_post', False) 
        
        text = await format_message(context, "admin_post_gen_ask_shortlink", {
            "original_download_url": original_download_url
        })
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML
        )
        
        return PG_GET_SHORT_LINK 
        
    except Exception as e:
        logger.error(f"Post generate karne me error: {e}", exc_info=True)
        await query.answer("Error! Post generate nahi kar paya.", show_alert=True)
        text = await format_message(context, "admin_post_gen_error_general")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        context.user_data.clear()
        return ConversationHandler.END
        
async def post_gen_get_short_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    short_link_url = update.message.text
    
    caption_raw = context.user_data['post_caption_raw']
    poster_id = context.user_data['post_poster_id']
    btn_backup = context.user_data['btn_backup']
    btn_donate = context.user_data['btn_donate']
    btn_help = context.user_data['btn_help'] # NAYA
    is_episode_post = context.user_data.get('is_episode_post', False)
    
    btn_download = InlineKeyboardButton("Download", url=short_link_url)
    
    if is_episode_post:
        keyboard = [
            [btn_donate, btn_download],
        ]
    else:
        keyboard = [
            [btn_backup, btn_donate],
            [btn_download]            
        ]
    
    context.user_data['post_keyboard'] = InlineKeyboardMarkup(keyboard)
    # NAYA: Caption ko font ke saath format karo (Post ke liye hamesha default)
    font_settings = {"font": "default", "style": "normal"}
    caption_formatted = await apply_font_formatting(caption_raw, font_settings)
    context.user_data['post_caption_formatted'] = caption_formatted
    
    text = await format_message(context, "admin_post_gen_ask_chat")
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML
    )
    
    return PG_GET_CHAT

async def post_gen_send_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.text
    is_episode_post = context.user_data.get('is_episode_post', False) 
    caption_text = context.user_data['post_caption_formatted'] # Pehle se formatted
    
    try:
        if is_episode_post:
            await context.bot.send_message(
                chat_id=chat_id,
                text=caption_text,
                parse_mode=ParseMode.HTML,
                reply_markup=context.user_data['post_keyboard']
            )
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=context.user_data['post_poster_id'],
                caption=caption_text,
                parse_mode=ParseMode.HTML,
                reply_markup=context.user_data['post_keyboard']
            )

        text = await format_message(context, "admin_post_gen_success", {"chat_id": chat_id})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Post channel me bhejme me error: {e}")
        text = await format_message(context, "admin_post_gen_error", {"chat_id": chat_id, "e": e})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    context.user_data.clear()
    return ConversationHandler.END

# --- NAYA: Conversation: Generate Link ---
async def gen_link_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🔗 Complete Anime Link", callback_data="gen_link_anime")],
        [InlineKeyboardButton("🔗 Season Link", callback_data="gen_link_season")],
        [InlineKeyboardButton("🔗 Episode Link", callback_data="gen_link_episode")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_gen_link")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return GL_MENU

async def gen_link_select_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    link_type = query.data
    context.user_data['link_type'] = link_type
    
    return await gen_link_show_anime_list(update, context, page=0)

async def gen_link_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("genlink_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()

    context.user_data['current_page'] = page
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="genlink_page_",
        item_callback_prefix="gen_link_anime_",
        back_callback="admin_gen_link" 
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_gen_link_no_anime")
    else:
        text = await format_message(context, "admin_gen_link_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return GL_GET_ANIME

async def gen_link_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("gen_link_anime_", "")
    context.user_data['anime_name'] = anime_name
    
    if context.user_data['link_type'] == 'gen_link_anime':
        context.user_data['season_name'] = None
        context.user_data['ep_num'] = None 
        return await gen_link_finish(update, context) 
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        text = await format_message(context, "admin_gen_link_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gen_link")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"gen_link_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"genlink_page_{current_page}")])

    text = await format_message(context, "admin_gen_link_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return GL_GET_SEASON

async def gen_link_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("gen_link_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    if context.user_data['link_type'] == 'gen_link_season':
        context.user_data['ep_num'] = None 
        return await gen_link_finish(update, context) 
        
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        text = await format_message(context, "admin_gen_link_no_episode", {
            "anime_name": anime_name,
            "season_name": season_name
        })
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gen_link")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"gen_link_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"gen_link_anime_{anime_name}")])

    text = await format_message(context, "admin_gen_link_select_episode", {"season_name": season_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return GL_GET_EPISODE

async def gen_link_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("gen_link_ep_"):
        ep_num = query.data.replace("gen_link_ep_", "")
        context.user_data['ep_num'] = ep_num
    
    try:
        bot_username = (await context.bot.get_me()).username
        
        anime_name = context.user_data['anime_name']
        season_name = context.user_data.get('season_name')
        ep_num = context.user_data.get('ep_num') 
        
        anime_doc = animes_collection.find_one({"name": anime_name})
        anime_id = str(anime_doc['_id'])
        
        link_type = context.user_data.get('link_type')
        
        dl_callback_data = f"dl{anime_id}" 
        title = anime_name
        
        if link_type == 'gen_link_season' and season_name:
            dl_callback_data = f"dl{anime_id}__{season_name}"
            title = f"{anime_name} - S{season_name}"
        elif link_type == 'gen_link_episode' and season_name and ep_num:
            dl_callback_data = f"dl{anime_id}__{season_name}__{ep_num}"
            title = f"{anime_name} - S{season_name} E{ep_num}"
        
        final_link = f"https://t.me/{bot_username}?start={dl_callback_data}"
        
        text = await format_message(context, "admin_gen_link_success", {
            "title": title,
            "final_link": final_link
        })
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]])
        )
        
    except Exception as e:
        logger.error(f"Link generate karne me error: {e}", exc_info=True)
        text = await format_message(context, "admin_gen_link_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
        
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Delete Anime ---
async def delete_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await delete_anime_show_anime_list(update, context, page=0)

async def delete_anime_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("delanime_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page 

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="delanime_page_",
        item_callback_prefix="del_anime_",
        back_callback="back_to_manage"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_del_anime_no_anime")
    else:
        text = await format_message(context, "admin_del_anime_select", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return DA_GET_ANIME

async def delete_anime_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_anime_", "")
    context.user_data['anime_name'] = anime_name
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {anime_name} ko Delete Karo", callback_data="del_anime_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    text = await format_message(context, "admin_del_anime_confirm", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return DA_CONFIRM

async def delete_anime_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    try:
        animes_collection.delete_one({"name": anime_name})
        logger.info(f"Anime deleted: {anime_name}")
        text = await format_message(context, "admin_del_anime_success", {"anime_name": anime_name})
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Anime delete karne me error: {e}")
        text = await format_message(context, "admin_del_anime_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    context.user_data.clear()
    await asyncio.sleep(3)
    await manage_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Delete Season ---
async def delete_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await delete_season_show_anime_list(update, context, page=0)

async def delete_season_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("delseason_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page 

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="delseason_page_",
        item_callback_prefix="del_season_anime_",
        back_callback="back_to_manage"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_del_season_no_anime")
    else:
        text = await format_message(context, "admin_del_season_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return DS_GET_ANIME

async def delete_season_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_season_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        text = await format_message(context, "admin_del_season_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"del_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"delseason_page_{current_page}")])

    text = await format_message(context, "admin_del_season_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return DS_GET_SEASON

async def delete_season_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("del_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    keyboard = [[InlineKeyboardButton(f"✅ Haan, Season {season_name} Delete Karo", callback_data="del_season_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    text = await format_message(context, "admin_del_season_confirm", {
        "anime_name": anime_name,
        "season_name": season_name
    })
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return DS_CONFIRM

async def delete_season_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    try:
        animes_collection.update_one(
            {"name": anime_name},
            {"$unset": {f"seasons.{season_name}": ""},
             "$set": {"last_modified": datetime.now()}} # NAYA: Timestamp
        )
        logger.info(f"Season deleted: {anime_name} - S{season_name}")
        text = await format_message(context, "admin_del_season_success", {"season_name": season_name})
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Season delete karne me error: {e}")
        text = await format_message(context, "admin_del_season_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    context.user_data.clear()
    await asyncio.sleep(3)
    await manage_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Delete Episode ---
async def delete_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await delete_episode_show_anime_list(update, context, page=0)

async def delete_episode_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("delep_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()

    context.user_data['current_page'] = page 
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="delep_page_",
        item_callback_prefix="del_ep_anime_",
        back_callback="back_to_manage"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_del_ep_no_anime")
    else:
        text = await format_message(context, "admin_del_ep_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return DE_GET_ANIME

async def delete_episode_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        text = await format_message(context, "admin_del_ep_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"del_ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"delep_page_{current_page}")])

    text = await format_message(context, "admin_del_ep_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return DE_GET_SEASON

async def delete_episode_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("del_ep_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        text = await format_message(context, "admin_del_ep_no_episode", {
            "anime_name": anime_name,
            "season_name": season_name
        })
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"del_ep_num_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"del_ep_anime_{anime_name}")])

    text = await format_message(context, "admin_del_ep_select_episode", {"season_name": season_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return DE_GET_EPISODE

async def delete_episode_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("del_ep_num_", "")
    context.user_data['ep_num'] = ep_num
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    keyboard = [[InlineKeyboardButton(f"✅ Haan, Ep {ep_num} Delete Karo", callback_data="del_ep_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    text = await format_message(context, "admin_del_ep_confirm", {
        "anime_name": anime_name,
        "season_name": season_name,
        "ep_num": ep_num
    })
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return DE_CONFIRM

async def delete_episode_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    ep_num = context.user_data['ep_num']
    try:
        animes_collection.update_one(
            {"name": anime_name},
            {"$unset": {f"seasons.{season_name}.{ep_num}": ""},
             "$set": {"last_modified": datetime.now()}} # NAYA: Timestamp
        )
        logger.info(f"Episode deleted: {anime_name} - S{season_name} - E{ep_num}")
        text = await format_message(context, "admin_del_ep_success", {"ep_num": ep_num})
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Episode delete karne me error: {e}")
        text = await format_message(context, "admin_del_ep_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    context.user_data.clear()
    await asyncio.sleep(3)
    await manage_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Update Photo ---
async def update_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await update_photo_show_anime_list(update, context, page=0)

async def update_photo_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("upphoto_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page 

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="upphoto_page_",
        item_callback_prefix="upphoto_anime_",
        back_callback="admin_menu" 
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_update_photo_no_anime")
    else:
        text = await format_message(context, "admin_update_photo_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return UP_GET_ANIME

async def update_photo_select_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("upphoto_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    
    buttons = [InlineKeyboardButton(f"🖼️ Main Anime Poster", callback_data=f"upphoto_target_MAIN")]
    
    seasons = anime_doc.get("seasons", {})
    if seasons:
        sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
        for s in sorted_seasons:
            buttons.append(InlineKeyboardButton(f"S{s} Poster", callback_data=f"upphoto_target_S__{s}"))

    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"upphoto_page_{current_page}")])
    
    text = await format_message(context, "admin_update_photo_select_target", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return UP_GET_TARGET

async def update_photo_get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    target = query.data.replace("upphoto_target_", "")
    context.user_data['target'] = target
    
    if target == "MAIN":
        target_name = "Main Anime Poster"
    else:
        season_name = target.replace("S__", "")
        context.user_data['season_name'] = season_name
        target_name = f"Season {season_name} Poster"

    text = await format_message(context, "admin_update_photo_get_poster", {"target_name": target_name})
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return UP_GET_POSTER

async def update_photo_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await format_message(context, "admin_update_photo_invalid")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return UP_GET_POSTER 

async def update_photo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        text = await format_message(context, "admin_update_photo_save_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return UP_GET_POSTER
    
    poster_id = update.message.photo[-1].file_id
    anime_name = context.user_data['anime_name']
    target = context.user_data['target']
    
    try:
        update_query = {"$set": {"last_modified": datetime.now()}} # NAYA: Timestamp
        
        if target == "MAIN":
            update_query["$set"]["poster_id"] = poster_id
            animes_collection.update_one({"name": anime_name}, update_query)
            caption = await format_message(context, "admin_update_photo_save_success_main", {"anime_name": anime_name})
            logger.info(f"Main poster change ho gaya: {anime_name}")
        else:
            season_name = context.user_data['season_name']
            update_query["$set"][f"seasons.{season_name}._poster_id"] = poster_id
            animes_collection.update_one(
                {"name": anime_name}, 
                update_query
            )
            caption = await format_message(context, "admin_update_photo_save_success_season", {
                "anime_name": anime_name,
                "season_name": season_name
            })
            logger.info(f"Season poster change ho gaya: {anime_name} S{season_name}")

        await update.message.reply_photo(photo=poster_id, caption=caption, parse_mode=ParseMode.HTML)
    
    except Exception as e:
        logger.error(f"Poster change karne me error: {e}")
        text = await format_message(context, "admin_update_photo_save_error_db")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await admin_command(update, context, from_callback=False) 
    return ConversationHandler.END


# --- Conversation: Edit Anime Name ---
async def edit_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await edit_anime_show_anime_list(update, context, page=0)

async def edit_anime_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("editanime_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page 

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="editanime_page_",
        item_callback_prefix="edit_anime_",
        back_callback="back_to_edit_menu"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_edit_anime_no_anime")
    else:
        text = await format_message(context, "admin_edit_anime_select", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return EA_GET_ANIME

async def edit_anime_get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("edit_anime_", "")
    context.user_data['old_anime_name'] = anime_name
    text = await format_message(context, "admin_edit_anime_get_name", {"anime_name": anime_name})
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return EA_GET_NEW_NAME

async def edit_anime_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text
    old_name = context.user_data['old_anime_name']
    
    if animes_collection.find_one({"name": new_name}):
        text = await format_message(context, "admin_edit_anime_save_exists", {"new_name": new_name})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return EA_GET_NEW_NAME
    
    context.user_data['new_anime_name'] = new_name
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, '{old_name}' ko '{new_name}' Karo", callback_data="edit_anime_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]
    text = await format_message(context, "admin_edit_anime_confirm", {
        "old_name": old_name,
        "new_name": new_name
    })
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return EA_CONFIRM

async def edit_anime_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Updating...")
    old_name = context.user_data['old_anime_name']
    new_name = context.user_data['new_anime_name']
    try:
        animes_collection.update_one(
            {"name": old_name},
            {"$set": {
                "name": new_name,
                "last_modified": datetime.now() # NAYA: Timestamp
            }}
        )
        logger.info(f"Anime naam update ho gaya: {old_name} -> {new_name}")
        text = await format_message(context, "admin_edit_anime_success", {
            "old_name": old_name,
            "new_name": new_name
        })
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Anime naam update karne me error: {e}")
        text = await format_message(context, "admin_edit_anime_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await edit_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Edit Season Name ---
async def edit_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await edit_season_show_anime_list(update, context, page=0)

async def edit_season_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("editseason_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="editseason_page_",
        item_callback_prefix="edit_season_anime_",
        back_callback="back_to_edit_menu"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_edit_season_no_anime")
    else:
        text = await format_message(context, "admin_edit_season_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return ES_GET_ANIME

async def edit_season_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("edit_season_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        text = await format_message(context, "admin_edit_season_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"edit_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"editseason_page_{current_page}")])

    text = await format_message(context, "admin_edit_season_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return ES_GET_SEASON

async def edit_season_get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("edit_season_", "")
    context.user_data['old_season_name'] = season_name
    anime_name = context.user_data['anime_name']
    text = await format_message(context, "admin_edit_season_get_name", {
        "anime_name": anime_name,
        "season_name": season_name
    })
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return ES_GET_NEW_NAME

async def edit_season_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text
    old_name = context.user_data['old_season_name']
    anime_name = context.user_data['anime_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if new_name in anime_doc.get("seasons", {}):
        text = await format_message(context, "admin_edit_season_save_exists", {"new_name": new_name})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return ES_GET_NEW_NAME
        
    context.user_data['new_season_name'] = new_name
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, '{old_name}' ko '{new_name}' Karo", callback_data="edit_season_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]
    text = await format_message(context, "admin_edit_season_confirm", {
        "anime_name": anime_name,
        "old_name": old_name,
        "new_name": new_name
    })
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return ES_CONFIRM

async def edit_season_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Updating...")
    old_name = context.user_data['old_season_name']
    new_name = context.user_data['new_season_name']
    anime_name = context.user_data['anime_name']
    try:
        animes_collection.update_one(
            {"name": anime_name},
            {"$rename": {f"seasons.{old_name}": f"seasons.{new_name}"},
             "$set": {"last_modified": datetime.now()}} # NAYA: Timestamp
        )
        logger.info(f"Season naam update ho gaya: {anime_name} - {old_name} -> {new_name}")
        text = await format_message(context, "admin_edit_season_success", {
            "old_name": old_name,
            "new_name": new_name
        })
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Season naam update karne me error: {e}")
        text = await format_message(context, "admin_edit_season_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await edit_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Edit Episode Number ---
async def edit_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await edit_episode_show_anime_list(update, context, page=0)

async def edit_episode_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("editep_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()

    context.user_data['current_page'] = page
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="editep_page_",
        item_callback_prefix="edit_ep_anime_",
        back_callback="back_to_edit_menu"
    )
    
    if not animes and page == 0:
        text = await format_message(context, "admin_edit_ep_no_anime")
    else:
        text = await format_message(context, "admin_edit_ep_select_anime", {"page": page + 1}) # NAYA: Text DB se

    await query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return EE_GET_ANIME

async def edit_episode_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("edit_ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        text = await format_message(context, "admin_edit_ep_no_season", {"anime_name": anime_name})
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"edit_ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"editep_page_{current_page}")])

    text = await format_message(context, "admin_edit_ep_select_season", {"anime_name": anime_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return EE_GET_SEASON

async def edit_episode_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("edit_ep_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        text = await format_message(context, "admin_edit_ep_no_episode", {
            "anime_name": anime_name,
            "season_name": season_name
        })
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]), parse_mode=ParseMode.HTML)
        return ConversationHandler.END
        
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"edit_ep_num_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"edit_ep_anime_{anime_name}")])

    text = await format_message(context, "admin_edit_ep_select_episode", {"season_name": season_name})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return EE_GET_EPISODE
    
async def edit_episode_get_new_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("edit_ep_num_", "")
    context.user_data['old_ep_num'] = ep_num
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    
    text = await format_message(context, "admin_edit_ep_get_num", {
        "anime_name": anime_name,
        "season_name": season_name,
        "ep_num": ep_num
    })
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    return EE_GET_NEW_NUM

async def edit_episode_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_num = update.message.text
    old_num = context.user_data['old_ep_num']
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if new_num in anime_doc.get("seasons", {}).get(season_name, {}):
        text = await format_message(context, "admin_edit_ep_save_exists", {"new_num": new_num})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return EE_GET_NEW_NUM
        
    context.user_data['new_ep_num'] = new_num
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, '{old_num}' ko '{new_num}' Karo", callback_data="edit_ep_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]
    text = await format_message(context, "admin_edit_ep_confirm", {
        "anime_name": anime_name,
        "season_name": season_name,
        "old_num": old_num,
        "new_num": new_num
    })
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return EE_CONFIRM

async def edit_episode_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Updating...")
    old_num = context.user_data['old_ep_num']
    new_num = context.user_data['new_ep_num']
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    try:
        animes_collection.update_one(
            {"name": anime_name},
            {"$rename": {f"seasons.{season_name}.{old_num}": f"seasons.{season_name}.{new_num}"},
             "$set": {"last_modified": datetime.now()}} # NAYA: Timestamp
        )
        logger.info(f"Episode number update ho gaya: {anime_name} S{season_name} - {old_num} -> {new_num}")
        text = await format_message(context, "admin_edit_ep_success", {
            "old_num": old_num,
            "new_num": new_num
        })
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Episode number update karne me error: {e}")
        text = await format_message(context, "admin_edit_ep_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await edit_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Admin Settings (Co-Admin, Custom Post) ---
async def co_admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = await format_message(context, "admin_co_admin_add_start")
    await query.edit_message_text(text, parse_mode=ParseMode.HTML,
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return CA_GET_ID

async def co_admin_add_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
    except ValueError:
        text = await format_message(context, "admin_co_admin_add_invalid_id")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CA_GET_ID

    if user_id == ADMIN_ID:
        text = await format_message(context, "admin_co_admin_add_is_main")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CA_GET_ID

    config = await get_config()
    if user_id in config.get("co_admins", []):
        text = await format_message(context, "admin_co_admin_add_exists", {"user_id": user_id})
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CA_GET_ID

    context.user_data['co_admin_to_add'] = user_id
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ko Co-Admin Banao", callback_data="co_admin_add_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]
    text = await format_message(context, "admin_co_admin_add_confirm", {"user_id": user_id})
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return CA_CONFIRM

async def co_admin_add_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Adding...")
    user_id = context.user_data['co_admin_to_add']
    try:
        config_collection.update_one(
            {"_id": "bot_config"},
            {"$push": {"co_admins": user_id}}
        )
        logger.info(f"Main Admin {query.from_user.id} ne {user_id} ko Co-Admin banaya.")
        text = await format_message(context, "admin_co_admin_add_success", {"user_id": user_id})
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Co-Admin add karne me error: {e}")
        text = await format_message(context, "admin_co_admin_add_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    context.user_data.clear()
    await asyncio.sleep(3)
    await admin_settings_menu(update, context)
    return ConversationHandler.END

async def co_admin_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    config = await get_config()
    co_admins = config.get("co_admins", [])

    if not co_admins:
        text = await format_message(context, "admin_co_admin_remove_no_co")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
        return ConversationHandler.END

    buttons = [InlineKeyboardButton(f"Remove {admin_id}", callback_data=f"co_admin_rem_{admin_id}") for admin_id in co_admins]
    keyboard = build_grid_keyboard(buttons, 1) 
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")])
    text = await format_message(context, "admin_co_admin_remove_start")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return CR_GET_ID

async def co_admin_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.replace("co_admin_rem_", ""))
    context.user_data['co_admin_to_remove'] = user_id

    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ko Remove Karo", callback_data="co_admin_rem_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]
    text = await format_message(context, "admin_co_admin_remove_confirm", {"user_id": user_id})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return CR_CONFIRM

async def co_admin_remove_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Removing...")
    user_id = context.user_data['co_admin_to_remove']
    try:
        config_collection.update_one(
            {"_id": "bot_config"},
            {"$pull": {"co_admins": user_id}}
        )
        logger.info(f"Main Admin {query.from_user.id} ne {user_id} ko Co-Admin se hataya.")
        text = await format_message(context, "admin_co_admin_remove_success", {"user_id": user_id})
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Co-Admin remove karne me error: {e}")
        text = await format_message(context, "admin_co_admin_remove_error")
        await query.edit_message_text(text, parse_mode=ParseMode.HTML)

    context.user_data.clear()
    await asyncio.sleep(3)
    await admin_settings_menu(update, context)
    return ConversationHandler.END

async def co_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = await get_config()
    co_admins = config.get("co_admins", [])
    if not co_admins:
        text = await format_message(context, "admin_co_admin_list_none")
    else:
        text = await format_message(context, "admin_co_admin_list_header")
        for admin_id in co_admins:
            text += f"- <code>{admin_id}</code>\n" # <pre> hata diya

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return ConversationHandler.END


# --- Conversation: Custom Post ---
async def custom_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = await format_message(context, "admin_custom_post_start")
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return CPOST_GET_CHAT

async def custom_post_get_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['chat_id'] = update.message.text
    text = await format_message(context, "admin_custom_post_get_chat")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return CPOST_GET_POSTER

async def custom_post_get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        text = await format_message(context, "admin_custom_post_get_poster_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CPOST_GET_POSTER
    context.user_data['poster_id'] = update.message.photo[-1].file_id
    text = await format_message(context, "admin_custom_post_get_poster")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return CPOST_GET_CAPTION

async def custom_post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['caption'] = update.message.text
    text = await format_message(context, "admin_custom_post_get_caption")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return CPOST_GET_BTN_TEXT

async def custom_post_get_btn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_text'] = update.message.text
    text = await format_message(context, "admin_custom_post_get_btn_text")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    return CPOST_GET_BTN_URL

async def custom_post_get_btn_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_url'] = update.message.text

    chat_id = context.user_data['chat_id']
    poster_id = context.user_data['poster_id']
    caption_raw = context.user_data['caption']
    btn_text = context.user_data['btn_text']
    btn_url = context.user_data['btn_url']

    # NAYA: Caption ko format karo (default font me)
    font_settings = {"font": "default", "style": "normal"}
    caption_formatted = await apply_font_formatting(caption_raw, font_settings)

    keyboard = [
        [InlineKeyboardButton(btn_text, url=btn_url)],
        [InlineKeyboardButton("✅ Post Karo", callback_data="cpost_send")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]
    ]

    caption_text = await format_message(context, "admin_custom_post_confirm", {
        "caption": caption_formatted,
        "chat_id": chat_id
    })
    await update.message.reply_photo(
        photo=poster_id,
        caption=caption_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CPOST_CONFIRM

async def custom_post_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Sending...")

    chat_id = context.user_data['chat_id']
    poster_id = context.user_data['poster_id']
    caption_raw = context.user_data['caption']
    btn_text = context.user_data['btn_text']
    btn_url = context.user_data['btn_url']

    # NAYA: Caption ko format karo (default font me)
    font_settings = {"font": "default", "style": "normal"}
    caption_formatted = await apply_font_formatting(caption_raw, font_settings)

    keyboard = [[InlineKeyboardButton(btn_text, url=btn_url)]]

    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=poster_id,
            caption=caption_formatted,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        text = await format_message(context, "admin_custom_post_success", {"chat_id": chat_id})
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Custom post bhejme me error: {e}")
        text = await format_message(context, "admin_custom_post_error", {"chat_id": chat_id, "e": e})
        await query.message.reply_text(text, parse_mode=ParseMode.HTML)

    await query.message.delete() 
    context.user_data.clear()
    await admin_settings_menu(update, context)
    return ConversationHandler.END


# --- NAYA: Conversation: Bot Appearance ---
async def appearance_menu_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    config = await get_config()
    appearance = config.get("appearance", {"font": "default", "style": "normal"})
    font = appearance.get("font", "default")
    style = appearance.get("style", "normal")
    
    keyboard = [
        [
            InlineKeyboardButton(f"🖋️ Font: {font.title()}", callback_data="app_set_font"),
            InlineKeyboardButton(f"✍️ Style: {style.title()}", callback_data="app_set_style")
        ],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_appearance", {
        "font": font.title(),
        "style": style.title()
    })
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        
    return AP_MENU

async def appearance_set_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config = await get_config()
    current_font = config.get("appearance", {}).get("font", "default")
    
    # NAYA: sans_serif_regular add kiya
    fonts = ["default", "small_caps", "sans_serif", "sans_serif_regular", "script", "monospace", "serif"]
    buttons = []
    for font in fonts:
        prefix = "✅ " if font == current_font else ""
        buttons.append(InlineKeyboardButton(f"{prefix}{font.title().replace('_', ' ')}", callback_data=f"app_font_{font}"))
        
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_appearance")])
    
    text = await format_message(context, "admin_appearance_select_font", {"font": current_font.title().replace('_', ' ')})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return AP_SET_FONT

async def appearance_save_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    font = query.data.replace("app_font_", "")
    
    config_collection.update_one(
        {"_id": "bot_config"},
        {"$set": {"appearance.font": font}},
        upsert=True
    )
    await query.answer(f"Font changed to {font}")
    
    text = await format_message(context, "admin_appearance_set_font_success", {"font": font.title().replace('_', ' ')})
    await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    await appearance_menu_start(update, context)
    return AP_MENU

async def appearance_set_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config = await get_config()
    current_style = config.get("appearance", {}).get("style", "normal")
    
    styles = ["normal", "bold"]
    buttons = []
    for style in styles:
        prefix = "✅ " if style == current_style else ""
        buttons.append(InlineKeyboardButton(f"{prefix}{style.title()}", callback_data=f"app_style_{style}"))
        
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_appearance")])
    
    text = await format_message(context, "admin_appearance_select_style", {"style": current_style.title()})
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return AP_SET_STYLE

async def appearance_save_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    style = query.data.replace("app_style_", "")
    
    config_collection.update_one(
        {"_id": "bot_config"},
        {"$set": {"appearance.style": style}},
        upsert=True
    )
    await query.answer(f"Style changed to {style}")
    
    text = await format_message(context, "admin_appearance_set_style_success", {"style": style.title()})
    await query.message.reply_text(text, parse_mode=ParseMode.HTML)
    
    await appearance_menu_start(update, context)
    return AP_MENU

    
# --- Admin Panel: Sub-Menu Functions ---
async def add_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("➕ Add Anime", callback_data="admin_add_anime")],
        [InlineKeyboardButton("➕ Add Season", callback_data="admin_add_season")],
        [InlineKeyboardButton("➕ Add Episode", callback_data="admin_add_episode")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_add_content")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    
async def manage_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_message: bool = False):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete Anime", callback_data="admin_del_anime")],
        [InlineKeyboardButton("🗑️ Delete Season", callback_data="admin_del_season")],
        [InlineKeyboardButton("🗑️ Delete Episode", callback_data="admin_del_episode")], 
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_manage_content")
    
    if from_message: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    elif query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def edit_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_message: bool = False):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✏️ Edit Anime Name", callback_data="admin_edit_anime")],
        [InlineKeyboardButton("✏️ Edit Season Name", callback_data="admin_edit_season")],
        [InlineKeyboardButton("✏️ Edit Episode Number", callback_data="admin_edit_episode")], 
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_edit_content")
    
    if from_message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    elif query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def donate_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    config = await get_config()
    donate_qr_status = "✅" if config.get('donate_qr_id') else "❌"
    keyboard = [
        [InlineKeyboardButton(f"Set Donate QR {donate_qr_status}", callback_data="admin_set_donate_qr")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_donate")
    if query: 
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def other_links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    config = await get_config()
    backup_status = "✅" if config.get('links', {}).get('backup') else "❌"
    download_status = "✅" if config.get('links', {}).get('download') else "❌"
    help_status = "✅" if config.get('links', {}).get('help') else "❌" # NAYA
    keyboard = [
        [InlineKeyboardButton(f"Set Backup Link {backup_status}", callback_data="admin_set_backup_link")],
        [InlineKeyboardButton(f"Set Download Link {download_status}", callback_data="admin_set_download_link")], 
        [InlineKeyboardButton(f"Set Help Link {help_status}", callback_data="admin_set_help_link")], # NAYA
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_links")
    if query: 
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

async def bot_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📥 Download Flow Messages", callback_data="msg_menu_dl")],
        [InlineKeyboardButton("✍️ Post Generator Messages", callback_data="msg_menu_postgen")],
        [InlineKeyboardButton("👑 Admin Flow Messages", callback_data="msg_menu_admin")], # NAYA
        [InlineKeyboardButton("⚙️ General Messages", callback_data="msg_menu_gen")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_messages_main")
    
    if query: 
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return M_MENU_MAIN

async def bot_messages_menu_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Check DM Alert", callback_data="msg_edit_user_dl_dm_alert")],
        [InlineKeyboardButton("Edit Fetching Files", callback_data="msg_edit_user_dl_fetching")],
        [InlineKeyboardButton("Edit Anime Not Found", callback_data="msg_edit_user_dl_anime_not_found")],
        [InlineKeyboardButton("Edit Seasons Not Found", callback_data="msg_edit_user_dl_seasons_not_found")],
        [InlineKeyboardButton("Edit Episodes Not Found", callback_data="msg_edit_user_dl_episodes_not_found")],
        [InlineKeyboardButton("Edit Sending Files", callback_data="msg_edit_user_dl_sending_files")],
        [InlineKeyboardButton("Edit Select Season", callback_data="msg_edit_user_dl_select_season")],
        [InlineKeyboardButton("Edit Select Episode", callback_data="msg_edit_user_dl_select_episode")],
        [InlineKeyboardButton("Edit File Warning", callback_data="msg_edit_file_warning")],
        [InlineKeyboardButton("Edit File Error", callback_data="msg_edit_user_dl_file_error")],
        [InlineKeyboardButton("Edit Blocked Error", callback_data="msg_edit_user_dl_blocked_error")],
        [InlineKeyboardButton("Edit General Error", callback_data="msg_edit_user_dl_general_error")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    text = await format_message(context, "admin_menu_messages_dl")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return M_MENU_DL
    
async def bot_messages_menu_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Menu Greeting", callback_data="msg_edit_user_menu_greeting")],
        [InlineKeyboardButton("Edit Donate QR Error", callback_data="msg_edit_user_donate_qr_error")],
        [InlineKeyboardButton("Edit Donate QR Text", callback_data="msg_edit_user_donate_qr_text")],
        [InlineKeyboardButton("Edit Donate Thanks", callback_data="msg_edit_donate_thanks")],
        [InlineKeyboardButton("Edit Not Admin", callback_data="msg_edit_user_not_admin")],
        [InlineKeyboardButton("Edit Welcome Admin", callback_data="msg_edit_user_welcome_admin")],
        [InlineKeyboardButton("Edit Welcome User", callback_data="msg_edit_user_welcome_basic")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    text = await format_message(context, "admin_menu_messages_gen")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return M_MENU_GEN

async def bot_messages_menu_postgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Anime Post Caption", callback_data="msg_edit_post_gen_anime_caption")], 
        [InlineKeyboardButton("Edit Season Post Caption", callback_data="msg_edit_post_gen_season_caption")],
        [InlineKeyboardButton("Edit Episode Post Caption", callback_data="msg_edit_post_gen_episode_caption")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    text = await format_message(context, "admin_menu_messages_postgen")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return M_MENU_POSTGEN

# NAYA: Admin Messages Menu
async def bot_messages_menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Simple list for all admin messages
    keys = await get_default_messages()
    admin_keys = sorted([k for k in keys.keys() if k.startswith("admin_")])
    
    buttons = [InlineKeyboardButton(k.replace("admin_", "").replace("_", " ").title(), callback_data=f"msg_edit_{k}") for k in admin_keys]
    keyboard = build_grid_keyboard(buttons, 1) # 1-column list
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")])
    
    text = await format_message(context, "admin_menu_messages_admin")
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    return M_MENU_ADMIN

# NAYA: Admin Settings Menu
async def admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Co-Admin", callback_data="admin_add_co_admin")],
        [InlineKeyboardButton("🚫 Remove Co-Admin", callback_data="admin_remove_co_admin")],
        [InlineKeyboardButton("👥 List Co-Admins", callback_data="admin_list_co_admin")],
        [InlineKeyboardButton("🚀 Custom Post Generator", callback_data="admin_custom_post")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = await format_message(context, "admin_menu_admin_settings")
    
    if query: 
        if query.message.photo: 
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

    
# --- User Handlers ---
async def handle_deep_link_donate(user: User, context: ContextTypes.DEFAULT_TYPE):
    """Deep link se /start=donate ko handle karega"""
    logger.info(f"User {user.id} ne Donate deep link use kiya.")
    try:
        config = await get_config()
        qr_id = config.get('donate_qr_id')
        
        if not qr_id: 
            msg = await format_message(context, "user_donate_qr_error")
            await context.bot.send_message(user.id, msg, parse_mode=ParseMode.HTML)
            return

        text = await format_message(context, "user_donate_qr_text")
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="user_back_menu")]]
        
        await context.bot.send_photo(
            chat_id=user.id, 
            photo=qr_id, 
            caption=text, 
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.job_queue.run_once(send_donate_thank_you, 60, chat_id=user.id)
    except Exception as e:
        logger.error(f"Deep link Donate QR bhejte waqt error: {e}")
        if "blocked" in str(e):
            logger.warning(f"User {user.id} ne bot ko block kiya hua hai.")

async def handle_deep_link_download(user: User, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """Deep link se /start=dl... ko handle karega"""
    logger.info(f"User {user.id} ne Download deep link use kiya: {payload}")
    
    class DummyChat:
        def __init__(self, chat_id):
            self.id = chat_id
            self.type = 'private'

    class DummyMessage:
        def __init__(self, chat_id, message_id=None):
            self.chat = DummyChat(chat_id)
            self.message_id = message_id or 12345
            self.photo = None 
            self.text = "Deep link request"

    class DummyCallbackQuery:
        def __init__(self, user, data):
            self.from_user = user
            self.data = data
            self.message = DummyMessage(user.id)
        
        async def answer(self, *args, **kwargs):
            pass
            
    class DummyUpdate:
        def __init__(self, user, data):
                self.callback_query = DummyCallbackQuery(user, data)
                self.effective_user = user

    dummy_update = DummyUpdate(user, payload)
    
    try:
        await download_button_handler(dummy_update, context)
    except Exception as e:
        logger.error(f"Deep link download handler fail ho gaya: {e}", exc_info=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart /start command"""
    user = update.effective_user
    user_id, full_name = user.id, user.full_name # NAYA: Full name
    logger.info(f"User {user_id} ({full_name}) ne /start dabaya.")
    
    user_data = users_collection.find_one({"_id": user_id})
    if not user_data:
        users_collection.insert_one({"_id": user_id, "first_name": user.first_name, "full_name": full_name, "username": user.username}) # NAYA
        logger.info(f"Naya user database me add kiya: {user_id}")
    else:
        users_collection.update_one(
            {"_id": user_id},
            {"$set": {"first_name": user.first_name, "full_name": full_name, "username": user.username}} # NAYA
        )
    
    args = context.args
    if args:
        payload = " ".join(args) 
        logger.info(f"User {user_id} ne deep link use kiya: {payload}")
        
        if payload.startswith("dl"):
            await handle_deep_link_download(user, context, payload)
            return
            
        elif payload == "donate":
            await handle_deep_link_donate(user, context)
            return
    
    logger.info("Koi deep link nahi. Sirf welcome message bhej raha hoon.")
    if await is_co_admin(user_id):
        text = await format_message(context, "user_welcome_admin")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    else:
            text = await format_message(context, "user_welcome_basic", {
                "full_name": full_name,
                "first_name": user.first_name # Compatibility ke liye add kiya
            }) # NAYA
            # Ensure the message uses /user, even if DB message is old
            text = text.replace("/subscription", "/user") 
            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    
async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    """User ka main menu (/user) dikhayega, photo ke saath (agar set ho)"""
    user = update.effective_user
    user_id = user.id

    if from_callback:
        logger.info(f"User {user_id} 'Back to Menu' se aaya.")
    else:
        logger.info(f"User {user_id} ne /user khola.")

    config = await get_config()
    links = config.get('links', {})
    backup_url = links.get('backup') or "https://t.me/"
    help_url = links.get('help') or "https://t.me/" 

    btn_backup = InlineKeyboardButton("Backup", url=backup_url)
    btn_donate = InlineKeyboardButton("Donate", callback_data="user_show_donate_menu")
    btn_help = InlineKeyboardButton("🆘 Help", url=help_url) 

    keyboard = [
        [btn_backup, btn_donate],
        [btn_help]
    ] 
    reply_markup = InlineKeyboardMarkup(keyboard)

    menu_text = await format_message(context, "user_menu_greeting", {
        "full_name": user.full_name,
        "first_name": user.first_name # Compatibility
    })

    menu_photo_id = config.get("user_menu_photo_id")

    if from_callback:
        query = update.callback_query
        await query.answer()

        try:
            if menu_photo_id:
                # Admin ne photo set kiya hai
                if query.message.photo:
                    # Pehle se photo hai, caption edit karo
                    await query.edit_message_caption(caption=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
                else:
                    # Pehle text tha, delete karke photo bhejo
                    await query.message.delete()
                    await context.bot.send_photo(chat_id=user_id, photo=menu_photo_id, caption=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                # Admin ne koi photo set nahi kiya (default)
                if query.message.photo:
                    # Pehle photo tha, delete karke text bhejo
                    await query.message.delete()
                    await context.bot.send_message(chat_id=user_id, text=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
                else:
                    # Pehle bhi text tha, edit karo
                    await query.edit_message_text(text=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Menu edit/reply nahi kar paya: {e}. Naya message bhej raha hoon.")
            try:
                # Fallback: Agar kuch bhi fail ho, naya message bhejo
                if menu_photo_id:
                    await context.bot.send_photo(chat_id=user_id, photo=menu_photo_id, caption=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
                else:
                    await context.bot.send_message(chat_id=user_id, text=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            except Exception as e2:
                logger.error(f"Menu command (callback) me critical error: {e2}")
    else:
        # Jab user ne /user command type kiya
        try:
            if menu_photo_id:
                await update.message.reply_photo(photo=menu_photo_id, caption=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                await update.message.reply_text(text=menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Show user menu me error: {e}")

async def user_show_donate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/menu se Donate button ko handle karega (DM bhejega)"""
    query = update.callback_query
    config = await get_config()
    qr_id = config.get('donate_qr_id')
    
    if not qr_id: 
        msg = await format_message(context, "user_donate_qr_error")
        await query.answer(msg, show_alert=True)
        return

    text = await format_message(context, "user_donate_qr_text")
    
    try:
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="user_back_menu")]]
        
        if not query.message.photo:
                await query.message.delete()
                
        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=qr_id,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        context.job_queue.run_once(send_donate_thank_you, 60, chat_id=query.from_user.id)
    except Exception as e:
        logger.error(f"Donate QR bhejte waqt error: {e}")
        await query.answer("❌ Error! Dobara try karein.", show_alert=True)


# --- Admin Panel ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    """Admin panel ka main menu"""
    user_id = update.effective_user.id
    if not await is_co_admin(user_id):
        if not from_callback: 
            if update.message:
                text = await format_message(context, "user_not_admin")
                await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            else:
                await update.callback_query.answer("Aap admin nahi hain.", show_alert=True)
        return
        
    logger.info("Admin/Co-Admin ne /admin command use kiya.")
    
    if not await is_main_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")],
            [InlineKeyboardButton("🗑️ Delete Content", callback_data="admin_menu_manage_content")], 
            [InlineKeyboardButton("✏️ Edit Content", callback_data="admin_menu_edit_content")], 
            [InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")],
            [
                InlineKeyboardButton("🖼️ Update Photo", callback_data="admin_update_photo"),
                InlineKeyboardButton("🔗 Gen Link", callback_data="admin_gen_link") 
            ]
        ]
        admin_menu_text = await format_message(context, "admin_panel_co")
    
    else:
        keyboard = [
            [InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")],
            [
                InlineKeyboardButton("🗑️ Delete Content", callback_data="admin_menu_manage_content"), 
                InlineKeyboardButton("✏️ Edit Content", callback_data="admin_menu_edit_content") 
            ],
            [
                InlineKeyboardButton("🔗 Other Links", callback_data="admin_menu_other_links"),
                InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")
            ],
            [
                InlineKeyboardButton("❤️ Donation", callback_data="admin_menu_donate_settings"),
                InlineKeyboardButton("⏱️ Auto-Delete Time", callback_data="admin_set_delete_time") 
            ],
            [
                InlineKeyboardButton("🖼️ Update Photo", callback_data="admin_update_photo"), 
                InlineKeyboardButton("🔗 Gen Link", callback_data="admin_gen_link") 
            ],
            [
                InlineKeyboardButton("🖼️ Set Menu Photo", callback_data="admin_set_menu_photo"),# NAYA
                InlineKeyboardButton("🎨 Bot Appearance", callback_data="admin_menu_appearance")
            ],
            [InlineKeyboardButton("⚙ Bot Messages", callback_data="admin_menu_messages")], 
            [InlineKeyboardButton("🛠️ Admin Settings", callback_data="admin_menu_admin_settings")] 
        ]
        admin_menu_text = await format_message(context, "admin_panel_main")
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if from_callback:
        query = update.callback_query
        try:
            if query.message.photo:
                await query.message.delete()
                await context.bot.send_message(query.from_user.id, admin_menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
            else:
                await query.edit_message_text(admin_menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.warning(f"Admin menu edit nahi kar paya: {e}")
            await query.answer()
        except Exception as e:
            logger.warning(f"Admin menu edit error: {e}")
            await query.answer()
    else:
        await update.message.reply_text(admin_menu_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# --- Conversation: Set User Menu Photo ---
async def set_menu_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = await format_message(context, "admin_set_menu_photo_start")
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
    return CS_GET_MENU_PHOTO

async def set_menu_photo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        text = await format_message(context, "admin_set_menu_photo_error")
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return CS_GET_MENU_PHOTO

    photo_id = update.message.photo[-1].file_id
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"user_menu_photo_id": photo_id}}, upsert=True)
    logger.info(f"User menu photo update ho gaya.")
    text = await format_message(context, "admin_set_menu_photo_success")
    await update.message.reply_photo(photo=photo_id, caption=text, parse_mode=ParseMode.HTML)

    await admin_command(update, context, from_callback=False)
    return ConversationHandler.END

async def skip_menu_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"user_menu_photo_id": None}}, upsert=True)
    logger.info(f"User menu photo remove kar diya gaya.")
    text = await format_message(context, "admin_set_menu_photo_skip")
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    await admin_command(update, context, from_callback=False)
    return ConversationHandler.END
# --- User Download Handler (CallbackQuery) ---
async def download_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback data 'dl' se shuru hone wale sabhi buttons ko handle karega.
    """
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    config = await get_config() 
    
    is_deep_link = not hasattr(query.message, 'edit_message_caption')
    is_in_dm = False 
    
    checking_msg_id = None
    
    try:
        # Step 1: Click ko acknowledge karo
        if not is_deep_link:
            is_in_dm = query.message.chat.type == 'private'
            if not is_in_dm:
                alert_msg = await format_message(context, "user_dl_dm_alert")
                # Font-formatted text alert me nahi dikh sakta, isliye <f> tags remove karo
                alert_msg_plain = re.sub(r'<f>(.*?)</f>', r'\1', alert_msg, flags=re.DOTALL)
                await query.answer(alert_msg_plain, show_alert=True)
            else:
                await query.answer()
        
        # Step 2: "Fetching..." message bhejo
        try:
            checking_text = await format_message(context, "user_dl_fetching")
            sent_msg = await context.bot.send_message(chat_id=user_id, text=checking_text, parse_mode=ParseMode.HTML, read_timeout=10, write_timeout=10)
            checking_msg_id = sent_msg.message_id
        except Exception as e:
            logger.error(f"User {user_id} ko 'Fetching...' message nahi bhej paya. Shayad bot block hai? Error: {e}")
            if not is_deep_link and not is_in_dm:
                await query.answer("❌ Error! Bot ko DM mein /start karke unblock karein.", show_alert=True)
            return 

        parts = query.data.split('__')
        
        anime_key = parts[0]
        if anime_key.startswith("dl_"):
            anime_key = anime_key.replace("dl_", "") 
        elif anime_key.startswith("dl"):
            anime_key = anime_key.replace("dl", "")  
            
        season_name = parts[1] if len(parts) > 1 else None
        ep_num = parts[2] if len(parts) > 2 else None
        
        anime_doc = None
        try:
            anime_doc = animes_collection.find_one({"_id": ObjectId(anime_key)})
        except Exception:
            logger.warning(f"ObjectId '{anime_key}' nahi mila. Name se search kar raha hoon...")
            anime_doc = animes_collection.find_one({"name": anime_key})
        
        if not anime_doc:
            logger.error(f"Anime '{anime_key}' na ID se mila na Name se.")
            msg = await format_message(context, "user_dl_anime_not_found")
            await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
            
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
            return
            
        anime_name = anime_doc['name'] 
        anime_id_str = str(anime_doc['_id']) 
        
        delete_time = config.get("delete_seconds", 300) 

        # Case 3: Episode click hua hai -> Saare Files Bhejo
        if ep_num:
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
            
            try:
                if is_in_dm and query.message.photo: 
                    await query.message.delete()
                    logger.info(f"User {user_id} ke liye episode list delete kar di.")
            except Exception as e:
                logger.warning(f"Episode list delete nahi kar paya: {e}")

            qualities_dict = anime_doc.get("seasons", {}).get(season_name, {}).get(ep_num, {})
            if not qualities_dict:
                msg = await format_message(context, "user_dl_episodes_not_found")
                await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
                return
            
            msg = await format_message(context, "user_dl_sending_files", {
                "anime_name": anime_name,
                "season_name": season_name,
                "ep_num": ep_num
            })
            
            sent_msg = await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
            msg_to_delete_id = sent_msg.message_id
            
            QUALITY_ORDER = ['480p', '720p', '1080p', '4K']
            available_qualities = qualities_dict.keys()
            sorted_q_list = [q for q in QUALITY_ORDER if q in available_qualities]
            extra_q = [q for q in available_qualities if q not in sorted_q_list]
            sorted_q_list.extend(extra_q)
            
            delete_minutes = max(1, delete_time // 60)
            warning_template = await format_message(context, "file_warning", {"minutes": str(delete_minutes)})
            
            for quality in sorted_q_list:
                file_id = qualities_dict.get(quality)
                if not file_id: continue
                
                sent_message = None 
                try:
                    # NAYA: Caption ko font ke saath format karo
                    caption_base = "🎬 <b>{anime_name}</b>\nS{season_name} - E{ep_num} ({quality})\n\n{warning_msg}" # <pre> hata diya
                    caption_raw = caption_base.format(
                        anime_name=anime_name,
                        season_name=season_name,
                        ep_num=ep_num,
                        quality=quality,
                        warning_msg=warning_template # Yeh pehle se formatted hai
                    )
                    
                    # File captions hamesha default font me honge
                    font_settings = {"font": "default", "style": "normal"}
                    caption = await apply_font_formatting(caption_raw, font_settings)

                    sent_message = await context.bot.send_video(
                        chat_id=user_id, 
                        video=file_id, 
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"User {user_id} ko file bhejte waqt error: {e}")
                    error_msg_key = "user_dl_blocked_error" if "blocked" in str(e) else "user_dl_file_error"
                    msg = await format_message(context, error_msg_key, {"quality": quality})
                    await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML) 
                
                if sent_message:
                    try:
                        asyncio.create_task(delete_message_later(
                            bot=context.bot, 
                            chat_id=user_id, 
                            message_id=sent_message.message_id, 
                            seconds=delete_time
                        ))
                    except Exception as e:
                        logger.error(f"asyncio.create_task schedule failed for user {user_id}: {e}")
            
            if msg_to_delete_id:
                try:
                    asyncio.create_task(delete_message_later(
                        bot=context.bot,
                        chat_id=user_id,
                        message_id=msg_to_delete_id, 
                        seconds=delete_time 
                    ))
                except Exception as e:
                    logger.error(f"Async 'Sending files...' message delete schedule failed: {e}")
            
            return 
            
        sent_selection_message = None 

        # Case 2: Season click hua hai -> Episode Bhejo
        if season_name:
            episodes = anime_doc.get("seasons", {}).get(season_name, {})
            
            episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
            
            if not episode_keys:
                msg = await format_message(context, "user_dl_episodes_not_found")
                if checking_msg_id:
                    try: await context.bot.delete_message(user_id, checking_msg_id)
                    except Exception: pass
                
                if is_in_dm:
                    if query.message.photo:
                        await query.edit_message_caption(msg, parse_mode=ParseMode.HTML)
                    else:
                        await query.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
                return
            
            sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"dl{anime_id_str}__{season_name}__{ep}") for ep in sorted_eps] 
            keyboard = build_grid_keyboard(buttons, 2)
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"dl{anime_id_str}")]) 
            
            msg = await format_message(context, "user_dl_select_episode", {
                "anime_name": anime_name,
                "season_name": season_name
            })

            season_poster_id = anime_doc.get("seasons", {}).get(season_name, {}).get("_poster_id")
            poster_to_use = season_poster_id or anime_doc['poster_id'] 
            
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
            
            if is_deep_link:
                sent_selection_message = await context.bot.send_photo(
                    chat_id=user_id, 
                    photo=poster_to_use, 
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else: 
                try:
                    if not query.message.photo:
                        await query.message.delete() 
                        sent_selection_message = await context.bot.send_photo(
                            chat_id=user_id,
                            photo=poster_to_use, 
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        await query.edit_message_media(
                            media=InputMediaPhoto(media=poster_to_use, caption=msg, parse_mode=ParseMode.HTML),
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        sent_selection_message = query.message 
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        logger.warning(f"DL Handler Case 2: Media edit fail, fallback to caption: {e}")
                        await query.edit_message_caption( 
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode=ParseMode.HTML
                        )
                        sent_selection_message = query.message 
                except Exception as e:
                    logger.error(f"DL Handler Case 2: Media edit critical fail: {e}")
                    await query.edit_message_caption( 
                        caption=msg,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode=ParseMode.HTML
                    )
                    sent_selection_message = query.message 
            
            if sent_selection_message:
                asyncio.create_task(delete_message_later(
                    bot=context.bot,
                    chat_id=user_id,
                    message_id=sent_selection_message.message_id, 
                    seconds=delete_time 
                ))
            return
            
        # Case 1: Sirf Anime click hua hai -> Season Bhejo
        seasons = anime_doc.get("seasons", {})
        if not seasons:
            msg = await format_message(context, "user_dl_seasons_not_found")
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
                
            if is_in_dm: 
                if query.message.photo:
                    await query.edit_message_caption(msg, parse_mode=ParseMode.HTML)
                else:
                    await query.edit_message_text(msg, parse_mode=ParseMode.HTML)
            else: 
                await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
            return
        
        sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
        buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"dl{anime_id_str}__{s}") for s in sorted_seasons] 
        keyboard = build_grid_keyboard(buttons, 1) 
        keyboard.append([InlineKeyboardButton("⬅️ Back to Bot Menu", callback_data="user_back_menu")])
        
        msg = await format_message(context, "user_dl_select_season", {"anime_name": anime_name})

        if checking_msg_id:
            try: await context.bot.delete_message(user_id, checking_msg_id)
            except Exception: pass
            
        if is_deep_link:
            sent_selection_message = await context.bot.send_photo(
                chat_id=user_id, 
                photo=anime_doc['poster_id'], 
                caption=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
        else: 
            if not query.message.photo:
                await query.message.delete() 
                sent_selection_message = await context.bot.send_photo(
                    chat_id=user_id,
                    photo=anime_doc['poster_id'], 
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
            else:
                await query.edit_message_caption(
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
                sent_selection_message = query.message 

        if sent_selection_message:
            asyncio.create_task(delete_message_later(
                bot=context.bot,
                chat_id=user_id,
                message_id=sent_selection_message.message_id, 
                seconds=delete_time 
            ))
        return

    except Exception as e:
        logger.error(f"Download button handler me error: {e}", exc_info=True)
        if checking_msg_id:
            try: await context.bot.delete_message(user_id, checking_msg_id)
            except Exception: pass
            
        msg = await format_message(context, "user_dl_general_error")
        try:
            if not is_deep_link and query.message and query.message.chat.type in ['channel', 'supergroup', 'group']:
                    await query.answer(msg, show_alert=True)
            else:
                    await context.bot.send_message(user_id, msg, parse_mode=ParseMode.HTML)
        except Exception: pass
        

# --- Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error} \nUpdate: {update}", exc_info=True)

# ============================================
# ===    NAYA WEBHOOK AUR THREADING SETUP    ===
# ============================================

app = Flask(__name__)
bot_app = None
bot_loop = None

@app.route('/')
def home():
    return "I am alive and running!", 200

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    global bot_app, bot_loop
    if request.is_json:
        update_data = request.get_json()
        update = Update.de_json(update_data, bot_app.bot)
        
        try:
            asyncio.run_coroutine_threadsafe(bot_app.process_update(update), bot_loop)
        except Exception as e:
            logger.error(f"Update ko threadsafe bhejne mein error: {e}", exc_info=True)
            
        return "OK", 200
    else:
        return "Bad request", 400

def run_async_bot_tasks(loop, app):
    global bot_loop
    bot_loop = loop 
    asyncio.set_event_loop(loop) 
    
    try:
        webhook_path_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
        logger.info(f"Webhook ko {webhook_path_url} par set kar raha hai...")
        # Use httpx for sync request in async thread setup
        with httpx.Client() as client:
            client.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_path_url}")
        logger.info("Webhook successfully set!")

        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.start())
        logger.info("Bot application initialized and started (async).")
        
        loop.run_forever() 
        
    except Exception as e:
        logger.error(f"Async thread fail ho gaya: {e}", exc_info=True)
    finally:
        logger.info("Async loop stop ho raha hai...")
        loop.run_until_complete(app.stop())
        loop.close()

# --- NAYA Main Bot Function (FINAL) ---
def main():
    global bot_app
    PORT = int(os.environ.get("PORT", 8080))
    
    # NAYA: Default ParseMode set karo
    my_defaults = Defaults(parse_mode=ParseMode.HTML)
    bot_app = Application.builder().token(BOT_TOKEN).defaults(my_defaults).build()
    
    # --- Saare Handlers ---
    
    global_cancel_handler = CommandHandler("cancel", cancel)
    # NAYA: Add Episode ke liye special cancel handler
    add_ep_cancel_handler = CommandHandler("cancel", cancel_add_episode)
    add_season_cancel_handler = CommandHandler("cancel", cancel_add_season)
    
    global_fallbacks = [
        CommandHandler("start", cancel),
        CommandHandler("menu", cancel),
        CommandHandler("admin", cancel),
        global_cancel_handler 
    ]
    admin_menu_fallback = [CallbackQueryHandler(back_to_admin_menu, pattern="^admin_menu$"), global_cancel_handler]
    add_content_fallback = [CallbackQueryHandler(back_to_add_content_menu, pattern="^back_to_add_content$"), global_cancel_handler]
    add_season_fallback = [CallbackQueryHandler(back_to_add_content_menu, pattern="^back_to_add_content$"), add_season_cancel_handler]
    # NAYA: Add Episode ke liye special fallback
    add_episode_fallback = [CallbackQueryHandler(back_to_add_content_menu, pattern="^back_to_add_content$"), add_ep_cancel_handler]
    
    manage_fallback = [CallbackQueryHandler(back_to_manage_menu, pattern="^back_to_manage$"), global_cancel_handler]
    edit_fallback = [CallbackQueryHandler(back_to_edit_menu, pattern="^back_to_edit_menu$"), global_cancel_handler] 
    sub_settings_fallback = [CallbackQueryHandler(back_to_sub_settings_menu, pattern="^back_to_sub_settings$"), global_cancel_handler]
    donate_settings_fallback = [CallbackQueryHandler(back_to_donate_settings_menu, pattern="^back_to_donate_settings$"), global_cancel_handler]
    links_fallback = [CallbackQueryHandler(back_to_links_menu, pattern="^back_to_links$"), global_cancel_handler]
    user_menu_fallback = [CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"), global_cancel_handler]
    messages_fallback = [CallbackQueryHandler(back_to_messages_menu, pattern="^admin_menu_messages$"), global_cancel_handler]
    admin_settings_fallback = [CallbackQueryHandler(back_to_admin_settings_menu, pattern="^back_to_admin_settings$"), global_cancel_handler]
    gen_link_fallback = [CallbackQueryHandler(gen_link_menu, pattern="^admin_gen_link$"), global_cancel_handler]
    appearance_fallback = [CallbackQueryHandler(back_to_appearance_menu, pattern="^back_to_appearance$"), global_cancel_handler]


    add_anime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_anime_start, pattern="^admin_add_anime$")], 
        states={
            A_GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_anime_name)], 
            A_GET_POSTER: [MessageHandler(filters.PHOTO, get_anime_poster)], 
            A_GET_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_anime_desc), CommandHandler("skip", skip_anime_desc)], 
            A_CONFIRM: [CallbackQueryHandler(save_anime_details, pattern="^save_anime$")]
        }, 
        fallbacks=global_fallbacks + add_content_fallback,
        allow_reentry=True 
    )
    add_season_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_season_start, pattern="^admin_add_season$")], 
        states={
            S_GET_ANIME: [
                CallbackQueryHandler(add_season_show_anime_list, pattern="^addseason_page_"),
                CallbackQueryHandler(get_anime_for_season, pattern="^season_anime_")
            ], 
            S_GET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_season_number)], 
            S_GET_POSTER: [
                MessageHandler(filters.PHOTO, get_season_poster), 
                CommandHandler("skip", skip_season_poster)
            ],
            S_GET_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_season_desc),
                CommandHandler("skip", skip_season_desc)
            ],
            S_CONFIRM: [CallbackQueryHandler(save_season, pattern="^save_season$")], # <-- YEH COMMA ADD KARO
            S_ASK_MORE: [ # NAYA State
                CallbackQueryHandler(add_more_seasons_yes, pattern="^add_season_more_yes$"),
                CallbackQueryHandler(add_more_seasons_no, pattern="^add_season_more_no$")
            ]
        }, 
        fallbacks=global_fallbacks + add_season_fallback,
        allow_reentry=True 
    )
    
    # NAYA: Updated Add Episode Conversation
    add_episode_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_episode_start, pattern="^admin_add_episode$")], 
        states={
            E_GET_ANIME: [
                CallbackQueryHandler(add_episode_show_anime_list, pattern="^addep_page_"), 
                CallbackQueryHandler(get_anime_for_episode, pattern="^ep_anime_")
            ], 
            E_GET_SEASON: [
                CallbackQueryHandler(get_season_for_episode, pattern="^ep_season_"),
                CallbackQueryHandler(add_episode_show_anime_list, pattern="^addep_page_") 
            ], 
            E_GET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_episode_number)],
            E_GET_480P: [MessageHandler(filters.ALL & ~filters.COMMAND, get_480p_file), CommandHandler("skip", skip_480p)],
            E_GET_720P: [MessageHandler(filters.ALL & ~filters.COMMAND, get_720p_file), CommandHandler("skip", skip_720p)],
            E_GET_1080P: [MessageHandler(filters.ALL & ~filters.COMMAND, get_1080p_file), CommandHandler("skip", skip_1080p)],
            E_GET_4K: [MessageHandler(filters.ALL & ~filters.COMMAND, get_4k_file), CommandHandler("skip", skip_4k)],
            E_ASK_MORE: [ # NAYA State
                CallbackQueryHandler(add_more_episodes_yes, pattern="^add_ep_more_yes$"),
                CallbackQueryHandler(add_more_episodes_no, pattern="^add_ep_more_no$")
            ]
        }, 
        fallbacks=global_fallbacks + add_episode_fallback, # NAYA: Special fallback
        allow_reentry=True 
    )
    
    set_donate_qr_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_donate_qr_start, pattern="^admin_set_donate_qr$")], 
        states={CD_GET_QR: [MessageHandler(filters.PHOTO, set_donate_qr_save)]}, 
        fallbacks=global_fallbacks + donate_settings_fallback,
        allow_reentry=True 
    )
    set_links_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_links_start, pattern="^admin_set_backup_link$|^admin_set_download_link$|^admin_set_help_link$")], # NAYA
        states={CL_GET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link), CommandHandler("skip", skip_link)]}, 
        fallbacks=global_fallbacks + links_fallback,
        allow_reentry=True 
    ) 
    post_gen_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(post_gen_menu, pattern="^admin_post_gen$")], 
        states={
            PG_MENU: [CallbackQueryHandler(post_gen_select_anime, pattern="^post_gen_season$|^post_gen_episode$|^post_gen_anime$")], 
            PG_GET_ANIME: [
                CallbackQueryHandler(post_gen_show_anime_list, pattern="^postgen_page_"),
                CallbackQueryHandler(post_gen_select_season, pattern="^post_anime_")
            ], 
            PG_GET_SEASON: [
                CallbackQueryHandler(post_gen_select_episode, pattern="^post_season_"),
                CallbackQueryHandler(post_gen_show_anime_list, pattern="^postgen_page_") 
            ], 
            PG_GET_EPISODE: [
                CallbackQueryHandler(post_gen_final_episode, pattern="^post_ep_"),
                CallbackQueryHandler(post_gen_select_season, pattern="^post_anime_") 
            ], 
            PG_GET_SHORT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_gen_get_short_link)],
            PG_GET_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_gen_send_to_chat)]
        }, 
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True 
    )
    del_anime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_anime_start, pattern="^admin_del_anime$")], 
        states={
            DA_GET_ANIME: [
                CallbackQueryHandler(delete_anime_show_anime_list, pattern="^delanime_page_"),
                CallbackQueryHandler(delete_anime_confirm, pattern="^del_anime_")
            ], 
            DA_CONFIRM: [CallbackQueryHandler(delete_anime_do, pattern="^del_anime_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    del_season_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_season_start, pattern="^admin_del_season$")], 
        states={
            DS_GET_ANIME: [
                CallbackQueryHandler(delete_season_show_anime_list, pattern="^delseason_page_"),
                CallbackQueryHandler(delete_season_select, pattern="^del_season_anime_")
            ], 
            DS_GET_SEASON: [
                CallbackQueryHandler(delete_season_confirm, pattern="^del_season_"),
                CallbackQueryHandler(delete_season_show_anime_list, pattern="^delseason_page_") 
            ], 
            DS_CONFIRM: [CallbackQueryHandler(delete_season_do, pattern="^del_season_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    del_episode_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_episode_start, pattern="^admin_del_episode$")], 
        states={
            DE_GET_ANIME: [
                CallbackQueryHandler(delete_episode_show_anime_list, pattern="^delep_page_"),
                CallbackQueryHandler(delete_episode_select_season, pattern="^del_ep_anime_")
            ],
          DE_GET_SEASON: [
                CallbackQueryHandler(delete_episode_select_episode, pattern="^del_ep_season_"),
                CallbackQueryHandler(delete_episode_show_anime_list, pattern="^delep_page_") 
            ],
            DE_GET_EPISODE: [
                CallbackQueryHandler(delete_episode_confirm, pattern="^del_ep_num_"),
                CallbackQueryHandler(delete_episode_select_season, pattern="^del_ep_anime_") 
            ],
            DE_CONFIRM: [CallbackQueryHandler(delete_episode_do, pattern="^del_ep_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    update_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_photo_start, pattern="^admin_update_photo$")],
        states={
            UP_GET_ANIME: [
                CallbackQueryHandler(update_photo_show_anime_list, pattern="^upphoto_page_"),
                CallbackQueryHandler(update_photo_select_target, pattern="^upphoto_anime_")
            ],
            UP_GET_TARGET: [
                CallbackQueryHandler(update_photo_get_poster, pattern="^upphoto_target_"),
                CallbackQueryHandler(update_photo_show_anime_list, pattern="^upphoto_page_") 
            ],
            UP_GET_POSTER: [
                MessageHandler(filters.PHOTO, update_photo_save),
                MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.PHOTO, update_photo_invalid_input)
            ]
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    edit_anime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_anime_start, pattern="^admin_edit_anime$")],
        states={
            EA_GET_ANIME: [
                CallbackQueryHandler(edit_anime_show_anime_list, pattern="^editanime_page_"),
                CallbackQueryHandler(edit_anime_get_new_name, pattern="^edit_anime_")
            ],
            EA_GET_NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_anime_save)],
            EA_CONFIRM: [CallbackQueryHandler(edit_anime_do, pattern="^edit_anime_confirm_yes$")]
        },
        fallbacks=global_fallbacks + edit_fallback,
        allow_reentry=True
    )
    edit_season_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_season_start, pattern="^admin_edit_season$")],
        states={
            ES_GET_ANIME: [
                CallbackQueryHandler(edit_season_show_anime_list, pattern="^editseason_page_"),
                CallbackQueryHandler(edit_season_select, pattern="^edit_season_anime_")
            ],
            ES_GET_SEASON: [
                CallbackQueryHandler(edit_season_get_new_name, pattern="^edit_season_"),
                CallbackQueryHandler(edit_season_show_anime_list, pattern="^editseason_page_") 
            ],
            ES_GET_NEW_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_season_save)],
            ES_CONFIRM: [CallbackQueryHandler(edit_season_do, pattern="^edit_season_confirm_yes$")]
        },
        fallbacks=global_fallbacks + edit_fallback,
        allow_reentry=True
    )
    edit_episode_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_episode_start, pattern="^admin_edit_episode$")],
        states={
            EE_GET_ANIME: [
                CallbackQueryHandler(edit_episode_show_anime_list, pattern="^editep_page_"),
                CallbackQueryHandler(edit_episode_select_season, pattern="^edit_ep_anime_")
            ],
            EE_GET_SEASON: [
                CallbackQueryHandler(edit_episode_select_episode, pattern="^edit_ep_season_"),
                CallbackQueryHandler(edit_episode_show_anime_list, pattern="^editep_page_") 
            ],
            EE_GET_EPISODE: [
                CallbackQueryHandler(edit_episode_get_new_num, pattern="^edit_ep_num_"),
                CallbackQueryHandler(edit_episode_select_season, pattern="^edit_ep_anime_") 
            ],
            EE_GET_NEW_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_episode_save)],
            EE_CONFIRM: [CallbackQueryHandler(edit_episode_do, pattern="^edit_ep_confirm_yes$")]
        },
        fallbacks=global_fallbacks + edit_fallback,
        allow_reentry=True
    )

    gen_link_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(gen_link_menu, pattern="^admin_gen_link$")],
        states={
            GL_MENU: [CallbackQueryHandler(gen_link_select_anime, pattern="^gen_link_anime$|^gen_link_season$|^gen_link_episode$")],
            GL_GET_ANIME: [
                CallbackQueryHandler(gen_link_show_anime_list, pattern="^genlink_page_"),
                CallbackQueryHandler(gen_link_select_season, pattern="^gen_link_anime_")
            ],
            GL_GET_SEASON: [
                CallbackQueryHandler(gen_link_select_episode, pattern="^gen_link_season_"),
                CallbackQueryHandler(gen_link_show_anime_list, pattern="^genlink_page_") 
            ],
            GL_GET_EPISODE: [
                CallbackQueryHandler(gen_link_finish, pattern="^gen_link_ep_"),
                CallbackQueryHandler(gen_link_select_season, pattern="^gen_link_anime_") 
            ],
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    add_co_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(co_admin_add_start, pattern="^admin_add_co_admin$")],
        states={
            CA_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, co_admin_add_get_id)],
            CA_CONFIRM: [CallbackQueryHandler(co_admin_add_do, pattern="^co_admin_add_yes$")]
        },
        fallbacks=global_fallbacks + admin_settings_fallback,
        allow_reentry=True
    )
    remove_co_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(co_admin_remove_start, pattern="^admin_remove_co_admin$")],
        states={
            CR_GET_ID: [CallbackQueryHandler(co_admin_remove_confirm, pattern="^co_admin_rem_")],
            CR_CONFIRM: [CallbackQueryHandler(co_admin_remove_do, pattern="^co_admin_rem_yes$")]
        },
        fallbacks=global_fallbacks + admin_settings_fallback,
        allow_reentry=True
    )
    custom_post_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(custom_post_start, pattern="^admin_custom_post$")],
        states={
            CPOST_GET_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_post_get_chat)],
            CPOST_GET_POSTER: [MessageHandler(filters.PHOTO, custom_post_get_poster)],
            CPOST_GET_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_post_get_caption)],
            CPOST_GET_BTN_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_post_get_btn_text)],
            CPOST_GET_BTN_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_post_get_btn_url)],
            CPOST_CONFIRM: [CallbackQueryHandler(custom_post_send, pattern="^cpost_send$")]
        },
        fallbacks=global_fallbacks + admin_settings_fallback,
        allow_reentry=True
    )
    set_delete_time_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_delete_time_start, pattern="^admin_set_delete_time$")],
        states={CS_GET_DELETE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_delete_time_save)]},
        fallbacks=global_fallbacks + admin_menu_fallback, 
        allow_reentry=True 
    )
    set_messages_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_messages_menu, pattern="^admin_menu_messages$")],
        states={
            M_MENU_MAIN: [
                CallbackQueryHandler(bot_messages_menu_dl, pattern="^msg_menu_dl$"),
                CallbackQueryHandler(bot_messages_menu_postgen, pattern="^msg_menu_postgen$"),
                CallbackQueryHandler(bot_messages_menu_gen, pattern="^msg_menu_gen$"),
                CallbackQueryHandler(bot_messages_menu_admin, pattern="^msg_menu_admin$"),
            ],
            M_MENU_DL: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_POSTGEN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_GEN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_ADMIN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_GET_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_msg_save)],
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    appearance_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(appearance_menu_start, pattern="^admin_menu_appearance$")],
        states={
            AP_MENU: [
                CallbackQueryHandler(appearance_set_font, pattern="^app_set_font$"),
                CallbackQueryHandler(appearance_set_style, pattern="^app_set_style$")
            ],
            AP_SET_FONT: [
                CallbackQueryHandler(appearance_save_font, pattern="^app_font_"),
                CallbackQueryHandler(back_to_appearance_menu, pattern="^back_to_appearance$")
            ],
            AP_SET_STYLE: [
                CallbackQueryHandler(appearance_save_style, pattern="^app_style_"),
                CallbackQueryHandler(back_to_appearance_menu, pattern="^back_to_appearance$")
            ]
        },
        fallbacks=global_fallbacks + admin_menu_fallback + appearance_fallback,
        allow_reentry=True
    )
    
    # --- Saare handlers ko bot_app me add karo ---
    bot_app.add_handler(add_anime_conv)
    bot_app.add_handler(add_season_conv)
    bot_app.add_handler(add_episode_conv)
    bot_app.add_handler(set_donate_qr_conv)
    bot_app.add_handler(set_links_conv)
    bot_app.add_handler(post_gen_conv)
    bot_app.add_handler(del_anime_conv)
    bot_app.add_handler(del_season_conv)
    bot_app.add_handler(del_episode_conv)
    bot_app.add_handler(update_photo_conv) 
    bot_app.add_handler(edit_anime_conv)
    bot_app.add_handler(edit_season_conv)
    bot_app.add_handler(edit_episode_conv)
    bot_app.add_handler(gen_link_conv)
    bot_app.add_handler(add_co_admin_conv) 
    bot_app.add_handler(remove_co_admin_conv) 
    bot_app.add_handler(custom_post_conv) 
    bot_app.add_handler(set_delete_time_conv) 
    bot_app.add_handler(set_messages_conv) 
    bot_app.add_handler(appearance_conv)

    set_menu_photo_conv = ConversationHandler(
       entry_points=[CallbackQueryHandler(set_menu_photo_start, pattern="^admin_set_menu_photo$")],
       states={
           CS_GET_MENU_PHOTO: [
               MessageHandler(filters.PHOTO, set_menu_photo_save),
               CommandHandler("skip", skip_menu_photo)
           ]
       },
       fallbacks=global_fallbacks + admin_menu_fallback,
       allow_reentry=True
    )
    bot_app.add_handler(set_menu_photo_conv)

    # Standard commands
    bot_app.add_handler(CommandHandler("start", start_command)) 
    bot_app.add_handler(CommandHandler("user", user_command)) 
    bot_app.add_handler(CommandHandler("menu", menu_command)) 
    bot_app.add_handler(CommandHandler("admin", admin_command)) 

    # Admin menu navigation (non-conversation)
    bot_app.add_handler(CallbackQueryHandler(add_content_menu, pattern="^admin_menu_add_content$"))
    bot_app.add_handler(CallbackQueryHandler(manage_content_menu, pattern="^admin_menu_manage_content$"))
    bot_app.add_handler(CallbackQueryHandler(edit_content_menu, pattern="^admin_menu_edit_content$")) 
    bot_app.add_handler(CallbackQueryHandler(donate_settings_menu, pattern="^admin_menu_donate_settings$"))
    bot_app.add_handler(CallbackQueryHandler(other_links_menu, pattern="^admin_menu_other_links$"))
    bot_app.add_handler(CallbackQueryHandler(admin_settings_menu, pattern="^admin_menu_admin_settings$")) 
    bot_app.add_handler(CallbackQueryHandler(co_admin_list, pattern="^admin_list_co_admin$")) 

    # User menu navigation (non-conversation)
    bot_app.add_handler(CallbackQueryHandler(user_show_donate_menu, pattern="^user_show_donate_menu$"))
    bot_app.add_handler(CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"))

# User Download Flow (Non-conversation)
    bot_app.add_handler(CallbackQueryHandler(download_button_handler, pattern="^dl"))

    # Error handler
    bot_app.add_error_handler(error_handler)

    # --- NAYA: Webhook setup ---
    logger.info("Starting Flask server for webhook...")
    
    # Start the bot in a separate thread
    bot_event_loop = asyncio.new_event_loop()
    bot_thread = threading.Thread(target=run_async_bot_tasks, args=(bot_event_loop, bot_app))
    bot_thread.start()
    
    # Start Flask app (Waitress)
    logger.info(f"Flask (Waitress) server {WEBHOOK_URL} port {PORT} par sun raha hai...")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    main()


