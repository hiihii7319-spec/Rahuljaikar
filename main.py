import os
import logging
import re
import asyncio # Auto-delete ke liye
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient
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
from flask import Flask
from threading import Thread
from waitress import serve 

# --- Flask Server Setup ---
app = Flask(__name__)
@app.route('/')
def home():
    return "I am alive and running!"
def run_flask():
    port = int(os.environ.get("PORT", 8080))
    serve(app, host="0.0.0.0", port=port)

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
    ADMIN_ID = int(os.getenv("ADMIN_ID")) # Yeh ab OWNER_ID hai
    LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID") 
    if not BOT_TOKEN or not MONGO_URI or not ADMIN_ID or not LOG_CHANNEL_ID:
        logger.error("Error: Secrets missing. BOT_TOKEN, MONGO_URI, ADMIN_ID, aur LOG_CHANNEL_ID check karo.")
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
    co_admins_collection = db['co_admins'] # NAYA: Co-Admins ke liye
    client.admin.command('ping') 
    logger.info("MongoDB se successfully connect ho gaya!")
except Exception as e:
    logger.error(f"MongoDB connection failed: {e}")
    exit()

# --- NAYA: Admin/Auth Check ---
async def is_owner(user_id: int) -> bool:
    """Check if user is the main Owner (ADMIN_ID)"""
    return user_id == ADMIN_ID

async def is_co_admin(user_id: int) -> bool:
    """Check if user is a Co-Admin"""
    return co_admins_collection.find_one({"_id": user_id}) is not None

async def is_authorized(user_id: int) -> bool:
    """Check if user is Owner OR Co-Admin"""
    if await is_owner(user_id):
        return True
    if await is_co_admin(user_id):
        return True
    return False

# --- Config Helper (MAJOR UPDATE: Custom Messages Added) ---
async def get_config():
    """Database se bot config fetch karega"""
    config = config_collection.find_one({"_id": "bot_config"})
    
    # Naye default messages
    default_messages = {
        # General
        "admin_menu_text": "Salaam, Admin Boss! 👑\nAapka control panel taiyyar hai.",
        "co_admin_menu_text": "Salaam, Co-Admin! 🫡\nAapka content panel taiyyar hai.",
        "user_menu_text": "Salaam {user_name}! Ye raha aapka menu:",
        "cancel_generic": "Operation cancel kar diya gaya hai.",
        "cancel_force": "Sabhi operations forcefully cancel kar diye gaye hain.",
        # Subscription
        "sub_pending": "✅ **Screenshot Bhej Diya Gaya!**\n\nAdmin jald hi aapka payment check karke approve kar denge. Intezaar karein.",
        "sub_approved": "🎉 **Congratulations!**\n\nAapka subscription approve ho gaya hai.\nAapka plan {days} din mein expire hoga ({expiry_date}).\n\n/menu se anime download karna shuru karein.",
        "sub_rejected": "❌ **Payment Rejected**\n\nAapka payment screenshot reject kar diya gaya hai. Shayad screenshot galat tha ya clear nahi tha.\n\nKripya /support se contact karein ya dobara try karein.",
        "sub_removed_dm": "ℹ️ Aapka subscription admin ne remove kar diya hai.\n\n/menu se dobara subscribe kar sakte hain.",
        "sub_already_subbed": "✅ Aap pehle se subscribed hain!\n\n/menu dabake anime download karna shuru karein.",
        # Donation
        "donate_text": "❤️ **Support Us!**\n\nAgar aapko hamara kaam pasand aata hai, toh aap humein support kar sakte hain.",
        "donate_thanks": "❤️ Support karne ke liye shukriya!",
        "donate_not_set": "❌ Donation info abhi admin ne set nahi ki hai.",
        # Download Flow
        "dl_check_dm_alert": "✅ Check your DM (private chat) with me!",
        "dl_sub_needed_alert": "❌ Access Denied! Subscribe karne ke liye DM check karein.",
        "dl_sub_needed_dm": "**Subscription Plan**\n\n**Price:** {price}\n**Validity:** {days} days\n\n"
                          "Aapko download karne ke liye subscribe karna hoga.\n\nIs QR code par payment karein aur payment ka **screenshot** "
                          "bhejne ke liye, bot ko DM mein /menu likhein aur 'Subscribe Now' -> 'Upload Screenshot' button dabayein.",
        "dl_select_season": "**{anime_name}**\n\nSeason select karein:",
        "dl_select_episode": "**{anime_name}** | **Season {season_name}**\n\nEpisode select karein:",
        "dl_files_ready": "✅ **{anime_name}** | **S{season_name} - E{ep_num}**\n\n{description}\n\nAapke files neeche aa rahe hain:",
        "dl_file_caption": "🎬 **{anime_name}**\nS{season_name} - E{ep_num} ({quality})",
        "file_warning": "⚠️ **Yeh file {minutes} minute(s) mein automatically delete ho jaayegi.**",
        # Errors
        "err_generic": "❌ Error! Please try again.",
        "err_anime_not_found": "❌ Error: Anime nahi mila.",
        "err_no_seasons": "❌ Error: Is anime ke liye seasons nahi mile.",
        "err_no_episodes": "❌ Error: Is season ke liye episodes nahi mile.",
        "err_file_not_found": "❌ Error: File ID nahi mili.",
        "err_sub_not_set": "❌ **Error!** Subscription system abhi setup nahi hua hai. Admin se baat karein.",
        "err_dm_failed": "❌ Error! Subscribe karne ke liye bot ko DM me /start karein.",
        "err_blocked": "❌ Error! File nahi bhej paya. Aapne bot ko block kiya hua hai.",
        "err_not_admin": "Aap admin nahi hain.",
    }
    
    if not config:
        default_config = {
            "_id": "bot_config", "sub_qr_id": None, "donate_qr_id": None, "price": None, 
            "links": {"backup": None, "support": None}, 
            "validity_days": None,
            "delete_seconds": 300, # NAYA: 5 Minute (300 sec)
            "messages": default_messages
        }
        config_collection.insert_one(default_config)
        return default_config
    
    # Purane users ke liye compatibility
    if "validity_days" not in config: config["validity_days"] = None
    if "delete_seconds" not in config: config["delete_seconds"] = 300 # NAYA: 5 Min
    if "messages" not in config: config["messages"] = {}
    
    # Default messages check
    needs_update = False
    for key, value in default_messages.items():
        if key not in config["messages"]:
            config["messages"][key] = value
            needs_update = True
            
    if needs_update or "delete_seconds" not in config.get("delete_seconds"):
        config_collection.update_one(
            {"_id": "bot_config"}, 
            {"$set": {
                "messages": config["messages"], 
                "delete_seconds": config.get("delete_seconds", 300)
            }}
        )
        
    if "donate" in config.get("links", {}): 
        config_collection.update_one({"_id": "bot_config"}, {"$unset": {"links.donate": ""}})
    return config

# --- Subscription Check Helper ---
async def check_subscription(user_id: int) -> bool:
    """Check if user is subscribed and not expired"""
    if await is_owner(user_id): # NAYA: Owner check
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

# FIX 2: Naya Auto-Delete Function (Job Queue Alternative)
async def delete_message_later(bot, chat_id: int, message_id: int, seconds: int):
    """asyncio.sleep ka use karke message delete karega (Job Queue Alternative)"""
    try:
        await asyncio.sleep(seconds)
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Auto-deleted message {message_id} for user {chat_id} (asyncio.sleep)")
    except Exception as e:
        logger.warning(f"Message (asyncio.sleep) delete karne me error: {e}")

# (Purana Job Queue function, abhi bhi use ho sakta hai agar kahin aur call ho)
async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    """File ko delete karega"""
    job = context.job
    try:
        await context.bot.delete_message(chat_id=job.chat_id, message_id=job.data)
        logger.info(f"Auto-deleted message {job.data} for user {job.chat_id} (Job Queue)")
    except Exception as e:
        logger.warning(f"Message (job_queue) delete karne me error: {e}")


# --- Conversation States ---
(A_GET_NAME, A_GET_POSTER, A_GET_DESC, A_CONFIRM) = range(4)
(S_GET_ANIME, S_GET_NUMBER, S_CONFIRM) = range(4, 7)
# NAYA: ADD EPISODE DESCRIPTION STATE
(E_GET_ANIME, E_GET_SEASON, E_GET_NUMBER, E_GET_EP_DESC, E_GET_480P, E_GET_720P, E_GET_1080P, E_GET_4K) = range(7, 15)
(CS_GET_QR,) = range(15, 16)
(CD_GET_QR,) = range(16, 17)
(CP_GET_PRICE,) = range(17, 18)
(CL_GET_BACKUP, CL_GET_DONATE, CL_GET_SUPPORT) = range(18, 21)
(PG_MENU, PG_GET_ANIME, PG_GET_SEASON, PG_GET_EPISODE, PG_GET_CHAT) = range(21, 26)
(DA_GET_ANIME, DA_CONFIRM) = range(26, 28)
(DS_GET_ANIME, DS_GET_SEASON, DS_CONFIRM) = range(28, 31)
(DE_GET_ANIME, DE_GET_SEASON, DE_GET_EPISODE, DE_CONFIRM) = range(31, 35)
(SUB_GET_SCREENSHOT,) = range(35, 36)
(ADMIN_GET_DAYS,) = range(36, 37)
(CV_GET_DAYS,) = range(37, 38) 
(M_GET_MESSAGE,) = range(38, 39) # NAYA: Generic Message Editor
(CS_GET_DELETE_TIME,) = range(39, 40)
(RS_GET_ID, RS_CONFIRM) = range(40, 42)
# NAYA: Co-Admin States
(CA_MENU, CA_GET_ID, CA_CONFIRM, CR_GET_ID, CR_CONFIRM) = range(42, 47)
# NAYA: Custom Post States
(CP_GET_POSTER, CP_GET_CAPTION, CP_GET_BUTTONS, CP_GET_CHAT, CP_CONFIRM) = range(47, 52)


# --- NAYA: Force Cancel Handler (Stuck Fix) ---
async def force_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Forcefully cancels any active conversation for the user
    and returns them to the appropriate menu.
    """
    user = update.effective_user
    state = context.user_data.get(ConversationHandler.STATE)
    logger.info(f"User {user.id} ne force /cancel use kiya. Current state: {state}")
    
    if context.user_data:
        context.user_data.clear()
        
    config = await get_config()
    msg = config.get("messages", {}).get("cancel_force", "Sabhi operations forcefully cancel kar diye gaye hain.")
    
    if update.message:
        await update.message.reply_text(msg)
    
    # Naya Auth Flow
    if await is_owner(user.id):
        await admin_command(update, context)
    elif await is_co_admin(user.id):
        await admin_command(update, context) # Co-admin menu dikhayega
    else:
        await menu_command(update, context)
        
    return ConversationHandler.END


# --- Common Conversation Fallbacks ---
async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles commands (like /start, /admin) during a conversation.
    It cancels the current operation and lets the new command run.
    """
    user = update.effective_user
    command = update.message.text
    logger.info(f"User {user.id} ne conversation ke beech me command use kiya: {command}")
    
    if context.user_data:
        context.user_data.clear()
        
    config = await get_config()
    msg = config.get("messages", {}).get("cancel_generic", "Operation cancel kar diya gaya hai.")
    
    try:
        await update.message.reply_text(f"{msg} Naya command process ho raha hai...")
    except Exception: pass
    
    return ConversationHandler.END


# NAYA FIX: Back button ke liye user_subscribe_start me naya argument
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
            msg = config.get("messages", {}).get("err_sub_not_set", "❌ **Error!** Subscription system abhi setup nahi hua hai. Admin se baat karein.")
            await query.message.reply_text(msg)
            if not from_conv_cancel:
                  await back_to_user_menu(update, context) 
            return ConversationHandler.END
            
        text = f"**Subscription Plan**\n\n**Price:** {price}\n**Validity:** {days} days\n\n"
        text += "Upar diye gaye QR code par payment karein aur payment ka **screenshot** neeche 'Upload Screenshot' button dabake bhejein."
        
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
                    if "Message is not modified" not in str(e):
                        raise e 
                
        except Exception as e:
            logger.warning(f"user_subscribe_start me edit nahi kar paya, naya bhej raha hoon: {e}")
            try:
                try: await query.message.delete()
                except: pass
                await context.bot.send_photo(chat_id=query.from_user.id, photo=qr_id, caption=text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
            except Exception as e_fail:
                logger.error(f"user_subscribe_start me critical error: {e_fail}")
                await context.bot.send_message(query.from_user.id, "❌ Error! Subscription menu nahi khul paya.")
                return ConversationHandler.END
            
        return ConversationHandler.END 

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
    await menu_command(update, context, from_callback=True)
    return ConversationHandler.END
async def back_to_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await bot_messages_menu(update, context)
    return ConversationHandler.END
async def back_to_co_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await co_admin_settings_menu(update, context)
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
    
    else:
        return A_CONFIRM
        
    return A_CONFIRM
async def save_anime_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() 
    try:
        name = context.user_data['anime_name']
        if animes_collection.find_one({"name": name}):
            await query.edit_message_caption(caption=f"⚠️ **Error:** Ye anime naam '{name}' pehle se hai.")
            return ConversationHandler.END
        
        anime_document = {
            "name": name, 
            "poster_id": context.user_data['anime_poster_id'], 
            "description": context.user_data['anime_desc'], 
            "seasons": {},
            "created_at": datetime.now() 
        }
        animes_collection.insert_one(anime_document)
        await query.edit_message_caption(caption=f"✅ **Success!** '{name}' add ho gaya hai.")
    except Exception as e:
        logger.error(f"Anime save karne me error: {e}")
        await query.edit_message_caption(caption=f"❌ **Error!** Database me save nahi kar paya.")
    context.user_data.clear() 
    return ConversationHandler.END

# --- Conversation: Add Season ---
async def add_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    all_animes = list(animes_collection.find({}, {"name": 1}).sort("created_at", -1))
    if not all_animes:
        await query.edit_message_text("❌ **Error!** Pehle `➕ Add Anime` se anime add karo.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]))
        return ConversationHandler.END
    
    buttons = [InlineKeyboardButton(anime['name'], callback_data=f"season_anime_{anime['name']}") for anime in all_animes]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")])
    
    text = "Aap kis anime mein season add karna chahte hain? (Sabse naya upar hai)"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return S_GET_ANIME
async def get_anime_for_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anime_name = query.data.replace("season_anime_", "")
    context.user_data['anime_name'] = anime_name
    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nAb is season ka **Number ya Naam** bhejo.\n(Jaise: 1, 2, Movie, Mugen Train)\n\n/cancel - Cancel.")
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
    keyboard = [[InlineKeyboardButton("✅ Haan, Save Karo", callback_data="save_season")], [InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]
    await update.message.reply_text(f"**Confirm Karo:**\nAnime: **{anime_name}**\nNaya Season: **{season_name}**\n\nSave kar doon?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return S_CONFIRM
async def save_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        animes_collection.update_one({"name": anime_name}, {"$set": {f"seasons.{season_name}": {}}})
        await query.edit_message_text(f"✅ **Success!**\n**{anime_name}** mein **Season {season_name}** add ho gaya hai.")
    except Exception as e:
        logger.error(f"Season save karne me error: {e}")
        await query.edit_message_text(f"❌ **Error!** Database me save nahi kar paya.")
    context.user_data.clear()
    return ConversationHandler.END

# --- NAYA FLOW: Conversation: Add Episode (Multi-Quality + Description) ---
async def add_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    all_animes = list(animes_collection.find({}, {"name": 1}).sort("created_at", -1))
    if not all_animes:
        await query.edit_message_text("❌ **Error!** Pehle `➕ Add Anime` se anime add karo.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")]]))
        return ConversationHandler.END
    
    buttons = [InlineKeyboardButton(anime['name'], callback_data=f"ep_anime_{anime['name']}") for anime in all_animes]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")])
    text = "Aap kis anime mein episode add karna chahte hain? (Sabse naya upar hai)"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
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
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_add_content")])
    
    await query.edit_message_text(f"Aapne **{anime_name}** select kiya hai.\n\nAb **Season** select karein:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return E_GET_SEASON

async def get_season_for_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    season_name = query.data.replace("ep_season_", "")
    context.user_data['season_name'] = season_name
    await query.edit_message_text(f"Aapne **Season {season_name}** select kiya hai.\n\nAb **Episode Number** bhejo.\n(Jaise: 1, 2, Full Movie)\n\n/cancel - Cancel.")
    return E_GET_NUMBER

async def _save_episode_file_helper(update: Update, context: ContextTypes.DEFAULT_TYPE, quality: str):
    """Helper function to save file ID and description to DB"""
    file_id = None
    if update.message.video: file_id = update.message.video.file_id
    elif update.message.document and (update.message.document.mime_type and update.message.document.mime_type.startswith('video')): file_id = update.message.document.file_id
    
    if not file_id:
        if update.message.text and update.message.text.startswith('/'):
            return False
        await update.message.reply_text("Ye video file nahi hai. Please dobara video file bhejein ya /skip karein.")
        return False # Failed

    try:
        anime_name = context.user_data['anime_name']
        season_name = context.user_data['season_name']
        ep_num = context.user_data['ep_num']
        
        dot_notation_key = f"seasons.{season_name}.{ep_num}.{quality}"
        
        # NAYA: Description ko $set payload me add karo (sirf ek baar)
        update_payload = {"$set": {dot_notation_key: file_id}}
        if 'ep_desc' in context.user_data:
            desc_key = f"seasons.{season_name}.{ep_num}.description"
            update_payload["$set"][desc_key] = context.user_data.pop('ep_desc') # Use karo aur remove karo
            
        animes_collection.update_one({"name": anime_name}, update_payload)
        
        logger.info(f"Naya episode save ho gaya: {anime_name} S{season_name} E{ep_num} {quality}")
        await update.message.reply_text(f"✅ **{quality}** save ho gaya.")
        return True # Success
    except Exception as e:
        logger.error(f"Episode file save karne me error: {e}")
        await update.message.reply_text(f"❌ **Error!** {quality} save nahi kar paya. Logs check karein.")
        return False # Failed

# Naya function
async def get_episode_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_num'] = update.message.text
    
    anime_name = context.user_data['anime_name']
    season_name = context.user_data['season_name']
    ep_num = context.user_data['ep_num']
    
    anime_doc = animes_collection.find_one({"name": anime_name})
    if anime_doc.get("seasons", {}).get(season_name, {}).get(ep_num):
        await update.message.reply_text(f"⚠️ **Error!** '{anime_name}' - Season {season_name} - Episode {ep_num} pehle se maujood hai. Please pehle isse delete karein ya koi doosra episode number dein.\n\n/cancel - Cancel.")
        return E_GET_NUMBER

    # NAYA STEP: Description Maango
    await update.message.reply_text(f"Aapne **Episode {ep_num}** select kiya hai.\n\n"
                                      "Ab is episode/movie ke liye ek **Description** bhejein (Optional).\n"
                                      "Ye description user ko download se pehle dikhega.\n\n"
                                      "Ya /skip type karein.", 
                                      parse_mode='Markdown')
    return E_GET_EP_DESC

# NAYA STATE
async def get_episode_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_desc'] = update.message.text
    await update.message.reply_text("✅ Description save ho gaya.\n\n"
                                      "Ab **480p** quality ki video file bhejein.\n"
                                      "Ya /skip type karein.", 
                                      parse_mode='Markdown')
    return E_GET_480P

# NAYA STATE
async def skip_episode_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['ep_desc'] = "" # Khali save karo (ya None)
    await update.message.reply_text("✅ Description skip kar diya.\n\n"
                                      "Ab **480p** quality ki video file bhejein.\n"
                                      "Ya /skip type karein.", 
                                      parse_mode='Markdown')
    return E_GET_480P

# Naye handlers
async def get_480p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _save_episode_file_helper(update, context, "480p")
    await update.message.reply_text("Ab **720p** quality ki video file bhejein.\nYa /skip type karein.", parse_mode='Markdown')
    return E_GET_720P

async def skip_480p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 480p skip kar diya.\n\n"
                                      "Ab **720p** quality ki video file bhejein.\n"
                                      "Ya /skip type karein.", parse_mode='Markdown')
    return E_GET_720P

async def get_720p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _save_episode_file_helper(update, context, "720p")
    await update.message.reply_text("Ab **1080p** quality ki video file bhejein.\nYa /skip type karein.", parse_mode='Markdown')
    return E_GET_1080P

async def skip_720p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 720p skip kar diya.\n\n"
                                      "Ab **1080p** quality ki video file bhejein.\n"
                                      "Ya /skip type karein.", parse_mode='Markdown')
    return E_GET_1080P

async def get_1080p_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _save_episode_file_helper(update, context, "1080p")
    await update.message.reply_text("Ab **4K** quality ki video file bhejein.\nYa /skip type karein.", parse_mode='Markdown')
    return E_GET_4K

async def skip_1080p(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 1080p skip kar diya.\n\n"
                                         "Ab **4K** quality ki video file bhejein.\n"
                                         "Ya /skip type karein.", parse_mode='Markdown')
    return E_GET_4K

async def get_4k_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _save_episode_file_helper(update, context, "4K")
    await update.message.reply_text("✅ **Success!** Saari qualities save ho gayi hain.", parse_mode='Markdown')
    context.user_data.clear()
    return ConversationHandler.END

async def skip_4k(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 4K skip kar diya.\n\n"
                                         "✅ **Success!** Episode save ho gaya hai.", parse_mode='Markdown')
    context.user_data.clear()
    return ConversationHandler.END
# --- End of Naya "Add Episode" Flow ---


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
    # NAYA BUG FIX: Clear user_data to prevent state collision
    context.user_data.clear() 
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
    text += "Naya time **seconds** mein bhejo.\n(Example: `300` for 5 minutes, `600` for 10 minutes)\n\n/cancel - Cancel."
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
        await update.message.reply_text("Yeh number nahi hai. Please sirf seconds bhejein (jaise 300) ya /cancel karein.")
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

# --- NAYA: Conversation: Set Custom Messages (Generic) ---
async def set_msg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic function to start message editing"""
    query = update.callback_query
    await query.answer()
    msg_key = query.data.replace("msg_", "")
    
    # Message titles
    titles = {
        "admin_menu_text": "Admin Menu Text",
        "co_admin_menu_text": "Co-Admin Menu Text",
        "user_menu_text": "User Menu Text (Use {user_name})",
        "cancel_generic": "Cancel Generic Text",
        "cancel_force": "Force Cancel Text",
        "sub_pending": "Subscription Pending",
        "sub_approved": "Subscription Approved (Use {days}, {expiry_date})",
        "sub_rejected": "Subscription Rejected",
        "sub_removed_dm": "Subscription Removed (DM to user)",
        "sub_already_subbed": "Already Subscribed (DM)",
        "donate_text": "Donate QR Caption",
        "donate_thanks": "Donate Thank You (DM)",
        "donate_not_set": "Donate Not Set (Alert)",
        "dl_check_dm_alert": "Download: Check DM (Alert)",
        "dl_sub_needed_alert": "Download: Sub Needed (Alert)",
        "dl_sub_needed_dm": "Download: Sub Needed (DM) (Use {price}, {days})",
        "dl_select_season": "Download: Select Season (Use {anime_name})",
        "dl_select_episode": "Download: Select Episode (Use {anime_name}, {season_name})",
        "dl_files_ready": "Download: Files Ready (Use {anime_name}, {season_name}, {ep_num}, {description})",
        "dl_file_caption": "Download: File Caption (Use {anime_name}, {season_name}, {ep_num}, {quality})",
        "file_warning": "File Auto-Delete Warning (Use {minutes})",
        "err_generic": "Error: Generic",
        "err_anime_not_found": "Error: Anime Not Found",
        "err_no_seasons": "Error: No Seasons",
        "err_no_episodes": "Error: No Episodes",
        "err_file_not_found": "Error: File Not Found",
        "err_sub_not_set": "Error: Subscription Not Set",
        "err_dm_failed": "Error: DM Failed (Alert)",
        "err_blocked": "Error: Bot Blocked (DM)",
        "err_not_admin": "Error: Not Admin",
    }
    
    if msg_key not in titles:
        await query.answer("Error: Invalid message key!", show_alert=True)
        return ConversationHandler.END

    context.user_data['msg_key'] = msg_key
    
    config = await get_config()
    current_msg = config.get("messages", {}).get(msg_key, "N/A")
    
    text = f"**Current Message ({titles[msg_key]}):**\n`{current_msg}`\n\n"
    text += f"Naya **{titles[msg_key].split('(')[0].strip()}** message bhejo.\n\n/cancel - Cancel."
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_messages")]]))
    
    return M_GET_MESSAGE

async def set_msg_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic function to save edited message"""
    try:
        msg_text = update.message.text
        msg_key = context.user_data['msg_key']
        
        config_collection.update_one({"_id": "bot_config"}, {"$set": {f"messages.{msg_key}": msg_text}}, upsert=True)
        logger.info(f"{msg_key} message update ho gaya: {msg_text}")
        await update.message.reply_text(f"✅ **Success!** Naya '{msg_key}' message set ho gaya hai.")
        
        await bot_messages_menu(update, context)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Message save karne me error: {e}")
        await update.message.reply_text("❌ Error! Save nahi kar paya.")
        context.user_data.clear()
        return ConversationHandler.END
    
# --- Conversation: Post Generator ---
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
    all_animes = list(animes_collection.find({}, {"name": 1}).sort("created_at", -1))
    if not all_animes:
        await query.edit_message_text("❌ **Error!** Database mein koi anime nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
    buttons = [InlineKeyboardButton(anime['name'], callback_data=f"post_anime_{anime['name']}") for anime in all_animes]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")])
    await query.edit_message_text("Kaunsa **Anime** select karna hai? (Sabse naya upar hai)", reply_markup=InlineKeyboardMarkup(keyboard))
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
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")])
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
    if not episodes:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' - Season {season_name} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episodes.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"post_ep_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")])
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
        
        if ep_num:
            # Episode Post
            caption = f"✨ **Episode {ep_num} Added** ✨\n\n🎬 **Anime:** {anime_name}\n➡️ **Season:** {season_name}\n\nNeeche [Download] button dabake download karein!"
            poster_id = anime_doc['poster_id']
        else:
            # Season Post
            caption = f"✅ **{anime_name}**\n"
            if season_name: caption += f"**[ S{season_name} ]**\n\n"
            if anime_doc.get('description'): caption += f"**📖 Synopsis:**\n{anime_doc['description']}\n\n"
            caption += "Neeche [Download] button dabake download karein!"
            poster_id = anime_doc['poster_id']
        
        links = config.get('links', {})
        
        dl_callback_data = f"dl_{anime_name}"
        
        donate_url = f"https://t.me/{bot_username}?start=donate" 
        subscribe_url = f"https://t.me/{bot_username}?start=subscribe"
        
        backup_url = links.get('backup')
        if not backup_url or not backup_url.startswith(("http", "t.me")):
            backup_url = "https://t.me/" 
        
        support_url = links.get('support')
        if not support_url or not support_url.startswith(("http", "t.me")):
            support_url = "https://t.me/"
            
        btn_backup = InlineKeyboardButton("Backup", url=backup_url)
        btn_donate = InlineKeyboardButton("Donate", url=donate_url)
        btn_support = InlineKeyboardButton("Support", url=support_url)
        
        btn_download = InlineKeyboardButton("Download", callback_data=dl_callback_data) 
        btn_subscribe = InlineKeyboardButton("Subscribe Now", url=subscribe_url)
        
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
    try:
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

# --- NAYA: Conversation: Custom Post Generator ---
async def custom_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['buttons'] = [] # Button list initialize karo
    await query.edit_message_text("📢 **Custom Post Generator** 📢\n\nSabse pehle, **Poster (Photo)** bhejo.\n\n/cancel - Cancel.")
    return CP_GET_POSTER

async def cp_get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek photo bhejo.")
        return CP_GET_POSTER 
    context.user_data['poster_id'] = update.message.photo[-1].file_id
    await update.message.reply_text("Poster mil gaya! Ab **Caption** bhejo.\n\n/skip ya /cancel.")
    return CP_GET_CAPTION

async def cp_get_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['caption'] = update.message.text
    await update.message.reply_text("Caption save ho gaya.\n\nAb buttons add karein.\nFormat: `Button Text - https://link.com`\n\nEk line mein ek hi button bhejein.\nJab ho jaaye, tab /done type karein.\n\n/cancel - Cancel.")
    return CP_GET_BUTTONS

async def cp_skip_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['caption'] = ""
    await update.message.reply_text("Caption skip kar diya.\n\nAb buttons add karein.\nFormat: `Button Text - https://link.com`\n\nEk line mein ek hi button bhejein.\nJab ho jaaye, tab /done type karein.\n\n/cancel - Cancel.")
    return CP_GET_BUTTONS

async def cp_get_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if " - " not in text:
        await update.message.reply_text("❌ Galat format. Format hai: `Button Text - https://link.com`\n\nDobara try karein ya /done type karein.")
        return CP_GET_BUTTONS
        
    try:
        btn_text, btn_url = text.split(" - ", 1)
        if not btn_url.startswith(("http", "t.me")):
             await update.message.reply_text("❌ Link galat hai. Link `http://` ya `https://` se shuru hona chahiye.\n\nDobara try karein.")
             return CP_GET_BUTTONS
             
        context.user_data['buttons'].append(InlineKeyboardButton(btn_text.strip(), url=btn_url.strip()))
        await update.message.reply_text(f"✅ Button '{btn_text}' add ho gaya.\n\nAur buttons add karein ya /done type karein.")
    except Exception as e:
        logger.warning(f"Custom button parse error: {e}")
        await update.message.reply_text("❌ Error. Format: `Button Text - https://link.com`\n\nDobara try karein ya /done type karein.")
        
    return CP_GET_BUTTONS

async def cp_done_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poster_id = context.user_data['poster_id']
    caption = context.user_data.get('caption', '')
    buttons = context.user_data['buttons']
    
    keyboard = build_grid_keyboard(buttons, 2) # 2x2 grid me dikhao
    
    await update.message.reply_text("✅ Buttons add ho gaye.\n\n**POST PREVIEW:**")
    await update.message.reply_photo(
        photo=poster_id,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )
    
    await update.message.reply_text(
        "Post sahi hai?\n\nAb uss **Channel ka @username** ya **Group/Channel ki Chat ID** bhejo jahaan ye post karna hai.\n"
        "(Example: @MyAnimeChannel ya -100123456789)\n\n/cancel - Cancel."
    )
    return CP_GET_CHAT

async def cp_send_to_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.text
    try:
        poster_id = context.user_data['poster_id']
        caption = context.user_data.get('caption', '')
        buttons = context.user_data['buttons']
        keyboard = InlineKeyboardMarkup(build_grid_keyboard(buttons, 2)) if buttons else None
        
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=poster_id,
            caption=caption,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        await update.message.reply_text(f"✅ **Success!**\nCustom Post ko '{chat_id}' par bhej diya gaya hai.")
    except Exception as e:
        logger.error(f"Custom post channel me bhejme me error: {e}")
        await update.message.reply_text(f"❌ **Error!**\nPost '{chat_id}' par nahi bhej paya. Check karo ki bot uss channel me admin hai ya ID sahi hai.\nError: {e}")
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: Delete Anime ---
async def delete_anime_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    all_animes = list(animes_collection.find({}, {"name": 1}).sort("created_at", -1))
    if not all_animes:
        await query.edit_message_text("❌ **Error!** Database mein koi anime nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    buttons = [InlineKeyboardButton(anime['name'], callback_data=f"del_anime_{anime['name']}") for anime in all_animes]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")])
    await query.edit_message_text("Kaunsa **Anime** delete karna hai? (Sabse naya upar hai)", reply_markup=InlineKeyboardMarkup(keyboard))
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
    return ConversationHandler.END

# --- Conversation: Delete Season ---
async def delete_season_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    all_animes = list(animes_collection.find({}, {"name": 1}).sort("created_at", -1))
    if not all_animes:
        await query.edit_message_text("❌ **Error!** Database mein koi anime nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    buttons = [InlineKeyboardButton(anime['name'], callback_data=f"del_season_anime_{anime['name']}") for anime in all_animes]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")])
    await query.edit_message_text("Kaunse **Anime** ka season delete karna hai? (Sabse naya upar hai)", reply_markup=InlineKeyboardMarkup(keyboard))
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
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")])
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
    return ConversationHandler.END

# --- NAYA FEATURE: Conversation: Delete Episode ---
async def delete_episode_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    all_animes = list(animes_collection.find({}, {"name": 1}).sort("created_at", -1))
    if not all_animes:
        await query.edit_message_text("❌ **Error!** Database mein koi anime nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    buttons = [InlineKeyboardButton(anime['name'], callback_data=f"del_ep_anime_{anime['name']}") for anime in all_animes]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")])
    await query.edit_message_text("Kaunse **Anime** ka episode delete karna hai? (Sabse naya upar hai)", reply_markup=InlineKeyboardMarkup(keyboard))
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
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")])
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
    if not episodes:
        await query.edit_message_text(f"❌ **Error!** '{anime_name}' - Season {season_name} mein koi episode nahi hai.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")]]))
        return ConversationHandler.END
    sorted_eps = sorted(episodes.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
    buttons = [InlineKeyboardButton(f"Episode {ep}", callback_data=f"del_ep_num_{ep}") for ep in sorted_eps]
    keyboard = build_grid_keyboard(buttons, 2)
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_manage")])
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
    return ConversationHandler.END

# --- NAYA FEATURE: Conversation: Remove Subscription ---
async def remove_sub_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # NAYA BUG FIX: Clear user_data to prevent state collision
    context.user_data.clear()
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Aap kis user ka subscription remove karna chahte hain?\n\nUs user ki **Telegram User ID** bhejein.\n\n/cancel - Cancel.")
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
    
    keyboard = [[InlineKeyboardButton(f"✅ Haan, {user_id} ka Subscription Remove Karo", callback_data="remove_sub_confirm_yes")], [InlineKeyboardButton("⬅️ Back", callback_data="admin_menu")]]
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
            msg = config.get("messages", {}).get("sub_removed_dm", "ℹ️ Aapka subscription admin ne remove kar diya hai.\n\n/menu se dobara subscribe kar sakte hain.")
            await context.bot.send_message(user_id, msg)
        except Exception as e:
            logger.warning(f"User {user_id} ko removal notification bhejte waqt error: {e}")

    except Exception as e:
        logger.error(f"Subscription remove karne me error: {e}")
        await query.edit_message_text("❌ **Error!** Subscription remove nahi ho paya.")
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Conversation: User Subscription ---
async def user_upload_ss_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Kripya apna payment screenshot yahan bhejein.\n\n/cancel - Cancel.")
    return SUB_GET_SCREENSHOT
    
async def user_get_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("Ye photo nahi hai. Please ek screenshot photo bhejein ya /cancel karein.")
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
        msg = config.get("messages", {}).get("sub_pending", "✅ Screenshot Bhej Diya Gaya! Admin jald hi approve kar denge.")
        await update.message.reply_text(msg, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Log channel me screenshot bhejte waqt error: {e}")
        await update.message.reply_text("❌ **Error!** Admin tak screenshot nahi bhej paya. Kripya /support se contact karein.")
        
    return ConversationHandler.END
    
async def activate_subscription(context: ContextTypes.DEFAULT_TYPE, user_id: int, days: int, admin_user_name: str, original_message=None):
    """User ko subscribe karega aur sabko inform karega (Notification Fix)"""
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
        msg_template = config.get("messages", {}).get("sub_approved", "🎉 **Congratulations!**\nAapka subscription approve ho gaya hai.\nAapka plan {days} din mein expire hoga ({expiry_date}).")
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
    
    if not await is_owner(query.from_user.id): # NAYA: Sirf Owner
        await query.answer("Aap Owner nahi hain!", show_alert=True)
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
    
    if not await is_owner(query.from_user.id): # NAYA: Sirf Owner
        await query.answer("Aap Owner nahi hain!", show_alert=True)
        return
        
    user_dm_success = False 
    try:
        user_id_to_reject = int(query.data.split("_")[-1])
        user_info = users_collection.find_one({"_id": user_id_to_reject}) 
        
        try:
            config = await get_config()
            msg = config.get("messages", {}).get("sub_rejected", "❌ **Payment Rejected**\n\nAapka payment screenshot reject kar diya gaya hai.")
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

# --- NAYA: Co-Admin Management ---
async def co_admin_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    text = "🛠️ **Co-Admin Settings** 🛠️\n\nAap yahan Co-Admins ko manage kar sakte hain. Co-Admins sirf content add/manage kar sakte hain."
    keyboard = [
        [InlineKeyboardButton("➕ Add Co-Admin", callback_data="co_admin_add")],
        [InlineKeyboardButton("🚫 Remove Co-Admin", callback_data="co_admin_remove")],
        [InlineKeyboardButton("👥 List Co-Admins", callback_data="co_admin_list")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    return CA_MENU

async def co_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    co_admins = list(co_admins_collection.find({}))
    if not co_admins:
        await query.edit_message_text("Abhi koi Co-Admin nahi hai.\n\n"
                                      "⬅️ Back", 
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_co_admin")]]))
        return CA_MENU

    text = "ℹ️ **Current Co-Admins:**\n\n"
    for admin in co_admins:
        text += f"- ` {admin['_id']} ` (Added on: {admin.get('added_on', 'N/A')})\n"
        
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_co_admin")]]))
    return CA_MENU

async def co_admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Naye Co-Admin ki **Telegram User ID** bhejein.\n\n/cancel - Cancel.",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_co_admin")]]))
    return CA_GET_ID

async def co_admin_add_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text)
        if user_id == ADMIN_ID:
            await update.message.reply_text("Aap Owner ko Co-Admin nahi bana sakte.")
            return CA_GET_ID
            
        if await is_co_admin(user_id):
            await update.message.reply_text("Ye user pehle se Co-Admin hai.")
            return CA_GET_ID
        
        co_admins_collection.insert_one({
            "_id": user_id,
            "added_by": update.from_user.id,
            "added_on": datetime.now().strftime('%Y-%m-%d')
        })
        
        await update.message.reply_text(f"✅ **Success!** User ID `{user_id}` ab Co-Admin hai.")
        logger.info(f"User {user_id} ko Co-Admin banaya gaya by {update.from_user.id}")
        
    except ValueError:
        await update.message.reply_text("Yeh valid User ID nahi hai. Please sirf number bhejein.")
        return CA_GET_ID
    except Exception as e:
        logger.error(f"Co-Admin add karte waqt error: {e}")
        await update.message.reply_text("❌ Error! Co-Admin add nahi kar paya.")
        
    await co_admin_settings_menu(update, context)
    return ConversationHandler.END

async def co_admin_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    co_admins = list(co_admins_collection.find({}))
    if not co_admins:
        await query.edit_message_text("Abhi koi Co-Admin nahi hai remove karne ke liye.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_to_co_admin")]]))
        return ConversationHandler.END

    buttons = []
    for admin in co_admins:
        buttons.append(InlineKeyboardButton(f"🚫 Remove {admin['_id']}", callback_data=f"co_remove_{admin['_id']}"))
    
    keyboard = build_grid_keyboard(buttons, 1) # List me dikhao
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="back_to_co_admin")])
    
    await query.edit_message_text("Aap kis Co-Admin ko remove karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
    return CR_GET_ID

async def co_admin_remove_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Removing...")
    
    try:
        user_id_to_remove = int(query.data.replace("co_remove_", ""))
        co_admins_collection.delete_one({"_id": user_id_to_remove})
        
        await query.edit_message_text(f"✅ **Success!** User ID `{user_id_to_remove}` ab Co-Admin nahi hai.")
        logger.info(f"User {user_id_to_remove} ko Co-Admin se hataya gaya by {query.from_user.id}")
        
    except Exception as e:
        logger.error(f"Co-Admin remove karte waqt error: {e}")
        await query.edit_message_text("❌ Error! Remove nahi kar paya.")
        
    await co_admin_settings_menu(update, context)
    return ConversationHandler.END
        
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
    
async def manage_content_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🗑️ Delete Anime", callback_data="admin_del_anime")],
        [InlineKeyboardButton("🗑️ Delete Season", callback_data="admin_del_season")],
        [InlineKeyboardButton("🗑️ Delete Episode", callback_data="admin_del_episode")], # NAYA
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    await query.edit_message_text("✏️ **Manage Content** ✏️\n\nAap kya manage karna chahte hain?", reply_markup=InlineKeyboardMarkup(keyboard))
    
async def sub_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    config = await get_config()
    sub_qr_status = "✅" if config.get('sub_qr_id') else "❌"
    price_status = "✅" if config.get('price') else "❌"
    days_val = config.get('validity_days')
    days_status = f"✅ ({days_val} days)" if days_val else "❌"
    delete_seconds = config.get("delete_seconds", 300) # NAYA: 300
    delete_status = f"✅ ({delete_seconds // 60} min)"
    
    keyboard = [
        [InlineKeyboardButton(f"Set Subscription QR {sub_qr_status}", callback_data="admin_set_sub_qr")],
        [InlineKeyboardButton(f"Set Price Text {price_status}", callback_data="admin_set_price")],
        [InlineKeyboardButton(f"Set Validity Days {days_status}", callback_data="admin_set_days")],
        [InlineKeyboardButton(f"Set Auto-Delete Time {delete_status}", callback_data="admin_set_delete_time")],
        [InlineKeyboardButton("🚫 Remove Subscription", callback_data="admin_remove_sub")], # NAYA
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

async def bot_messages_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    
    text = "⚙️ **Bot Messages** ⚙️\n\nAap bot ke replies ko yahan edit kar sakte hain."
    
    keyboard = [
        [InlineKeyboardButton("General Messages", callback_data="msg_page_general")],
        [InlineKeyboardButton("Subscription Messages", callback_data="msg_page_sub")],
        [InlineKeyboardButton("Download Flow Messages", callback_data="msg_page_dl")],
        [InlineKeyboardButton("Error Messages", callback_data="msg_page_err")],
        [InlineKeyboardButton("⬅️ Back to Admin Menu", callback_data="admin_menu")]
    ]
    
    page_data = query.data if query else None
    
    if page_data == "msg_page_general":
        text += "\n\n**General Messages:**"
        keyboard = [
            [InlineKeyboardButton("Edit Admin Menu Text", callback_data="msg_admin_menu_text")],
            [InlineKeyboardButton("Edit Co-Admin Menu Text", callback_data="msg_co_admin_menu_text")],
            [InlineKeyboardButton("Edit User Menu Text", callback_data="msg_user_menu_text")],
            [InlineKeyboardButton("Edit Donate QR Caption", callback_data="msg_donate_text")],
            [InlineKeyboardButton("Edit Donate Thanks Msg", callback_data="msg_donate_thanks")],
            [InlineKeyboardButton("Edit Cancel Generic Msg", callback_data="msg_cancel_generic")],
            [InlineKeyboardButton("Edit Force Cancel Msg", callback_data="msg_cancel_force")],
            [InlineKeyboardButton("⬅️ Back to Msg Menu", callback_data="back_to_messages_main")]
        ]
    elif page_data == "msg_page_sub":
        text += "\n\n**Subscription Messages:**"
        keyboard = [
            [InlineKeyboardButton("Edit Sub Pending Msg", callback_data="msg_sub_pending")],
            [InlineKeyboardButton("Edit Sub Approved Msg", callback_data="msg_sub_approved")],
            [InlineKeyboardButton("Edit Sub Rejected Msg", callback_data="msg_sub_rejected")],
            [InlineKeyboardButton("Edit Sub Removed DM", callback_data="msg_sub_removed_dm")],
            [InlineKeyboardButton("Edit Already Subbed DM", callback_data="msg_sub_already_subbed")],
            [InlineKeyboardButton("⬅️ Back to Msg Menu", callback_data="back_to_messages_main")]
        ]
    elif page_data == "msg_page_dl":
        text += "\n\n**Download Flow Messages:**"
        keyboard = [
            [InlineKeyboardButton("Edit Check DM Alert", callback_data="msg_dl_check_dm_alert")],
            [InlineKeyboardButton("Edit Sub Needed Alert", callback_data="msg_dl_sub_needed_alert")],
            [InlineKeyboardButton("Edit Sub Needed DM", callback_data="msg_dl_sub_needed_dm")],
            [InlineKeyboardButton("Edit Select Season Msg", callback_data="msg_dl_select_season")],
            [InlineKeyboardButton("Edit Select Episode Msg", callback_data="msg_dl_select_episode")],
            [InlineKeyboardButton("Edit Files Ready Msg", callback_data="msg_dl_files_ready")],
            [InlineKeyboardButton("Edit File Caption", callback_data="msg_dl_file_caption")],
            [InlineKeyboardButton("Edit File Warning Msg", callback_data="msg_file_warning")],
            [InlineKeyboardButton("⬅️ Back to Msg Menu", callback_data="back_to_messages_main")]
        ]
    elif page_data == "msg_page_err":
        text += "\n\n**Error Messages:**"
        keyboard = [
            [InlineKeyboardButton("Edit Generic Error", callback_data="msg_err_generic")],
            [InlineKeyboardButton("Edit Anime Not Found", callback_data="msg_err_anime_not_found")],
            [InlineKeyboardButton("Edit No Seasons", callback_data="msg_err_no_seasons")],
            [InlineKeyboardButton("Edit No Episodes", callback_data="msg_err_no_episodes")],
            [InlineKeyboardButton("Edit File Not Found", callback_data="msg_err_file_not_found")],
            [InlineKeyboardButton("Edit Sub Not Set", callback_data="msg_err_sub_not_set")],
            [InlineKeyboardButton("Edit DM Failed Alert", callback_data="msg_err_dm_failed")],
            [InlineKeyboardButton("Edit Bot Blocked DM", callback_data="msg_err_blocked")],
            [InlineKeyboardButton("Edit Not Admin", callback_data="msg_err_not_admin")],
            [InlineKeyboardButton("⬅️ Back to Msg Menu", callback_data="back_to_messages_main")]
        ]
    
    if query: 
        if query.message.photo:
            await query.message.delete()
            await context.bot.send_message(query.from_user.id, text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else: 
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
# --- User Handlers ---

# NAYA: Yeh function ab sirf "Donate" URL se /start ko handle karega
async def handle_deep_link_donate(user: User, context: ContextTypes.DEFAULT_TYPE):
    """Deep link se /start=donate ko handle karega"""
    logger.info(f"User {user.id} ne Donate deep link use kiya.")
    try:
        config = await get_config()
        qr_id = config.get('donate_qr_id')
        messages = config.get("messages", {})
        
        if not qr_id: 
            await context.bot.send_message(user.id, messages.get("donate_not_set", "❌ Donation info abhi admin ne set nahi ki hai."))
            return

        text = messages.get("donate_text", "❤️ **Support Us!**")
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

# ===== NAYA CHANGE: SUBSCRIBE DEEP LINK =====
async def handle_deep_link_subscribe(user: User, context: ContextTypes.DEFAULT_TYPE):
    """Deep link se /start=subscribe ko handle karega"""
    logger.info(f"User {user.id} ne Subscribe deep link use kiya.")
    config = await get_config()
    messages = config.get("messages", {})
    
    # 1. Check if already subscribed
    if await check_subscription(user.id):
        msg = messages.get("sub_already_subbed", "✅ Aap pehle se subscribed hain!")
        await context.bot.send_message(user.id, msg)
        return

    # 2. Not subscribed, show the QR code
    try:
        qr_id = config.get('sub_qr_id')
        price = config.get('price')
        days = config.get('validity_days')
        
        if not qr_id or not price or not days:
            msg = messages.get("err_sub_not_set", "❌ **Error!** Subscription system abhi setup nahi hua hai.")
            await context.bot.send_message(user.id, msg)
            return
            
        text = f"**Subscription Plan**\n\n**Price:** {price}\n**Validity:** {days} days\n\n"
        text += "Upar diye gaye QR code par payment karein aur payment ka **screenshot** neeche 'Upload Screenshot' button dabake bhejein."
        
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

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Smart /start command (Deep link sirf Donate ke liye)"""
    user = update.effective_user
    user_id, first_name = user.id, user.first_name
    logger.info(f"User {user_id} ({first_name}) ne /start dabaya.")
    
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
        payload = args[0]
        logger.info(f"User {user_id} ne deep link use kiya: {payload}")
        
        if payload == "donate":
            await handle_deep_link_donate(user, context)
        elif payload == "subscribe": # Naya handler
            await handle_deep_link_subscribe(user, context)
            
        return 
    
    # NAYA Auth Flow
    if await is_authorized(user_id):
        logger.info("Admin/Co-Admin detected. Admin panel dikha raha hoon.")
        await admin_command(update, context) 
    else:
        logger.info("User detected. User menu dikha raha hoon.")
        await menu_command(update, context) 

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
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
            sub_text = "✅ Subscribed (Permanent)"
        sub_cb = "user_check_sub" 
    else:
        sub_text = "💰 Subscribe Now"
        sub_cb = "user_subscribe" 
    
    backup_url = links.get('backup')
    if not backup_url or not backup_url.startswith(("http", "t.me")):
        backup_url = "https://t.me/" 
    
    support_url = links.get('support')
    if not support_url or not support_url.startswith(("http", "t.me")):
        support_url = "https://t.me/"
        
    btn_backup = InlineKeyboardButton("Backup", url=backup_url)
    btn_donate = InlineKeyboardButton("Donate", callback_data="user_show_donate_menu")
    btn_support = InlineKeyboardButton("Support", url=support_url)
    
    btn_sub = InlineKeyboardButton(sub_text, callback_data=sub_cb)
    keyboard = [[btn_sub], [btn_backup, btn_donate], [btn_support]]
    
    menu_text = config.get("messages", {}).get("user_menu_text", "Salaam {user_name}! Ye raha aapka menu:")
    menu_text = menu_text.replace("{user_name}", user.first_name)
    
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
    messages = config.get("messages", {})
    qr_id = config.get('donate_qr_id')
    
    if not qr_id: 
        await query.answer(messages.get("donate_not_set", "❌ Donation info abhi admin ne set nahi ki hai."), show_alert=True)
        return

    text = messages.get("donate_text", "❤️ **Support Us!**")
    
    try:
        keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="user_back_menu")]]
        await query.message.reply_photo(
            photo=qr_id,
            caption=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        await query.message.delete() # Purana /menu delete karo
        await query.answer()

        context.job_queue.run_once(send_donate_thank_you, 60, chat_id=query.from_user.id)

    except Exception as e:
        logger.error(f"Donate QR bhejte waqt error: {e}")
        await query.answer(messages.get("err_generic", "❌ Error! Please try again."), show_alert=True)


# --- Admin Panel ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback: bool = False):
    """Admin panel ka main menu (NAYA: Owner vs Co-Admin)"""
    user_id = update.effective_user.id
    config = await get_config()
    messages = config.get("messages", {})
    
    if not await is_authorized(user_id):
        if not from_callback: 
            msg = messages.get("err_not_admin", "Aap admin nahi hain.")
            if update.message:
                await update.message.reply_text(msg)
            else:
                await update.callback_query.answer(msg, show_alert=True)
        return
        
    logger.info("Admin/Co-Admin ne /admin command use kiya.")
    
    is_bot_owner = await is_owner(user_id) # Check if Owner
    
    try:
        log_chat = await context.bot.get_chat(LOG_CHANNEL_ID)
        if log_chat.username:
             log_url = f"https{':'*2}//t.me/{log_chat.username}"
        else:
            log_url = log_chat.invite_link or f"https{':'*2}//t.me/c/{str(LOG_CHANNEL_ID).replace('-100', '')}"
    except Exception as e:
        logger.error(f"Log channel ({LOG_CHANNEL_ID}) fetch nahi kar paya: {e}")
        log_url = "https://t.me/"

    # Buttons define karo
    btn_add = InlineKeyboardButton("➕ Add Content", callback_data="admin_menu_add_content")
    btn_manage = InlineKeyboardButton("✏️ Manage Content", callback_data="admin_menu_manage_content")
    btn_post = InlineKeyboardButton("✍️ Post Generator", callback_data="admin_post_gen")
    btn_sub_settings = InlineKeyboardButton("💲 Sub Settings", callback_data="admin_menu_sub_settings")
    btn_donate = InlineKeyboardButton("❤️ Donate Settings", callback_data="admin_menu_donate_settings")
    btn_links = InlineKeyboardButton("🔗 Other Links", callback_data="admin_menu_other_links")
    btn_msgs = InlineKeyboardButton("⚙️ Bot Messages", callback_data="admin_menu_messages")
    btn_users = InlineKeyboardButton("👥 Sub Users", callback_data="admin_list_subs")
    btn_log = InlineKeyboardButton("🔔 Sub Log", url=log_url)
    btn_co_admin = InlineKeyboardButton("🛠️ Co-Admin Settings", callback_data="admin_co_admin_settings")
    btn_custom_post = InlineKeyboardButton("📢 Custom Post", callback_data="admin_custom_post")
    
    if is_bot_owner:
        # NAYA 2x2 Grid Layout (Owner)
        keyboard = [
            [btn_add, btn_manage],
            [btn_post, btn_custom_post],
            [btn_sub_settings, btn_donate],
            [btn_msgs, btn_links],
            [btn_users, btn_co_admin],
            [btn_log]
        ]
        admin_menu_text = messages.get("admin_menu_text", "Salaam, Admin Boss! 👑")
    else:
        # NAYA 2x2 Grid Layout (Co-Admin)
        keyboard = [
            [btn_add, btn_manage],
            [btn_post],
            [btn_log]
        ]
        admin_menu_text = messages.get("co_admin_menu_text", "Salaam, Co-Admin! 🫡")

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if from_callback:
        query = update.callback_query
        try:
            if query.message.photo:
                await query.message.delete()
                await context.bot.send_message(query.from_user.id, admin_menu_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await query.edit_message_text(admin_menu_text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.warning(f"Admin menu edit nahi kar paya (shayad message same tha): {e}")
            await query.answer()
    else:
        await update.message.reply_text(admin_menu_text, reply_markup=reply_markup, parse_mode='Markdown')

# NAYA: Subscribed users ki list
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
        os.remove(file_path) # File delete karo
        await query.message.delete() # Purana menu delete karo
        
    except Exception as e:
        logger.error(f"Subscribed users ki list banate waqt error: {e}")
        await context.bot.send_message(query.from_user.id, "❌ Error! List nahi bana paya.")


async def placeholder_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "user_check_sub":
        await query.answer("Aap pehle se subscribed hain!", show_alert=True)
    else:
        await query.answer(f"Button '{query.data}' jald aa raha hai...", show_alert=True)
        
# --- User Download Handler (CallbackQuery) ---
# NAYA: YEH FUNCTION AB CHANNEL AUR DM DONO HANDLE KAREGA
async def download_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback data 'dl_' se shuru hone wale sabhi buttons ko handle karega.
    (MAJOR UPDATE: No quality selection, send all files)
    """
    query = update.callback_query
    user = query.from_user
    user_id = user.id
    config = await get_config()
    messages = config.get("messages", {})
    
    try:
        # Step 1: Check Subscription
        if not await check_subscription(user_id):
            alert_msg = messages.get("dl_sub_needed_alert", "❌ Access Denied! Subscribe karne ke liye DM check karein.")
            await query.answer(alert_msg, show_alert=True)
            
            qr_id = config.get('sub_qr_id')
            price = config.get('price')
            days = config.get('validity_days')

            if not qr_id or not price or not days:
                try:
                    msg = messages.get("err_sub_not_set", "❌ Subscription system abhi setup nahi hua hai.")
                    await context.bot.send_message(user_id, msg)
                except Exception as e: logger.warning(f"Error sending sub error to user {user_id}: {e}")
                return

            text = messages.get("dl_sub_needed_dm", "**Subscription Plan**\n\nPrice: {price}\nValidity: {days} days\n\n...")
            text = text.replace("{price}", str(price)).replace("{days}", str(days))
            
            try:
                await context.bot.send_photo(chat_id=user_id, photo=qr_id, caption=text, parse_mode='Markdown')
            except Exception as e:
                logger.error(f"User {user_id} ko DM me QR bhejte waqt error: {e}")
                if "blocked" in str(e):
                    await query.answer(messages.get("err_dm_failed", "❌ Error! Subscribe karne ke liye bot ko DM me /start karein."), show_alert=True)
            return
            
        # Step 2: User Subscribed Hai
        is_in_dm = query.message.chat.type == 'private'
        
        if not is_in_dm:
            await query.answer(messages.get("dl_check_dm_alert", "✅ Check your DM (private chat) with me!"), show_alert=True)
        else:
            await query.answer() 
        
        parts = query.data.split('__')
        anime_name = parts[0].replace("dl_", "")
        season_name = parts[1] if len(parts) > 1 else None
        ep_num = parts[2] if len(parts) > 2 else None
        
        anime_doc = animes_collection.find_one({"name": anime_name})
        if not anime_doc:
            await context.bot.send_message(user_id, messages.get("err_anime_not_found", "❌ Error: Anime nahi mila."))
            return

        # --- NAYA FLOW (REQ 4): Send all files, no quality selection ---
        if ep_num:
            ep_data = anime_doc.get("seasons", {}).get(season_name, {}).get(ep_num, {})
            if not ep_data:
                await query.edit_message_caption(messages.get("err_no_episodes", "❌ Error: Is episode ke liye qualities nahi mili."))
                return
                
            ep_desc = ep_data.get('description', '')
            qualities = {k: v for k, v in ep_data.items() if k != 'description'}
            
            if not qualities:
                await query.edit_message_caption(messages.get("err_no_episodes", "❌ Error: Is episode ke liye qualities nahi mili."))
                return

            # Purana message (jo Poster wala था) delete karo
            try:
                await query.message.delete()
            except Exception as e:
                logger.warning(f"Purana message delete nahi kar paya: {e}")

            # Naya "Files Ready" message bhejo
            ready_msg_template = messages.get("dl_files_ready", "✅ **{anime_name}** | **S{season_name} - E{ep_num}**\n\n{description}\n\nAapke files neeche aa rahe hain:")
            ready_msg = ready_msg_template.format(
                anime_name=anime_name,
                season_name=season_name,
                ep_num=ep_num,
                description=ep_desc
            )
            await context.bot.send_message(user_id, ready_msg, parse_mode='Markdown')

            # Quality sort karo
            QUALITY_ORDER = ['480p', '720p', '1080p', '4K']
            sorted_q_list = [q for q in QUALITY_ORDER if q in qualities]
            extra_q = [q for q in qualities if q not in sorted_q_list]
            sorted_q_list.extend(extra_q)
            
            delete_time = config.get("delete_seconds", 300) 
            delete_minutes = max(1, delete_time // 60)
            warning_template = messages.get("file_warning", "⚠️ Yeh file {minutes} minute(s) mein automatically delete ho jaayegi.")
            caption_template = messages.get("dl_file_caption", "🎬 **{anime_name}**\nS{season_name} - E{ep_num} ({quality})")
            
            # Loop karke saari files bhejo
            for q in sorted_q_list:
                file_id = qualities[q]
                sent_message = None 
                try:
                    caption = caption_template.format(anime_name=anime_name, season_name=season_name, ep_num=ep_num, quality=q)
                    caption += f"\n\n{warning_template.replace('{minutes}', str(delete_minutes))}"
                    
                    sent_message = await context.bot.send_video(
                        chat_id=user_id, 
                        video=file_id, 
                        caption=caption,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"User {user_id} ko file {q} bhejte waqt error: {e}")
                    if "blocked" in str(e) or "bot was blocked" in str(e):
                        await context.bot.send_message(user_id, messages.get("err_blocked", "❌ Error! File nahi bhej paya. Aapne bot ko block kiya hua hai."))
                        break # Loop tod do
                    else:
                        await context.bot.send_message(user_id, f"❌ Error! File {q} nahi bhej paya. Please try again.")
                
                # Har message ke liye auto-delete schedule karo
                if sent_message:
                    try:
                        asyncio.create_task(delete_message_later(
                            bot=context.bot, 
                            chat_id=user_id, 
                            message_id=sent_message.message_id, 
                            seconds=delete_time
                        ))
                        logger.info(f"Scheduled message {sent_message.message_id} for deletion in {delete_time}s (using asyncio.create_task)")
                    except Exception as e:
                        logger.error(f"asyncio.create_task schedule failed for user {user_id}: {e}")
            return
            
        # Case 2: Season click hua hai -> Episode Bhejo
        if season_name:
            episodes = anime_doc.get("seasons", {}).get(season_name, {})
            if not episodes:
                await query.edit_message_caption(messages.get("err_no_episodes", "❌ Error: Is season ke liye episodes nahi mile."))
                return
            
            sorted_eps = sorted(episodes.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            
            buttons = []
            for ep in sorted_eps:
                cb_data = f"dl_{anime_name}__{season_name}__{ep}"
                buttons.append(InlineKeyboardButton(f"Episode {ep}", callback_data=cb_data))
            
            keyboard = build_grid_keyboard(buttons, 2)
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f"dl_{anime_name}")])
            
            caption_template = messages.get("dl_select_episode", "**{anime_name}** | **Season {season_name}**\n\nEpisode select karein:")
            caption = caption_template.format(anime_name=anime_name, season_name=season_name)
            
            await query.edit_message_caption(
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            return
            
        # Case 1: Sirf Anime click hua hai (Channel se) -> Season Bhejo
        if not is_in_dm:
            seasons = anime_doc.get("seasons", {})
            if not seasons:
                await context.bot.send_message(user_id, messages.get("err_no_seasons", "❌ Error: Is anime ke liye seasons nahi mile."))
                return
            
            sorted_seasons = sorted(seasons.keys(), key=lambda x: [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', x)])
            
            buttons = []
            for s in sorted_seasons:
                cb_data = f"dl_{anime_name}__{s}"
                buttons.append(InlineKeyboardButton(f"Season {s}", callback_data=cb_data))
            
            keyboard = build_grid_keyboard(buttons, 2)
            keyboard.append([InlineKeyboardButton("⬅️ Back to Bot Menu", callback_data="user_back_menu")])
            
            caption_template = messages.get("dl_select_season", "**{anime_name}**\n\nSeason select karein:")
            caption = caption_template.format(anime_name=anime_name)
            
            await context.bot.send_photo(
                chat_id=user_id,
                photo=anime_doc['poster_id'],
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        return

    except Exception as e:
        logger.error(f"Download button handler me error: {e}", exc_info=True)
        if query.message and query.message.chat.type in ['channel', 'supergroup', 'group']:
             await query.answer(messages.get("err_generic", "❌ Error! Please try again."), show_alert=True)
        else:
             try:
                 await context.bot.send_message(user_id, messages.get("err_generic", "❌ Error! Please try again."))
             except Exception: pass


# --- Error Handler ---
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error} \nUpdate: {update}", exc_info=True)

# --- Main Bot Function ---
def main():
    logger.info("Flask web server start ho raha hai (Render port ke liye)...")
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    logger.info("Bot Application ban raha hai...")
    application = Application.builder().token(BOT_TOKEN).build()
    
    # --- NAYA: Global Fallback (Sirf /cancel ke liye) ---
    global_fallbacks = [
        CommandHandler("cancel", force_cancel),
        # Command fallbacks (cancel karke naya command chalayega)
        CommandHandler("start", conv_cancel),
        CommandHandler("menu", conv_cancel),
        CommandHandler("admin", conv_cancel),
    ]
    
    # Local Fallbacks (Sirf "Back" buttons ke liye)
    admin_menu_fallback = [CallbackQueryHandler(back_to_admin_menu, pattern="^admin_menu$")]
    add_content_fallback = [CallbackQueryHandler(back_to_add_content_menu, pattern="^back_to_add_content$")]
    manage_fallback = [CallbackQueryHandler(back_to_manage_menu, pattern="^back_to_manage$")]
    sub_settings_fallback = [CallbackQueryHandler(back_to_sub_settings_menu, pattern="^back_to_sub_settings$")]
    donate_settings_fallback = [CallbackQueryHandler(back_to_donate_settings_menu, pattern="^back_to_donate_settings$")]
    links_fallback = [CallbackQueryHandler(back_to_links_menu, pattern="^back_to_links$")]
    user_menu_fallback = [CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$")]
    messages_fallback = [
        CallbackQueryHandler(bot_messages_menu, pattern="^back_to_messages_main$"),
        CallbackQueryHandler(back_to_admin_menu, pattern="^admin_menu$") # Fail-safe
    ]
    co_admin_fallback = [CallbackQueryHandler(back_to_co_admin_menu, pattern="^back_to_co_admin$")]

    # --- STABILITY FIX: Sabhi Conversations me "allow_reentry=True" add kiya gaya hai ---

    # Admin Conversations
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
            S_GET_ANIME: [CallbackQueryHandler(get_anime_for_season, pattern="^season_anime_")], 
            S_GET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_season_number)], 
            S_CONFIRM: [CallbackQueryHandler(save_season, pattern="^save_season$")]
        }, 
        fallbacks=global_fallbacks + add_content_fallback,
        allow_reentry=True 
    )
    
    # NAYA "Add Episode" Conversation Handler (Description ke saath)
    add_episode_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_episode_start, pattern="^admin_add_episode$")], 
        states={
            E_GET_ANIME: [CallbackQueryHandler(get_anime_for_episode, pattern="^ep_anime_")], 
            E_GET_SEASON: [CallbackQueryHandler(get_season_for_episode, pattern="^ep_season_")], 
            E_GET_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_episode_number)],
            E_GET_EP_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_episode_description), CommandHandler("skip", skip_episode_description)],
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
            PG_MENU: [CallbackQueryHandler(post_gen_select_anime, pattern="^post_gen_season$"), CallbackQueryHandler(post_gen_select_anime, pattern="^post_gen_episode$")], 
            PG_GET_ANIME: [CallbackQueryHandler(post_gen_select_season, pattern="^post_anime_")], 
            PG_GET_SEASON: [CallbackQueryHandler(post_gen_select_episode, pattern="^post_season_")], 
            PG_GET_EPISODE: [CallbackQueryHandler(post_gen_final_episode, pattern="^post_ep_")], 
            PG_GET_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_gen_send_to_chat)]
        }, 
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True 
    )
    # NAYA: Custom Post Conv
    custom_post_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(custom_post_start, pattern="^admin_custom_post$")],
        states={
            CP_GET_POSTER: [MessageHandler(filters.PHOTO, cp_get_poster)],
            CP_GET_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, cp_get_caption), CommandHandler("skip", cp_skip_caption)],
            CP_GET_BUTTONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cp_get_buttons), CommandHandler("done", cp_done_buttons)],
            CP_GET_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cp_send_to_chat)],
        },
        fallbacks=global_fallbacks + admin_menu_fallback,
        allow_reentry=True
    )
    
    del_anime_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_anime_start, pattern="^admin_del_anime$")], 
        states={
            DA_GET_ANIME: [CallbackQueryHandler(delete_anime_confirm, pattern="^del_anime_")], 
            DA_CONFIRM: [CallbackQueryHandler(delete_anime_do, pattern="^del_anime_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    del_season_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_season_start, pattern="^admin_del_season$")], 
        states={
            DS_GET_ANIME: [CallbackQueryHandler(delete_season_select, pattern="^del_season_anime_")], 
            DS_GET_SEASON: [CallbackQueryHandler(delete_season_confirm, pattern="^del_season_")], 
            DS_CONFIRM: [CallbackQueryHandler(delete_season_do, pattern="^del_season_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    
    del_episode_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(delete_episode_start, pattern="^admin_del_episode$")], 
        states={
            DE_GET_ANIME: [CallbackQueryHandler(delete_episode_select_season, pattern="^del_ep_anime_")],
            DE_GET_SEASON: [CallbackQueryHandler(delete_episode_select_episode, pattern="^del_ep_season_")],
            DE_GET_EPISODE: [CallbackQueryHandler(delete_episode_confirm, pattern="^del_ep_num_")],
            DE_CONFIRM: [CallbackQueryHandler(delete_episode_do, pattern="^del_ep_confirm_yes$")]
        }, 
        fallbacks=global_fallbacks + manage_fallback,
        allow_reentry=True 
    )
    
    remove_sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(remove_sub_start, pattern="^admin_remove_sub$")],
        states={
            RS_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_sub_get_id)],
            RS_CONFIRM: [CallbackQueryHandler(remove_sub_do, pattern="^remove_sub_confirm_yes$")]
        },
        fallbacks=global_fallbacks + admin_menu_fallback, 
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
    
    # NAYA: Co-Admin Conv
    co_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(co_admin_settings_menu, pattern="^admin_co_admin_settings$")],
        states={
            CA_MENU: [
                CallbackQueryHandler(co_admin_add_start, pattern="^co_admin_add$"),
                CallbackQueryHandler(co_admin_remove_start, pattern="^co_admin_remove$"),
                CallbackQueryHandler(co_admin_list, pattern="^co_admin_list$")
            ],
            CA_GET_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, co_admin_add_save)],
            CR_GET_ID: [CallbackQueryHandler(co_admin_remove_do, pattern="^co_remove_")]
        },
        fallbacks=global_fallbacks + admin_menu_fallback + co_admin_fallback,
        allow_reentry=True
    )

    # NAYA: Generic Message Conv
    set_messages_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_msg_start, pattern="^msg_")],
        states={
            M_GET_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_msg_save)],
        },
        fallbacks=global_fallbacks + messages_fallback,
        allow_reentry=True 
    )

    # User Subscription Conversation
    sub_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(user_upload_ss_start, pattern="^user_upload_ss$")],
        states={SUB_GET_SCREENSHOT: [MessageHandler(filters.PHOTO, user_get_screenshot)]},
        fallbacks=global_fallbacks + user_menu_fallback,
        allow_reentry=True 
    )
    
    # Admin Approval Conversation
    approve_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_approve_start, pattern="^admin_approve_")],
        states={ADMIN_GET_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_get_days_save)]},
        fallbacks=global_fallbacks,
        allow_reentry=True 
    )

    # --- Handlers ko Add Karo ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("cancel", force_cancel)) # Global force cancel
    
    application.add_handler(CallbackQueryHandler(admin_command, pattern="^admin_menu$"))
    application.add_handler(CallbackQueryHandler(back_to_user_menu, pattern="^user_back_menu$"))
    
    # Admin Sub-Menu Handlers (Owner checks in functions)
    application.add_handler(CallbackQueryHandler(add_content_menu, pattern="^admin_menu_add_content$"))
    application.add_handler(CallbackQueryHandler(manage_content_menu, pattern="^admin_menu_manage_content$"))
    
    # NAYA: Owner-Only Handlers
    async def owner_only_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, callback_func):
        if not await is_owner(update.effective_user.id):
            await update.callback_query.answer("❌ Access Denied! Sirf Bot Owner hi ise access kar sakta hai.", show_alert=True)
            return
        await callback_func(update, context)

    application.add_handler(CallbackQueryHandler(lambda u, c: owner_only_wrapper(u, c, sub_settings_menu), pattern="^admin_menu_sub_settings$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: owner_only_wrapper(u, c, donate_settings_menu), pattern="^admin_menu_donate_settings$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: owner_only_wrapper(u, c, other_links_menu), pattern="^admin_menu_other_links$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: owner_only_wrapper(u, c, bot_messages_menu), pattern="^admin_menu_messages$|^msg_page_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: owner_only_wrapper(u, c, admin_list_subs), pattern="^admin_list_subs$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: owner_only_wrapper(u, c, admin_reject_user), pattern="^admin_reject_"))
    
    # Conversations (Auth checks are inside entry points or handlers)
    application.add_handler(add_anime_conv)
    application.add_handler(add_season_conv)
    application.add_handler(add_episode_conv)
    application.add_handler(set_sub_qr_conv)
    application.add_handler(set_price_conv)
    application.add_handler(set_donate_qr_conv)
    application.add_handler(set_links_conv)
    application.add_handler(post_gen_conv)
    application.add_handler(custom_post_conv) # NAYA
    application.add_handler(del_anime_conv)
    application.add_handler(del_season_conv)
    application.add_handler(del_episode_conv)
    application.add_handler(remove_sub_conv)
    application.add_handler(sub_conv)
    application.add_handler(approve_conv)
    application.add_handler(set_days_conv) 
    application.add_handler(set_delete_time_conv)
    application.add_handler(set_messages_conv)
    application.add_handler(co_admin_conv) # NAYA
    
    # User Handlers
    application.add_handler(CallbackQueryHandler(user_subscribe_start, pattern="^user_subscribe$"))
    application.add_handler(CallbackQueryHandler(admin_reject_user, pattern="^admin_reject_"))
    
    application.add_handler(CallbackQueryHandler(user_show_donate_menu, pattern="^user_show_donate_menu$"))
    
    # NAYA: Yeh naye download flow ko handle karega
    application.add_handler(CallbackQueryHandler(download_button_handler, pattern="^dl_"))
    
    application.add_handler(CallbackQueryHandler(placeholder_button_handler, pattern="^user_check_sub$"))

    application.add_error_handler(error_handler)

    logger.info("Bot polling start kar raha hai...")
    application.run_polling()

if __name__ == "__main__":
    main()
