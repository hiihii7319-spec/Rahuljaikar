# ============================================
# ===       COMPLETE FINAL FIX (v29)       ===
# ============================================
# === (FEAT: Add "Generate Link" System)   ===
# === (FIX: "Fetching" Msg Deletion)       ===
# === (FEAT: 2x2 Admin Button Layout)      ===
# === (FEAT: Add Edit Content Menus)       ===
# === (FIX: Crash on Deep Link 'delete')   ===
# === (FIX: Command Remapping /start)      ===
# === (FEAT: Add "Complete Anime" Post)    ===
# === (FIX: DB Migration Conflict)         ===
# === (FEAT: Remove Sub/Support System)    ===
# === (FEAT: Add Admin Download Link)      ===
# === (FEAT: Add Post Shortener Step)      ===
# === (FEAT: Instant Ep List Deletion)     ===
# === (FIX: Deep Link 'dl' Handler)        ===
# ============================================
# === (USER REQ: Remove Quote Box)         ===
# === (FEAT: Add Monospace/Bold/Italic)    ===
# === (FIX: Font System vs Clickable Links)===
# === (REFACTOR: All ParseMode to HTML)    ===
# === (FIX: Fallback Message Error)        ===
# ============================================
import os
import logging
import re
import asyncio # Auto-delete aur Threading ke liye
import threading # Threading ke liye
import httpx # Webhook set karne ke liye
import html # NAYA: Font change ke liye
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING # NAYA: DESCENDING add kiya
from bson.objectid import ObjectId # NAYA (v13): ID se search ke liye
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, User, InputMediaPhoto
from telegram.constants import ParseMode # MODIFIED: HTML use karenge
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.error import BadRequest
# Flask server ke liye
from flask import Flask, request # NAYA: 'request' add kiya
from waitress import serve 

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
    WEBHOOK_URL = os.environ.get('WEBHOOK_URL') # NAYA: Webhook URL
    
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
    
    # Index add karo (Search ke liye name, Naye ke liye created_at)
    animes_collection.create_index([("name", ASCENDING)])
    animes_collection.create_index([("created_at", DESCENDING)]) # NAYA: Newest first ke liye
    
    client.admin.command('ping') # Check connection
    logger.info("MongoDB se successfully connect ho gaya!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit()

# NAYA (v10): Pagination ke liye constant
ITEMS_PER_PAGE = 8 # 2x4 grid = 8 items

# --- NAYA: Font Change Constants ---
# User Request: ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘQʀꜱᴛᴜᴠᴡxʏᴢ
FONT_MAP_APPLE_SMALL_CAPS = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'Q', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ', 'G': 'ɢ', 
    'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 
    'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'Q', 'R': 'ʀ', 'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 
    'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x', 'Y': 'ʏ', 'Z': 'ᴢ'
}

# Extra Font: Sans Serif Bold
FONT_MAP_SANS_BOLD = {
    'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳', 'g': '𝗴', 'h': '𝗵', 
    'i': '𝗶', 'j': '𝗷', 'k': '𝗸', 'l': '𝗹', 'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 
    'q': '𝗾', 'r': '𝗿', 's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅', 
    'y': '𝘆', 'z': '𝘇',
    'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙', 'G': '𝗚', 'H': '𝗛', 
    'I': '𝗜', 'J': '𝗝', 'K': '𝗞', 'L': '𝗟', 'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 
    'Q': '𝗤', 'R': '𝗥', 'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫', 
    'Y': '𝗬', 'Z': '𝗭',
    '0': '𝟬', '1': '𝟭', '2': '𝟮', '3': '𝟯', '4': '𝟰', '5': '𝟱', '6': '𝟲', '7': '𝟳', 
    '8': '𝟴', '9': '𝟵'
}

FONT_MAPS = {
    "apple": FONT_MAP_APPLE_SMALL_CAPS,
    "sans_bold": FONT_MAP_SANS_BOLD
}

# --- NAYA: Font & Quote Helper Functions ---

def apply_font(text: str, font: str) -> str:
    """
    Applies the selected font to the text, skipping links, commands, and HTML tags.
    MODIFIED: Ab 'bold', 'italic', 'monospace' ko bhi handle karta hai.
    """
    if font == "default":
        return text
    
    # Regex to find parts to *not* convert:
    # 1. HTML tags: <...>
    # 2. Code blocks: <code>...</code>
    # 3. Links/Commands: http://, https://, t.me/, /start
    skip_pattern = re.compile(
        r'(<[^>]+>|<code>.*?</code>|(?:\b(?:https?://|t\.me/|/)\S+))',
        re.IGNORECASE
    )
    
    parts = skip_pattern.split(text)
    new_parts = []
    
    for part in parts:
        if part is None or part == "":
            continue
        
        # Check if this part matches any of the skip patterns
        if skip_pattern.fullmatch(part):
            new_parts.append(part) # Don't convert, add as is
            continue

        # This is normal text, apply font
        # Pehle se HTML escape karo taaki tags toot na jaayein
        part = html.escape(part)

        if font in FONT_MAPS:
            # Character-map fonts
            font_map = FONT_MAPS[font]
            new_parts.append("".join([font_map.get(char, char) for char in part]))
        elif font == "bold":
            new_parts.append(f"<b>{part}</b>")
        elif font == "italic":
            new_parts.append(f"<i>{part}</i>")
        elif font == "monospace":
            new_parts.append(f"<code>{part}</code>")
        else:
            # Unknown font, just add the part
            new_parts.append(part)
            
    return "".join(new_parts)

async def format_bot_reply(text: str) -> (str, str):
    """
    Applies selected font to a message.
    Returns (formatted_text, ParseMode.HTML)
    """
    config = await get_config()
    prefs = config.get("bot_preferences", {})
    
    font = prefs.get("font", "default")
    
    # 1. Apply Font (if not default)
    if font != "default":
        final_text = apply_font(text, font)
    else:
        final_text = text
        
    # 2. REMOVED: Quote Box logic
        
    return final_text, ParseMode.HTML

# --- NAYA: Wrapper functions for sending formatted messages ---
# In helper functions ko use karke humein har jagah manually format nahi karna padega

async def send_formatted_message(
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    text: str, 
    **kwargs
):
    """Sends a new message using the bot's format settings."""
    formatted_text, parse_mode = await format_bot_reply(text)
    kwargs['parse_mode'] = parse_mode
    return await context.bot.send_message(chat_id=chat_id, text=formatted_text, **kwargs)

async def reply_formatted_text(
    update: Update, 
    text: str, 
    **kwargs
):
    """Replies to a user's message using the bot's format settings."""
    formatted_text, parse_mode = await format_bot_reply(text)
    kwargs['parse_mode'] = parse_mode
    return await update.message.reply_text(text=formatted_text, **kwargs)

async def edit_formatted_message_text(
    context: ContextTypes.DEFAULT_TYPE, # NAYA FIX: Context add kiya
    query: Update.callback_query, 
    text: str, 
    **kwargs
):
    """Edits an existing message text using the bot's format settings."""
    try:
        formatted_text, parse_mode = await format_bot_reply(text)
        kwargs['parse_mode'] = parse_mode
        return await query.edit_message_text(text=formatted_text, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Edit formatted text failed: {e}")
            # Fallback: Send new message if edit fails
            try:
                await query.answer()
                # NAYA FIX: Fallback ko 'context' aur 'text' pass karo
                return await send_formatted_message(
                    context, # <-- Pass context
                    query.message.chat.id, 
                    text, # <-- Pass text
                    reply_markup=kwargs.get('reply_markup')
                )
            except Exception as e2:
                logger.error(f"Edit formatted text fallback failed: {e2}")
        else:
            await query.answer() # Answer query even if not modified
    except Exception as e:
        logger.error(f"Edit formatted text critical fail: {e}")

async def send_formatted_photo(
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    photo: str, 
    caption: str, 
    **kwargs
):
    """Sends a photo with a caption using the bot's format settings."""
    formatted_caption, parse_mode = await format_bot_reply(caption)
    kwargs['parse_mode'] = parse_mode
    return await context.bot.send_photo(
        chat_id=chat_id, 
        photo=photo, 
        caption=formatted_caption, 
        **kwargs
    )

async def reply_formatted_photo(
    update: Update, 
    photo: str, 
    caption: str, 
    **kwargs
):
    """Replies with a photo and caption using the bot's format settings."""
    formatted_caption, parse_mode = await format_bot_reply(caption)
    kwargs['parse_mode'] = parse_mode
    return await update.message.reply_photo(
        photo=photo, 
        caption=formatted_caption, 
        **kwargs
    )

async def edit_formatted_message_caption(
    context: ContextTypes.DEFAULT_TYPE, # NAYA FIX: Context add kiya
    query: Update.callback_query, 
    caption: str, 
    **kwargs
):
    """Edits an existing message's caption using the bot's format settings."""
    try:
        formatted_caption, parse_mode = await format_bot_reply(caption)
        kwargs['parse_mode'] = parse_mode
        return await query.edit_message_caption(caption=formatted_caption, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Edit formatted caption failed: {e}")
            # NAYA FIX: Fallback add kiya
            try:
                # Sirf text bhej do agar caption edit fail ho
                await query.answer()
                return await send_formatted_message(
                    context, 
                    query.message.chat.id, 
                    caption, 
                    reply_markup=kwargs.get('reply_markup')
                )
            except Exception as e2:
                logger.error(f"Edit formatted caption fallback failed: {e2}")
        else:
            await query.answer()
    except Exception as e:
        logger.error(f"Edit formatted caption critical fail: {e}")

async def edit_formatted_message_media(
    context: ContextTypes.DEFAULT_TYPE, # NAYA FIX: Context add kiya
    query: Update.callback_query, 
    media: InputMediaPhoto, 
    **kwargs
):
    """Edits an existing message's media, formatting the caption."""
    try:
        formatted_caption, parse_mode = await format_bot_reply(media.caption)
        media.parse_mode = parse_mode
        media.caption = formatted_caption
        return await query.edit_message_media(media=media, **kwargs)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.warning(f"Edit formatted media failed: {e}")
            # NAYA FIX: Fallback
            try:
                # Agar media edit fail ho, to sirf caption edit try karo
                await edit_formatted_message_caption(context, query, media.caption, reply_markup=kwargs.get('reply_markup'))
            except Exception as e2:
                 logger.error(f"Edit formatted media fallback failed: {e2}")
        else:
            await query.answer()
    except Exception as e:
        logger.error(f"Edit formatted media critical fail: {e}")

# --- Admin & Co-Admin Checks ---
async def is_main_admin(user_id: int) -> bool:
    """Check if user is ONLY the main admin"""
    return user_id == ADMIN_ID

async def is_co_admin(user_id: int) -> bool:
    """Check if user is main admin OR co-admin"""
    if user_id == ADMIN_ID:
        return True
    config = await get_config()
    return user_id in config.get("co_admins", [])


# --- Config Helper (NAYA FEATURE: Bahut Saare Custom Messages) ---
async def get_config():
    """Database se bot config fetch karega"""
    config = config_collection.find_one({"_id": "bot_config"})
    
    # NAYA: Default messages ki poori list
    # MODIFIED: All messages converted to HTML ParseMode
    default_messages = {
        # Subscription Flow (REMOVED)
        
        # Download Flow
        "user_dl_dm_alert": "✅ Check your DM (private chat) with me!",
        "user_dl_anime_not_found": "❌ Error: Anime nahi mila.",
        "user_dl_file_error": "❌ Error! {quality} file nahi bhej paya. Please try again.",
        "user_dl_blocked_error": "❌ Error! File nahi bhej paya. Aapne bot ko block kiya hua hai.",
        "user_dl_episodes_not_found": "❌ Error: Is season ke liye episodes nahi mile.",
        "user_dl_seasons_not_found": "❌ Error: Is anime ke liye seasons nahi mile.",
        "user_dl_general_error": "❌ Error! Please try again.",
        "user_dl_sending_files": "✅ <b>{anime_name}</b> | <b>S{season_name}</b> | <b>E{ep_num}</b>\n\nAapke saare files bhej raha hoon...",
        "user_dl_select_episode": "<b>{anime_name}</b> | <b>Season {season_name}</b>\n\nEpisode select karein:",
        "user_dl_select_season": "<b>{anime_name}</b>\n\nSeason select karein:",
        "file_warning": "⚠️ <b>Yeh file {minutes} minute(s) mein automatically delete ho jaayegi.</b>",

        # General
        "user_menu_greeting": "Salaam {first_name}! Ye raha aapka menu:",
        "user_donate_qr_error": "❌ Donation info abhi admin ne set nahi ki hai.",
        "user_donate_qr_text": "❤️ <b>Support Us!</b>\n\nAgar aapko hamara kaam pasand aata hai, toh aap humein support kar sakte hain.",
        "donate_thanks": "❤️ Support karne ke liye shukriya!",
        
        # Post Generator Messages
        # ============================================
        # ===           NAYA FIX (v23)             ===
        # ============================================
        "post_gen_anime_caption": "✅ <b>{anime_name}</b>\n\n<b>📖 Synopsis:</b>\n{description}\n\nNeeche [Download] button dabake download karein!", # NAYA
        # ============================================
        "post_gen_season_caption": "✅ <b>{anime_name}</b>\n<b>[ S{season_name} ]</b>\n\n<b>📖 Synopsis:</b>\n{description}\n\nNeeche [Download] button dabake download karein!",
        "post_gen_episode_caption": "✨ <b>Episode {ep_num} Added</b> ✨\n\n🎬 <b>Anime:</b> {anime_name}\n➡️ <b>Season:</b> {season_name}\n\nNeeche [Download] button dabake download karein!",
        
        # Generate Link Messages (REMOVED)
    }

    if not config:
        default_config = {
            "_id": "bot_config", "donate_qr_id": None, 
            "links": {"backup": None, "download": None}, # MODIFIED: Removed support, added download
            "delete_seconds": 300, # NAYA: 5 Minute (300 sec)
            "messages": default_messages,
            "co_admins": [], # NAYA: Co-admin list
            "bot_preferences": { # MODIFIED: Removed Quote Box
                "font": "default"
            }
        }
        config_collection.insert_one(default_config)
        return default_config
    
    # --- Compatibility aur Migration ---
    needs_update = False
    
    # REMOVED: validity_days check
    if "delete_seconds" not in config: 
        config["delete_seconds"] = 300 # NAYA: 5 min
        needs_update = True
    if "co_admins" not in config:
        config["co_admins"] = []
        needs_update = True
    
    # NAYA: Bot Preferences Migration
    if "bot_preferences" not in config:
        config["bot_preferences"] = {
            "font": "default"
        }
        needs_update = True
    
    # MODIFIED: Remove old quote box keys if they exist
    if "quote_box_text" in config.get("bot_preferences", {}):
        config_collection.update_one(
            {"_id": "bot_config"},
            {"$unset": {
                "bot_preferences.quote_box_text": "",
                "bot_preferences.quote_box_enabled": ""
            }}
        )
        # Refetch config after update
        config = config_collection.find_one({"_id": "bot_config"})


    if "messages" not in config: 
        config["messages"] = {}
        needs_update = True

    # Check karo ki saare default messages config me hain ya nahi
    for key, value in default_messages.items():
        if key not in config["messages"]:
            config["messages"][key] = value
            needs_update = True
    
    # Remove old messages if they exist
    messages_to_remove = [
        "user_sub_qr_error", "user_sub_qr_text", "user_sub_ss_prompt", "user_sub_ss_not_photo",
        "user_sub_ss_error", "sub_pending", "sub_approved", "sub_rejected", "user_sub_removed",
        "user_already_subscribed", "user_dl_unsubscribed_alert", "user_dl_unsubscribed_dm",
        "user_dl_checking_sub", "gen_link_caption_anime", "gen_link_caption_ep", "gen_link_caption_season"
    ]

    # --- NAYA FIX SHURU (Conflict aur IndentationError ke liye) ---
    keys_to_actually_remove = []
    if "messages" in config:
        for key in messages_to_remove:
            if key in config["messages"]:
                keys_to_actually_remove.append(key)
                needs_update = True
    
    # Pehle Python mein keys delete karo
    if keys_to_actually_remove:
        for key in keys_to_actually_remove:
            del config["messages"][key] 
    # --- NAYA FIX KHATAM ---

    if needs_update:
        update_set = {
            "messages": config["messages"], # Ab yeh object saaf hai
            "delete_seconds": config.get("delete_seconds", 300),
            "co_admins": config.get("co_admins", []),
            "bot_preferences": config.get("bot_preferences") # NAYA
        }
        # update_unset ko poori tarah hata diya gaya hai
        
        config_collection.update_one(
            {"_id": "bot_config"}, 
            {
                "$set": update_set
                # "$unset" waali line yahan se hata di gayi hai
            }
        )
        
    if "donate" in config.get("links", {}): 
        config_collection.update_one({"_id": "bot_config"}, {"$unset": {"links.donate": ""}})
    
    # MODIFIED: Remove support link, add download link if missing
    if "links" in config:
        if "support" in config["links"]:
            config_collection.update_one({"_id": "bot_config"}, {"$unset": {"links.support": ""}})
        if "download" not in config["links"]:
            # Pehle 'download' set karte the, ab 'dl_link' set karte hain.
            # Dono check kar lete hain safety ke liye.
            if "dl_link" in config["links"]: # Purana naam
                 config_collection.update_one({"_id": "bot_config"}, {"$rename": {"links.dl_link": "links.download"}})
            else:
                 config_collection.update_one({"_id": "bot_config"}, {"$set": {"links.download": None}})

    return config

# --- Subscription Check Helper (REMOVED) ---
# (All calls to check_subscription() must be removed)

# NAYA FIX: 2x2 Grid Helper
def build_grid_keyboard(buttons, items_per_row=2):
    """Buttons ki list ko 2x2 grid keyboard me badalta hai."""
    keyboard = []
    row = []
    for button in buttons:
        row.append(button)
        if len(row) == items_per_row:
            keyboard.append(row)
            row = []
    if row: # Bachi hui buttons ko add karo
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
    """
    "Newest First" ke hisaab se paginated keyboard banata hai.
    """
    if filter_query is None:
        filter_query = {}
        
    skip = page * ITEMS_PER_PAGE
    total_items = collection.count_documents(filter_query)
    
    # Hamesha naye se puraane sort karo
    items = list(collection.find(filter_query).sort("created_at", DESCENDING).skip(skip).limit(ITEMS_PER_PAGE))
    
    if not items and page == 0:
        return None, InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_callback)]])

    buttons = []
    for item in items:
        # Check if item is an anime document
        if "name" in item:
            buttons.append(InlineKeyboardButton(item['name'], callback_data=f"{item_callback_prefix}{item['name']}"))
        # Check if item is a user document
        elif "first_name" in item:
            user_id = item['_id']
            first_name = item.get('first_name', f"ID: {user_id}")
            buttons.append(InlineKeyboardButton(first_name, callback_data=f"{item_callback_prefix}{user_id}"))

    # NAYA (v10): Use 2x2 Grid
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
        config = await get_config()
        msg = config.get("messages", {}).get("donate_thanks", "❤️ Support karne ke liye shukriya!")
        # NAYA: Use formatted sender
        await send_formatted_message(context, chat_id=job.chat_id, text=msg)
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

# --- Conversation States ---
(A_GET_NAME, A_GET_POSTER, A_GET_DESC, A_CONFIRM) = range(4)
# NAYA (v10): Add Season Description
(S_GET_ANIME, S_GET_NUMBER, S_GET_POSTER, S_GET_DESC, S_CONFIRM) = range(4, 9)
(E_GET_ANIME, E_GET_SEASON, E_GET_NUMBER, E_GET_480P, E_GET_720P, E_GET_1080P, E_GET_4K) = range(9, 16)
# (CS_GET_QR,) = range(16, 17) # REMOVED
(CD_GET_QR,) = range(17, 18)
# (CP_GET_PRICE,) = range(18, 19) # REMOVED
(CL_GET_LINK,) = range(19, 20) # MODIFIED (Was 19-22)
(PG_MENU, PG_GET_ANIME, PG_GET_SEASON, PG_GET_EPISODE, PG_GET_SHORT_LINK, PG_GET_CHAT) = range(22, 28) # NAYA: Short Link
(DA_GET_ANIME, DA_CONFIRM) = range(28, 30)
(DS_GET_ANIME, DS_GET_SEASON, DS_CONFIRM) = range(30, 33)
(DE_GET_ANIME, DE_GET_SEASON, DE_GET_EPISODE, DE_CONFIRM) = range(33, 37)
# (SUB_GET_SCREENSHOT,) = range(36, 37) # REMOVED
# (ADMIN_GET_DAYS,) = range(37, 38) # REMOVED
# (CV_GET_DAYS,) = range(38, 39) # REMOVED
(M_GET_DONATE_THANKS, M_GET_FILE_WARNING) = range(39, 41) # MODIFIED (Removed sub messages)
(CS_GET_DELETE_TIME,) = range(44, 45)
# (RS_GET_ID, RS_CONFIRM) = range(45, 47) # REMOVED

# NAYA (v10): Change Poster States (Update Photo)
(UP_GET_ANIME, UP_GET_TARGET, UP_GET_POSTER) = range(47, 50)

# NAYA: Co-Admin States
(CA_GET_ID, CA_CONFIRM) = range(50, 52)
(CR_GET_ID, CR_CONFIRM) = range(52, 54)

# NAYA: Custom Post States
(CPOST_GET_CHAT, CPOST_GET_POSTER, CPOST_GET_CAPTION, CPOST_GET_BTN_TEXT, CPOST_GET_BTN_URL, CPOST_CONFIRM) = range(54, 60)

# --- NAYA (v27): Edit States ---
(EA_GET_ANIME, EA_GET_NEW_NAME, EA_CONFIRM) = range(60, 63)
(ES_GET_ANIME, ES_GET_SEASON, ES_GET_NEW_NAME, ES_CONFIRM) = range(63, 67)
(EE_GET_ANIME, EE_GET_SEASON, EE_GET_EPISODE, EE_GET_NEW_NUM, EE_CONFIRM) = range(67, 72)
# ---

# NAYA: Bot Messages States (v10: Gen-Link state)
(M_MENU_MAIN, M_MENU_DL, M_MENU_GEN, M_MENU_POSTGEN, M_GET_MSG) = range(72, 77) # MODIFIED (Removed sub and genlink)

# --- NAYA: Generate Link States ---
(GL_MENU, GL_GET_ANIME, GL_GET_SEASON, GL_GET_EPISODE) = range(77, 81) 

# NAYA: Bot Preferences States (REMOVED QUOTE STATES)
(BP_MENU, BP_FONT_MENU) = range(81, 83)

# --- NAYA: Global Cancel Function ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the current conversation."""
    user = update.effective_user
    logger.info(f"User {user.id} ne operation cancel kiya.")
    if context.user_data:
        context.user_data.clear()
    
    reply_text = "Operation cancel kar diya gaya hai."
    
    try:
        if update.message:
            # NAYA: Use formatted reply
            await reply_formatted_text(update, reply_text)
        elif update.callback_query:
            query = update.callback_query
            # Don't answer if the query is a menu button, it will be handled by its own handler
            if not query.data.startswith("admin_menu_") and not query.data == "admin_menu":
                await query.answer("Canceled!")
                # NAYA: Use formatted edit
                await edit_formatted_message_text(context, query, reply_text)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
                logger.warning(f"Cancel me edit nahi kar paya: {e}")
    except Exception as e:
        logger.error(f"Cancel me error: {e}")

    # Return to main admin menu if co-admin
    if await is_co_admin(user.id):
        # Use a small delay to allow the ConversationHandler to END
        await asyncio.sleep(0.1) 
        await admin_command(update, context, from_callback=(update.callback_query is not None))
    
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
    await add_content_menu(update, context)
    return ConversationHandler.END

async def back_to_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await manage_content_menu(update, context)
    return ConversationHandler.END

# NAYA (v27): Edit Menu Fallback
async def back_to_edit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_content_menu(update, context)
    return ConversationHandler.END

async def back_to_sub_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This function remains as a fallback, but the menu it points to is removed.
    # We'll retarget it to the main admin menu.
    query = update.callback_query
    await query.answer()
    await admin_command(update, context, from_callback=True) # MODIFIED
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
    """User ko wapas main menu bhejega"""
    # v22 FIX: menu_command ke bajaye show_user_menu call karo
    await show_user_menu(update, context, from_callback=True) 
    return ConversationHandler.END
    
async def subscription_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NAYA (v22): /subscription command ko handle karega"""
    logger.info(f"User {update.effective_user.id} ne /subscription dabaya.")
    await show_user_menu(update, context)

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NAYA (v22): /menu command ab admin panel kholega"""
    logger.info(f"User {update.effective_user.id} ne /menu dabaya (Admin Panel).")
    await admin_command(update, context)
    
async def back_to_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await bot_messages_menu(update, context)
    return ConversationHandler.END

# NAYA: Admin Settings back button
async def back_to_admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await admin_settings_menu(update, context)
    return ConversationHandler.END

# NAYA: Bot Preferences back button
async def back_to_bot_prefs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await bot_prefs_menu(update, context)
    return BP_MENU # NAYA: Go to BP_MENU state


# --- User Subscription Flow (REMOVED) ---
# (user_subscribe_start, user_upload_ss_start, user_get_screenshot)


# --- Admin Conversations (Add, Delete, etc.) ---
# --- Conversation: Add Anime ---
async def add_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "Salaam Admin! Anime ka <b>Naam</b> kya hai?\n\n/cancel - Cancel."
    # NAYA: Use formatted edit
    await edit_formatted_message_text(context, query, text) 
    return A_GET_NAME
async def get_anime_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime_name'] = update.message.text
    # NAYA: Use formatted reply
    await reply_formatted_text(update, "Badhiya! Ab anime ka <b>Poster (Photo)</b> bhejo.\n\n/cancel - Cancel.")
    return A_GET_POSTER
async def get_anime_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        # NAYA: Use formatted reply
        await reply_formatted_text(update, "Ye photo nahi hai. Please ek photo bhejo.")
        return A_GET_POSTER 
    context.user_data['anime_poster_id'] = update.message.photo[-1].file_id
    # NAYA: Use formatted reply
    await reply_formatted_text(update, "Poster mil gaya! Ab <b>Description (Synopsis)</b> bhejo.\n\n/skip ya /cancel.")
    return A_GET_DESC
async def get_anime_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA: Escape user input for HTML
    context.user_data['anime_desc'] = html.escape(update.message.text)
    return await confirm_anime_details(update, context)
async def skip_anime_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime_desc'] = None 
    return await confirm_anime_details(update, context)
async def confirm_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data['anime_name']
    poster_id = context.user_data['anime_poster_id']
    desc = context.user_data['anime_desc']
    
    # NAYA: Format caption text *before* passing to helper
    caption = f"<b>{html.escape(name)}</b>\n\n{desc if desc else ''}\n\n--- Details Check Karo ---"
    
    keyboard = [[InlineKeyboardButton("✅ Save", callback_data="save_anime")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    
    if update.message:
        try:
            # NAYA: Use formatted reply (ParseMode HTML)
            # We call the *unformatted* helper here because the caption is already HTML
            await update.message.reply_photo(
                photo=poster_id, 
                caption=caption, 
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Confirm anime details me error: {e}")
            await reply_formatted_text(update, "❌ Error: Poster bhej nahi paya. Dobara try karein ya /cancel.")
            return A_GET_DESC 
    return A_CONFIRM
async def save_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    try:
        name = context.user_data['anime_name']
        if animes_collection.find_one({"name": name}):
            # NAYA: Use formatted edit
            await edit_formatted_message_caption(context, query, caption=f"⚠️ <b>Error:</b> Ye anime naam '{html.escape(name)}' pehle se hai.")
            await asyncio.sleep(3)
            await add_content_menu(update, context)
            return ConversationHandler.END
        
        anime_document = {
            "name": name, 
            "poster_id": context.user_data['anime_poster_id'], 
            "description": context.user_data['anime_desc'], # Already escaped
            "seasons": {},
            "created_at": datetime.now() # NAYA (v10): created_at add kiya
        }
        animes_collection.insert_one(anime_document)
        # NAYA: Use formatted edit
        await edit_formatted_message_caption(context, query, caption=f"✅ <b>Success!</b> '{html.escape(name)}' add ho gaya hai.")
        await asyncio.sleep(3)
        await add_content_menu(update, context)
    except Exception as e:
        logger.error(f"Anime save karne me error: {e}")
        await edit_formatted_message_caption(context, query, caption=f"❌ <b>Error!</b> Database me save nahi kar paya.")
    context.user_data.clear() 
    return ConversationHandler.END

# --- Conversation: Add Season (NAYA v10: Paginated) ---
async def add_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    # Helper function ko call karo
    return await add_season_show_anime_list(update, context, page=0)

async def add_season_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    # Check if called from pagination button
    if query.data.startswith("addseason_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page # NAYA (v10): Back button ke liye page save karo
    
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="addseason_page_",
        item_callback_prefix="season_anime_",
        back_callback="back_to_add_content"
    )
    
    text = f"Aap kis anime mein season add karna chahte hain?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai. Pehle 'Add Anime' se add karein."
    
    # NAYA: Use formatted edit
    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return S_GET_ANIME

async def get_anime_for_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("season_anime_", "")
    context.user_data['anime_name'] = anime_name
    # NAYA: Use formatted edit
    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nAb is season ka <b>Number ya Naam</b> bhejo.\n(Jaise: 1, 2, Movie)\n\n/cancel - Cancel.")
    return S_GET_NUMBER

async def get_season_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    season_name = update.message.text
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if not anime_doc:
            # NAYA: Use formatted reply
            await reply_formatted_text(update, f"⚠️ <b>Error!</b> Anime '{html.escape(anime_name)}' database mein nahi mila. /cancel karke dobara try karein.")
            return ConversationHandler.END
            
    if season_name in anime_doc.get("seasons", {}):
        # NAYA: Use formatted reply
        await reply_formatted_text(update, f"⚠️ <b>Error!</b> '{html.escape(anime_name)}' mein 'Season {html.escape(season_name)}' pehle se hai.\n\nKoi doosra naam/number type karein ya /cancel karein.")
        return S_GET_NUMBER

    # NAYA: Use formatted reply
    await reply_formatted_text(update, f"Aapne Season '{html.escape(season_name)}' select kiya hai.\n\nAb is season ka <b>Poster (Photo)</b> bhejo.\n\n/skip - Default anime poster use karo.\n/cancel - Cancel.")
    return S_GET_POSTER

async def get_season_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await reply_formatted_text(update, "Ye photo nahi hai. Please ek photo bhejo.")
        return S_GET_POSTER
    context.user_data['season_poster_id'] = update.message.photo[-1].file_id
    # NAYA (v10): Description state par jao
    await reply_formatted_text(update, "Poster mil gaya! Ab is season ka <b>Description</b> bhejo.\n(Yeh post generator mein use hoga)\n\n/skip ya /cancel.")
    return S_GET_DESC

async def skip_season_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season_poster_id'] = None
    # NAYA (v10): Description state par jao
    await reply_formatted_text(update, "Default poster set! Ab is season ka <b>Description</b> bhejo.\n(Yeh post generator mein use hoga)\n\n/skip ya /cancel.")
    return S_GET_DESC

# NAYA (v10): Season Description functions
async def get_season_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA: Escape user input
    context.user_data['season_desc'] = html.escape(update.message.text)
    return await confirm_season_details(update, context)

async def skip_season_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season_desc'] = None
    return await confirm_season_details(update, context)

async def confirm_season_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    season_poster_id = context.user_data.get('season_poster_id')
    season_desc = context.user_data.get('season_desc') # NAYA (v10)
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    poster_id_to_show = season_poster_id or anime_doc.get('poster_id')
    
    caption = f"<b>Confirm Karo:</b>\nAnime: <b>{html.escape(anime_name)}</b>\nNaya Season: <b>{html.escape(season_name)}</b>\nDescription: {season_desc or 'N/A'}\n\nSave kar doon?"
    keyboard = [[InlineKeyboardButton("✅ Haan, Save Karo", callback_data="save_season")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    
    # NAYA: Use formatted reply (HTML)
    # We call the *unformatted* helper here because the caption is already HTML
    await update.message.reply_photo(
        photo=poster_id_to_show,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode=ParseMode.HTML
    )
    return S_CONFIRM
async def save_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        season_poster_id = context.user_data.get('season_poster_id')
        season_desc = context.user_data.get('season_desc') # NAYA (v10)
        
        season_data = {} 
        if season_poster_id:
            season_data["_poster_id"] = season_poster_id # Poster ID
        if season_desc:
            season_data["_description"] = season_desc # NAYA (v10): Description ID
        
        animes_collection.update_one(
            {"name": anime_name}, 
            {"$set": {f"seasons.{season_name}": season_data}} # season_data object ko save karo
        )
        
        # NAYA: Use formatted edit (HTML)
        await edit_formatted_message_caption(context, query, caption=f"✅ <b>Success!</b>\n<b>{html.escape(anime_name)}</b> mein <b>Season {html.escape(season_name)}</b> add ho gaya hai.")
        await asyncio.sleep(3)
        await add_content_menu(update, context)
    except Exception as e:
        logger.error(f"Season save karne me error: {e}")
        await edit_formatted_message_caption(context, query, caption=f"❌ <b>Error!</b> Database me save nahi kar paya.")
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Add Episode (Multi-Quality) (NAYA v10: Paginated) ---
async def add_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await add_episode_show_anime_list(update, context, page=0)

async def add_episode_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("addep_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page # NAYA (v10)
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="addep_page_",
        item_callback_prefix="ep_anime_",
        back_callback="back_to_add_content"
    )
    
    text = f"Aap kis anime mein episode add karna chahte hain?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai. Pehle 'Add Anime' se add karein."

    # NAYA: Use formatted edit
    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return E_GET_ANIME

async def get_anime_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        # NAYA: Use formatted edit
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.\n\nPehle <code>➕ Add Season</code> se season add karo.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]))
        return ConversationHandler.END
    
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1) 
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"addep_page_{current_page}")])
    
    # NAYA: Use formatted edit
    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nAb <b>Season</b> select karein:", reply_markup=InlineKeyboardMarkup(keyboard))
    return E_GET_SEASON

async def get_season_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("ep_season_", "")
    context.user_data['season_name'] = season_name
    
    # NAYA (v10) FIX: Back button ke liye anime name save karo
    anime_name = context.user_data['anime_name']

    # NAYA: Use formatted edit
    await edit_formatted_message_text(context, query, f"Aapne <b>Season {html.escape(season_name)}</b> select kiya hai.\n\nAb <b>Episode Number</b> bhejo.\n(Jaise: 1, 2, 3...)\n\n(Agar yeh ek movie hai, toh <code>1</code> type karein.)\n\n/cancel - Cancel.")
    
    # NAYA (v10) FIX: State change
    return E_GET_NUMBER

async def _save_episode_file_helper(update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
    """Helper function to save file ID to DB"""
    file_id = None
    if update.message.video: file_id = update.message.video.file_id
    elif update.message.document and (update.message.document.mime_type and update.message.document.mime_type.startswith('video')): file_id = update.message.document.file_id
    
    if not file_id:
        if update.message.text and update.message.text.startswith('/'):
            # User ne /skip ya /cancel type kiya
            return False # False return karo taaki main function ko pata chale
        await reply_formatted_text(update, "Ye video file nahi hai. Please dobara video file bhejein ya /skip karein.")
        return False # False return karo

    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        ep_num = context.user_data['ep_num']
        
        # Keys ko filter karo
        dot_notation_key = f"seasons.{season_name}.{ep_num}.{quality}"
        animes_collection.update_one({"name": anime_name}, {"$set": {dot_notation_key: file_id}})
        logger.info(f"Naya episode save ho gaya: {anime_name} S{season_name} E{ep_num} {quality}")
        await reply_formatted_text(update, f"✅ <b>{quality}</b> save ho gaya.")
        return True # Success
    except Exception as e:
        logger.error(f"Episode file save karne me error: {e}")
        await reply_formatted_text(update, f"❌ <b>Error!</b> {quality} save nahi kar paya. Logs check karein.")
        return False # Fail

async def get_episode_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_num'] = update.message.text
    
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    ep_num = context.user_data['ep_num']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    # Filter keys
    existing_eps = anime_doc.get("seasons", {}).get(season_name, {})
    if ep_num in existing_eps:
        await reply_formatted_text(update, f"⚠️ <b>Error!</b> '{html.escape(anime_name)}' - Season {html.escape(season_name)} - Episode {html.escape(ep_num)} pehle se maujood hai. Please pehle isse delete karein ya koi doosra episode number dein.\n\n/cancel - Cancel.")
        return E_GET_NUMBER

    await reply_formatted_text(update, f"Aapne <b>Episode {context.user_data['ep_num']}</b> select kiya hai.\n\n"
                                        "Ab <b>480p</b> quality ki video file bhejein.\n"
                                        "Ya /skip type karein.")
    return E_GET_480P

async def get_480p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if not await _save_episode_file_helper(update, context, "480p"):
        return E_GET_480P # Agar fail hua (e.g., text bheja), toh isi state par raho
    await reply_formatted_text(update, "Ab <b>720p</b> quality ki video file bhejein.\nYa /skip type karein.")
    return E_GET_720P

async def skip_480p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_formatted_text(update, "✅ 480p skip kar diya.\n\n"
                                    "Ab <b>720p</b> quality ki video file bhejein.\n"
                                    "Ya /skip type karein.")
    return E_GET_720P

async def get_720p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if not await _save_episode_file_helper(update, context, "720p"):
        return E_GET_720P # Agar fail hua, toh isi state par raho
    await reply_formatted_text(update, "Ab <b>1080p</b> quality ki video file bhejein.\nYa /skip type karein.")
    return E_GET_1080P

async def skip_720p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_formatted_text(update, "✅ 720p skip kar diya.\n\n"
                                    "Ab <b>1080p</b> quality ki video file bhejein.\n"
                                    "Ya /skip type karein.")
    return E_GET_1080P

async def get_1080p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if not await _save_episode_file_helper(update, context, "1080p"):
        return E_GET_1080P # Agar fail hua, toh isi state par raho
    await reply_formatted_text(update, "Ab <b>4K</b> quality ki video file bhejein.\nYa /skip type karein.")
    return E_GET_4K

async def skip_1080p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_formatted_text(update, "✅ 1080p skip kar diya.\n\n"
                                    "Ab <b>4K</b> quality ki video file bhejein.\n"
                                    "Ya /skip type karein.")
    return E_GET_4K

async def get_4k_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if await _save_episode_file_helper(update, context, "4K"):
        await reply_formatted_text(update, "✅ <b>Success!</b> Saari qualities save ho gayi hain.")
    else:
        return E_GET_4K # Agar fail hua, toh isi state par raho
    
    await add_content_menu(update, context) # NAYA (v10): Go back to menu
    context.user_data.clear()
    return ConversationHandler.END

async def skip_4k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_formatted_text(update, "✅ 4K skip kar diya.\n\n"
                                    "✅ <b>Success!</b> Episode save ho gaya hai.")
    
    await add_content_menu(update, context) # NAYA (v10): Go back to menu
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Set Subscription QR (REMOVED) ---
# --- Conversation: Set Price (REMOVED) ---
# --- Conversation: Set Validity Days (REMOVED) ---

# --- NAYA: Conversation: Set Auto-Delete Time ---
async def set_delete_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = await get_config()
    current_seconds = config.get("delete_seconds", 300) # NAYA: Default 300
    current_minutes = current_seconds // 60
    text = f"Abhi file auto-delete <b>{current_minutes} minute(s)</b> ({current_seconds} seconds) par set hai.\n\n"
    text += "Naya time <b>seconds</b> mein bhejo.\n(Example: <code>300</code> for 5 minutes)\n\n/cancel - Cancel."
    # MODIFIED: Back button goes to main admin menu
    await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
    return CS_GET_DELETE_TIME
async def set_delete_time_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        seconds = int(update.message.text)
        if seconds <= 10:
                await reply_formatted_text(update, "Time 10 second se zyada hona chahiye.")
                return CS_GET_DELETE_TIME
                
        config_collection.update_one({"_id": "bot_config"}, {"$set": {"delete_seconds": seconds}}, upsert=True)
        logger.info(f"Auto-delete time update ho gaya: {seconds} seconds")
        await reply_formatted_text(update, f"✅ <b>Success!</b> Auto-delete time ab <b>{seconds} seconds</b> ({seconds // 60} min) par set ho gaya hai.")
        await admin_command(update, context, from_callback=False) # MODIFIED
        return ConversationHandler.END
        
    except ValueError:
        await reply_formatted_text(update, "Yeh number nahi hai. Please sirf seconds bhejein (jaise 180) ya /cancel karein.")
        return CS_GET_DELETE_TIME
    except Exception as e:
        logger.error(f"Delete time save karte waqt error: {e}")
        await reply_formatted_text(update, "❌ Error! Save nahi kar paya.")
        context.user_data.clear()
        return ConversationHandler.END

# --- Conversation: Set Donate QR ---
async def set_donate_qr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_formatted_message_text(context, query, "Aapna <b>Donate QR Code</b> ki photo bhejo.\n\n/cancel - Cancel.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_donate_settings")]]))
    return CD_GET_QR
async def set_donate_qr_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await reply_formatted_text(update, "Ye photo nahi hai. Please ek photo bhejo ya /cancel karein.")
        return CD_GET_QR
    qr_file_id = update.message.photo[-1].file_id
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"donate_qr_id": qr_file_id}}, upsert=True)
    logger.info(f"Donate QR code update ho gaya.")
    await reply_formatted_text(update, "✅ <b>Success!</b> Naya donate QR code set ho gaya hai.")
    await donate_settings_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Set Links ---
async def set_links_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    link_type = query.data.replace("admin_set_", "") 
    
    if link_type == "backup_link":
        context.user_data['link_type'] = "backup"
        text = "Aapke <b>Backup Channel</b> ka link bhejo.\n(Example: https://t.me/mychannel)\n\n/skip - Skip.\n/cancel - Cancel."
        back_button = "back_to_links"
    # MODIFIED: Added download_link
    elif link_type == "download_link":
        context.user_data['link_type'] = "download"
        text = "Aapka global <b>Download Link</b> bhejo.\n(Yeh post generator mein use hoga)\n\n/skip - Skip.\n/cancel - Cancel."
        back_button = "back_to_links"
    # REMOVED: support_link
    else:
        await query.answer("Invalid button!", show_alert=True)
        return ConversationHandler.END

    await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_button)]]))
    return CL_GET_LINK # MODIFIED 
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link_url = update.message.text
    link_type = context.user_data['link_type']
    config_collection.update_one({"_id": "bot_config"}, {"$set": {f"links.{link_type}": link_url}}, upsert=True)
    logger.info(f"{link_type} link update ho gaya: {link_url}")
    await reply_formatted_text(update, f"✅ <b>Success!</b> Naya {link_type} link set ho gaya hai.")
    await other_links_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END
async def skip_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link_type = context.user_data['link_type']
    config_collection.update_one({"_id": "bot_config"}, {"$set": {f"links.{link_type}": None}}, upsert=True)
    logger.info(f"{link_type} link skip kiya (None set).")
    await reply_formatted_text(update, f"✅ <b>Success!</b> {link_type} link remove kar diya गया है.")
    await other_links_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END

# --- NAYA: Conversation: Set Custom Messages (PAGINATED) ---
async def set_msg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Message select karne ke liye naya function"""
    query = update.callback_query
    await query.answer()
    msg_key = query.data.replace("msg_edit_", "")
    
    config = await get_config()
    current_msg = config.get("messages", {}).get(msg_key, "N/A")
    
    context.user_data['msg_key'] = msg_key
    
    text = f"<b>Editing:</b> <code>{msg_key}</code>\n\n"
    text += f"<b>Current Message:</b>\n<code>{html.escape(current_msg)}</code>\n\n"
    text += f"Naya message bhejo. (Aap <b>, <i>, <code>, <a> tags use kar sakte hain)\n\n/cancel - Cancel."
    
    # Determine the correct back button
    # REMOVED: Sub menu
    if msg_key in ["user_dl_unsubscribed_alert", "user_dl_unsubscribed_dm", "user_dl_dm_alert", "user_dl_anime_not_found", "user_dl_file_error", "user_dl_blocked_error", "user_dl_episodes_not_found", "user_dl_seasons_not_found", "user_dl_general_error", "user_dl_sending_files", "user_dl_select_episode", "user_dl_select_season", "file_warning"]:
        back_cb = "msg_menu_dl"
    elif msg_key in ["post_gen_season_caption", "post_gen_episode_caption", "post_gen_anime_caption"]: 
        back_cb = "msg_menu_postgen" 
    # REMOVED: Genlink menu
    else:
        back_cb = "msg_menu_gen"
        
    await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_cb)]]))
    return M_GET_MSG

async def set_msg_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic function to save edited message"""
    try:
        # NAYA: Message text ko save karo (HTML ke liye escape nahi karna)
        msg_text = update.message.text
        msg_key = context.user_data['msg_key']
        
        config_collection.update_one({"_id": "bot_config"}, {"$set": {f"messages.{msg_key}": msg_text}}, upsert=True)
        logger.info(f"{msg_key} message update ho gaya: {msg_text}")
        await reply_formatted_text(update, f"✅ <b>Success!</b> Naya '{msg_key}' message set ho gaya hai.")
        
        await bot_messages_menu(update, context) # Go back to main messages menu
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Message save karne me error: {e}")
        await reply_formatted_text(update, "❌ Error! Save nahi kar paya.")
        context.user_data.clear()
        return ConversationHandler.END
    
# --- Conversation: Post Generator (NAYA v10: Paginated) ---
async def post_gen_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        # ============================================
        # ===           NAYA FIX (v23)             ===
        # ============================================
        [InlineKeyboardButton("✍️ Complete Anime Post", callback_data="post_gen_anime")],
        # ============================================
        [InlineKeyboardButton("✍️ Season Post", callback_data="post_gen_season")],
        [InlineKeyboardButton("✍️ Episode Post", callback_data="post_gen_episode")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    await edit_formatted_message_text(context, query, "✍️ <b>Post Generator</b> ✍️\n\nAap kis tarah ka post generate karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
    return PG_MENU

async def post_gen_select_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    post_type = query.data
    context.user_data['post_type'] = post_type
    
    # NAYA (v10): Paginated list ko call karo
    return await post_gen_show_anime_list(update, context, page=0)

async def post_gen_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("postgen_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()

    context.user_data['current_page'] = page # NAYA (v10)
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="postgen_page_",
        item_callback_prefix="post_anime_",
        back_callback="admin_post_gen" # Back to Post Gen Menu
    )
    
    text = f"Kaunsa <b>Anime</b> select karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return PG_GET_ANIME

async def post_gen_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("post_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    
    # ============================================
    # ===           NAYA FIX (v23)             ===
    # ============================================
    if context.user_data['post_type'] == 'post_gen_anime':
        # Agar "Complete Anime Post" hai, toh season mat poocho
        context.user_data['season_name'] = None
        context.user_data['ep_num'] = None 
        await generate_post_ask_chat(update, context) 
        return PG_GET_SHORT_LINK # MODIFIED: Go to short link state
    # ============================================

    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"post_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"postgen_page_{current_page}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nAb <b>Season</b> select karein:", reply_markup=InlineKeyboardMarkup(keyboard))
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
        return PG_GET_SHORT_LINK # MODIFIED: Go to short link state
        
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    # Filter out _poster_id, _description
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' - Season {html.escape(season_name)} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"post_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    # NAYA (v10) FIX: Back button ko season list par bhejo
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"post_anime_{anime_name}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>Season {html.escape(season_name)}</b> select kiya hai.\n\nAb <b>Episode</b> select karein:", reply_markup=InlineKeyboardMarkup(keyboard))
    return PG_GET_EPISODE
async def post_gen_final_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("post_ep_", "")
    context.user_data['ep_num'] = ep_num
    
    await generate_post_ask_chat(update, context) 
    return PG_GET_SHORT_LINK # MODIFIED: Go to short link state

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
        
        # --- NAYA LOGIC SHURU: Deep Link Banane Ke Liye ---
        dl_callback_data = f"dl{anime_id}" # Default (Anime Post)
        # --- NAYA LOGIC KHATAM ---
        
        if post_type == 'post_gen_anime':
            # --- YEH COMPLETE ANIME POST HAI ---
            context.user_data['is_episode_post'] = False
            poster_id = anime_doc['poster_id']
            description = anime_doc.get('description', '')
            
            caption_template = config.get("messages", {}).get("post_gen_anime_caption", "...")
            caption = caption_template.replace("{anime_name}", html.escape(anime_name)) \
                                        .replace("{description}", description if description else "")
            # dl_callback_data (dl{anime_id}) pehle se sahi hai

        elif not ep_num and season_name:
            # --- YEH SEASON POST HAI ---
            context.user_data['is_episode_post'] = False
            dl_callback_data = f"dl{anime_id}__{season_name}" # NAYA: Season Link
            
            season_data = anime_doc.get("seasons", {}).get(season_name, {})
            
            # Season poster check karo, nahi toh anime poster lo
            poster_id = season_data.get("_poster_id") or anime_doc['poster_id']
            
            # NAYA (v10): Season description check karo, nahi toh anime description lo
            description = season_data.get("_description") or anime_doc.get('description', '')
            
            caption_template = config.get("messages", {}).get("post_gen_season_caption", "...")
            caption = caption_template.replace("{anime_name}", html.escape(anime_name)) \
                                        .replace("{season_name}", html.escape(season_name)) \
                                        .replace("{description}", description if description else "")
    
        elif ep_num:
                # --- YEH EPISODE POST HAI ---
            context.user_data['is_episode_post'] = True
            dl_callback_data = f"dl{anime_id}__{season_name}__{ep_num}" # NAYA: Episode Link
            
            caption_template = config.get("messages", {}).get("post_gen_episode_caption", "...")
            caption = caption_template.replace("{anime_name}", html.escape(anime_name)) \
                                        .replace("{season_name}", html.escape(season_name)) \
                                        .replace("{ep_num}", html.escape(ep_num))
            
            poster_id = None # Episode post ke liye koi poster nahi
        
        else:
            logger.warning("Post generator me invalid state")
            await edit_formatted_message_text(context, query, "❌ Error! Invalid state. Please start over.")
            return ConversationHandler.END
        
        links = config.get('links', {})
        
        # ============================================
        # ===     MODIFIED: Shortener Flow Start   ===
        # ============================================
        
        # Get URLs
        backup_url = links.get('backup') or "https://t.me/"
        donate_url = f"https://t.me/{bot_username}?start=donate"
        
        # --- YEH RAHA AAPKA FIX ---
        # Ab link config se nahi, automatic generate hoga
        original_download_url = f"https://t.me/{bot_username}?start={dl_callback_data}"
        # --- FIX KHATAM ---
        
        # Sirf Backup aur Donate button banao
        btn_backup = InlineKeyboardButton("Backup", url=backup_url)
        btn_donate = InlineKeyboardButton("Donate", url=donate_url)

        # Partial data ko save karo
        context.user_data['post_caption'] = caption
        context.user_data['post_poster_id'] = poster_id 
        context.user_data['btn_backup'] = btn_backup
        context.user_data['btn_donate'] = btn_donate
        context.user_data['is_episode_post'] = context.user_data.get('is_episode_post', False) # NAYA: Isko bhi save karo
        
        # Ab Channel ID ke bajaye Short Link maango
        await edit_formatted_message_text(
            context, query,
            "✅ <b>Post Ready!</b>\n\n"
            "Aapka original download link hai:\n"
            f"<code>{original_download_url}</code>\n\n"  # Ab yahaan sahi link aayega
            "Please iska <b>shortened link</b> reply mein bhejein.\n"
            "(Agar link change nahi karna hai, toh upar waala link hi copy karke bhej dein.)\n\n"
            "/cancel - Cancel."
        )
        
        return PG_GET_SHORT_LINK # Naye state par bhejo
        # ============================================
        
    except Exception as e:
        logger.error(f"Post generate karne me error: {e}", exc_info=True)
        await query.answer("Error! Post generate nahi kar paya.", show_alert=True)
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Post generate nahi ho paya. Logs check karein.")
        context.user_data.clear()
        return ConversationHandler.END
        
# --- NAYA FUNCTION: Short Link Lene Ke Liye ---
async def post_gen_get_short_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Admin ka bheja hua short link lo
    short_link_url = update.message.text
    
    # 2. Pehle se save kiya hua data wapas nikalo
    caption = context.user_data['post_caption']
    poster_id = context.user_data['post_poster_id']
    btn_backup = context.user_data['btn_backup']
    btn_donate = context.user_data['btn_donate']
    is_episode_post = context.user_data.get('is_episode_post', False)
    
    # 3. Naye link se final download button banao
    btn_download = InlineKeyboardButton("Download", url=short_link_url)
    
    # 4. Final keyboard layout banao (NAYA LAYOUT LOGIC)
    if is_episode_post:
        # Episode Post: Donate aur Download
        keyboard = [[btn_donate, btn_download]]
    else:
        # Anime/Season Post: Backup, Donate, Download
        keyboard = [
            [btn_backup, btn_donate],  # Row 1
            [btn_download]             # Row 2
        ]
    
    # 5. Final keyboard ko save karo taaki agla function use kar sake
    context.user_data['post_keyboard'] = InlineKeyboardMarkup(keyboard)
    
    # 6. Ab Channel ID maango (jo pehle waala function kar raha tha)
    await reply_formatted_text(
        update,
        "✅ <b>Short Link Saved!</b>\n\n"
        "Ab uss <b>Channel ka @username</b> ya <b>Group/Channel ki Chat ID</b> bhejo jahaan ye post karna hai.\n"
        "(Example: @MyAnimeChannel ya -100123456789)\n\n/cancel - Cancel."
    )
    
    # 7. Agle state (PG_GET_CHAT) par jao
    return PG_GET_CHAT

async def post_gen_send_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.text
    is_episode_post = context.user_data.get('is_episode_post', False) 
    
    try:
        if is_episode_post:
            await context.bot.send_message(
                chat_id=chat_id,
                text=context.user_data['post_caption'],
                parse_mode=ParseMode.HTML, # NAYA: Use HTML
                reply_markup=context.user_data['post_keyboard']
            )
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=context.user_data['post_poster_id'],
                caption=context.user_data['post_caption'],
                parse_mode=ParseMode.HTML, # NAYA: Use HTML
                reply_markup=context.user_data['post_keyboard']
            )

        await reply_formatted_text(update, f"✅ <b>Success!</b>\nPost ko '{chat_id}' par bhej diya gaya hai.")
    except Exception as e:
        logger.error(f"Post channel me bhejme me error: {e}")
        await reply_formatted_text(update, f"❌ <b>Error!</b>\nPost '{chat_id}' par nahi bhej paya. Check karo ki bot uss channel me admin hai ya ID sahi hai.\nError: {e}")
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
    await edit_formatted_message_text(context, query, "🔗 <b>Generate Download Link</b> 🔗\n\nAap kis cheez ka link generate karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
    return GL_MENU
async def gen_link_select_anime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    link_type = query.data
    context.user_data['link_type'] = link_type
    
    # Paginated list ko call karo
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
        back_callback="admin_gen_link" # Back to Gen Link Menu
    )
    
    text = f"Kaunsa <b>Anime</b> select karna hai?\n\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return GL_GET_ANIME

async def gen_link_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("gen_link_anime_", "")
    context.user_data['anime_name'] = anime_name
    
    if context.user_data['link_type'] == 'gen_link_anime':
        # Agar "Complete Anime" hai, toh season mat poocho
        context.user_data['season_name'] = None
        context.user_data['ep_num'] = None 
        return await gen_link_finish(update, context) # Final step par jao
    
    # Season ya Episode ke liye, season list dikhao
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gen_link")]]))
        return ConversationHandler.END
        
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"gen_link_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"genlink_page_{current_page}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nAb <b>Season</b> select karein:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GL_GET_SEASON

async def gen_link_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("gen_link_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    if context.user_data['link_type'] == 'gen_link_season':
        context.user_data['ep_num'] = None 
        return await gen_link_finish(update, context) # Final step par jao
        
    # Episode ke liye, episode list dikhao
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' - Season {html.escape(season_name)} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_gen_link")]]))
        return ConversationHandler.END
        
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"gen_link_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"gen_link_anime_{anime_name}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>Season {html.escape(season_name)}</b> select kiya hai.\n\nAb <b>Episode</b> select karein:", reply_markup=InlineKeyboardMarkup(keyboard))
    return GL_GET_EPISODE

async def gen_link_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Agar episode se aa rahe hain
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
        
        # Deep Link banao
        dl_callback_data = f"dl{anime_id}" # Default (Anime)
        title = html.escape(anime_name)
        
        if link_type == 'gen_link_season' and season_name:
            dl_callback_data = f"dl{anime_id}__{season_name}"
            title = f"{html.escape(anime_name)} - S{html.escape(season_name)}"
        elif link_type == 'gen_link_episode' and season_name and ep_num:
            dl_callback_data = f"dl{anime_id}__{season_name}__{ep_num}"
            title = f"{html.escape(anime_name)} - S{html.escape(season_name)} E{html.escape(ep_num)}"
        
        final_link = f"https://t.me/{bot_username}?start={dl_callback_data}"
        
        await edit_formatted_message_text(
            context, query,
            f"✅ <b>Link Generated!</b>\n\n"
            f"<b>Target:</b> {title}\n"
            f"<b>Link:</b>\n<code>{final_link}</code>\n\n" # NAYA: Use <code> for copy-paste
            f"Is link ko copy karke kahin bhi paste karein.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]])
        )
        
    except Exception as e:
        logger.error(f"Link generate karne me error: {e}", exc_info=True)
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Link generate nahi ho paya. Logs check karein.")
        
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Delete Anime (NAYA v10: Paginated) ---
async def delete_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await delete_anime_show_anime_list(update, context, page=0)

async def delete_anime_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("delanime_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page # NAYA (v10)

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="delanime_page_",
        item_callback_prefix="del_anime_",
        back_callback="back_to_manage"
    )
    
    text = f"Kaunsa <b>Anime</b> delete karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return DA_GET_ANIME
async def delete_anime_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_anime_", "")
    context.user_data['anime_name'] = anime_name
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {anime_name} ko Delete Karo", callback_data="del_anime_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    await edit_formatted_message_text(context, query, f"⚠️ <b>FINAL WARNING</b> ⚠️\n\nAap <b>{html.escape(anime_name)}</b> ko delete karne wale hain. Iske saare seasons aur episodes delete ho jayenge.\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return DA_CONFIRM
async def delete_anime_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    try:
        animes_collection.delete_one({"name": anime_name})
        logger.info(f"Anime deleted: {anime_name}")
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nAnime '{html.escape(anime_name)}' delete ho gaya hai.")
    except Exception as e:
        logger.error(f"Anime delete karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Anime delete nahi ho paya.")
    context.user_data.clear()
    await asyncio.sleep(3)
    await manage_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Delete Season (NAYA v10: Paginated) ---
async def delete_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await delete_season_show_anime_list(update, context, page=0)

async def delete_season_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("delseason_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page # NAYA (v10)

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="delseason_page_",
        item_callback_prefix="del_season_anime_",
        back_callback="back_to_manage"
    )
    
    text = f"Kaunse <b>Anime</b> ka season delete karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return DS_GET_ANIME

async def delete_season_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_season_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"del_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"delseason_page_{current_page}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nKaunsa <b>Season</b> delete karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return DS_GET_SEASON
async def delete_season_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("del_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    keyboard = [[InlineKeyboardButton(f"✅ Haan, Season {season_name} Delete Karo", callback_data="del_season_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    await edit_formatted_message_text(context, query, f"⚠️ <b>FINAL WARNING</b> ⚠️\n\nAap <b>{html.escape(anime_name)}</b> ka <b>Season {html.escape(season_name)}</b> delete karne wale hain. Iske saare episodes delete ho jayenge.\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return DS_CONFIRM
async def delete_season_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    try:
        animes_collection.update_one({"name": anime_name}, {"$unset": {f"seasons.{season_name}": ""}})
        logger.info(f"Season deleted: {anime_name} - S{season_name}")
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nSeason '{html.escape(season_name)}' delete ho gaya hai.")
    except Exception as e:
        logger.error(f"Season delete karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Season delete nahi ho paya.")
    context.user_data.clear()
    await asyncio.sleep(3)
    await manage_content_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Delete Episode (NAYA v10: Paginated) ---
async def delete_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await delete_episode_show_anime_list(update, context, page=0)

async def delete_episode_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("delep_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()

    context.user_data['current_page'] = page # NAYA (v10)
        
    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="delep_page_",
        item_callback_prefix="del_ep_anime_",
        back_callback="back_to_manage"
    )
    
    text = f"Kaunse <b>Anime</b> ka episode delete karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return DE_GET_ANIME

async def delete_episode_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"del_ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"delep_page_{current_page}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nKaunsa <b>Season</b> delete karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return DE_GET_SEASON
async def delete_episode_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("del_ep_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    # Filter out _poster_id, _description
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' - Season {html.escape(season_name)} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"del_ep_num_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    # NAYA (v10) FIX: Back button ko season list par bhejo
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"del_ep_anime_{anime_name}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>Season {html.escape(season_name)}</b> select kiya hai.\n\nKaunsa <b>Episode</b> delete karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return DE_GET_EPISODE
async def delete_episode_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("del_ep_num_", "")
    context.user_data['ep_num'] = ep_num
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    keyboard = [[InlineKeyboardButton(f"✅ Haan, Ep {ep_num} Delete Karo", callback_data="del_ep_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    await edit_formatted_message_text(context, query, f"⚠️ <b>FINAL WARNING</b> ⚠️\n\nAap <b>{html.escape(anime_name)}</b> - <b>S{html.escape(season_name)}</b> - <b>Ep {html.escape(ep_num)}</b> delete karne wale hain. Iske saare qualities delete ho jayenge.\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return DE_CONFIRM
async def delete_episode_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    ep_num = context.user_data['ep_num']
    try:
        animes_collection.update_one({"name": anime_name}, {"$unset": {f"seasons.{season_name}.{ep_num}": ""}})
        logger.info(f"Episode deleted: {anime_name} - S{season_name} - E{ep_num}")
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nEpisode '{html.escape(ep_num)}' delete ho gaya hai.")
    except Exception as e:
        logger.error(f"Episode delete karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Episode delete nahi ho paya.")
    context.user_data.clear()
    await asyncio.sleep(3)
    await manage_content_menu(update, context)
    return ConversationHandler.END
# --- NAYA (v10): Conversation: Update Photo (Paginated) ---
async def update_photo_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    return await update_photo_show_anime_list(update, context, page=0)

async def update_photo_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("upphoto_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page # NAYA (v10)

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="upphoto_page_",
        item_callback_prefix="upphoto_anime_",
        back_callback="admin_menu" # Back to main admin menu
    )
    
    text = f"Kaunse <b>Anime</b> ka poster update karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
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
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"upphoto_page_{current_page}")])
    
    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nAap iska <b>Main Poster</b> change karna chahte hain ya kisi <b>Season</b> ka?", reply_markup=InlineKeyboardMarkup(keyboard))
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

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(target_name)}</b> select kiya hai.\n\nAb naya <b>Poster (Photo)</b> bhejo.\n\n/cancel - Cancel.")
    return UP_GET_POSTER

# NAYA FIX (v12): Galti se text bhejne par handle karo
async def update_photo_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_formatted_text(update, "Ye photo nahi hai. Please ek photo bhejo ya /cancel karo.")
    return UP_GET_POSTER # Isi state par raho

async def update_photo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await reply_formatted_text(update, "Ye photo nahi hai. Please ek photo bhejo.")
        return UP_GET_POSTER
    
    poster_id = update.message.photo[-1].file_id
    anime_name = context.user_data['anime_name']
    target = context.user_data['target']
    
    try:
        if target == "MAIN":
            animes_collection.update_one({"name": anime_name}, {"$set": {"poster_id": poster_id}})
            caption = f"✅ <b>Success!</b>\n{html.escape(anime_name)} ka <b>Main Poster</b> change ho gaya hai."
            logger.info(f"Main poster change ho gaya: {anime_name}")
        else:
            season_name = context.user_data['season_name']
            animes_collection.update_one(
                {"name": anime_name}, 
                {"$set": {f"seasons.{season_name}._poster_id": poster_id}}
            )
            caption = f"✅ <b>Success!</b>\n{html.escape(anime_name)} - <b>Season {html.escape(season_name)}</b> ka poster change ho gaya hai."
            logger.info(f"Season poster change ho gaya: {anime_name} S{season_name}")
        
        # We call the *unformatted* helper here because the caption is already HTML
        await update.message.reply_photo(photo=poster_id, caption=caption, parse_mode=ParseMode.HTML)
    
    except Exception as e:
        logger.error(f"Poster change karne me error: {e}")
        await reply_formatted_text(update, "❌ <b>Error!</b> Poster update nahi ho paya.")
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await admin_command(update, context, from_callback=False) # Go to main menu
    return ConversationHandler.END


# --- NAYA (v27): Conversation: Edit Anime Name ---
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
    
    text = f"Kaunsa <b>Anime</b> ka naam edit karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return EA_GET_ANIME

async def edit_anime_get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("edit_anime_", "")
    context.user_data['old_anime_name'] = anime_name
    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nAb iska <b>Naya Naam</b> bhejo.\n\n/cancel - Cancel.")
    return EA_GET_NEW_NAME

async def edit_anime_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text
    old_name = context.user_data['old_anime_name']
    
    if animes_collection.find_one({"name": new_name}):
        await reply_formatted_text(update, f"⚠️ <b>Error!</b> Naya naam '{html.escape(new_name)}' pehle se maujood hai. Koi doosra naam dein.\n\n/cancel - Cancel.")
        return EA_GET_NEW_NAME
    
    context.user_data['new_anime_name'] = new_name
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, '{old_name}' ko '{new_name}' Karo", callback_data="edit_anime_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]
    await reply_formatted_text(update, f"<b>Confirm Karo:</b>\n\nPurana Naam: <code>{html.escape(old_name)}</code>\nNaya Naam: <code>{html.escape(new_name)}</code>\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return EA_CONFIRM

async def edit_anime_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Updating...")
    old_name = context.user_data['old_anime_name']
    new_name = context.user_data['new_anime_name']
    try:
        animes_collection.update_one({"name": old_name}, {"$set": {"name": new_name}})
        logger.info(f"Anime naam update ho gaya: {old_name} -> {new_name}")
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nAnime '{html.escape(old_name)}' ka naam badal kar '{html.escape(new_name)}' ho gaya hai.")
    except Exception as e:
        logger.error(f"Anime naam update karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Anime naam update nahi ho paya.")
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await edit_content_menu(update, context)
    return ConversationHandler.END

# --- NAYA (v27): Conversation: Edit Season Name ---
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
    
    text = f"Kaunse <b>Anime</b> ka season edit karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return ES_GET_ANIME

async def edit_season_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("edit_season_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]))
        return ConversationHandler.END
        
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"edit_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"editseason_page_{current_page}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nKaunsa <b>Season</b> ka naam edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return ES_GET_SEASON

async def edit_season_get_new_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("edit_season_", "")
    context.user_data['old_season_name'] = season_name
    anime_name = context.user_data['anime_name']
    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> -> <b>Season {html.escape(season_name)}</b> select kiya hai.\n\nAb iska <b>Naya Naam/Number</b> bhejo.\n\n/cancel - Cancel.", parse_mode='Markdown')
    return ES_GET_NEW_NAME

async def edit_season_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_name = update.message.text
    old_name = context.user_data['old_season_name']
    anime_name = context.user_data['anime_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if new_name in anime_doc.get("seasons", {}):
        await reply_formatted_text(update, f"⚠️ <b>Error!</b> Naya naam '{html.escape(new_name)}' is anime mein pehle se maujood hai. Koi doosra naam dein.\n\n/cancel - Cancel.")
        return ES_GET_NEW_NAME
        
    context.user_data['new_season_name'] = new_name
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, '{old_name}' ko '{new_name}' Karo", callback_data="edit_season_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]
    await reply_formatted_text(update, f"<b>Confirm Karo:</b>\n\nAnime: <code>{html.escape(anime_name)}</code>\nPurana Season: <code>{html.escape(old_name)}</code>\nNaya Season: <code>{html.escape(new_name)}</code>\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return ES_CONFIRM

async def edit_season_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Updating...")
    old_name = context.user_data['old_season_name']
    new_name = context.user_data['new_season_name']
    anime_name = context.user_data['anime_name']
    try:
        # MongoDB $rename operator ka istemaal
        animes_collection.update_one(
            {"name": anime_name},
            {"$rename": {f"seasons.{old_name}": f"seasons.{new_name}"}}
        )
        logger.info(f"Season naam update ho gaya: {anime_name} - {old_name} -> {new_name}")
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nSeason '{html.escape(old_name)}' ka naam badal kar '{html.escape(new_name)}' ho gaya hai.")
    except Exception as e:
        logger.error(f"Season naam update karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Season naam update nahi ho paya.")
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await edit_content_menu(update, context)
    return ConversationHandler.END

# --- NAYA (v27): Conversation: Edit Episode Number ---
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
    
    text = f"Kaunse <b>Anime</b> ka episode edit karna hai?\n\n<b>Newest First</b> (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await edit_formatted_message_text(context, query, text, reply_markup=keyboard)
    return EE_GET_ANIME

async def edit_episode_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("edit_ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"edit_ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"editep_page_{current_page}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> select kiya hai.\n\nKaunsa <b>Season</b> select karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return EE_GET_SEASON
async def edit_episode_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("edit_ep_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    # Filter out _poster_id, _description
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        await edit_formatted_message_text(context, query, f"❌ <b>Error!</b> '{html.escape(anime_name)}' - Season {html.escape(season_name)} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"edit_ep_num_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"edit_ep_anime_{anime_name}")])

    await edit_formatted_message_text(context, query, f"Aapne <b>Season {html.escape(season_name)}</b> select kiya hai.\n\nKaunsa <b>Episode</b> ka number edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return EE_GET_EPISODE
    
async def edit_episode_get_new_num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("edit_ep_num_", "")
    context.user_data['old_ep_num'] = ep_num
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    
    await edit_formatted_message_text(context, query, f"Aapne <b>{html.escape(anime_name)}</b> -> <b>S{html.escape(season_name)}</b> -> <b>Ep {html.escape(ep_num)}</b> select kiya hai.\n\nAb iska <b>Naya Number</b> bhejo.\n\n/cancel - Cancel.")
    return EE_GET_NEW_NUM

async def edit_episode_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_num = update.message.text
    old_num = context.user_data['old_ep_num']
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if new_num in anime_doc.get("seasons", {}).get(season_name, {}):
        await reply_formatted_text(update, f"⚠️ <b>Error!</b> Naya number '{html.escape(new_num)}' is season mein pehle se maujood hai. Koi doosra number dein.\n\n/cancel - Cancel.")
        return EE_GET_NEW_NUM
        
    context.user_data['new_ep_num'] = new_num
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, '{old_num}' ko '{new_num}' Karo", callback_data="edit_ep_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_edit_menu")]]
    await reply_formatted_text(update, f"<b>Confirm Karo:</b>\n\nAnime: <code>{html.escape(anime_name)}</code>\nSeason: <code>{html.escape(season_name)}</code>\nPurana Episode: <code>{html.escape(old_num)}</code>\nNaya Episode: <code>{html.escape(new_num)}</code>\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
    return EE_CONFIRM

async def edit_episode_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Updating...")
    old_num = context.user_data['old_ep_num']
    new_num = context.user_data['new_ep_num']
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    try:
        # MongoDB $rename operator ka istemaal
        animes_collection.update_one(
            {"name": anime_name},
            {"$rename": {f"seasons.{season_name}.{old_num}": f"seasons.{season_name}.{new_num}"}}
        )
        logger.info(f"Episode number update ho gaya: {anime_name} S{season_name} - {old_num} -> {new_num}")
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nEpisode '{html.escape(old_num)}' ka number badal kar '{html.escape(new_num)}' ho gaya hai.")
    except Exception as e:
        logger.error(f"Episode number update karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Episode number update nahi ho paya.")
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await edit_content_menu(update, context)
    return ConversationHandler.END

# --- NAYA: Conversation: Co-Admin Add ---
async def co_admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_formatted_message_text(context, query, "Naye Co-Admin ki <b>Telegram User ID</b> bhejein.\n\n/cancel - Cancel.",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return CA_GET_ID
async def co_admin_add_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
    except ValueError:
        await reply_formatted_text(update, "Yeh valid User ID nahi hai. Please sirf number bhejein.\n\n/cancel - Cancel.")
        return CA_GET_ID

    if user_id == ADMIN_ID:
        await reply_formatted_text(update, "Aap Main Admin hain, khud ko add nahi kar sakte.\n\n/cancel - Cancel.")
        return CA_GET_ID

    config = await get_config()
    if user_id in config.get("co_admins", []):
        await reply_formatted_text(update, f"User <code>{user_id}</code> pehle se Co-Admin hai.\n\n/cancel - Cancel.")
        return CA_GET_ID

    context.user_data['co_admin_to_add'] = user_id
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ko Co-Admin Banao", callback_data="co_admin_add_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]
    await reply_formatted_text(update, f"Aap user ID <code>{user_id}</code> ko <b>Co-Admin</b> banane wale hain.\n\nWoh content add, remove, aur post generate kar payenge.\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
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
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nUser ID <code>{user_id}</code> ab Co-Admin hai.")
    except Exception as e:
        logger.error(f"Co-Admin add karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Co-Admin add nahi ho paya.")

    context.user_data.clear()
    await asyncio.sleep(3)
    await admin_settings_menu(update, context)
    return ConversationHandler.END

# --- NAYA: Conversation: Co-Admin Remove ---
async def co_admin_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    config = await get_config()
    co_admins = config.get("co_admins", [])

    if not co_admins:
        await edit_formatted_message_text(context, query, "Abhi koi Co-Admin nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
        return ConversationHandler.END

    buttons = [InlineKeyboardButton(f"Remove {admin_id}", callback_data=f"co_admin_rem_{admin_id}") for admin_id in co_admins]
    keyboard = build_grid_keyboard(buttons, 1) # List me dikhao
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")])
    await edit_formatted_message_text(context, query, "Kis Co-Admin ko remove karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CR_GET_ID
async def co_admin_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.replace("co_admin_rem_", ""))
    context.user_data['co_admin_to_remove'] = user_id

    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ko Remove Karo", callback_data="co_admin_rem_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]
    await edit_formatted_message_text(context, query, f"Aap Co-Admin ID <code>{user_id}</code> ko remove karne wale hain.\n\n<b>Are you sure?</b>", reply_markup=InlineKeyboardMarkup(keyboard))
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
        await edit_formatted_message_text(context, query, f"✅ <b>Success!</b>\nCo-Admin ID <code>{user_id}</code> remove ho gaya hai.")
    except Exception as e:
        logger.error(f"Co-Admin remove karne me error: {e}")
        await edit_formatted_message_text(context, query, "❌ <b>Error!</b> Co-Admin remove nahi ho paya.")

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
        text = "Abhi koi Co-Admin nahi hai."
    else:
        text = "List of Co-Admins:\n"
        for admin_id in co_admins:
            text += f"- <code>{admin_id}</code>\n"

    await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return ConversationHandler.END


# --- NAYA: Conversation: Custom Post ---
async def custom_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_formatted_message_text(
        context, query,
        "<b>🚀 Custom Post Generator</b>\n\n"
        "Ab uss <b>Channel ka @username</b> ya <b>Group/Channel ki Chat ID</b> bhejo jahaan ye post karna hai.\n"
        "(Example: @MyAnimeChannel ya -100123456789)\n\n/cancel - Cancel.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return CPOST_GET_CHAT
async def custom_post_get_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['chat_id'] = update.message.text
    await reply_formatted_text(update, "Chat ID set! Ab post ka <b>Poster (Photo)</b> bhejo.\n\n/cancel - Cancel.")
    return CPOST_GET_POSTER
async def custom_post_get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await reply_formatted_text(update, "Ye photo nahi hai. Please ek photo bhejo.")
        return CPOST_GET_POSTER
    context.user_data['poster_id'] = update.message.photo[-1].file_id
    await reply_formatted_text(update, "Poster set! Ab post ka <b>Caption</b> (text) bhejo.\n\n/cancel - Cancel.")
    return CPOST_GET_CAPTION
async def custom_post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA: Save raw text with entities for HTML parsing
    context.user_data['caption'] = update.message.text_html
    await reply_formatted_text(update, "Caption set! Ab custom button ka <b>Text</b> bhejo.\n(Example: 'Join Now')\n\n/cancel - Cancel.")
    return CPOST_GET_BTN_TEXT
async def custom_post_get_btn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_text'] = update.message.text
    await reply_formatted_text(update, "Button text set! Ab button ka <b>URL (Link)</b> bhejo.\n(Example: 'https://t.me/mychannel')\n\n/cancel - Cancel.")
    return CPOST_GET_BTN_URL
async def custom_post_get_btn_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_url'] = update.message.text

    # Confirmation dikhao
    chat_id = context.user_data['chat_id']
    poster_id = context.user_data['poster_id']
    caption = context.user_data['caption'] # Already HTML
    btn_text = context.user_data['btn_text']
    btn_url = context.user_data['btn_url']

    keyboard = [
        [InlineKeyboardButton(btn_text, url=btn_url)],
        [InlineKeyboardButton("✅ Post Karo", callback_data="cpost_send")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]
    ]

    # NAYA: Set ParseMode to HTML for the formatted reply
    await update.message.reply_photo(
        photo=poster_id,
        caption=f"<b>--- PREVIEW ---</b>\n\n{caption}\n\n<b>Target:</b> <code>{html.escape(chat_id)}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CPOST_CONFIRM
async def custom_post_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Sending...")

    chat_id = context.user_data['chat_id']
    poster_id = context.user_data['poster_id']
    caption = context.user_data['caption'] # Already HTML
    btn_text = context.user_data['btn_text']
    btn_url = context.user_data['btn_url']

    keyboard = [[InlineKeyboardButton(btn_text, url=btn_url)]]

    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=poster_id,
            caption=caption,
            parse_mode=ParseMode.HTML, # NAYA: Use HTML
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await reply_formatted_text(query.message, f"✅ <b>Success!</b>\nPost ko '{chat_id}' par bhej diya gaya hai.")
    except Exception as e:
        logger.error(f"Custom post bhejme me error: {e}")
        await reply_formatted_text(query.message, f"❌ <b>Error!</b>\nPost '{chat_id}' par nahi bhej paya.\nError: {e}")

    await query.message.delete() # Preview delete karo
    context.user_data.clear()
    await admin_settings_menu(update, context)
    return ConversationHandler.END


# --- Conversation: User Subscription (REMOVED) ---
# --- Conversation: Admin Approval (REMOVED) ---

# --- NAYA: Conversation: Bot Preferences (Font Only) ---
async def bot_prefs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    config = await get_config()
    prefs = config.get("bot_preferences", {})
        
    # Font Status
    font = prefs.get("font", "default")
    if font == "default":
        font_status = "Default"
    elif font == "apple":
        font_status = "ᴀᴘᴘʟᴇ Sᴍᴀʟʟ Cᴀᴘꜱ"
    elif font == "sans_bold":
        font_status = "𝗦𝗮𝗻𝘀 𝗕𝗼𝗹𝗱"
    elif font == "bold":
        font_status = "Bold"
    elif font == "italic":
        font_status = "Italic"
    elif font == "monospace":
        font_status = "Monospace (Box)"
    else:
        font_status = f"Unknown ({font})"
    
    keyboard = [
        [InlineKeyboardButton(f"🔡 Change Font: {font_status}", callback_data="pref_font_menu")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "⚙️ <b>Bot Preferences</b> ⚙️\n\nYahan aap bot ke replies ka look change kar sakte hain."
    
    if query: 
        await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    return BP_MENU

async def bot_prefs_font_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config = await get_config()
    current_font = config.get("bot_preferences", {}).get("font", "default")
    
    def status(font_name):
        return " (Active)" if current_font == font_name else ""

    keyboard = [
        [InlineKeyboardButton(f"Default Font{status('default')}", callback_data="pref_font_set_default")],
        [InlineKeyboardButton(f"<b>Bold</b>{status('bold')}", callback_data="pref_font_set_bold")],
        [InlineKeyboardButton(f"<i>Italic</i>{status('italic')}", callback_data="pref_font_set_italic")],
        [InlineKeyboardButton(f"<code>Monospace (Box)</code>{status('monospace')}", callback_data="pref_font_set_monospace")],
        [InlineKeyboardButton(f"ᴀᴘᴘʟᴇ Sᴍᴀʟʟ Cᴀᴘꜱ{status('apple')}", callback_data="pref_font_set_apple")],
        [InlineKeyboardButton(f"𝗦𝗮𝗻𝘀 𝗕𝗼𝗹𝗱{status('sans_bold')}", callback_data="pref_font_set_sans_bold")],
        [InlineKeyboardButton("⬅️ Back", callback_data="pref_main_menu")]
    ]
    
    text = ("🔡 <b>Change Font</b> 🔡\n\n"
            "Select karein kaunsa font bot ke replies mein use karna hai.\n\n"
            "<b>Note:</b> Links, <code>/commands</code>, aur pehle se format kiye gaye <code>code blocks</code> par font apply nahi hoga.")
            
    await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    return BP_FONT_MENU

async def bot_prefs_font_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    font_name = query.data.replace("pref_font_set_", "") # default, apple, sans_bold, etc.
    
    config_collection.update_one(
        {"_id": "bot_config"},
        {"$set": {"bot_preferences.font": font_name}}
    )
    
    await bot_prefs_font_menu(update, context) # Refresh menu
    return BP_FONT_MENU
    
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
    await edit_formatted_message_text(context, query, "➕ <b>Add Content</b> ➕\n\nAap kya add karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
    
async def manage_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_message: bool = False):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete Anime", callback_data="admin_del_anime")],
        [InlineKeyboardButton("🗑️ Delete Season", callback_data="admin_del_season")],
        [InlineKeyboardButton("🗑️ Delete Episode", callback_data="admin_del_episode")], 
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "🗑️ <b>Delete Content</b> 🗑️\n\nAap kya delete karna chahte hain?"
    
    if from_message: # Helper for change_poster_save
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif query:
        await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- NAYA (v27): Edit Content Menu ---
async def edit_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_message: bool = False):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✏️ Edit Anime Name", callback_data="admin_edit_anime")],
        [InlineKeyboardButton("✏️ Edit Season Name", callback_data="admin_edit_season")],
        [InlineKeyboardButton("✏️ Edit Episode Number", callback_data="admin_edit_episode")], 
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "✏️ <b>Edit Content</b> ✏️\n\nAap kya edit karna chahte hain?"
    
    if from_message:
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif query:
        await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))


# --- sub_settings_menu (REMOVED) ---

async def donate_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    config = await get_config()
    donate_qr_status = "✅" if config.get('donate_qr_id') else "❌"
    keyboard = [
        [InlineKeyboardButton(f"Set Donate QR {donate_qr_status}", callback_data="admin_set_donate_qr")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "❤️ <b>Donation Settings</b> ❤️\n\nSirf QR code se donation accept karein."
    if query: 
        if query.message.photo:
            await query.message.delete()
            # NAYA: Use formatted send
            await send_formatted_message(context, query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

async def other_links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    config = await get_config()
    backup_status = "✅" if config.get('links', {}).get('backup') else "❌"
    # MODIFIED: Added download_link
    download_status = "✅" if config.get('links', {}).get('download') else "❌"
    keyboard = [
        [InlineKeyboardButton(f"Set Backup Link {backup_status}", callback_data="admin_set_backup_link")],
        [InlineKeyboardButton(f"Set Download Link {download_status}", callback_data="admin_set_download_link")], # MODIFIED
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "🔗 <b>Other Links</b> 🔗\n\nDoosre links yahan set karein."
    if query: 
        if query.message.photo:
            await query.message.delete()
            await send_formatted_message(context, query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

# NAYA: Bot Messages Menu (Paginated)
async def bot_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        # [InlineKeyboardButton("💲 Subscription Messages", callback_data="msg_menu_sub")], # REMOVED
        [InlineKeyboardButton("📥 Download Flow Messages", callback_data="msg_menu_dl")],
        [InlineKeyboardButton("✍️ Post Generator Messages", callback_data="msg_menu_postgen")],
        # [InlineKeyboardButton("🔗 Gen-Link Messages", callback_data="msg_menu_genlink")], # REMOVED
        [InlineKeyboardButton("⚙️ General Messages", callback_data="msg_menu_gen")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "⚙️ <b>Bot Messages</b> ⚙️\n\nAap bot ke replies ko edit karne ke liye category select karein."
    
    if query: 
        await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_MAIN

# --- bot_messages_menu_sub (REMOVED) ---

async def bot_messages_menu_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        # REMOVED: Unsubscribed messages
        [InlineKeyboardButton("Edit Check DM Alert", callback_data="msg_edit_user_dl_dm_alert")],
        # REMOVED: Checking Sub
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
    await edit_formatted_message_text(context, query, "📥 <b>Download Flow Messages</b> 📥\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_DL
    
async def bot_messages_menu_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Menu Greeting", callback_data="msg_edit_user_menu_greeting")],
        [InlineKeyboardButton("Edit Donate QR Error", callback_data="msg_edit_user_donate_qr_error")],
        [InlineKeyboardButton("Edit Donate QR Text", callback_data="msg_edit_user_donate_qr_text")],
        [InlineKeyboardButton("Edit Donate Thanks", callback_data="msg_edit_donate_thanks")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    await edit_formatted_message_text(context, query, "⚙️ <b>General Messages</b> ⚙️\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_GEN

async def bot_messages_menu_postgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Anime Post Caption", callback_data="msg_edit_post_gen_anime_caption")], # NAYA (v23)
        [InlineKeyboardButton("Edit Season Post Caption", callback_data="msg_edit_post_gen_season_caption")],
        [InlineKeyboardButton("Edit Episode Post Caption", callback_data="msg_edit_post_gen_episode_caption")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    await edit_formatted_message_text(context, query, "✍️ <b>Post Generator Messages</b> ✍️\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_POSTGEN

# --- bot_messages_menu_genlink (REMOVED) ---

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
    text = "🛠️ <b>Admin Settings</b> 🛠️\n\nYahan aap Co-Admins aur doosri advanced settings manage kar sakte hain."
    
    if query: 
        if query.message.photo: # Handle coming back from custom post
            await query.message.delete()
            await send_formatted_message(context, query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await edit_formatted_message_text(context, query, text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await reply_formatted_text(update, text, reply_markup=InlineKeyboardMarkup(keyboard))

    
# --- User Handlers ---
async def handle_deep_link_donate(user: User, context: ContextTypes.DEFAULT_TYPE):
    """Deep link se /start=donate ko handle karega"""
    logger.info(f"User {user.id} ne Donate deep link use kiya.")
    try:
        config = await get_config()
        qr_id = config.get('donate_qr_id')
        
        if not qr_id: 
            msg = config.get("messages", {}).get("user_donate_qr_error", "Error")
            await send_formatted_message(context, user.id, msg)
            return

        text = config.get("messages", {}).get("user_donate_qr_text", "Support us.")
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="user_back_menu")]]
        
        # NAYA: Use formatted sender
        await send_formatted_photo(
            context,
            chat_id=user.id, 
            photo=qr_id, 
            caption=text, 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.job_queue.run_once(send_donate_thank_you, 60, chat_id=user.id)
    except Exception as e:
        logger.error(f"Deep link Donate QR bhejte waqt error: {e}")
        if "blocked" in str(e):
            logger.warning(f"User {user.id} ne bot ko block kiya hua hai.")

# --- handle_deep_link_subscribe (REMOVED) ---

# --- NAYA (v26) FIX: Deep Link Download Handler ---
async def handle_deep_link_download(user: User, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """Deep link se /start=dl... ko handle karega"""
    logger.info(f"User {user.id} ne Download deep link use kiya: {payload}")
    
    # Ek dummy Update aur CallbackQuery object banayein
    # Taaki hum existing download_button_handler ko reuse kar sakein
    
    class DummyChat:
        def __init__(self, chat_id):
            self.id = chat_id
            self.type = 'private'

    class DummyMessage:
        def __init__(self, chat_id, message_id=None):
            self.chat = DummyChat(chat_id)
            self.message_id = message_id or 12345
            self.photo = None # Force it to send a new message
            self.text = "Deep link request"

    class DummyCallbackQuery:
        def __init__(self, user, data):
            self.from_user = user
            self.data = data
            self.message = DummyMessage(user.id)
        
        async def answer(self, *args, **kwargs):
            # Deep link ke liye answer() kuch nahi karega
            pass
        
        # (Yahan 'edit_message_text' aur 'edit_message_caption' functions
        #   jaanबूझकर nahi diye gaye hain, taaki 'hasattr' check kaam kare)
            
    class DummyUpdate:
        def __init__(self, user, data):
                self.callback_query = DummyCallbackQuery(user, data)
                self.effective_user = user

    dummy_update = DummyUpdate(user, payload)
    
    try:
        # Ab 'download_button_handler' ko call karo
        await download_button_handler(dummy_update, context)
    except Exception as e:
        logger.error(f"Deep link download handler fail ho gaya: {e}", exc_info=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart /start command (v23)"""
    user = update.effective_user
    user_id, first_name = user.id, user.first_name
    logger.info(f"User {user_id} ({first_name}) ne /start dabaya.")
    
    # User DB logic (waise hi rahega)
    user_data = users_collection.find_one({"_id": user_id})
    if not user_data:
        # MODIFIED: Removed sub fields
        users_collection.insert_one({"_id": user_id, "first_name": first_name, "username": user.username})
        logger.info(f"Naya user database me add kiya: {user_id}")
    else:
        users_collection.update_one(
            {"_id": user_id},
            {"$set": {"first_name": first_name, "username": user.username}}
        )
    
    args = context.args
    if args:
        # (v17 Fix: Handle deep links with spaces)
        payload = " ".join(args) 
        logger.info(f"User {user_id} ne deep link use kiya: {payload}")
        
        # --- NAYA (v26) FIX: 'dl' link ko handle karo ---
        if payload.startswith("dl"):
            await handle_deep_link_download(user, context, payload)
            return
        # --- FIX KHATAM ---
            
        elif payload == "donate":
            await handle_deep_link_donate(user, context)
            return
    
    # ============================================
    # ===           NAYA FIX (v23)             ===
    # === /start ab sirf welcome karega      ===
    # ============================================
    logger.info("Koi deep link nahi. Sirf welcome message bhej raha hoon.")
    # Check karo ki admin hai ya user
    if await is_co_admin(user_id):
        await reply_formatted_text(update, f"Salaam, Admin! Admin panel ke liye /menu use karein.")
    else:
        await reply_formatted_text(update, f"Salaam, {html.escape(first_name)}! Apna user menu dekhne ke liye /subscription use karein.")
    
async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    """User ka main menu (/menu)"""
    user = update.effective_user
    user_id = user.id
    
    if from_callback:
        logger.info(f"User {user_id} 'Back to Menu' se aaya.")
    else:
        logger.info(f"User {user_id} ne /menu khola.")
    
    config = await get_config()
    links = config.get('links', {})
    
    # MODIFIED: Removed subscription check and button
    
    backup_url = links.get('backup') or "https://t.me/"
        
    btn_backup = InlineKeyboardButton("Backup", url=backup_url)
    btn_donate = InlineKeyboardButton("Donate", callback_data="user_show_donate_menu")
    # REMOVED: btn_support
    
    keyboard = [[btn_backup, btn_donate]] # MODIFIED: Simplified layout
    
    menu_text = config.get("messages", {}).get("user_menu_greeting", "Salaam {first_name}!")
    menu_text = menu_text.replace("{first_name}", html.escape(user.first_name))
    
    if from_callback:
        query = update.callback_query
        await query.answer()
        try:
            if query.message.photo:
                await query.message.delete()
                # NAYA: Use formatted send
                await send_formatted_message(context, query.from_user.id, menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                # NAYA: Use formatted edit
                await edit_formatted_message_text(context, query, menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.warning(f"Menu edit/reply nahi kar paya: {e}")
            try:
                await send_formatted_message(context, query.from_user.id, menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e2:
                logger.error(f"Menu command (callback) me critical error: {e2}")
    else:
        # NAYA: Use formatted reply
        await reply_formatted_text(update, menu_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def user_show_donate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/menu se Donate button ko handle karega (DM bhejega)"""
    query = update.callback_query
    config = await get_config()
    qr_id = config.get('donate_qr_id')
    
    if not qr_id: 
        msg = config.get("messages", {}).get("user_donate_qr_error", "Error")
        # NAYA: Format alert
        formatted_msg, _ = await format_bot_reply(msg)
        await query.answer(formatted_msg, show_alert=True)
        return

    text = config.get("messages", {}).get("user_donate_qr_text", "Support us.")
    
    try:
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="user_back_menu")]]
        
        # NAYA (v10) FIX: Purana menu message delete karo
        if not query.message.photo:
                await query.message.delete()
                
        # NAYA: Use formatted sender
        await send_formatted_photo(
            context,
            chat_id=query.from_user.id,
            photo=qr_id,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
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
                await reply_formatted_text(update, "Aap admin nahi hain.")
            else:
                await update.callback_query.answer("Aap admin nahi hain.", show_alert=True)
        return
        
    logger.info("Admin/Co-Admin ne /admin command use kiya.")
    
    # NAYA (v10): Co-Admin limited menu
    if not await is_main_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")],
            [InlineKeyboardButton("🗑️ Delete Content", callback_data="admin_menu_manage_content")], # MODIFIED
            [InlineKeyboardButton("✏️ Edit Content", callback_data="admin_menu_edit_content")], # NAYA (v27)
            [InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")],
            [
                InlineKeyboardButton("🖼️ Update Photo", callback_data="admin_update_photo"),
                InlineKeyboardButton("🔗 Gen Link", callback_data="admin_gen_link") # <-- NAYA
            ]
        ]
        admin_menu_text = f"Salaam, Co-Admin! 👑\nAapka content panel taiyyar hai."
    
    # Main Admin full menu
    else:
        # REMOVED: log_url logic (not needed)

        # NAYA (v12) FIX: User ke request ke mutabik naya layout (Admin Settings neeche)
        # MODIFIED: Removed Sub, Gen Link, Sub List, Sub Log
        keyboard = [
            [InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")],
            [
                InlineKeyboardButton("🗑️ Delete Content", callback_data="admin_menu_manage_content"), # MODIFIED
                InlineKeyboardButton("✏️ Edit Content", callback_data="admin_menu_edit_content") # NAYA (v27)
            ],
            [
                InlineKeyboardButton("🔗 Other Links", callback_data="admin_menu_other_links"),
                InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")
            ],
            [
                InlineKeyboardButton("❤️ Donation", callback_data="admin_menu_donate_settings"),
                InlineKeyboardButton("⏱️ Auto-Delete Time", callback_data="admin_set_delete_time") # MODIFIED: Replaced Sub settings
            ],
            [
                InlineKeyboardButton("🖼️ Update Photo", callback_data="admin_update_photo"), # <-- MODIFIED ROW
                InlineKeyboardButton("🔗 Gen Link", callback_data="admin_gen_link") # <-- NAYA
            ],
            [
                InlineKeyboardButton("⚙️ Bot Messages", callback_data="admin_menu_messages"),
                InlineKeyboardButton("💅 Bot Preferences", callback_data="admin_menu_prefs") # NAYA: User Request
            ],
            [InlineKeyboardButton("🛠️ Admin Settings", callback_data="admin_menu_admin_settings")] # FIX: Last row
        ]
        admin_menu_text = f"Salaam, Admin Boss! 👑\nAapka control panel taiyyar hai."
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if from_callback:
        query = update.callback_query
        try:
            if query.message.photo:
                await query.message.delete()
                await send_formatted_message(context, query.from_user.id, admin_menu_text, reply_markup=reply_markup)
            else:
                await edit_formatted_message_text(context, query, admin_menu_text, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.warning(f"Admin menu edit nahi kar paya: {e}")
            await query.answer()
        except Exception as e:
            logger.warning(f"Admin menu edit error: {e}")
            await query.answer()
    else:
        await reply_formatted_text(update, admin_menu_text, reply_markup=reply_markup)

# --- admin_list_subs (REMOVED) ---
# --- placeholder_button_handler (REMOVED) ---

# --- User Download Handler (CallbackQuery) ---
async def download_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback data 'dl' se shuru hone wale sabhi buttons ko handle karega.
    MODIFIED: Subscription check has been removed.
    """
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    config = await get_config() 
    
    # (v23 Fix: 'delete' crash ko fix karne ke liye)
    is_deep_link = not hasattr(query.message, 'edit_message_caption')
    is_in_dm = False # Default
    
    # --- NAYA (v28) FIX: "Fetching" message ke liye ---
    checking_msg_id = None
    
    try:
        # Step 1: Click ko acknowledge karo
        if not is_deep_link:
            is_in_dm = query.message.chat.type == 'private'
            if not is_in_dm:
                # Channel/Group me click
                alert_msg = config.get("messages", {}).get("user_dl_dm_alert", "Check DM")
                # NAYA: Format alert
                formatted_alert_msg, _ = await format_bot_reply(alert_msg)
                await query.answer(formatted_alert_msg, show_alert=True)
            else:
                # DM me click
                await query.answer()
        
        # Step 2: "Checking..." message bhejo (Sabhi cases me)
        # MODIFIED: No longer checking subscription, but good for user feedback
        try:
            checking_text = "⏳ Fetching files..." # MODIFIED
            # --- NAYA (v28) FIX: Message ID save karo ---
            # NAYA: Use formatted send
            sent_msg = await send_formatted_message(context, chat_id=user_id, text=checking_text, read_timeout=10, write_timeout=10)
            checking_msg_id = sent_msg.message_id
        except Exception as e:
            logger.error(f"User {user_id} ko 'Fetching...' message nahi bhej paya. Shayad bot block hai? Error: {e}")
            if not is_deep_link and not is_in_dm:
                await query.answer("❌ Error! Bot ko DM mein /start karke unblock karein.", show_alert=True)
            return # Function rok do

        # Step 3: Check Subscription (REMOVED)
            
        # Step 4: User is "Subscribed" (i.e., allowed)
        # (The 'checking_msg' will be deleted by the logic below)

        parts = query.data.split('__')
        
        # (v17 Fix: 'dl_' aur 'dl' dono ko handle karo)
        anime_key = parts[0]
        if anime_key.startswith("dl_"):
            anime_key = anime_key.replace("dl_", "") # Puraana format (dl_ANIME_NAME...)
        elif anime_key.startswith("dl"):
            anime_key = anime_key.replace("dl", "")  # Naya format (dlANIME_ID...)
            
        season_name = parts[1] if len(parts) > 1 else None
        ep_num = parts[2] if len(parts) > 2 else None
        
        anime_doc = None
        try:
            # 1. Pehle ObjectId se search karne ki koshish karo (Naya format)
            anime_doc = animes_collection.find_one({"_id": ObjectId(anime_key)})
        except Exception:
            # 2. Agar woh fail ho (yaani woh ID nahi, naam hai), toh Name se search karo (Puraana format)
            logger.warning(f"ObjectId '{anime_key}' nahi mila. Name se search kar raha hoon...")
            anime_doc = animes_collection.find_one({"name": anime_key})
        
        if not anime_doc:
            logger.error(f"Anime '{anime_key}' na ID se mila na Name se.")
            msg = config.get("messages", {}).get("user_dl_anime_not_found", "Error")
            await send_formatted_message(context, user_id, msg)
            
            # --- NAYA (v28) FIX: Error par "Fetching" delete karo ---
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
            return
            
        anime_name = anime_doc['name'] 
        anime_id_str = str(anime_doc['_id']) 
        
        # ============================================
        # ===           NAYA FIX (v24)             ===
        # ===   Auto-delete ke liye seconds lao    ===
        # ============================================
        delete_time = config.get("delete_seconds", 300) 
        # ============================================

        # Case 3: Episode click hua hai -> Saare Files Bhejo
        if ep_num:
            # --- NAYA (v28) FIX: "Fetching" delete karo ---
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
            
            # ============================================
            # ===     NAYA FIX: Instant List Delete    ===
            # ============================================
            try:
                if is_in_dm and query.message.photo: # Sirf DM mein aur agar photo message hai (yaani season/ep list hai)
                    await query.message.delete()
                    logger.info(f"User {user_id} ke liye episode list delete kar di.")
            except Exception as e:
                logger.warning(f"Episode list delete nahi kar paya: {e}")
            # ============================================

            qualities_dict = anime_doc.get("seasons", {}).get(season_name, {}).get(ep_num, {})
            if not qualities_dict:
                msg = config.get("messages", {}).get("user_dl_episodes_not_found", "Error")
                await send_formatted_message(context, user_id, msg)
                return
            
            msg = config.get("messages", {}).get("user_dl_sending_files", "Sending...")
            msg = msg.replace("{anime_name}", html.escape(anime_name)).replace("{season_name}", html.escape(season_name)).replace("{ep_num}", html.escape(ep_num))
            
            sent_msg = await send_formatted_message(context, user_id, msg)
            msg_to_delete_id = sent_msg.message_id
            
            QUALITY_ORDER = ['480p', '720p', '1080p', '4K']
            available_qualities = qualities_dict.keys()
            sorted_q_list = [q for q in QUALITY_ORDER if q in available_qualities]
            extra_q = [q for q in available_qualities if q not in sorted_q_list]
            sorted_q_list.extend(extra_q)
            
            delete_minutes = max(1, delete_time // 60)
            warning_template = config.get("messages", {}).get("file_warning", "Warning")
            warning_msg = warning_template.replace('{minutes}', str(delete_minutes))
            
            for quality in sorted_q_list:
                file_id = qualities_dict.get(quality)
                if not file_id: continue
                
                sent_message = None 
                try:
                    caption = f"🎬 <b>{html.escape(anime_name)}</b>\nS{html.escape(season_name)} - E{html.escape(ep_num)} ({quality})\n\n{warning_msg}"
                    
                    # NAYA: Use formatted send (Quotes/Fonts apply nahi honge, but uses HTML)
                    formatted_caption, _ = await format_bot_reply(caption)
                    
                    sent_message = await context.bot.send_video(
                        chat_id=user_id, 
                        video=file_id, 
                        caption=formatted_caption,
                        parse_mode=ParseMode.HTML
                    )
                except Exception as e:
                    logger.error(f"User {user_id} ko file bhejte waqt error: {e}")
                    error_msg_key = "user_dl_blocked_error" if "blocked" in str(e) else "user_dl_file_error"
                    msg = config.get("messages", {}).get(error_msg_key, "Error")
                    msg = msg.replace("{quality}", quality)
                    await send_formatted_message(context, user_id, msg) 
                
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
            
        # ============================================
        # ===           NAYA FIX (v24)             ===
        # ===  Selection Menus ko delete karo      ===
        # ============================================
        sent_selection_message = None # Delete karne ke liye message save karo
        # ============================================

        # Case 2: Season click hua hai -> Episode Bhejo
        if season_name:
            episodes = anime_doc.get("seasons", {}).get(season_name, {})
            
            episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
            
            if not episode_keys:
                msg = config.get("messages", {}).get("user_dl_episodes_not_found", "Error")
                # --- NAYA (v28) FIX: "Fetching" delete karo ---
                if checking_msg_id:
                    try: await context.bot.delete_message(user_id, checking_msg_id)
                    except Exception: pass
                
                if is_in_dm:
                    if query.message.photo:
                        await edit_formatted_message_caption(context, query, msg)
                    else:
                        await reply_formatted_text(query.message, msg)
                else:
                    await send_formatted_message(context, user_id, msg)
                return
            
            sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"dl{anime_id_str}__{season_name}__{ep}") for ep in sorted_eps] # NAYA (v1V): Use ID
            keyboard = build_grid_keyboard(buttons, 2)
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"dl{anime_id_str}")]) # NAYA (v1V): Use ID
            
            msg = config.get("messages", {}).get("user_dl_select_episode", "Select episode")
            msg = msg.replace("{anime_name}", html.escape(anime_name)).replace("{season_name}", html.escape(season_name))

            season_poster_id = anime_doc.get("seasons", {}).get(season_name, {}).get("_poster_id")
            poster_to_use = season_poster_id or anime_doc['poster_id'] 
            
            # --- NAYA (v28) FIX: "Fetching" delete karo ---
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
            
            # (v23 Fix: 'DummyMessage' delete bug)
            if is_deep_link:
                # Deep link hai -> Hamesha nayi photo DM me bhejo
                sent_selection_message = await send_formatted_photo(
                    context,
                    chat_id=user_id, 
                    photo=poster_to_use, 
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else: 
                # Channel ya DM me click hua hai (real message)
                try:
                    if not query.message.photo:
                        await query.message.delete() # Ab yeh safe hai, kyunki is_deep_link False hai
                        sent_selection_message = await send_formatted_photo(
                            context,
                            chat_id=user_id,
                            photo=poster_to_use, 
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        # NAYA: Use formatted edit
                        await edit_formatted_message_media(
                            context, query,
                            media=InputMediaPhoto(media=poster_to_use, caption=msg),
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        sent_selection_message = query.message # Edit kiye gaye message ko save karo
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        logger.warning(f"DL Handler Case 2: Media edit fail, fallback to caption: {e}")
                        await edit_formatted_message_caption( 
                            context, query,
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                        sent_selection_message = query.message # Edit kiye gaye message ko save karo
                except Exception as e:
                    logger.error(f"DL Handler Case 2: Media edit critical fail: {e}")
                    await edit_formatted_message_caption( 
                        context, query,
                        caption=msg,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    sent_selection_message = query.message # Edit kiye gaye message ko save karo
            
            # ============================================
            # ===           NAYA FIX (v24)             ===
            # ============================================
            if sent_selection_message:
                asyncio.create_task(delete_message_later(
                    bot=context.bot,
                    chat_id=user_id,
                    message_id=sent_selection_message.message_id, 
                    seconds=delete_time 
                ))
            # ============================================
            return
            
        # Case 1: Sirf Anime click hua hai -> Season Bhejo
        seasons = anime_doc.get("seasons", {})
        if not seasons:
            msg = config.get("messages", {}).get("user_dl_seasons_not_found", "Error")
            # --- NAYA (v28) FIX: "Fetching" delete karo ---
            if checking_msg_id:
                try: await context.bot.delete_message(user_id, checking_msg_id)
                except Exception: pass
                
            if is_in_dm: 
                if query.message.photo:
                    await edit_formatted_message_caption(context, query, msg)
                else:
                    await edit_formatted_message_text(context, query, msg)
            else: 
                await send_formatted_message(context, user_id, msg)
            return
        
        sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
        buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"dl{anime_id_str}__{s}") for s in sorted_seasons] # NAYA (v17): Use ID
        keyboard = build_grid_keyboard(buttons, 1) 
        keyboard.append([InlineKeyboardButton("⬅️ Back to Bot Menu", callback_data="user_back_menu")])
        
        msg = config.get("messages", {}).get("user_dl_select_season", "Select season")
        msg = msg.replace("{anime_name}", html.escape(anime_name))

        # --- NAYA (v28) FIX: "Fetching" delete karo ---
        if checking_msg_id:
            try: await context.bot.delete_message(user_id, checking_msg_id)
            except Exception: pass
            
        # (v23 Fix: 'DummyMessage' delete bug)
        if is_deep_link:
            # Deep link hai -> Hamesha nayi photo DM me bhejo
            sent_selection_message = await send_formatted_photo(
                context,
                chat_id=user_id, 
                photo=anime_doc['poster_id'], 
                caption=msg,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else: 
            # DM me hai, aur deep link nahi hai (yaani purane message par click kiya)
            if not query.message.photo:
                await query.message.delete() # Safe hai
                sent_selection_message = await send_formatted_photo(
                    context,
                    chat_id=user_id,
                    photo=anime_doc['poster_id'], 
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await edit_formatted_message_caption(
                    context, query,
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                sent_selection_message = query.message # Edit kiye gaye message ko save karo

        # ============================================
        # ===           NAYA FIX (v24)             ===
        # ============================================
        if sent_selection_message:
            asyncio.create_task(delete_message_later(
                bot=context.bot,
                chat_id=user_id,
                message_id=sent_selection_message.message_id, 
                seconds=delete_time 
            ))
        # ============================================
        return

    except Exception as e:
        # Main error handler
        logger.error(f"Download button handler me error: {e}", exc_info=True)
        # --- NAYA (v28) FIX: Error par "Fetching" delete karo ---
        if checking_msg_id:
            try: await context.bot.delete_message(user_id, checking_msg_id)
            except Exception: pass
            
        msg = config.get("messages", {}).get("user_dl_general_error", "Error")
        try:
            if not is_deep_link and query.message and query.message.chat.type in ['channel', 'supergroup', 'group']:
                    await query.answer(msg, show_alert=True)
            else:
                    await send_formatted_message(context, user_id, msg)
        except Exception: pass
        

# --- Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error} \nUpdate: {update}", exc_info=True)

# ============================================
# ===    NAYA WEBHOOK AUR THREADING SETUP    ===
# ============================================

# --- NAYA: Flask Server Setup ---
app = Flask(__name__)

# Global variable to hold the bot application
bot_app = None
# Global variable to hold the bot's event loop
bot_loop = None

@app.route('/')
def home():
    """Render ka health check yahaan aayega."""
    return "I am alive and running!", 200

@app.route(f"/{BOT_TOKEN}", methods=['POST'])
def webhook():
    """
    Yeh SYNC function hai jo Waitress chalaayega.
    Yeh message ko pakad kar ASYNC bot ko de dega.
    """
    global bot_app, bot_loop
    if request.is_json:
        update_data = request.get_json()
        update = Update.de_json(update_data, bot_app.bot)
        
        try:
            # Update ko bot ke async thread mein process karne ke liye bhejo
            asyncio.run_coroutine_threadsafe(bot_app.process_update(update), bot_loop)
        except Exception as e:
            logger.error(f"Update ko threadsafe bhejne mein error: {e}", exc_info=True)
            
        return "OK", 200
    else:
        return "Bad request", 400

# --- NAYA: Bot ko alag thread mein chalaane ke liye function ---
def run_async_bot_tasks(loop, app):
    """
    Yeh function ek naye thread mein chalega.
    Yeh bot ka async setup karega aur uske loop ko zinda rakhega.
    """
    global bot_loop
    bot_loop = loop # Loop ko global variable mein save karo
    asyncio.set_event_loop(loop) # Is thread ko naya loop do
    
    try:
        # Webhook set karo
        webhook_path_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
        logger.info(f"Webhook ko {webhook_path_url} par set kar raha hai...")
        # Normal (sync) httpx request ka istemaal karo
        httpx.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_path_url}")
        logger.info("Webhook successfully set!")

        # Bot ko start karo
        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.start())
        logger.info("Bot application initialized and started (async).")
        
        # Is thread mein loop ko hamesha zinda rakho
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
    
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    # --- Saare Handlers (Aapke original code se) ---
    
    global_cancel_handler = CommandHandler("cancel", cancel)
    global_fallbacks = [
        CommandHandler("start", cancel),
        CommandHandler("menu", cancel),
        CommandHandler("admin", cancel),
        global_cancel_handler 
    ]
    admin_menu_fallback = [CallbackQueryHandler(back_to_admin_menu, pattern="^admin_menu$"), global_cancel_handler]
    add_content_fallback = [CallbackQueryHandler(back_to_add_content_menu, pattern="^back_to_add_content$"), global_cancel_handler]
    manage_fallback = [CallbackQueryHandler(back_to_manage_menu, pattern="^back_to_manage$"), global_cancel_handler]
    edit_fallback = [CallbackQueryHandler(back_to_edit_menu, pattern="^back_to_edit_menu$"), global_cancel_handler] # NAYA (v27)
    sub_settings_fallback = [CallbackQueryHandler(back_to_sub_settings_menu, pattern="^back_to_sub_settings$"), global_cancel_handler]
    donate_settings_fallback = [CallbackQueryHandler(back_to_donate_settings_menu, pattern="^back_to_donate_settings$"), global_cancel_handler]
    links_fallback = [CallbackQueryHandler(back_to_links_menu, pattern="^back_to_links$"), global_cancel_handler]
    user_menu_fallback = [CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"), global_cancel_handler]
    messages_fallback = [CallbackQueryHandler(back_to_messages_menu, pattern="^admin_menu_messages$"), global_cancel_handler]
    admin_settings_fallback = [CallbackQueryHandler(back_to_admin_settings_menu, pattern="^back_to_admin_settings$"), global_cancel_handler]
    
    # NAYA (v28): Gen Link Fallback
    gen_link_fallback = [CallbackQueryHandler(gen_link_menu, pattern="^admin_gen_link$"), global_cancel_handler]
    
    # NAYA: Bot Prefs Fallback
    bot_prefs_fallback = [CallbackQueryHandler(back_to_bot_prefs_menu, pattern="^pref_main_menu$"), global_cancel_handler]


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
            # NAYA (v10)
            S_GET_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_season_desc),
                CommandHandler("skip", skip_season_desc)
            ],
            S_CONFIRM: [CallbackQueryHandler(save_season, pattern="^save_season$")]
        }, 
        fallbacks=global_fallbacks + add_content_fallback,
        allow_reentry=True 
    )
    add_episode_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_episode_start, pattern="^admin_add_episode$")], 
        states={
            E_GET_ANIME: [
                CallbackQueryHandler(add_episode_show_anime_list, pattern="^addep_page_"), 
                CallbackQueryHandler(get_anime_for_episode, pattern="^ep_anime_")
            ], 
            E_GET_SEASON: [
                CallbackQueryHandler(get_season_for_episode, pattern="^ep_season_"),
                # NAYA (v10) BUG FIX: Back button ko state me add karo
                CallbackQueryHandler(add_episode_show_anime_list, pattern="^addep_page_") 
            ], 
            E_GET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_episode_number)],
            # NAYA FIX (v12): filters.ALL ko rakha hai, lekin logic functions (get_480p_file etc.) ab error handle karte hain
            E_GET_480P: [MessageHandler(filters.ALL & ~filters.COMMAND, get_480p_file), CommandHandler("skip", skip_480p)],
            E_GET_720P: [MessageHandler(filters.ALL & ~filters.COMMAND, get_720p_file), CommandHandler("skip", skip_720p)],
            E_GET_1080P: [MessageHandler(filters.ALL & ~filters.COMMAND, get_1080p_file), CommandHandler("skip", skip_1080p)],
            E_GET_4K: [MessageHandler(filters.ALL & ~filters.COMMAND, get_4k_file), CommandHandler("skip", skip_4k)],
        }, 
        fallbacks=global_fallbacks + add_content_fallback,
        allow_reentry=True 
    )
    # set_sub_qr_conv = ... # REMOVED
    # set_price_conv = ... # REMOVED
    set_donate_qr_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_donate_qr_start, pattern="^admin_set_donate_qr$")], 
        states={CD_GET_QR: [MessageHandler(filters.PHOTO, set_donate_qr_save)]}, 
        fallbacks=global_fallbacks + donate_settings_fallback,
        allow_reentry=True 
    )
    # MODIFIED: Updated patterns
    set_links_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_links_start, pattern="^admin_set_backup_link$|^admin_set_download_link$")], 
        states={CL_GET_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link), CommandHandler("skip", skip_link)]}, 
        fallbacks=global_fallbacks + links_fallback,
        allow_reentry=True 
    ) 
    post_gen_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(post_gen_menu, pattern="^admin_post_gen$")], 
        states={
            PG_MENU: [CallbackQueryHandler(post_gen_select_anime, pattern="^post_gen_season$|^post_gen_episode$|^post_gen_anime$")], # v23 FIX
            PG_GET_ANIME: [
                CallbackQueryHandler(post_gen_show_anime_list, pattern="^postgen_page_"),
                CallbackQueryHandler(post_gen_select_season, pattern="^post_anime_")
            ], 
            PG_GET_SEASON: [
                CallbackQueryHandler(post_gen_select_episode, pattern="^post_season_"),
                # NAYA (v10) BUG FIX: Back button ko state me add karo
                CallbackQueryHandler(post_gen_show_anime_list, pattern="^postgen_page_") 
            ], 
            PG_GET_EPISODE: [
                CallbackQueryHandler(post_gen_final_episode, pattern="^post_ep_"),
                # NAYA (v10) BUG FIX: Back button ko state me add karo
                CallbackQueryHandler(post_gen_select_season, pattern="^post_anime_") 
            ], 
            # --- YEH NAYI LINE ADD KARO ---
            PG_GET_SHORT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_gen_get_short_link)],
            # ---
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
                # NAYA (v10) BUG FIX: Back button ko state me add karo
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
                # NAYA (v10) BUG FIX: Back button ko state me add karo
                CallbackQueryHandler(delete_episode_show_anime_list, pattern="^delep_page_") 
            ],
            DE_GET_EPISODE: [
                CallbackQueryHandler(delete_episode_confirm, pattern="^del_ep_num_"),
                # NAYA (v10) BUG FIX: Back button ko state me add karo
                CallbackQueryHandler(delete_episode_select_season, pattern="^del_ep_anime_") 
            ],
            DE_CONFIRM: [CallbackQueryHandler(delete_episode_do, pattern="^del_ep_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    # NAYA (v10)
    update_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_photo_start, pattern="^admin_update_photo$")],
        states={
            UP_GET_ANIME: [
                CallbackQueryHandler(update_photo_show_anime_list, pattern="^upphoto_page_"),
                CallbackQueryHandler(update_photo_select_target, pattern="^upphoto_anime_")
            ],
            UP_GET_TARGET: [
                CallbackQueryHandler(update_photo_get_poster, pattern="^upphoto_target_"),
                # NAYA (v1a0) BUG FIX: Back button ko state me add karo
                CallbackQueryHandler(update_photo_show_anime_list, pattern="^upphoto_page_") 
            ],
            # NAYA FIX (v12): Invalid input ko handle karo
            UP_GET_POSTER: [
                MessageHandler(filters.PHOTO, update_photo_save),
                MessageHandler(filters.ALL & ~filters.COMMAND & ~filters.PHOTO, update_photo_invalid_input)
            ]
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    # --- NAYA (v27): Edit Conversations ---
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
                CallbackQueryHandler(edit_season_show_anime_list, pattern="^editseason_page_") # Back
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
                CallbackQueryHandler(edit_episode_show_anime_list, pattern="^editep_page_") # Back
            ],
            EE_GET_EPISODE: [
                CallbackQueryHandler(edit_episode_get_new_num, pattern="^edit_ep_num_"),
                CallbackQueryHandler(edit_episode_select_season, pattern="^edit_ep_anime_") # Back
            ],
            EE_GET_NEW_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_episode_save)],
            EE_CONFIRM: [CallbackQueryHandler(edit_episode_do, pattern="^edit_ep_confirm_yes$")]
        },
        fallbacks=global_fallbacks + edit_fallback,
        allow_reentry=True
    )
    # --- Edit Conversations End ---

    # --- NAYA (v28): Generate Link Conv ---
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
    
    # remove_sub_conv = ... # REMOVED
    
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
    # set_days_conv = ... # REMOVED
    set_delete_time_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_delete_time_start, pattern="^admin_set_delete_time$")],
        states={CS_GET_DELETE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_delete_time_save)]},
        fallbacks=global_fallbacks + admin_menu_fallback, # MODIFIED: Fallback to main menu
        allow_reentry=True 
    )
    set_messages_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_messages_menu, pattern="^admin_menu_messages$")],
        states={
            M_MENU_MAIN: [
                # CallbackQueryHandler(bot_messages_menu_sub, pattern="^msg_menu_sub$"), # REMOVED
                CallbackQueryHandler(bot_messages_menu_dl, pattern="^msg_menu_dl$"),
                CallbackQueryHandler(bot_messages_menu_postgen, pattern="^msg_menu_postgen$"),
                # CallbackQueryHandler(bot_messages_menu_genlink, pattern="^msg_menu_genlink$"), # REMOVED
                CallbackQueryHandler(bot_messages_menu_gen, pattern="^msg_menu_gen$"),
            ],
            # M_MENU_SUB: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")], # REMOVED
            M_MENU_DL: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_POSTGEN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            # M_MENU_GENLINK: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")], # REMOVED
            M_MENU_GEN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_GET_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_msg_save)],
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    # NAYA: Bot Preferences Conversation (REMOVED QUOTE STATES)
    bot_prefs_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_prefs_menu, pattern="^admin_menu_prefs$")],
        states={
            BP_MENU: [
                CallbackQueryHandler(bot_prefs_font_menu, pattern="^pref_font_menu$"),
            ],
            BP_FONT_MENU: [
                CallbackQueryHandler(bot_prefs_font_set, pattern="^pref_font_set_"),
                CallbackQueryHandler(back_to_bot_prefs_menu, pattern="^pref_main_menu$"), # Back button
            ]
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    # sub_conv = ... # REMOVED
    # admin_approve_conv = ... # REMOVED
    
    # --- Saare handlers ko bot_app me add karo ---
    bot_app.add_handler(add_anime_conv)
    bot_app.add_handler(add_season_conv)
    bot_app.add_handler(add_episode_conv)
    # bot_app.add_handler(set_sub_qr_conv) # REMOVED
    # bot_app.add_handler(set_price_conv) # REMOVED
    bot_app.add_handler(set_donate_qr_conv)
    bot_app.add_handler(set_links_conv)
    bot_app.add_handler(post_gen_conv)
    bot_app.add_handler(del_anime_conv)
    bot_app.add_handler(del_season_conv)
    bot_app.add_handler(del_episode_conv)
    bot_app.add_handler(update_photo_conv) # NAYA (v10)
    
    # --- NAYA (v27): Edit Handlers ---
    bot_app.add_handler(edit_anime_conv)
    bot_app.add_handler(edit_season_conv)
    bot_app.add_handler(edit_episode_conv)
    # ---
    
    # --- NAYA (v28): Gen Link Handler ---
    bot_app.add_handler(gen_link_conv)
    
    # bot_app.add_handler(remove_sub_conv) # REMOVED
    bot_app.add_handler(add_co_admin_conv) 
    bot_app.add_handler(remove_co_admin_conv) 
    bot_app.add_handler(custom_post_conv) 
    # bot_app.add_handler(set_days_conv) # REMOVED
    bot_app.add_handler(set_delete_time_conv) 
    bot_app.add_handler(set_messages_conv) 
    
   # NAYA: Bot Prefs Handler
    bot_app.add_handler(bot_prefs_conv)
    
    # bot_app.add_handler(sub_conv) # REMOVED
    # bot_app.add_handler(admin_approve_conv) # REMOVED

    # Standard commands
   # Standard commands (v22 RE-MAPPED)
    bot_app.add_handler(CommandHandler("start", start_command)) # Start hamesha user menu/deep link
    bot_app.add_handler(CommandHandler("subscription", subscription_command)) # Naya command user menu ke liye
    bot_app.add_handler(CommandHandler("menu", menu_command)) # /menu ab admin panel hai
    bot_app.add_handler(CommandHandler("admin", admin_command)) # /admin bhi admin panel hai (alias)

    # Admin menu navigation (non-conversation)
    bot_app.add_handler(CallbackQueryHandler(add_content_menu, pattern="^admin_menu_add_content$"))
    bot_app.add_handler(CallbackQueryHandler(manage_content_menu, pattern="^admin_menu_manage_content$"))
    bot_app.add_handler(CallbackQueryHandler(edit_content_menu, pattern="^admin_menu_edit_content$")) # NAYA (v27)
    # bot_app.add_handler(CallbackQueryHandler(sub_settings_menu, pattern="^admin_menu_sub_settings$")) # REMOVED
    bot_app.add_handler(CallbackQueryHandler(donate_settings_menu, pattern="^admin_menu_donate_settings$"))
    bot_app.add_handler(CallbackQueryHandler(other_links_menu, pattern="^admin_menu_other_links$"))
    # bot_app.add_handler(CallbackQueryHandler(admin_list_subs, pattern="^admin_list_subs$")) # REMOVED
    bot_app.add_handler(CallbackQueryHandler(admin_settings_menu, pattern="^admin_menu_admin_settings$")) 
    bot_app.add_handler(CallbackQueryHandler(co_admin_list, pattern="^admin_list_co_admin$")) 

    # User menu navigation (non-conversation)
    # bot_app.add_handler(CallbackQueryHandler(user_subscribe_start, pattern="^user_subscribe$")) # REMOVED
    bot_app.add_handler(CallbackQueryHandler(user_show_donate_menu, pattern="^user_show_donate_menu$"))
    bot_app.add_handler(CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"))

    # Admin log channel actions (non-conversation)
    # bot_app.add_handler(CallbackQueryHandler(admin_reject_user, pattern="^admin_reject_")) # REMOVED

    # User Download Flow (Non-conversation)
    bot_app.add_handler(CallbackQueryHandler(download_button_handler, pattern="^dl"))
    
    # Placeholders
    # bot_app.add_handler(CallbackQueryHandler(placeholder_button_handler, pattern="^user_check_sub$")) # REMOVED

    # Error handler
    bot_app.add_error_handler(error_handler)
    
   # --- NAYA: Threading setup ---
    # 1. Bot ke liye naya event loop banayein
    bot_event_loop = asyncio.new_event_loop()
    
    # 2. Bot ko naye thread mein start karein
    bot_thread = threading.Thread(
        target=run_async_bot_tasks,
        args=(bot_event_loop, bot_app), # 'bot_app' pass karein
        daemon=True
    )
    bot_thread.start()
    
    # 3. Main thread mein Flask/Waitress server start karein
    logger.info(f"Main thread mein Waitress server ko 0.0.0.0:{PORT} par start kar raha hai...")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == "__main__":
    main()
