# ============================================
# ===       COMPLETE FINAL FIX (v14)       ===
# ============================================
# === (FIX: Dual Link Handling ID & Name)  ===
# ===   (FIX: Deep link space handling)    ===
# ===   (FIX: Add Episode state handling)  ===
# ============================================
import os
import logging
import re
import asyncio # Auto-delete aur Threading ke liye
import threading # Threading ke liye
import httpx # Webhook set karne ke liye
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING # NAYA: DESCENDING add kiya
from bson.objectid import ObjectId # NAYA (v13): ID se search ke liye
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, User, InputMediaPhoto
from telegram.constants import ParseMode
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

# --- NAYA: Admin & Co-Admin Checks ---
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
    default_messages = {
        # Subscription Flow
        "user_sub_qr_error": "❌ **Error!** Subscription system abhi setup nahi hua hai. Admin se baat karein.",
        "user_sub_qr_text": "**Subscription Plan**\n\n**Price:** {price}\n**Validity:** {days} days\n\nUpar diye gaye QR code par payment karein aur payment ka **screenshot** neeche 'Upload Screenshot' button dabake bhejein.",
        "user_sub_ss_prompt": "Kripya apna payment screenshot yahan bhejein.\n\n/cancel - Cancel.",
        "user_sub_ss_not_photo": "Ye photo nahi hai. Please ek screenshot photo bhejein ya /cancel karein.",
        "user_sub_ss_error": "❌ **Error!** Admin tak screenshot nahi bhej paya. Kripya /support se contact karein.",
        "sub_pending": "✅ **Screenshot Bhej Diya Gaya!**\n\nAdmin jald hi aapka payment check karke approve kar denge. Intezaar karein.",
        "sub_approved": "🎉 **Congratulations!**\n\nAapka subscription approve ho gaya hai.\nAapka plan {days} din mein expire hoga ({expiry_date}).\n\n/menu se anime download karna shuru karein.",
        "sub_rejected": "❌ **Payment Rejected**\n\nAapka payment screenshot reject kar diya gaya hai. Shayad screenshot galat tha ya clear nahi tha.\n\nKripya /support se contact karein ya dobara try karein.",
        "user_sub_removed": "ℹ️ Aapka subscription admin ne remove kar diya hai.\n\n/menu se dobara subscribe kar sakte hain.",
        "user_already_subscribed": "✅ Aap pehle se subscribed hain!\n\n/menu dabake anime download karna shuru karein.",
        
        # Download Flow
        "user_dl_unsubscribed_alert": "❌ Access Denied! Subscribe karne ke liye DM check karein.",
        "user_dl_unsubscribed_dm": "**Subscription Plan**\n\n**Price:** {price}\n**Validity:** {days} days\n\nAapko download karne ke liye subscribe karna hoga.\n\nIs QR code par payment karein aur payment ka **screenshot** bhejne ke liye, bot ko DM mein /menu likhein aur 'Subscribe Now' -> 'Upload Screenshot' button dabayein.",
        "user_dl_dm_alert": "✅ Check your DM (private chat) with me!",
        "user_dl_anime_not_found": "❌ Error: Anime nahi mila.",
        "user_dl_file_error": "❌ Error! {quality} file nahi bhej paya. Please try again.",
        "user_dl_blocked_error": "❌ Error! File nahi bhej paya. Aapne bot ko block kiya hua hai.",
        "user_dl_episodes_not_found": "❌ Error: Is season ke liye episodes nahi mile.",
        "user_dl_seasons_not_found": "❌ Error: Is anime ke liye seasons nahi mile.",
        "user_dl_general_error": "❌ Error! Please try again.",
        "user_dl_sending_files": "✅ **{anime_name}** | **S{season_name}** | **E{ep_num}**\n\nAapke saare files bhej raha hoon...",
        "user_dl_select_episode": "**{anime_name}** | **Season {season_name}**\n\nEpisode select karein:",
        "user_dl_select_season": "**{anime_name}**\n\nSeason select karein:",
        "file_warning": "⚠️ **Yeh file {minutes} minute(s) mein automatically delete ho jaayegi.**",

        # General
        "user_menu_greeting": "Salaam {first_name}! Ye raha aapka menu:",
        "user_donate_qr_error": "❌ Donation info abhi admin ne set nahi ki hai.",
        "user_donate_qr_text": "❤️ **Support Us!**\n\nAgar aapko hamara kaam pasand aata hai, toh aap humein support kar sakte hain.",
        "donate_thanks": "❤️ Support karne ke liye shukriya!",
        
        # NAYA (v10): Post Generator Messages
        "post_gen_season_caption": "✅ **{anime_name}**\n**[ S{season_name} ]**\n\n**📖 Synopsis:**\n{description}\n\nNeeche [Download] button dabake download karein!",
        "post_gen_episode_caption": "✨ **Episode {ep_num} Added** ✨\n\n🎬 **Anime:** {anime_name}\n➡️ **Season:** {season_name}\n\nNeeche [Download] button dabake download karein!",
        
        # NAYA (v10): Generate Link Messages
        "gen_link_caption_ep": "🔗 **Download Link Generated** 🔗\n\n**Anime:** {anime_name}\n**Season:** {season_name}\n**Episode:** {ep_num}\n\nYeh raha aapka **Direct Download Link**:\n`{download_url}`\n\nIs link ko group/channel mein share karein. Sirf **subscribed users** hi isse download kar payenge.",
        "gen_link_caption_season": "🔗 **Season Link Generated** 🔗\n\n**Anime:** {anime_name}\n**Season:** {season_name}\n\nYeh raha aapka **Direct Download Link**:\n`{download_url}`\n\nIs link ko group/channel mein share karein. Sirf **subscribed users** hi isse download kar payenge."
    }

    if not config:
        default_config = {
            "_id": "bot_config", "sub_qr_id": None, "donate_qr_id": None, "price": None, 
            "links": {"backup": None, "support": None}, 
            "validity_days": None,
            "delete_seconds": 300, # NAYA: 5 Minute (300 sec)
            "messages": default_messages,
            "co_admins": [] # NAYA: Co-admin list
        }
        config_collection.insert_one(default_config)
        return default_config
    
    # --- Compatibility aur Migration ---
    needs_update = False
    
    if "validity_days" not in config: config["validity_days"] = None
    if "delete_seconds" not in config: 
        config["delete_seconds"] = 300 # NAYA: 5 min
        needs_update = True
    if "co_admins" not in config:
        config["co_admins"] = []
        needs_update = True
    
    if "messages" not in config: 
        config["messages"] = {}
        needs_update = True

    # Check karo ki saare default messages config me hain ya nahi
    for key, value in default_messages.items():
        if key not in config["messages"]:
            config["messages"][key] = value
            needs_update = True
    
    if needs_update:
        config_collection.update_one(
            {"_id": "bot_config"}, 
            {"$set": {
                "messages": config["messages"], 
                "delete_seconds": config.get("delete_seconds", 300),
                "co_admins": config.get("co_admins", [])
            }}
        )
        
    if "donate" in config.get("links", {}): 
        config_collection.update_one({"_id": "bot_config"}, {"$unset": {"links.donate": ""}})
    
    return config

# --- Subscription Check Helper ---
async def check_subscription(user_id: int) -> bool:
    """Check if user is subscribed and not expired"""
    if await is_main_admin(user_id): # Sirf main admin ko free access hai
        return True 
        
    user_data = users_collection.find_one({"_id": user_id})
    if not user_data:
        return False
        
    if user_data.get('subscribed', False):
        expiry_date = user_data.get('expiry_date')
        if expiry_date:
            if datetime.now() > expiry_date:
                users_collection.update_one({"_id": user_id}, {"$set": {"subscribed": False}})
                return False
            else:
                return True 
        else:
            return True 
    return False

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
        await context.bot.send_message(chat_id=job.chat_id, text=msg, parse_mode='Markdown')
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
(CS_GET_QR,) = range(16, 17)
(CD_GET_QR,) = range(17, 18)
(CP_GET_PRICE,) = range(18, 19)
(CL_GET_BACKUP, CL_GET_DONATE, CL_GET_SUPPORT) = range(19, 22)
(PG_MENU, PG_GET_ANIME, PG_GET_SEASON, PG_GET_EPISODE, PG_GET_CHAT) = range(22, 27)
(DA_GET_ANIME, DA_CONFIRM) = range(27, 29)
(DS_GET_ANIME, DS_GET_SEASON, DS_CONFIRM) = range(29, 32)
(DE_GET_ANIME, DE_GET_SEASON, DE_GET_EPISODE, DE_CONFIRM) = range(32, 36)
(SUB_GET_SCREENSHOT,) = range(36, 37)
(ADMIN_GET_DAYS,) = range(37, 38)
(CV_GET_DAYS,) = range(38, 39) 
(M_GET_DONATE_THANKS, M_GET_SUB_PENDING, M_GET_SUB_APPROVED, M_GET_SUB_REJECTED, M_GET_FILE_WARNING) = range(39, 44)
(CS_GET_DELETE_TIME,) = range(44, 45)
(RS_GET_ID, RS_CONFIRM) = range(45, 47)

# NAYA (v10): Change Poster States (Update Photo)
(UP_GET_ANIME, UP_GET_TARGET, UP_GET_POSTER) = range(47, 50)

# NAYA: Co-Admin States
(CA_GET_ID, CA_CONFIRM) = range(50, 52)
(CR_GET_ID, CR_CONFIRM) = range(52, 54)

# NAYA: Custom Post States
(CPOST_GET_CHAT, CPOST_GET_POSTER, CPOST_GET_CAPTION, CPOST_GET_BTN_TEXT, CPOST_GET_BTN_URL, CPOST_CONFIRM) = range(54, 60)

# NAYA: Bot Messages States (v10: Gen-Link state)
(M_MENU_MAIN, M_MENU_SUB, M_MENU_DL, M_MENU_GEN, M_MENU_POSTGEN, M_MENU_GENLINK, M_GET_MSG) = range(60, 67)

# NAYA (v11): Generate Link States (Re-structured)
(GL_START, GL_GET_ANIME, GL_GET_SEASON, GL_GET_EPISODE) = range(67, 71)


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
            await update.message.reply_text(reply_text)
        elif update.callback_query:
            query = update.callback_query
            # Don't answer if the query is a menu button, it will be handled by its own handler
            if not query.data.startswith("admin_menu_") and not query.data == "admin_menu":
                await query.answer("Canceled!")
                await query.edit_message_text(reply_text)
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

async def back_to_sub_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await sub_settings_menu(update, context)
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


# --- User Subscription Flow ---
async def user_subscribe_start(update: Update, context: ContextTypes.DEFAULT_TYPE, from_conv_cancel: bool = False):
    if update.callback_query:
        query = update.callback_query
        if not from_conv_cancel:
            await query.answer()
        
        config = await get_config()
        qr_id = config.get('sub_qr_id')
        price = config.get('price')
        days = config.get('validity_days')
        
        if not qr_id or not price or not days:
            msg = config.get("messages", {}).get("user_sub_qr_error", "Error")
            await query.message.reply_text(msg)
            if not from_conv_cancel:
                    await back_to_user_menu(update, context) 
            return ConversationHandler.END
            
        text = config.get("messages", {}).get("user_sub_qr_text", "{price} {days}")
        text = text.replace("{price}", str(price)).replace("{days}", str(days))
        
        keyboard = [[InlineKeyboardButton("⬆️ Upload Screenshot", callback_data="user_upload_ss")], [InlineKeyboardButton("⬅️ Back", callback_data="user_back_menu")]]
        
        try:
            if query.message.photo:
                await query.message.delete()
                await context.bot.send_photo(chat_id=query.from_user.id, photo=qr_id, caption=text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                try:
                    await query.edit_message_media(
                        media=InputMediaPhoto(media=qr_id, caption=text, parse_mode='Markdown'),
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except BadRequest as e:
                    if "Message is not modified" not in str(e): raise e 
        except Exception as e:
            logger.warning(f"user_subscribe_start me edit nahi kar paya: {e}")
            try:
                try: await query.message.delete()
                except: pass
                await context.bot.send_photo(chat_id=query.from_user.id, photo=qr_id, caption=text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e_fail:
                logger.error(f"user_subscribe_start me critical error: {e_fail}")
                await context.bot.send_message(query.from_user.id, "❌ Error! Subscription menu nahi khul paya.")
                return ConversationHandler.END
            
        return ConversationHandler.END 

# --- Admin Conversations (Add, Delete, etc.) ---
# --- Conversation: Add Anime ---
async def add_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "Salaam Admin! Anime ka **Naam** kya hai?\n\n/cancel - Cancel."
    await query.edit_message_text(text, parse_mode='Markdown') 
    return A_GET_NAME
async def get_anime_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['anime_name'] = update.message.text
    await update.message.reply_text("Badhiya! Ab anime ka **Poster (Photo)** bhejo.\n\n/cancel - Cancel.")
    return A_GET_POSTER
async def get_anime_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo.")
        return A_GET_POSTER 
    context.user_data['anime_poster_id'] = update.message.photo[-1].file_id
    await update.message.reply_text("Poster mil gaya! Ab **Description (Synopsis)** bhejo.\n\n/skip ya /cancel.")
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
    caption = f"**{name}**\n\n{desc if desc else ''}\n\n--- Details Check Karo ---"
    keyboard = [[InlineKeyboardButton("✅ Save", callback_data="save_anime")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    
    if update.message:
        try:
            await update.message.reply_photo(photo=poster_id, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        except Exception as e:
            logger.warning(f"Confirm anime details me error: {e}")
            await update.message.reply_text("❌ Error: Poster bhej nahi paya. Dobara try karein ya /cancel.")
            return A_GET_DESC 
    return A_CONFIRM
async def save_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    try:
        name = context.user_data['anime_name']
        if animes_collection.find_one({"name": name}):
            await query.edit_message_caption(caption=f"⚠️ **Error:** Ye anime naam '{name}' pehle se hai.")
            await asyncio.sleep(3)
            await add_content_menu(update, context)
            return ConversationHandler.END
        
        anime_document = {
            "name": name, 
            "poster_id": context.user_data['anime_poster_id'], 
            "description": context.user_data['anime_desc'], 
            "seasons": {},
            "created_at": datetime.now() # NAYA (v10): created_at add kiya
        }
        animes_collection.insert_one(anime_document)
        await query.edit_message_caption(caption=f"✅ **Success!** '{name}' add ho gaya hai.")
        await asyncio.sleep(3)
        await add_content_menu(update, context)
    except Exception as e:
        logger.error(f"Anime save karne me error: {e}")
        await query.edit_message_caption(caption=f"❌ **Error!** Database me save nahi kar paya.")
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
    
    text = f"Aap kis anime mein season add karna chahte hain?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai. Pehle 'Add Anime' se add karein."
    
    await query.edit_message_text(text, reply_markup=keyboard)
    return S_GET_ANIME

async def get_anime_for_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("season_anime_", "")
    context.user_data['anime_name'] = anime_name
    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nAb is season ka **Number ya Naam** bhejo.\n(Jaise: 1, 2, Movie)\n\n/cancel - Cancel.")
    return S_GET_NUMBER

async def get_season_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    season_name = update.message.text
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if not anime_doc:
            await update.message.reply_text(f"⚠️ **Error!** Anime '{anime_name}' database mein nahi mila. /cancel karke dobara try karein.")
            return ConversationHandler.END
            
    if season_name in anime_doc.get("seasons", {}):
        await update.message.reply_text(f"⚠️ **Error!** '{anime_name}' mein 'Season {season_name}' pehle se hai.\n\nKoi doosra naam/number type karein ya /cancel karein.")
        return S_GET_NUMBER

    await update.message.reply_text(f"Aapne Season '{season_name}' select kiya hai.\n\nAb is season ka **Poster (Photo)** bhejo.\n\n/skip - Default anime poster use karo.\n/cancel - Cancel.", parse_mode='Markdown')
    return S_GET_POSTER

async def get_season_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo.")
        return S_GET_POSTER
    context.user_data['season_poster_id'] = update.message.photo[-1].file_id
    # NAYA (v10): Description state par jao
    await update.message.reply_text("Poster mil gaya! Ab is season ka **Description** bhejo.\n(Yeh post generator mein use hoga)\n\n/skip ya /cancel.")
    return S_GET_DESC

async def skip_season_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['season_poster_id'] = None
    # NAYA (v10): Description state par jao
    await update.message.reply_text("Default poster set! Ab is season ka **Description** bhejo.\n(Yeh post generator mein use hoga)\n\n/skip ya /cancel.")
    return S_GET_DESC

# NAYA (v10): Season Description functions
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
    season_desc = context.user_data.get('season_desc') # NAYA (v10)
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    poster_id_to_show = season_poster_id or anime_doc.get('poster_id')
    
    caption = f"**Confirm Karo:**\nAnime: **{anime_name}**\nNaya Season: **{season_name}**\nDescription: {season_desc or 'N/A'}\n\nSave kar doon?"
    keyboard = [[InlineKeyboardButton("✅ Haan, Save Karo", callback_data="save_season")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    
    await update.message.reply_photo(
        photo=poster_id_to_show,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
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
        
        await query.edit_message_caption(caption=f"✅ **Success!**\n**{anime_name}** mein **Season {season_name}** add ho gaya hai.")
        await asyncio.sleep(3)
        await add_content_menu(update, context)
    except Exception as e:
        logger.error(f"Season save karne me error: {e}")
        await query.edit_message_caption(caption=f"❌ **Error!** Database me save nahi kar paya.")
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
    
    text = f"Aap kis anime mein episode add karna chahte hain?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai. Pehle 'Add Anime' se add karein."

    await query.edit_message_text(text, reply_markup=keyboard)
    return E_GET_ANIME

async def get_anime_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' mein koi season nahi hai.\n\nPehle `➕ Add Season` se season add karo.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]))
        return ConversationHandler.END
    
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1) 
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"addep_page_{current_page}")])
    
    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nAb **Season** select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return E_GET_SEASON

async def get_season_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("ep_season_", "")
    context.user_data['season_name'] = season_name
    
    # NAYA (v10) FIX: Back button ke liye anime name save karo
    anime_name = context.user_data['anime_name']

    await query.edit_message_text(f"Aapne **Season {season_name}** select kiya hai.\n\nAb **Episode Number** bhejo.\n(Jaise: 1, 2, 3...)\n\n(Agar yeh ek movie hai, toh `1` type karein.)\n\n/cancel - Cancel.")
    
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
        await update.message.reply_text("Ye video file nahi hai. Please dobara video file bhejein ya /skip karein.")
        return False # False return karo

    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        ep_num = context.user_data['ep_num']
        
        # Keys ko filter karo
        dot_notation_key = f"seasons.{season_name}.{ep_num}.{quality}"
        animes_collection.update_one({"name": anime_name}, {"$set": {dot_notation_key: file_id}})
        logger.info(f"Naya episode save ho gaya: {anime_name} S{season_name} E{ep_num} {quality}")
        await update.message.reply_text(f"✅ **{quality}** save ho gaya.")
        return True # Success
    except Exception as e:
        logger.error(f"Episode file save karne me error: {e}")
        await update.message.reply_text(f"❌ **Error!** {quality} save nahi kar paya. Logs check karein.")
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
        await update.message.reply_text(f"⚠️ **Error!** '{anime_name}' - Season {season_name} - Episode {ep_num} pehle se maujood hai. Please pehle isse delete karein ya koi doosra episode number dein.\n\n/cancel - Cancel.")
        return E_GET_NUMBER

    await update.message.reply_text(f"Aapne **Episode {context.user_data['ep_num']}** select kiya hai.\n\n"
                                        "Ab **480p** quality ki video file bhejein.\n"
                                        "Ya /skip type karein.", 
                                        parse_mode='Markdown')
    return E_GET_480P

async def get_480p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if not await _save_episode_file_helper(update, context, "480p"):
        return E_GET_480P # Agar fail hua (e.g., text bheja), toh isi state par raho
    await update.message.reply_text("Ab **720p** quality ki video file bhejein.\nYa /skip type karein.", parse_mode='Markdown')
    return E_GET_720P

async def skip_480p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 480p skip kar diya.\n\n"
                                    "Ab **720p** quality ki video file bhejein.\n"
                                    "Ya /skip type karein.", parse_mode='Markdown')
    return E_GET_720P

async def get_720p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if not await _save_episode_file_helper(update, context, "720p"):
        return E_GET_720P # Agar fail hua, toh isi state par raho
    await update.message.reply_text("Ab **1080p** quality ki video file bhejein.\nYa /skip type karein.", parse_mode='Markdown')
    return E_GET_1080P

async def skip_720p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 720p skip kar diya.\n\n"
                                    "Ab **1080p** quality ki video file bhejein.\n"
                                    "Ya /skip type karein.", parse_mode='Markdown')
    return E_GET_1080P

async def get_1080p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if not await _save_episode_file_helper(update, context, "1080p"):
        return E_GET_1080P # Agar fail hua, toh isi state par raho
    await update.message.reply_text("Ab **4K** quality ki video file bhejein.\nYa /skip type karein.", parse_mode='Markdown')
    return E_GET_4K

async def skip_1080p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 1080p skip kar diya.\n\n"
                                    "Ab **4K** quality ki video file bhejein.\n"
                                    "Ya /skip type karein.", parse_mode='Markdown')
    return E_GET_4K

async def get_4k_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA FIX (v12): Check return value
    if await _save_episode_file_helper(update, context, "4K"):
        await update.message.reply_text("✅ **Success!** Saari qualities save ho gayi hain.", parse_mode='Markdown')
    else:
        return E_GET_4K # Agar fail hua, toh isi state par raho
    
    await add_content_menu(update, context) # NAYA (v10): Go back to menu
    context.user_data.clear()
    return ConversationHandler.END

async def skip_4k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 4K skip kar diya.\n\n"
                                    "✅ **Success!** Episode save ho gaya hai.", parse_mode='Markdown')
    
    await add_content_menu(update, context) # NAYA (v10): Go back to menu
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Set Subscription QR ---
async def set_sub_qr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Aapna **Subscription (Payment) QR Code** ki photo bhejo.\n\n/cancel - Cancel.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_sub_settings")]]))
    return CS_GET_QR
async def set_sub_qr_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo ya /cancel karein.")
        return CS_GET_QR
    qr_file_id = update.message.photo[-1].file_id
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"sub_qr_id": qr_file_id}}, upsert=True)
    logger.info(f"Subscription QR code update ho gaya.")
    await update.message.reply_text("✅ **Success!** Naya subscription QR code set ho gaya hai.")
    await sub_settings_menu(update, context) 
    return ConversationHandler.END

# --- Conversation: Set Price ---
async def set_price_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Subscription ka **Price** bhejo.\n(Example: 50 INR)\n\n/cancel - Cancel.", 
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_sub_settings")]]))
    return CP_GET_PRICE
async def set_price_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_text = update.message.text
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"price": price_text}}, upsert=True)
    logger.info(f"Price update ho gaya: {price_text}")
    await update.message.reply_text(f"✅ **Success!** Naya price set ho gaya hai: '{price_text}'.")
    await sub_settings_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Set Validity Days ---
async def set_days_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = await get_config()
    current_days = config.get("validity_days")
    text = f"Abhi automatic approval **{current_days or 'OFF'}** days par set hai.\n\n"
    text += "Naya duration (sirf number mein) bhejo.\n(Example: `30`)\n\n/cancel - Cancel."
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_sub_settings")]]))
    return CV_GET_DAYS
async def set_days_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        if days <= 0:
                await update.message.reply_text("Din 0 se zyada hone chahiye.")
                return CV_GET_DAYS
                
        config_collection.update_one({"_id": "bot_config"}, {"$set": {"validity_days": days}}, upsert=True)
        logger.info(f"Validity days update ho gaye: {days}")
        await update.message.reply_text(f"✅ **Success!** Automatic approval ab **{days} din** par set ho gaya hai.")
        await sub_settings_menu(update, context) 
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Yeh number nahi hai. Please sirf number bhejein (jaise 30) ya /cancel karein.")
        return CV_GET_DAYS
    except Exception as e:
        logger.error(f"Validity days save karte waqt error: {e}")
        await update.message.reply_text("❌ Error! Save nahi kar paya.")
        context.user_data.clear()
        return ConversationHandler.END
# --- NAYA: Conversation: Set Auto-Delete Time ---
async def set_delete_time_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = await get_config()
    current_seconds = config.get("delete_seconds", 300) # NAYA: Default 300
    current_minutes = current_seconds // 60
    text = f"Abhi file auto-delete **{current_minutes} minute(s)** ({current_seconds} seconds) par set hai.\n\n"
    text += "Naya time **seconds** mein bhejo.\n(Example: `300` for 5 minutes)\n\n/cancel - Cancel."
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_sub_settings")]]))
    return CS_GET_DELETE_TIME
async def set_delete_time_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        seconds = int(update.message.text)
        if seconds <= 10:
                await update.message.reply_text("Time 10 second se zyada hona chahiye.")
                return CS_GET_DELETE_TIME
                
        config_collection.update_one({"_id": "bot_config"}, {"$set": {"delete_seconds": seconds}}, upsert=True)
        logger.info(f"Auto-delete time update ho gaya: {seconds} seconds")
        await update.message.reply_text(f"✅ **Success!** Auto-delete time ab **{seconds} seconds** ({seconds // 60} min) par set ho gaya hai.")
        await sub_settings_menu(update, context) 
        return ConversationHandler.END
        
    except ValueError:
        await update.message.reply_text("Yeh number nahi hai. Please sirf seconds bhejein (jaise 180) ya /cancel karein.")
        return CS_GET_DELETE_TIME
    except Exception as e:
        logger.error(f"Delete time save karte waqt error: {e}")
        await update.message.reply_text("❌ Error! Save nahi kar paya.")
        context.user_data.clear()
        return ConversationHandler.END

# --- Conversation: Set Donate QR ---
async def set_donate_qr_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Aapna **Donate QR Code** ki photo bhejo.\n\n/cancel - Cancel.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_donate_settings")]]))
    return CD_GET_QR
async def set_donate_qr_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo ya /cancel karein.")
        return CD_GET_QR
    qr_file_id = update.message.photo[-1].file_id
    config_collection.update_one({"_id": "bot_config"}, {"$set": {"donate_qr_id": qr_file_id}}, upsert=True)
    logger.info(f"Donate QR code update ho gaya.")
    await update.message.reply_text("✅ **Success!** Naya donate QR code set ho gaya hai.")
    await donate_settings_menu(update, context)
    return ConversationHandler.END

# --- Conversation: Set Links ---
async def set_links_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    link_type = query.data.replace("admin_set_", "") 
    
    if link_type == "backup_link":
        context.user_data['link_type'] = "backup"
        text = "Aapke **Backup Channel** ka link bhejo.\n(Example: https://t.me/mychannel)\n\n/skip - Skip.\n/cancel - Cancel."
        back_button = "back_to_links"
    elif link_type == "support_link":
        context.user_data['link_type'] = "support"
        text = "Aapke **Support Inbox/Group** ka link bhejo.\n(Example: https://t.me/mygroup)\n\n/skip - Skip.\n/cancel - Cancel."
        back_button = "back_to_links"
    else:
        await query.answer("Invalid button!", show_alert=True)
        return ConversationHandler.END

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_button)]]))
    return CL_GET_BACKUP 
async def get_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link_url = update.message.text
    link_type = context.user_data['link_type']
    config_collection.update_one({"_id": "bot_config"}, {"$set": {f"links.{link_type}": link_url}}, upsert=True)
    logger.info(f"{link_type} link update ho gaya: {link_url}")
    await update.message.reply_text(f"✅ **Success!** Naya {link_type} link set ho gaya hai.")
    await other_links_menu(update, context)
    context.user_data.clear()
    return ConversationHandler.END
async def skip_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link_type = context.user_data['link_type']
    config_collection.update_one({"_id": "bot_config"}, {"$set": {f"links.{link_type}": None}}, upsert=True)
    logger.info(f"{link_type} link skip kiya (None set).")
    await update.message.reply_text(f"✅ **Success!** {link_type} link remove kar diya गया है.")
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
    
    text = f"**Editing:** `{msg_key}`\n\n"
    text += f"**Current Message:**\n`{current_msg}`\n\n"
    text += f"Naya message bhejo.\n\n/cancel - Cancel."
    
    # Determine the correct back button
    if msg_key in ["user_sub_qr_error", "user_sub_qr_text", "user_sub_ss_prompt", "user_sub_ss_not_photo", "user_sub_ss_error", "sub_pending", "sub_approved", "sub_rejected", "user_sub_removed", "user_already_subscribed"]:
        back_cb = "msg_menu_sub"
    elif msg_key in ["user_dl_unsubscribed_alert", "user_dl_unsubscribed_dm", "user_dl_dm_alert", "user_dl_anime_not_found", "user_dl_file_error", "user_dl_blocked_error", "user_dl_episodes_not_found", "user_dl_seasons_not_found", "user_dl_general_error", "user_dl_sending_files", "user_dl_select_episode", "user_dl_select_season", "file_warning"]:
        back_cb = "msg_menu_dl"
    elif msg_key in ["post_gen_season_caption", "post_gen_episode_caption"]: 
        back_cb = "msg_menu_postgen" 
    elif msg_key in ["gen_link_caption_ep", "gen_link_caption_season"]: # NAYA (v10)
        back_cb = "msg_menu_genlink"
    else:
        back_cb = "msg_menu_gen"
        
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=back_cb)]]))
    return M_GET_MSG

async def set_msg_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic function to save edited message"""
    try:
        msg_text = update.message.text
        msg_key = context.user_data['msg_key']
        
        config_collection.update_one({"_id": "bot_config"}, {"$set": {f"messages.{msg_key}": msg_text}}, upsert=True)
        logger.info(f"{msg_key} message update ho gaya: {msg_text}")
        await update.message.reply_text(f"✅ **Success!** Naya '{msg_key}' message set ho gaya hai.")
        
        await bot_messages_menu(update, context) # Go back to main messages menu
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Message save karne me error: {e}")
        await update.message.reply_text("❌ Error! Save nahi kar paya.")
        context.user_data.clear()
        return ConversationHandler.END
    
# --- Conversation: Post Generator (NAYA v10: Paginated) ---
async def post_gen_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("✍️ Season Post", callback_data="post_gen_season")],
        [InlineKeyboardButton("✍️ Episode Post", callback_data="post_gen_episode")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    await query.edit_message_text("✍️ **Post Generator** ✍️\n\nAap kis tarah ka post generate karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
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
    
    text = f"Kaunsa **Anime** select karna hai?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await query.edit_message_text(text, reply_markup=keyboard)
    return PG_GET_ANIME

async def post_gen_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("post_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"post_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"postgen_page_{current_page}")])

    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nAb **Season** select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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
        return PG_GET_CHAT 
        
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    # Filter out _poster_id, _description
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' - Season {season_name} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"post_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    # NAYA (v10) FIX: Back button ko season list par bhejo
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"post_anime_{anime_name}")])

    await query.edit_message_text(f"Aapne **Season {season_name}** select kiya hai.\n\nAb **Episode** select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return PG_GET_EPISODE
async def post_gen_final_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("post_ep_", "")
    context.user_data['ep_num'] = ep_num
    
    await generate_post_ask_chat(update, context) 
    return PG_GET_CHAT 

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
        
        if not ep_num and season_name:
            # --- YEH SEASON POST HAI ---
            context.user_data['is_episode_post'] = False
            
            season_data = anime_doc.get("seasons", {}).get(season_name, {})
            
            # Season poster check karo, nahi toh anime poster lo
            poster_id = season_data.get("_poster_id") or anime_doc['poster_id']
            
            # NAYA (v10): Season description check karo, nahi toh anime description lo
            description = season_data.get("_description") or anime_doc.get('description', '')
            
            caption_template = config.get("messages", {}).get("post_gen_season_caption", "...")
            caption = caption_template.replace("{anime_name}", anime_name) \
                                        .replace("{season_name}", season_name) \
                                        .replace("{description}", description if description else "")
    
        elif ep_num:
                # --- YEH EPISODE POST HAI ---
            context.user_data['is_episode_post'] = True
            
            caption_template = config.get("messages", {}).get("post_gen_episode_caption", "...")
            caption = caption_template.replace("{anime_name}", anime_name) \
                                        .replace("{season_name}", season_name) \
                                        .replace("{ep_num}", ep_num)
            
            poster_id = None # Episode post ke liye koi poster nahi
        
        else:
            logger.warning("Post generator me invalid state")
            await query.edit_message_text("❌ Error! Invalid state. Please start over.")
            return ConversationHandler.END
        
        links = config.get('links', {})
        
        ep_num_check = context.user_data.get('ep_num')
        season_name_check = context.user_data.get('season_name')
        
        # (v17 Fix: Extra underscore ('_') hatao)
        if not ep_num_check and season_name_check: # Season Post
            dl_callback_data = f"dl{anime_id}__{season_name_check}"
        else: # Episode Post
            dl_callback_data = f"dl{anime_id}__{season_name_check}__{ep_num_check}" 
            
        donate_url = f"https://t.me/{bot_username}?start=donate" 
        subscribe_url = f"https://t.me/{bot_username}?start=subscribe"
        
        backup_url = links.get('backup') or "https://t.me/"
        support_url = links.get('support') or "https://t.me/"
                
        btn_backup = InlineKeyboardButton("Backup", url=backup_url)
        btn_donate = InlineKeyboardButton("Donate", url=donate_url)
        btn_support = InlineKeyboardButton("Support", url=support_url)
        
        # ============================================
        # ===           NAYA FIX (v18)             ===
        # ===   Callback_data ko URL me badlo      ===
        # ============================================
        download_url = f"https://t.me/{bot_username}?start={dl_callback_data}"
        btn_download = InlineKeyboardButton("Download", url=download_url) 
        # ============================================

        btn_subscribe = InlineKeyboardButton("Subscribe Now", url=subscribe_url)
        
        if context.user_data.get('is_episode_post', False):
            # Episode post: Sirf Subscribe aur Download
            keyboard = [[btn_subscribe, btn_download]]
        else:
            # Season post: Poora keyboard
            keyboard = [
                [btn_subscribe, btn_download], 
                [btn_backup, btn_donate, btn_support]
            ]
        
        context.user_data['post_caption'] = caption
        context.user_data['post_poster_id'] = poster_id 
        context.user_data['post_keyboard'] = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ **Post Ready!**\n\nAb uss **Channel ka @username** ya **Group/Channel ki Chat ID** bhejo jahaan ye post karna hai.\n"
            "(Example: @MyAnimeChannel ya -100123456789)\n\n/cancel - Cancel."
        )
        
    except Exception as e:
        logger.error(f"Post generate karne me error: {e}", exc_info=True)
        await query.answer("Error! Post generate nahi kar paya.", show_alert=True)
        await query.edit_message_text("❌ **Error!** Post generate nahi ho paya. Logs check karein.")
        context.user_data.clear()
        return ConversationHandler.END

async def post_gen_send_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.text
    is_episode_post = context.user_data.get('is_episode_post', False) 
    
    try:
        if is_episode_post:
            await context.bot.send_message(
                chat_id=chat_id,
                text=context.user_data['post_caption'],
                parse_mode='Markdown',
                reply_markup=context.user_data['post_keyboard']
            )
        else:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=context.user_data['post_poster_id'],
                caption=context.user_data['post_caption'],
                parse_mode='Markdown',
                reply_markup=context.user_data['post_keyboard']
            )

        await update.message.reply_text(f"✅ **Success!**\nPost ko '{chat_id}' par bhej diya gaya hai.")
    except Exception as e:
        logger.error(f"Post channel me bhejme me error: {e}")
        await update.message.reply_text(f"❌ **Error!**\nPost '{chat_id}' par nahi bhej paya. Check karo ki bot uss channel me admin hai ya ID sahi hai.\nError: {e}")
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
    
    text = f"Kaunsa **Anime** delete karna hai?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await query.edit_message_text(text, reply_markup=keyboard)
    return DA_GET_ANIME
async def delete_anime_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_anime_", "")
    context.user_data['anime_name'] = anime_name
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {anime_name} ko Delete Karo", callback_data="del_anime_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    await query.edit_message_text(f"⚠️ **FINAL WARNING** ⚠️\n\nAap **{anime_name}** ko delete karne wale hain. Iske saare seasons aur episodes delete ho jayenge.\n\n**Are you sure?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return DA_CONFIRM
async def delete_anime_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    try:
        animes_collection.delete_one({"name": anime_name})
        logger.info(f"Anime deleted: {anime_name}")
        await query.edit_message_text(f"✅ **Success!**\nAnime '{anime_name}' delete ho gaya hai.")
    except Exception as e:
        logger.error(f"Anime delete karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Anime delete nahi ho paya.")
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
    
    text = f"Kaunse **Anime** ka season delete karna hai?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await query.edit_message_text(text, reply_markup=keyboard)
    return DS_GET_ANIME

async def delete_season_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_season_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"del_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"delseason_page_{current_page}")])

    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nKaunsa **Season** delete karna hai?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return DS_GET_SEASON
async def delete_season_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("del_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    keyboard = [[InlineKeyboardButton(f"✅ Haan, Season {season_name} Delete Karo", callback_data="del_season_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    await query.edit_message_text(f"⚠️ **FINAL WARNING** ⚠️\n\nAap **{anime_name}** ka **Season {season_name}** delete karne wale hain. Iske saare episodes delete ho jayenge.\n\n**Are you sure?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return DS_CONFIRM
async def delete_season_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Deleting...")
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    try:
        animes_collection.update_one({"name": anime_name}, {"$unset": {f"seasons.{season_name}": ""}})
        logger.info(f"Season deleted: {anime_name} - S{season_name}")
        await query.edit_message_text(f"✅ **Success!**\nSeason '{season_name}' delete ho gaya hai.")
    except Exception as e:
        logger.error(f"Season delete karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Season delete nahi ho paya.")
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
    
    text = f"Kaunse **Anime** ka episode delete karna hai?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await query.edit_message_text(text, reply_markup=keyboard)
    return DE_GET_ANIME

async def delete_episode_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("del_ep_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    if not seasons:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"del_ep_season_{s}") for s in sorted_seasons]
    keyboard = build_grid_keyboard(buttons, 1)
    
    # NAYA (v10) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    keyboard.append([InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"delep_page_{current_page}")])

    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nKaunsa **Season** delete karna hai?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' - Season {season_name} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"del_ep_num_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    # NAYA (v10) FIX: Back button ko season list par bhejo
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"del_ep_anime_{anime_name}")])

    await query.edit_message_text(f"Aapne **Season {season_name}** select kiya hai.\n\nKaunsa **Episode** delete karna hai?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return DE_GET_EPISODE
async def delete_episode_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ep_num = query.data.replace("del_ep_num_", "")
    context.user_data['ep_num'] = ep_num
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    keyboard = [[InlineKeyboardButton(f"✅ Haan, Ep {ep_num} Delete Karo", callback_data="del_ep_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]
    await query.edit_message_text(f"⚠️ **FINAL WARNING** ⚠️\n\nAap **{anime_name}** - **S{season_name}** - **Ep {ep_num}** delete karne wale hain. Iske saare qualities delete ho jayenge.\n\n**Are you sure?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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
        await query.edit_message_text(f"✅ **Success!**\nEpisode '{ep_num}' delete ho gaya hai.")
    except Exception as e:
        logger.error(f"Episode delete karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Episode delete nahi ho paya.")
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
    
    text = f"Kaunse **Anime** ka poster update karna hai?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await query.edit_message_text(text, reply_markup=keyboard)
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
    
    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nAap iska **Main Poster** change karna chahte hain ya kisi **Season** ka?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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

    await query.edit_message_text(f"Aapne **{target_name}** select kiya hai.\n\nAb naya **Poster (Photo)** bhejo.\n\n/cancel - Cancel.")
    return UP_GET_POSTER

# NAYA FIX (v12): Galti se text bhejne par handle karo
async def update_photo_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo ya /cancel karo.")
    return UP_GET_POSTER # Isi state par raho

async def update_photo_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo.")
        return UP_GET_POSTER
    
    poster_id = update.message.photo[-1].file_id
    anime_name = context.user_data['anime_name']
    target = context.user_data['target']
    
    try:
        if target == "MAIN":
            animes_collection.update_one({"name": anime_name}, {"$set": {"poster_id": poster_id}})
            caption = f"✅ **Success!**\n{anime_name} ka **Main Poster** change ho gaya hai."
            logger.info(f"Main poster change ho gaya: {anime_name}")
        else:
            season_name = context.user_data['season_name']
            animes_collection.update_one(
                {"name": anime_name}, 
                {"$set": {f"seasons.{season_name}._poster_id": poster_id}}
            )
            caption = f"✅ **Success!**\n{anime_name} - **Season {season_name}** ka poster change ho gaya hai."
            logger.info(f"Season poster change ho gaya: {anime_name} S{season_name}")

        await update.message.reply_photo(photo=poster_id, caption=caption, parse_mode='Markdown')
    
    except Exception as e:
        logger.error(f"Poster change karne me error: {e}")
        await update.message.reply_text("❌ **Error!** Poster update nahi ho paya.")
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await admin_command(update, context, from_callback=False) # Go to main menu
    return ConversationHandler.END


# --- NAYA (v11): Conversation: Generate Link (FIXED) ---
async def generate_link_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NAYA (v11): Pehle type poochega (Episode ya Season)"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔗 Generate Episode Link", callback_data="genlink_type_episode")],
        [InlineKeyboardButton("🔗 Generate Season Link", callback_data="genlink_type_season")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]
    ]
    await query.edit_message_text(
        "Aap kis tarah ka link generate karna chahte hain?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return GL_START

async def generate_link_select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NAYA (v11): Link type save karega aur anime list dikhayega"""
    query = update.callback_query
    await query.answer()
    link_type = query.data.replace("genlink_type_", "") # 'episode' ya 'season'
    context.user_data['link_type'] = link_type
    
    # Ab anime list dikhao
    return await generate_link_show_anime_list(update, context, page=0)
    
async def generate_link_show_anime_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    
    if query.data.startswith("genlink_page_"):
        page = int(query.data.split("_")[-1])
        await query.answer()
        
    context.user_data['current_page'] = page # NAYA (v10)

    animes, keyboard = await build_paginated_keyboard(
        collection=animes_collection,
        page=page,
        page_callback_prefix="genlink_page_",
        item_callback_prefix="genlink_anime_",
        back_callback="admin_gen_link" # NAYA (v11): Back to type selection
    )
    
    text = f"Kaunse **Anime** ka link generate karna hai?\n\n**Newest First** (Sabse naya pehle):\n(Page {page + 1})"
    
    if not animes and page == 0:
        text = "❌ Error: Abhi koi anime add nahi hua hai."

    await query.edit_message_text(text, reply_markup=keyboard)
    return GL_GET_ANIME

async def generate_link_select_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NAYA (v11): Logic change. Type ke hisaab se season list ya ep list par bhejega"""
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("genlink_anime_", "")
    context.user_data['anime_name'] = anime_name
    anime_doc = animes_collection.find_one({"name": anime_name})
    seasons = anime_doc.get("seasons", {})
    
    if not seasons:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' mein koi season nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
        
    sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = []
    
    link_type = context.user_data.get('link_type')
    
    # NAYA (v11) FIX: Back button ko pagination par bhejo
    current_page = context.user_data.get('current_page', 0)
    back_button = [InlineKeyboardButton("⬅️ Back to Animes", callback_data=f"genlink_page_{current_page}")]

    if link_type == 'season':
        # Agar season link karna hai, toh season select karte hi link generate karo
        text = f"Aap **{anime_name}** ka kaunsa **Season** link karna chahte hain?"
        for s in sorted_seasons:
            buttons.append(InlineKeyboardButton(f"🔗 Link Season {s}", callback_data=f"genlink_ep_S__{s}")) # Use 'genlink_ep_' prefix
        keyboard = build_grid_keyboard(buttons, 1)
        keyboard.append(back_button)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return GL_GET_EPISODE # Final step par jao
        
    else: # link_type == 'episode'
        # Agar episode link karna hai, toh normal flow
        text = f"Aap **{anime_name}** ke kaunse **Season** ka episode link karna chahte hain?"
        for s in sorted_seasons:
            buttons.append(InlineKeyboardButton(f"S{s} Episodes", callback_data=f"genlink_season_{s}"))
        keyboard = build_grid_keyboard(buttons, 1)
        keyboard.append(back_button)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return GL_GET_SEASON # Agle step (ep list) par jao

async def generate_link_select_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """NAYA (v11): Yeh function ab sirf episode link ke liye use hoga"""
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("genlink_season_", "")
    context.user_data['season_name'] = season_name
    anime_name = context.user_data['anime_name']
    
    # Handle "Select specific episode"
    anime_doc = animes_collection.find_one({"name": anime_name})
    episodes = anime_doc.get("seasons", {}).get(season_name, {})
    
    episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
    
    if not episode_keys:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' - Season {season_name} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
        
    sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"🔗 Link Episode {ep}", callback_data=f"genlink_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    
    # NAYA (v11) FIX: Back button ko season list par bhejo
    keyboard.append([InlineKeyboardButton("⬅️ Back to Seasons", callback_data=f"genlink_anime_{anime_name}")])

    await query.edit_message_text(f"Aapne **Season {season_name}** select kiya hai.\n\nKaunsa **Episode** link karna hai?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return GL_GET_EPISODE
    
async def generate_link_final_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating link...")
    
    ep_num = query.data.replace("genlink_ep_", "") # Yeh 'S__1' ya '1' ho sakta hai
    anime_name = context.user_data['anime_name']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if not anime_doc:
        await query.edit_message_text("❌ Error! Anime database me nahi mila. Cancel kar raha hoon.")
        return ConversationHandler.END
    anime_id = str(anime_doc['_id'])
    
    bot_username = (await context.bot.get_me()).username
    config = await get_config()
    
    # Check if this is a "Link Season" request
    if ep_num.startswith("S__"):
        season_name_for_link = ep_num.replace("S__", "")
        # This is a Season Link
        # ============================================
        # ===           NAYA FIX (v17)             ===
        # ===    Extra underscore ('_') hatao      ===
        # ============================================
        dl_callback_data = f"dl{anime_id}__{season_name_for_link}" # Use ID
        # ============================================
        caption_template = config.get("messages", {}).get("gen_link_caption_season", "...")
        download_url = f"https://t.me/{bot_username}?start={dl_callback_data}"
        
        caption = caption_template.replace("{anime_name}", anime_name) \
                                    .replace("{season_name}", season_name_for_link) \
                                    .replace("{download_url}", download_url)

    else:
        # This is an Episode Link
        season_name = context.user_data['season_name']
        # ============================================
        # ===           NAYA FIX (v17)             ===
        # ===    Extra underscore ('_') hatao      ===
        # ============================================
        dl_callback_data = f"dl{anime_id}__{season_name}__{ep_num}" # Use ID
        # ============================================
        caption_template = config.get("messages", {}).get("gen_link_caption_ep", "...")
        download_url = f"https://t.me/{bot_username}?start={dl_callback_data}"
        
        caption = caption_template.replace("{anime_name}", anime_name) \
                                    .replace("{season_name}", season_name) \
                                    .replace("{ep_num}", ep_num) \
                                    .replace("{download_url}", download_url)
    
    # Admin ko text link bhejo
    await query.edit_message_text(
        caption,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]])
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Remove Subscription ---
async def remove_sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Aap kis user ka subscription remove karna chahte hain?\n\nUs user ki **Telegram User ID** bhejein.\n\n/cancel - Cancel.",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_sub_settings")]]))
    return RS_GET_ID
async def remove_sub_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Yeh valid User ID nahi hai. Please sirf number bhejein.\n\n/cancel - Cancel.")
        return RS_GET_ID
    
    user_data = users_collection.find_one({"_id": user_id})
    
    if not user_data:
        await update.message.reply_text("❌ Error: Is User ID se koi user database mein nahi mila.\n\n/cancel - Cancel.")
        return RS_GET_ID
    
    if not user_data.get('subscribed', False):
        await update.message.reply_text(f"ℹ️ User {user_id} ({user_data.get('first_name')}) pehle se subscribed nahi hai.\n\n/cancel - Cancel.")
        return RS_GET_ID
    
    context.user_data['user_to_remove'] = user_id
    context.user_data['user_to_remove_name'] = user_data.get('first_name')
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ka Subscription Remove Karo", callback_data="remove_sub_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_sub_settings")]]
    await update.message.reply_text(f"⚠️ **Warning!** ⚠️\nAap user **{user_data.get('first_name')}** (ID: `{user_id}`) ka subscription remove karne wale hain.\n\n**Are you sure?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return RS_CONFIRM
async def remove_sub_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Removing subscription...")
    
    user_id = context.user_data['user_to_remove']
    user_name = context.user_data['user_to_remove_name']
    
    try:
        users_collection.update_one(
            {"_id": user_id},
            {"$set": {"subscribed": False, "expiry_date": None}}
        )
        logger.info(f"Admin {query.from_user.id} ne user {user_id} ka subscription remove kar diya.")
        
        await query.edit_message_text(f"✅ **Success!**\nUser {user_name} (ID: `{user_id}`) ka subscription remove kar diya gaya hai.")
        
        try:
            config = await get_config()
            msg = config.get("messages", {}).get("user_sub_removed", "Subscription removed.")
            await context.bot.send_message(user_id, msg)
        except Exception as e:
            logger.warning(f"User {user_id} ko removal notification bhejte waqt error: {e}")

    except Exception as e:
        logger.error(f"Subscription remove karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Subscription remove nahi ho paya.")
    
    context.user_data.clear()
    await asyncio.sleep(3)
    await sub_settings_menu(update, context)
    return ConversationHandler.END

# --- NAYA: Conversation: Co-Admin Add ---
async def co_admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Naye Co-Admin ki **Telegram User ID** bhejein.\n\n/cancel - Cancel.",
                                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return CA_GET_ID
async def co_admin_add_get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Yeh valid User ID nahi hai. Please sirf number bhejein.\n\n/cancel - Cancel.")
        return CA_GET_ID
    
    if user_id == ADMIN_ID:
        await update.message.reply_text("Aap Main Admin hain, khud ko add nahi kar sakte.\n\n/cancel - Cancel.")
        return CA_GET_ID
    
    config = await get_config()
    if user_id in config.get("co_admins", []):
        await update.message.reply_text(f"User `{user_id}` pehle se Co-Admin hai.\n\n/cancel - Cancel.", parse_mode='Markdown')
        return CA_GET_ID

    context.user_data['co_admin_to_add'] = user_id
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ko Co-Admin Banao", callback_data="co_admin_add_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]
    await update.message.reply_text(f"Aap user ID `{user_id}` ko **Co-Admin** banane wale hain.\n\nWoh content add, remove, aur post generate kar payenge.\n\n**Are you sure?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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
        await query.edit_message_text(f"✅ **Success!**\nUser ID `{user_id}` ab Co-Admin hai.")
    except Exception as e:
        logger.error(f"Co-Admin add karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Co-Admin add nahi ho paya.")
    
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
        await query.edit_message_text("Abhi koi Co-Admin nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
        return ConversationHandler.END
        
    buttons = [InlineKeyboardButton(f"Remove {admin_id}", callback_data=f"co_admin_rem_{admin_id}") for admin_id in co_admins]
    keyboard = build_grid_keyboard(buttons, 1) # List me dikhao
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")])
    await query.edit_message_text("Kis Co-Admin ko remove karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CR_GET_ID
async def co_admin_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.replace("co_admin_rem_", ""))
    context.user_data['co_admin_to_remove'] = user_id
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ko Remove Karo", callback_data="co_admin_rem_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]
    await query.edit_message_text(f"Aap Co-Admin ID `{user_id}` ko remove karne wale hain.\n\n**Are you sure?**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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
        await query.edit_message_text(f"✅ **Success!**\nCo-Admin ID `{user_id}` remove ho gaya hai.")
    except Exception as e:
        logger.error(f"Co-Admin remove karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Co-Admin remove nahi ho paya.")
    
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
            text += f"- `{admin_id}`\n"
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return ConversationHandler.END
    

# --- NAYA: Conversation: Custom Post ---
async def custom_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "**🚀 Custom Post Generator**\n\n"
        "Ab uss **Channel ka @username** ya **Group/Channel ki Chat ID** bhejo jahaan ye post karna hai.\n"
        "(Example: @MyAnimeChannel ya -100123456789)\n\n/cancel - Cancel.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]]))
    return CPOST_GET_CHAT
async def custom_post_get_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['chat_id'] = update.message.text
    await update.message.reply_text("Chat ID set! Ab post ka **Poster (Photo)** bhejo.\n\n/cancel - Cancel.")
    return CPOST_GET_POSTER
async def custom_post_get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo.")
        return CPOST_GET_POSTER
    context.user_data['poster_id'] = update.message.photo[-1].file_id
    await update.message.reply_text("Poster set! Ab post ka **Caption** (text) bhejo.\n\n/cancel - Cancel.")
    return CPOST_GET_CAPTION
async def custom_post_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['caption'] = update.message.text
    await update.message.reply_text("Caption set! Ab custom button ka **Text** bhejo.\n(Example: 'Join Now')\n\n/cancel - Cancel.")
    return CPOST_GET_BTN_TEXT
async def custom_post_get_btn_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_text'] = update.message.text
    await update.message.reply_text("Button text set! Ab button ka **URL (Link)** bhejo.\n(Example: 'https://t.me/mychannel')\n\n/cancel - Cancel.")
    return CPOST_GET_BTN_URL
async def custom_post_get_btn_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['btn_url'] = update.message.text
    
    # Confirmation dikhao
    chat_id = context.user_data['chat_id']
    poster_id = context.user_data['poster_id']
    caption = context.user_data['caption']
    btn_text = context.user_data['btn_text']
    btn_url = context.user_data['btn_url']
    
    keyboard = [
        [InlineKeyboardButton(btn_text, url=btn_url)],
        [InlineKeyboardButton("✅ Post Karo", callback_data="cpost_send")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_admin_settings")]
    ]
    
    await update.message.reply_photo(
        photo=poster_id,
        caption=f"**--- PREVIEW ---**\n\n{caption}\n\n**Target:** `{chat_id}`",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CPOST_CONFIRM
async def custom_post_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Sending...")
    
    chat_id = context.user_data['chat_id']
    poster_id = context.user_data['poster_id']
    caption = context.user_data['caption']
    btn_text = context.user_data['btn_text']
    btn_url = context.user_data['btn_url']
    
    keyboard = [[InlineKeyboardButton(btn_text, url=btn_url)]]
    
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=poster_id,
            caption=caption,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.message.reply_text(f"✅ **Success!**\nPost ko '{chat_id}' par bhej diya gaya hai.")
    except Exception as e:
        logger.error(f"Custom post bhejme me error: {e}")
        await query.message.reply_text(f"❌ **Error!**\nPost '{chat_id}' par nahi bhej paya.\nError: {e}")
    
    await query.message.delete() # Preview delete karo
    context.user_data.clear()
    await admin_settings_menu(update, context)
    return ConversationHandler.END
    

# --- Conversation: User Subscription ---
async def user_upload_ss_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config = await get_config()
    msg = config.get("messages", {}).get("user_sub_ss_prompt", "Screenshot bhejo.")
    await query.message.reply_text(msg)
    return SUB_GET_SCREENSHOT
    
async def user_get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        config = await get_config()
        msg = config.get("messages", {}).get("user_sub_ss_not_photo", "Photo nahi hai.")
        await update.message.reply_text(msg)
        return SUB_GET_SCREENSHOT
        
    user = update.effective_user
    screenshot_id = update.message.photo[-1].file_id
    
    users_collection.update_one(
        {"_id": user.id},
        {"$set": {"first_name": user.first_name, "username": user.username}},
        upsert=True
    )
    
    logger.info(f"User {user.id} ({user.first_name}) ne subscription screenshot bheja hai.")
    
    caption = f"🔔 **Naya Subscription Request**\n\n**User:** {user.first_name} (ID: `{user.id}`)\n**Username:** @{user.username}\n\nNeeche diye gaye buttons se approve ya reject karein."
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{user.id}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{user.id}")]
    ]
    
    try:
        await context.bot.send_photo(
            chat_id=LOG_CHANNEL_ID,
            photo=screenshot_id,
            caption=caption,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        config = await get_config()
        msg = config.get("messages", {}).get("sub_pending", "Pending...")
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Log channel me screenshot bhejte waqt error: {e}")
        config = await get_config()
        msg = config.get("messages", {}).get("user_sub_ss_error", "Error...")
        await update.message.reply_text(msg)
        
    return ConversationHandler.END
    
async def activate_subscription(context: ContextTypes.DEFAULT_TYPE, user_id: int, days: int, admin_user_name: str, original_message=None):
    """User ko subscribe karega aur sabko inform karega"""
    expiry_date = datetime.now() + timedelta(days=days)
    users_collection.update_one(
        {"_id": user_id},
        {"$set": {"subscribed": True, "expiry_date": expiry_date}},
        upsert=True
    )
    logger.info(f"User {user_id} ko {days} din ka subscription mil gaya hai.")
    
    user_dm_success = False
    try:
        config = await get_config()
        msg_template = config.get("messages", {}).get("sub_approved", "Approved.")
        msg = msg_template.replace("{days}", str(days)).replace("{expiry_date}", expiry_date.strftime('%Y-%m-%d'))
        
        await context.bot.send_message(
            chat_id=user_id,
            text=msg,
            parse_mode='Markdown'
        )
        user_dm_success = True
    except Exception as e:
        logger.error(f"User {user_id} ko subscription message bhejte waqt error (blocked?): {e}")

    if original_message:
        try:
            await original_message.edit_caption(
                caption=original_message.caption + f"\n\n**[APPROVED by {admin_user_name} for {days} days]**",
                parse_mode='Markdown'
            )
        except Exception as e:
                logger.error(f"Original message edit nahi ho paya: {e}")
    
    admin_confirm_text = f"✅ **Success!**\nUser ID `{user_id}` ko {days} din ka subscription mil gaya hai.\nExpiry: {expiry_date.strftime('%Y-%m-%d')}"
    if not user_dm_success:
        admin_confirm_text += "\n\n⚠️ **Warning:** User ko notification DM nahi bhej paya. (Shayad user ne bot ko start/unblock nahi kiya hai)."
    
    return admin_confirm_text

    
# --- Conversation: Admin Approval ---
async def admin_approve_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await is_main_admin(query.from_user.id):
        await query.answer("Aap main admin nahi hain!", show_alert=True)
        return ConversationHandler.END
        
    try:
        user_id_to_approve = int(query.data.split("_")[-1])
        context.user_data['user_to_approve'] = user_id_to_approve
        context.user_data['original_query_message'] = query.message
        user_info = users_collection.find_one({"_id": user_id_to_approve})
        
        config = await get_config()
        days = config.get('validity_days')
        
        if days:
            confirmation_text = await activate_subscription(
                context, 
                user_id_to_approve, 
                days, 
                query.from_user.first_name, 
                query.message
            )
            await query.message.reply_text(confirmation_text, parse_mode='Markdown') 
            context.user_data.clear()
            return ConversationHandler.END 
        else:
            await query.message.reply_text(
                f"⚠️ **Validity Days set nahi hai!**\n\n"
                f"Aap user **{user_info.get('first_name', 'N/A')}** (ID: `{user_id_to_approve}`) ko approve kar rahe hain.\n\n"
                f"Kitne din ka subscription dena hai? (Number mein bhejein, jaise: 30)\n\n"
                f"Aap /admin -> Subscription Settings -> Set Validity Days se isse automatic kar sakte hain.\n\n"
                f"/cancel - Cancel.",
                parse_mode='Markdown'
            )
            return ADMIN_GET_DAYS
            
    except Exception as e:
        logger.error(f"Approve start me error: {e}")
        await query.message.reply_text("❌ Error! User ID nahi mili.")
        return ConversationHandler.END

async def admin_get_days_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        user_id = context.user_data['user_to_approve']
        original_message = context.user_data.get('original_query_message') 
        
        confirmation_text = await activate_subscription(
            context, 
            user_id, 
            days, 
            update.from_user.first_name, 
            original_message
        )
        await update.message.reply_text(confirmation_text, parse_mode='Markdown')

    except ValueError:
        await update.message.reply_text("Yeh number nahi hai. Please sirf number bhejein (jaise 30) ya /cancel karein.")
        return ADMIN_GET_DAYS
    except Exception as e:
        logger.error(f"Subscription save karte waqt error: {e}")
        await update.message.reply_text("❌ Error! Subscription save nahi kar paya.")
        
    context.user_data.clear()
    return ConversationHandler.END
    
async def admin_reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not await is_main_admin(query.from_user.id):
        await query.answer("Aap main admin nahi hain!", show_alert=True)
        return
        
    user_dm_success = False 
    try:
        user_id_to_reject = int(query.data.split("_")[-1])
        user_info = users_collection.find_one({"_id": user_id_to_reject}) 
        
        try:
            config = await get_config()
            msg = config.get("messages", {}).get("sub_rejected", "Rejected.")
            await context.bot.send_message(
                chat_id=user_id_to_reject,
                text=msg,
                parse_mode='Markdown'
            )
            user_dm_success = True 
        except Exception as e:
            logger.error(f"User {user_id_to_reject} ko rejection message bhejte waqt error (blocked?): {e}")
            
        admin_confirm_text = f"✅ User {user_id_to_reject} ({user_info.get('first_name', 'N/A')}) ko reject kar diya gaya hai."
        if not user_dm_success:
                admin_confirm_text += "\n\n⚠️ **Warning:** User ko notification DM nahi bhej paya."
                
        await query.message.reply_text(admin_confirm_text, parse_mode='Markdown') 
        
        try:
                await query.edit_message_caption(
                    caption=query.message.caption + f"\n\n**[REJECTED by {query.from_user.first_name}]**",
                    parse_mode='Markdown'
                )
        except Exception as e:
                logger.error(f"Original rejection message edit nahi ho paya: {e}")
        
    except Exception as e:
        logger.error(f"Reject karte waqt error: {e}")
        await query.message.reply_text("❌ Error! Reject nahi kar paya.")
        
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
    await query.edit_message_text("➕ **Add Content** ➕\n\nAap kya add karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
    
async def manage_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_message: bool = False):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete Anime", callback_data="admin_del_anime")],
        [InlineKeyboardButton("🗑️ Delete Season", callback_data="admin_del_season")],
        [InlineKeyboardButton("🗑️ Delete Episode", callback_data="admin_del_episode")], 
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "✏️ **Manage Content** ✏️\n\nAap kya manage karna chahte hain?"
    
    if from_message: # Helper for change_poster_save
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def sub_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    config = await get_config()
    sub_qr_status = "✅" if config.get('sub_qr_id') else "❌"
    price_status = "✅" if config.get('price') else "❌"
    days_val = config.get('validity_days')
    days_status = f"✅ ({days_val} days)" if days_val else "❌"
    delete_seconds = config.get("delete_seconds", 300)
    delete_status = f"✅ ({delete_seconds // 60} min)"
    
    keyboard = [
        [InlineKeyboardButton(f"Set Subscription QR {sub_qr_status}", callback_data="admin_set_sub_qr")],
        [InlineKeyboardButton(f"Set Price Text {price_status}", callback_data="admin_set_price")],
        [InlineKeyboardButton(f"Set Validity Days {days_status}", callback_data="admin_set_days")],
        [InlineKeyboardButton(f"Set Auto-Delete Time {delete_status}", callback_data="admin_set_delete_time")],
        [InlineKeyboardButton("🚫 Remove Subscription", callback_data="admin_remove_sub")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "💲 **Subscription Settings** 💲\n\n`Set Validity Days` se automatic approval days set karein."
    if query: 
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def donate_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    config = await get_config()
    donate_qr_status = "✅" if config.get('donate_qr_id') else "❌"
    keyboard = [
        [InlineKeyboardButton(f"Set Donate QR {donate_qr_status}", callback_data="admin_set_donate_qr")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "❤️ **Donation Settings** ❤️\n\nSirf QR code se donation accept karein."
    if query: 
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def other_links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    config = await get_config()
    backup_status = "✅" if config.get('links', {}).get('backup') else "❌"
    support_status = "✅" if config.get('links', {}).get('support') else "❌"
    keyboard = [
        [InlineKeyboardButton(f"Set Backup Link {backup_status}", callback_data="admin_set_backup_link")],
        [InlineKeyboardButton(f"Set Support Link {support_status}", callback_data="admin_set_support_link")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "🔗 **Other Links** 🔗\n\nDoosre links yahan set karein."
    if query: 
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# NAYA: Bot Messages Menu (Paginated)
async def bot_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("💲 Subscription Messages", callback_data="msg_menu_sub")],
        [InlineKeyboardButton("📥 Download Flow Messages", callback_data="msg_menu_dl")],
        [InlineKeyboardButton("✍️ Post Generator Messages", callback_data="msg_menu_postgen")],
        [InlineKeyboardButton("🔗 Gen-Link Messages", callback_data="msg_menu_genlink")], # NAYA (v10)
        [InlineKeyboardButton("⚙️ General Messages", callback_data="msg_menu_gen")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    text = "⚙️ **Bot Messages** ⚙️\n\nAap bot ke replies ko edit karne ke liye category select karein."
    
    if query: 
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return M_MENU_MAIN

async def bot_messages_menu_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Sub QR Error", callback_data="msg_edit_user_sub_qr_error")],
        [InlineKeyboardButton("Edit Sub QR Text", callback_data="msg_edit_user_sub_qr_text")],
        [InlineKeyboardButton("Edit SS Prompt", callback_data="msg_edit_user_sub_ss_prompt")],
        [InlineKeyboardButton("Edit SS Not Photo", callback_data="msg_edit_user_sub_ss_not_photo")],
        [InlineKeyboardButton("Edit SS Error", callback_data="msg_edit_user_sub_ss_error")],
        [InlineKeyboardButton("Edit Sub Pending", callback_data="msg_edit_sub_pending")],
        [InlineKeyboardButton("Edit Sub Approved", callback_data="msg_edit_sub_approved")],
        [InlineKeyboardButton("Edit Sub Rejected", callback_data="msg_edit_sub_rejected")],
        [InlineKeyboardButton("Edit Sub Removed (by Admin)", callback_data="msg_edit_user_sub_removed")],
        [InlineKeyboardButton("Edit Already Subscribed", callback_data="msg_edit_user_already_subscribed")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    await query.edit_message_text("💲 **Subscription Messages** 💲\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_SUB

async def bot_messages_menu_dl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Unsubscribed Alert", callback_data="msg_edit_user_dl_unsubscribed_alert")],
        [InlineKeyboardButton("Edit Unsubscribed DM", callback_data="msg_edit_user_dl_unsubscribed_dm")],
        [InlineKeyboardButton("Edit Check DM Alert", callback_data="msg_edit_user_dl_dm_alert")],
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
    await query.edit_message_text("📥 **Download Flow Messages** 📥\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
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
    await query.edit_message_text("⚙️ **General Messages** ⚙️\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_GEN

async def bot_messages_menu_postgen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Season Post Caption", callback_data="msg_edit_post_gen_season_caption")],
        [InlineKeyboardButton("Edit Episode Post Caption", callback_data="msg_edit_post_gen_episode_caption")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    await query.edit_message_text("✍️ **Post Generator Messages** ✍️\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_POSTGEN

# NAYA (v10): Gen-Link Messages Menu
async def bot_messages_menu_genlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Edit Season Link Caption", callback_data="msg_edit_gen_link_caption_season")],
        [InlineKeyboardButton("Edit Episode Link Caption", callback_data="msg_edit_gen_link_caption_ep")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu_messages")]
    ]
    await query.edit_message_text("🔗 **Generate Link Messages** 🔗\n\nKaunsa message edit karna hai?", reply_markup=InlineKeyboardMarkup(keyboard))
    return M_MENU_GENLINK

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
    text = "🛠️ **Admin Settings** 🛠️\n\nYahan aap Co-Admins aur doosri advanced settings manage kar sakte hain."
    
    if query: 
        if query.message.photo: # Handle coming back from custom post
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    
# --- User Handlers ---
async def handle_deep_link_donate(user: User, context: ContextTypes.DEFAULT_TYPE):
    """Deep link se /start=donate ko handle karega"""
    logger.info(f"User {user.id} ne Donate deep link use kiya.")
    try:
        config = await get_config()
        qr_id = config.get('donate_qr_id')
        
        if not qr_id: 
            msg = config.get("messages", {}).get("user_donate_qr_error", "Error")
            await context.bot.send_message(user.id, msg)
            return

        text = config.get("messages", {}).get("user_donate_qr_text", "Support us.")
        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data="user_back_menu")]]
        
        await context.bot.send_photo(
            chat_id=user.id, 
            photo=qr_id, 
            caption=text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.job_queue.run_once(send_donate_thank_you, 60, chat_id=user.id)
    except Exception as e:
        logger.error(f"Deep link Donate QR bhejte waqt error: {e}")
        if "blocked" in str(e):
            logger.warning(f"User {user.id} ne bot ko block kiya hua hai.")

async def handle_deep_link_subscribe(user: User, context: ContextTypes.DEFAULT_TYPE):
    """Deep link se /start=subscribe ko handle karega"""
    logger.info(f"User {user.id} ne Subscribe deep link use kiya.")
    config = await get_config()

    if await check_subscription(user.id):
        msg = config.get("messages", {}).get("user_already_subscribed", "Already subbed.")
        await context.bot.send_message(user.id, msg)
        return

    try:
        qr_id = config.get('sub_qr_id')
        price = config.get('price')
        days = config.get('validity_days')
        
        if not qr_id or not price or not days:
            msg = config.get("messages", {}).get("user_sub_qr_error", "Error")
            await context.bot.send_message(user.id, msg)
            return
            
        text = config.get("messages", {}).get("user_sub_qr_text", "{price} {days}")
        text = text.replace("{price}", str(price)).replace("{days}", str(days))
        
        keyboard = [[InlineKeyboardButton("⬆️ Upload Screenshot", callback_data="user_upload_ss")], [InlineKeyboardButton("⬅️ Back", callback_data="user_back_menu")]]
        
        await context.bot.send_photo(
            chat_id=user.id, 
            photo=qr_id, 
            caption=text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Deep link Subscribe QR bhejte waqt error: {e}")
        if "blocked" in str(e):
            logger.warning(f"User {user.id} ne bot ko block kiya hua hai.")

# NAYA (v10): Deep Link Download Handler
async def handle_deep_link_download(user: User, context: ContextTypes.DEFAULT_TYPE, payload: str):
    """Deep link se /start=dl_... ko handle karega"""
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
        
        async def edit_message_text(self, *args, **kwargs):
            # edit() bhi kuch nahi karega, naya message banega
            pass
        
        async def edit_message_caption(self, *args, **kwargs):
            # edit() bhi kuch nahi karega, naya message banega
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
    """Smart /start command (v22)"""
    user = update.effective_user
    user_id, first_name = user.id, user.first_name
    logger.info(f"User {user_id} ({first_name}) ne /start dabaya.")
    
    # User DB logic (waise hi rahega)
    user_data = users_collection.find_one({"_id": user_id})
    if not user_data:
        users_collection.insert_one({"_id": user_id, "first_name": first_name, "username": user.username, "subscribed": False, "expiry_date": None})
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
        
        # (v17 Fix: Handle 'dl' and 'dl_')
        if payload.startswith("dl"): # 'dl' ya 'dl_' dono match honge
            await handle_deep_link_download(user, context, payload)
            return
        elif payload == "donate":
            await handle_deep_link_donate(user, context)
            return
        elif payload == "subscribe": 
            await handle_deep_link_subscribe(user, context)
            return
    
    # ============================================
    # ===           NAYA FIX (v22)             ===
    # === /start hamesha User Menu dikhayega ===
    # === Admin panel ab /menu par hai       ===
    # ============================================
    logger.info("Koi deep link nahi. User menu dikha raha hoon.")
    await show_user_menu(update, context) # Admin panel nahi, user menu dikhao
    
async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    """User ka main menu (/menu)"""
    user = update.effective_user
    user_id = user.id
    
    if from_callback:
        logger.info(f"User {user_id} 'Back to Menu' se aaya.")
    else:
        logger.info(f"User {user_id} ne /menu khola.")
    
    config = await get_config()
    user_data = users_collection.find_one({"_id": user_id}) or {}
    links = config.get('links', {})
    
    if await check_subscription(user_id):
        expiry = user_data.get('expiry_date')
        if expiry:
            sub_text = f"✅ Subscribed (Expires: {expiry.strftime('%Y-%m-%d')})"
        else:
            sub_text = "✅ Subscribed (Permanent)" # Main Admin
        sub_cb = "user_check_sub" 
    else:
        sub_text = "💰 Subscribe Now"
        sub_cb = "user_subscribe" 
    
    backup_url = links.get('backup') or "https://t.me/"
    support_url = links.get('support') or "https://t.me/"
        
    btn_backup = InlineKeyboardButton("Backup", url=backup_url)
    btn_donate = InlineKeyboardButton("Donate", callback_data="user_show_donate_menu")
    btn_support = InlineKeyboardButton("Support", url=support_url)
    btn_sub = InlineKeyboardButton(sub_text, callback_data=sub_cb)
    keyboard = [[btn_sub], [btn_backup, btn_donate], [btn_support]]
    
    menu_text = config.get("messages", {}).get("user_menu_greeting", "Salaam {first_name}!")
    menu_text = menu_text.replace("{first_name}", user.first_name)
    
    if from_callback:
        query = update.callback_query
        await query.answer()
        try:
            if query.message.photo:
                await query.message.delete()
                await context.bot.send_message(query.from_user.id, menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await query.edit_message_text(menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.warning(f"Menu edit/reply nahi kar paya: {e}")
            try:
                await context.bot.send_message(query.from_user.id, menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e2:
                logger.error(f"Menu command (callback) me critical error: {e2}")
    else:
        await update.message.reply_text(menu_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def user_show_donate_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/menu se Donate button ko handle karega (DM bhejega)"""
    query = update.callback_query
    config = await get_config()
    qr_id = config.get('donate_qr_id')
    
    if not qr_id: 
        msg = config.get("messages", {}).get("user_donate_qr_error", "Error")
        await query.answer(msg, show_alert=True)
        return

    text = config.get("messages", {}).get("user_donate_qr_text", "Support us.")
    
    try:
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="user_back_menu")]]
        
        # NAYA (v10) FIX: Purana menu message delete karo
        if not query.message.photo:
                await query.message.delete()
                
        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=qr_id,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
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
                await update.message.reply_text("Aap admin nahi hain.")
            else:
                await update.callback_query.answer("Aap admin nahi hain.", show_alert=True)
        return
        
    logger.info("Admin/Co-Admin ne /admin command use kiya.")
    
    # NAYA (v10): Co-Admin limited menu
    if not await is_main_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")],
            [InlineKeyboardButton("✏️ Manage Content", callback_data="admin_menu_manage_content")],
            [InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")],
            # NAYA (v10): Co-admin ko bhi link gen aur photo update do
            [
                InlineKeyboardButton("🖼️ Update Photo", callback_data="admin_update_photo"),
                InlineKeyboardButton("🔗 Generate Link", callback_data="admin_gen_link")
            ]
        ]
        admin_menu_text = f"Salaam, Co-Admin! 👑\nAapka content panel taiyyar hai."
    
    # Main Admin full menu
    else:
        try:
            log_chat = await context.bot.get_chat(LOG_CHANNEL_ID)
            if log_chat.username:
                    log_url = f"https://t.me/{log_chat.username}"
            else:
                log_url = log_chat.invite_link or f"https://t.me/c/{str(LOG_CHANNEL_ID).replace('-100', '')}"
        except Exception as e:
            logger.error(f"Log channel ({LOG_CHANNEL_ID}) fetch nahi kar paya: {e}")
            log_url = "https://t.me/"

        # NAYA (v12) FIX: User ke request ke mutabik naya layout (Admin Settings neeche)
        keyboard = [
            [InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")],
            [
                InlineKeyboardButton("✏️ Manage Content", callback_data="admin_menu_manage_content"),
                InlineKeyboardButton("🔗 Other Links", callback_data="admin_menu_other_links")
            ],
            [InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")],
            [
                InlineKeyboardButton("❤️ Donation", callback_data="admin_menu_donate_settings"),
                InlineKeyboardButton("💲 Subscription", callback_data="admin_menu_sub_settings")
            ],
            [InlineKeyboardButton("⚙️ Bot Messages", callback_data="admin_menu_messages")],
            [
                InlineKeyboardButton("🖼️ Update Photo", callback_data="admin_update_photo"),
                InlineKeyboardButton("🔗 Generate Link", callback_data="admin_gen_link")
            ],
            [
                InlineKeyboardButton("👥 Subscribed Users", callback_data="admin_list_subs"),
                InlineKeyboardButton("🔔 Subscription Log", url=log_url)
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
                await context.bot.send_message(query.from_user.id, admin_menu_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await query.edit_message_text(admin_menu_text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                logger.warning(f"Admin menu edit nahi kar paya: {e}")
            await query.answer()
        except Exception as e:
            logger.warning(f"Admin menu edit error: {e}")
            await query.answer()
    else:
        await update.message.reply_text(admin_menu_text, reply_markup=reply_markup, parse_mode='Markdown')

async def admin_list_subs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Fetching user list...")
    
    try:
        subscribed_users = users_collection.find({"subscribed": True})
        user_list = []
        count = 0
        for user in subscribed_users:
            user_id = user['_id']
            name = user.get('first_name', 'N/A')
            expiry = user.get('expiry_date')
            expiry_str = expiry.strftime('%Y-%m-%d') if expiry else "Permanent"
            user_list.append(f"ID: {user_id} | Name: {name} | Expires: {expiry_str}")
            count += 1
        
        if count == 0:
            await query.edit_message_text("Bot par koi bhi subscribed user nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
            return
        
        file_content = "\n".join(user_list)
        file_path = f"subscribed_users_{datetime.now().strftime('%Y%m%d')}.txt"
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        
        await context.bot.send_document(
            chat_id=query.from_user.id,
            document=open(file_path, "rb"),
            filename=file_path,
            caption=f"Yeh rahi **{count}** subscribed users ki poori list.",
            parse_mode='Markdown'
        )
        os.remove(file_path) 
        await query.message.delete()
        
    except Exception as e:
        logger.error(f"Subscribed users ki list banate waqt error: {e}")
        await context.bot.send_message(query.from_user.id, "❌ Error! List nahi bana paya.")
    
    # Re-show admin menu
    await admin_command(update, context, from_callback=True)
async def placeholder_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "user_check_sub":
        await query.answer("Aap pehle se subscribed hain!", show_alert=True)
    else:
        await query.answer(f"Button '{query.data}' jald aa raha hai...", show_alert=True)
        
# --- User Download Handler (CallbackQuery) ---
async def download_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback data 'dl' se shuru hone wale sabhi buttons ko handle karega.
    """
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    config = await get_config() 
    
    # NAYA (v10): Dummy object check
    is_deep_link = not hasattr(query.message, 'chat')
    is_in_dm = False # Default
    
    checking_msg = None # Initialize
    
    try:
        # ============================================
        # ===           NAYA FIX (v19)             ===
        # ============================================
        
        # Step 1: Click ko acknowledge karo
        if not is_deep_link:
            is_in_dm = query.message.chat.type == 'private'
            if not is_in_dm:
                # Channel/Group me click
                alert_msg = config.get("messages", {}).get("user_dl_dm_alert", "Check DM")
                await query.answer(alert_msg, show_alert=True)
            else:
                # DM me click
                await query.answer()
        
        # Step 2: "Checking..." message bhejo (Sabhi cases me)
        try:
            checking_msg = await context.bot.send_message(chat_id=user_id, text="⏳ Checking subscription...")
            await asyncio.sleep(1.5) # 1.5 second ka delay
        except Exception as e:
            logger.error(f"User {user_id} ko 'Checking...' message nahi bhej paya. Shayad bot block hai? Error: {e}")
            if not is_deep_link and not is_in_dm:
                # Agar bot block hai aur channel me click hua hai, toh alert dikhao
                await query.answer("❌ Error! Bot ko DM mein /start karke unblock karein.", show_alert=True)
            return # Function rok do
        # ============================================

        # Step 3: Check Subscription
        if not await check_subscription(user_id):
            # NAYA: Checking message delete karo
            if checking_msg: await checking_msg.delete()

            # (Baaki ka QR code logic waisa hi rahega)
            qr_id = config.get('sub_qr_id')
            price = config.get('price')
            days = config.get('validity_days')

            if not qr_id or not price or not days:
                try:
                    msg = config.get("messages", {}).get("user_sub_qr_error", "Error")
                    await context.bot.send_message(user_id, msg)
                except Exception as e: logger.warning(f"Error sending sub error to user {user_id}: {e}")
                return

            text = config.get("messages", {}).get("user_dl_unsubscribed_dm", "{price} {days}")
            text = text.replace("{price}", str(price)).replace("{days}", str(days))
            
            try:
                bot_username = (await context.bot.get_me()).username
                keyboard = [[InlineKeyboardButton("Subscribe Now", url=f"https://t.me/{bot_username}?start=subscribe")]]
                
                await context.bot.send_photo(
                    chat_id=user_id, 
                    photo=qr_id, 
                    caption=text, 
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except Exception as e:
                logger.error(f"User {user_id} ko DM me QR bhejte waqt error: {e}")
            return
            
        # Step 4: User Subscribed Hai
        # NAYA: Checking message delete karo
        if checking_msg: await checking_msg.delete()

        # (Baaki ka logic (v17 wala) waisa hi rahega)
        parts = query.data.split('__')
        
        # ============================================
        # ===           NAYA FIX (v17)             ===
        # ===  'dl_' aur 'dl' dono ko handle karo   ===
        # ============================================
        anime_key = parts[0]
        if anime_key.startswith("dl_"):
            anime_key = anime_key.replace("dl_", "") # Puraana format (dl_ANIME_NAME...)
        elif anime_key.startswith("dl"):
            anime_key = anime_key.replace("dl", "")  # Naya format (dlANIME_ID...)
            
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
            # Dono methods fail ho gaye
            logger.error(f"Anime '{anime_key}' na ID se mila na Name se.")
            msg = config.get("messages", {}).get("user_dl_anime_not_found", "Error")
            await context.bot.send_message(user_id, msg)
            return
            
        anime_name = anime_doc['name'] # Get the real name for captions
        anime_id_str = str(anime_doc['_id']) # Get the real ID for future buttons
        # ============================================
        
        # Case 3: Episode click hua hai -> Saare Files Bhejo
        if ep_num:
            qualities_dict = anime_doc.get("seasons", {}).get(season_name, {}).get(ep_num, {})
            if not qualities_dict:
                msg = config.get("messages", {}).get("user_dl_episodes_not_found", "Error")
                
                if is_in_dm:
                    if query.message.photo:
                        await query.edit_message_caption(msg)
                    else:
                        await query.message.reply_text(msg) 
                else:
                    await context.bot.send_message(user_id, msg)
                return
            
            msg = config.get("messages", {}).get("user_dl_sending_files", "Sending...")
            msg = msg.replace("{anime_name}", anime_name).replace("{season_name}", season_name).replace("{ep_num}", ep_num)
            
            msg_to_delete_id = None 

            if is_in_dm:
                if query.message.photo:
                        await query.edit_message_caption(caption=msg, parse_mode='Markdown')
                        msg_to_delete_id = query.message.message_id 
                else:
                    sent_msg = await query.message.reply_text(msg, parse_mode='Markdown')
                    msg_to_delete_id = sent_msg.message_id 
            else:
                # NAYA (v10): Deep link/Channel click ke liye naya message
                    sent_msg = await context.bot.send_message(user_id, msg, parse_mode='Markdown')
                    msg_to_delete_id = sent_msg.message_id
            
            QUALITY_ORDER = ['480p', '720p', '1080p', '4K']
            available_qualities = qualities_dict.keys()
            sorted_q_list = [q for q in QUALITY_ORDER if q in available_qualities]
            extra_q = [q for q in available_qualities if q not in sorted_q_list]
            sorted_q_list.extend(extra_q)
            
            delete_time = config.get("delete_seconds", 300) 
            delete_minutes = max(1, delete_time // 60)
            warning_template = config.get("messages", {}).get("file_warning", "Warning")
            warning_msg = warning_template.replace('{minutes}', str(delete_minutes))
            
            for quality in sorted_q_list:
                file_id = qualities_dict.get(quality)
                if not file_id: continue
                
                sent_message = None 
                try:
                    caption = f"🎬 **{anime_name}**\nS{season_name} - E{ep_num} ({quality})\n\n{warning_msg}"
                    
                    sent_message = await context.bot.send_video(
                        chat_id=user_id, 
                        video=file_id, 
                        caption=caption,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"User {user_id} ko file bhejte waqt error: {e}")
                    error_msg_key = "user_dl_blocked_error" if "blocked" in str(e) else "user_dl_file_error"
                    msg = config.get("messages", {}).get(error_msg_key, "Error")
                    msg = msg.replace("{quality}", quality)
                    await context.bot.send_message(user_id, msg) 
                
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
            
        # Case 2: Season click hua hai -> Episode Bhejo
        if season_name:
            episodes = anime_doc.get("seasons", {}).get(season_name, {})
            
            episode_keys = [ep for ep in episodes.keys() if not ep.startswith("_")]
            
            if not episode_keys:
                msg = config.get("messages", {}).get("user_dl_episodes_not_found", "Error")
                if is_in_dm:
                    if query.message.photo:
                        await query.edit_message_caption(msg)
                    else:
                        await query.message.reply_text(msg)
                else:
                    await context.bot.send_message(user_id, msg)
                return
            
            sorted_eps = sorted(episode_keys, key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"dl{anime_id_str}__{season_name}__{ep}") for ep in sorted_eps] # NAYA (v17): Use ID
            keyboard = build_grid_keyboard(buttons, 2)
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"dl{anime_id_str}")]) # NAYA (v17): Use ID
            
            msg = config.get("messages", {}).get("user_dl_select_episode", "Select episode")
            msg = msg.replace("{anime_name}", anime_name).replace("{season_name}", season_name)

            season_poster_id = anime_doc.get("seasons", {}).get(season_name, {}).get("_poster_id")
            poster_to_use = season_poster_id or anime_doc['poster_id'] 
            
            # ============================================
            # ===           NAYA FIX (v15)             ===
            # ===  'DummyMessage' delete bug fix karo  ===
            # ============================================
            if is_deep_link or not is_in_dm:
                # Deep link hai YA channel me click hua -> Hamesha nayi photo DM me bhejo
                await context.bot.send_photo(
                    chat_id=user_id, 
                    photo=poster_to_use, 
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else: 
                # DM me hai, aur deep link nahi hai (yaani purane message par click kiya)
                try:
                    if not query.message.photo:
                        await query.message.delete() # Ab yeh safe hai, kyunki is_deep_link False hai
                        await context.bot.send_photo(
                            chat_id=user_id,
                            photo=poster_to_use, 
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                    else:
                        await query.edit_message_media(
                            media=InputMediaPhoto(media=poster_to_use, caption=msg, parse_mode='Markdown'),
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                except BadRequest as e:
                    if "Message is not modified" not in str(e):
                        logger.warning(f"DL Handler Case 2: Media edit fail, fallback to caption: {e}")
                        await query.edit_message_caption( 
                            caption=msg,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                except Exception as e:
                    logger.error(f"DL Handler Case 2: Media edit critical fail: {e}")
                    # Fallback to just editing caption
                    await query.edit_message_caption( 
                        caption=msg,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
            return
            # ============================================
            
        # Case 1: Sirf Anime click hua hai -> Season Bhejo
        seasons = anime_doc.get("seasons", {})
        if not seasons:
            msg = config.get("messages", {}).get("user_dl_seasons_not_found", "Error")
            if is_in_dm: 
                if query.message.photo:
                    await query.edit_message_caption(msg)
                else:
                    await query.edit_message_text(msg)
            else: 
                await context.bot.send_message(user_id, msg)
            return
        
        sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
        buttons = [InlineKeyboardButton(f"Season {s}", callback_data=f"dl{anime_id_str}__{s}") for s in sorted_seasons] # NAYA (v17): Use ID
        keyboard = build_grid_keyboard(buttons, 1) 
        keyboard.append([InlineKeyboardButton("⬅️ Back to Bot Menu", callback_data="user_back_menu")])
        
        msg = config.get("messages", {}).get("user_dl_select_season", "Select season")
        msg = msg.replace("{anime_name}", anime_name)

        # ============================================
        # ===           NAYA FIX (v15)             ===
        # ===  'DummyMessage' delete bug fix karo  ===
        # ============================================
        if is_deep_link or not is_in_dm:
            # Deep link hai YA channel me click hua -> Hamesha nayi photo DM me bhejo
            await context.bot.send_photo(
                chat_id=user_id, 
                photo=anime_doc['poster_id'], 
                caption=msg,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else: 
            # DM me hai, aur deep link nahi hai (yaani purane message par click kiya)
            if not query.message.photo:
                await query.message.delete() # Safe hai
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=anime_doc['poster_id'], 
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_caption(
                    caption=msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
        return
        # ============================================

    except Exception as e:
        # Main error handler
        logger.error(f"Download button handler me error: {e}", exc_info=True)
        # NAYA: Yahan bhi checking message delete karo
        try:
            if checking_msg:
                await context.bot.delete_message(chat_id=user_id, message_id=checking_msg.message_id)
        except Exception:
            pass # Agar delete na ho toh koi baat nahi
            
        msg = config.get("messages", {}).get("user_dl_general_error", "Error")
        try:
            if not is_deep_link and query.message and query.message.chat.type in ['channel', 'supergroup', 'group']:
                    await query.answer(msg, show_alert=True)
            else:
                    await context.bot.send_message(user_id, msg)
        except Exception: pass
            
# --- Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error} \nUpdate: {update}", exc_info=True)

# ============================================
# ===    NAYA WEBHOOK AUR THREADING SETUP    ===
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
    sub_settings_fallback = [CallbackQueryHandler(back_to_sub_settings_menu, pattern="^back_to_sub_settings$"), global_cancel_handler]
    donate_settings_fallback = [CallbackQueryHandler(back_to_donate_settings_menu, pattern="^back_to_donate_settings$"), global_cancel_handler]
    links_fallback = [CallbackQueryHandler(back_to_links_menu, pattern="^back_to_links$"), global_cancel_handler]
    user_menu_fallback = [CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"), global_cancel_handler]
    messages_fallback = [CallbackQueryHandler(back_to_messages_menu, pattern="^admin_menu_messages$"), global_cancel_handler]
    admin_settings_fallback = [CallbackQueryHandler(back_to_admin_settings_menu, pattern="^back_to_admin_settings$"), global_cancel_handler]
    
    # NAYA (v11) FIX: 'admin_gen_link' ko gen-link conv ke fallback me add karo
    gen_link_fallback = [CallbackQueryHandler(generate_link_start, pattern="^admin_gen_link$"), global_cancel_handler]


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
    set_sub_qr_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_sub_qr_start, pattern="^admin_set_sub_qr$")], 
        states={CS_GET_QR: [MessageHandler(filters.PHOTO, set_sub_qr_save)]}, 
        fallbacks=global_fallbacks + sub_settings_fallback,
        allow_reentry=True 
    )
    set_price_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_price_start, pattern="^admin_set_price$")], 
        states={CP_GET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_price_save)]}, 
        fallbacks=global_fallbacks + sub_settings_fallback,
        allow_reentry=True 
    )
    set_donate_qr_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_donate_qr_start, pattern="^admin_set_donate_qr$")], 
        states={CD_GET_QR: [MessageHandler(filters.PHOTO, set_donate_qr_save)]}, 
        fallbacks=global_fallbacks + donate_settings_fallback,
        allow_reentry=True 
    )
    set_links_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_links_start, pattern="^admin_set_backup_link$|^admin_set_support_link$")], 
        states={CL_GET_BACKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_link), CommandHandler("skip", skip_link)]}, 
        fallbacks=global_fallbacks + links_fallback,
        allow_reentry=True 
    ) 
    post_gen_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(post_gen_menu, pattern="^admin_post_gen$")], 
        states={
            PG_MENU: [CallbackQueryHandler(post_gen_select_anime, pattern="^post_gen_season$|^post_gen_episode$")], 
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
                # NAYA (v10) BUG FIX: Back button ko state me add karo
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
    
    # NAYA (v11) FIX: Generate Link Conversation
    generate_link_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(generate_link_start, pattern="^admin_gen_link$")],
        states={
            GL_START: [
                CallbackQueryHandler(generate_link_select_type, pattern="^genlink_type_")
            ],
            GL_GET_ANIME: [
                CallbackQueryHandler(generate_link_show_anime_list, pattern="^genlink_page_"),
                CallbackQueryHandler(generate_link_select_season, pattern="^genlink_anime_")
            ],
            GL_GET_SEASON: [
                CallbackQueryHandler(generate_link_select_episode, pattern="^genlink_season_"),
                CallbackQueryHandler(generate_link_show_anime_list, pattern="^genlink_page_") # Back from Ep list to Anime list
            ],
            GL_GET_EPISODE: [
                CallbackQueryHandler(generate_link_final_link, pattern="^genlink_ep_"),
                CallbackQueryHandler(generate_link_select_season, pattern="^genlink_anime_") # Back from Ep list to Season list
            ]
        },
        fallbacks=global_fallbacks + admin_menu_fallback + gen_link_fallback, # NAYA (v11): Back to start of conv
        allow_reentry=True
    )
    
    remove_sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_sub_start, pattern="^admin_remove_sub$")],
        states={
            RS_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_sub_get_id)],
            RS_CONFIRM: [CallbackQueryHandler(remove_sub_do, pattern="^remove_sub_confirm_yes$")]
        },
        fallbacks=global_fallbacks + sub_settings_fallback, 
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
    set_days_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_days_start, pattern="^admin_set_days$")], 
        states={CV_GET_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_days_save)]}, 
        fallbacks=global_fallbacks + sub_settings_fallback,
        allow_reentry=True 
    )
    set_delete_time_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_delete_time_start, pattern="^admin_set_delete_time$")],
        states={CS_GET_DELETE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_delete_time_save)]},
        fallbacks=global_fallbacks + sub_settings_fallback,
        allow_reentry=True 
    )
    set_messages_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bot_messages_menu, pattern="^admin_menu_messages$")],
        states={
            M_MENU_MAIN: [
                CallbackQueryHandler(bot_messages_menu_sub, pattern="^msg_menu_sub$"),
                CallbackQueryHandler(bot_messages_menu_dl, pattern="^msg_menu_dl$"),
                CallbackQueryHandler(bot_messages_menu_postgen, pattern="^msg_menu_postgen$"),
                CallbackQueryHandler(bot_messages_menu_genlink, pattern="^msg_menu_genlink$"), # NAYA (v10)
                CallbackQueryHandler(bot_messages_menu_gen, pattern="^msg_menu_gen$"),
            ],
            M_MENU_SUB: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_DL: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_POSTGEN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_MENU_GENLINK: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")], # NAYA (v10)
            M_MENU_GEN: [CallbackQueryHandler(set_msg_start, pattern="^msg_edit_")],
            M_GET_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_msg_save)],
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_upload_ss_start, pattern="^user_upload_ss$")],
        states={
            SUB_GET_SCREENSHOT: [MessageHandler(filters.PHOTO, user_get_screenshot)],
        },
        fallbacks=global_fallbacks + user_menu_fallback,
        allow_reentry=True
    )
    
    admin_approve_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_approve_start, pattern="^admin_approve_")],
        states={
            ADMIN_GET_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_days_save)],
        },
        fallbacks=global_fallbacks, # Yeh log channel me hai
        allow_reentry=True
    )
    
    # --- Saare handlers ko bot_app me add karo ---
    bot_app.add_handler(add_anime_conv)
    bot_app.add_handler(add_season_conv)
    bot_app.add_handler(add_episode_conv)
    bot_app.add_handler(set_sub_qr_conv)
    bot_app.add_handler(set_price_conv)
    bot_app.add_handler(set_donate_qr_conv)
    bot_app.add_handler(set_links_conv)
    bot_app.add_handler(post_gen_conv)
    bot_app.add_handler(del_anime_conv)
    bot_app.add_handler(del_season_conv)
    bot_app.add_handler(del_episode_conv)
    bot_app.add_handler(update_photo_conv) # NAYA (v10)
    bot_app.add_handler(generate_link_conv) # NAYA (v11) FIX
    bot_app.add_handler(remove_sub_conv)
    bot_app.add_handler(add_co_admin_conv) 
    bot_app.add_handler(remove_co_admin_conv) 
    bot_app.add_handler(custom_post_conv) 
    bot_app.add_handler(set_days_conv)
    bot_app.add_handler(set_delete_time_conv) 
    bot_app.add_handler(set_messages_conv) 
    bot_app.add_handler(sub_conv)
    bot_app.add_handler(admin_approve_conv)

    # Standard commands
    # Standard commands (v22 RE-MAPPED)
    bot_app.add_handler(CommandHandler("start", start_command)) # Start hamesha user menu/deep link
    bot_app.add_handler(CommandHandler("subscription", subscription_command)) # Naya command user menu ke liye
    bot_app.add_handler(CommandHandler("menu", menu_command)) # /menu ab admin panel hai
    bot_app.add_handler(CommandHandler("admin", admin_command)) # /admin bhi admin panel hai (alias)

    # Admin menu navigation (non-conversation)
    bot_app.add_handler(CallbackQueryHandler(add_content_menu, pattern="^admin_menu_add_content$"))
    bot_app.add_handler(CallbackQueryHandler(manage_content_menu, pattern="^admin_menu_manage_content$"))
    bot_app.add_handler(CallbackQueryHandler(sub_settings_menu, pattern="^admin_menu_sub_settings$"))
    bot_app.add_handler(CallbackQueryHandler(donate_settings_menu, pattern="^admin_menu_donate_settings$"))
    bot_app.add_handler(CallbackQueryHandler(other_links_menu, pattern="^admin_menu_other_links$"))
    bot_app.add_handler(CallbackQueryHandler(admin_list_subs, pattern="^admin_list_subs$"))
    bot_app.add_handler(CallbackQueryHandler(admin_settings_menu, pattern="^admin_menu_admin_settings$")) 
    bot_app.add_handler(CallbackQueryHandler(co_admin_list, pattern="^admin_list_co_admin$")) 

    # User menu navigation (non-conversation)
    bot_app.add_handler(CallbackQueryHandler(user_subscribe_start, pattern="^user_subscribe$"))
    bot_app.add_handler(CallbackQueryHandler(user_show_donate_menu, pattern="^user_show_donate_menu$"))
    bot_app.add_handler(CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"))

    # Admin log channel actions (non-conversation)
    bot_app.add_handler(CallbackQueryHandler(admin_reject_user, pattern="^admin_reject_"))

    # User Download Flow (Non-conversation)
    bot_app.add_handler(CallbackQueryHandler(download_button_handler, pattern="^dl"))
    
    # Placeholders
    bot_app.add_handler(CallbackQueryHandler(placeholder_button_handler, pattern="^user_check_sub$"))

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
