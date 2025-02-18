from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import os
from dotenv import load_dotenv
from scrapper import get_attendance_report
from model import init_db, save_user, get_user
import logging
import asyncio
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

# Add this at the top of your file with other constants
MARKDOWN_ESCAPE_TABLE = str.maketrans({
    '_': '\\_', '*': '\\*', '[': '\\[', ']': '\\]',
    '(': '\\(', ')': '\\)', '~': '\\~', '`': '\\`',
    '>': '\\>', '#': '\\#', '+': '\\+', '-': '\\-',
    '=': '\\=', '|': '\\|', '{': '\\{', '}': '\\}',
    '.': '\\.', '!': '\\!'
})

# Create a thread pool for background tasks
executor = ThreadPoolExecutor(max_workers=3)

# Cache formatted reports for 5 minutes
@lru_cache(maxsize=32)
def format_report_for_markdown(report):
    """Format report with better alignment and cleaner output"""
    sections = report.split('\n\n')
    formatted = []
    
    for section in sections:
        if 'Hi ' in section:
            formatted.append(f"*{section.replace('Hi ', '')}*")
        elif 'Total:' in section:
            p = section.split()
            n = p[1].split('/')
            formatted.append(f"*{p[0]}: {n[0]}/{n[1]} ({p[2]})*")
        elif "Today's Attendance:" in section:
            lines = [line for line in section.split('\n') if ':' in line]
            attendance = [f"• {s}: {st}" for s, st in 
                        (line.split(':', 1) for line in lines[1:])
                        if st.strip() in ['P', 'A']]
            if attendance:
                formatted.append(f"{lines[0]}\n{chr(10).join(attendance)}")
            else:
                formatted.append(lines[0])
        elif 'You can skip' in section:
            # Format skippable hours message
            formatted.append(f"*{section}*")
        elif 'Subject-wise Attendance:' in section:
            lines = section.split('\n')
            subjects = []
            for line in lines[1:]:
                if not line.strip(): continue
                parts = line.replace('..', ' ').split()
                if len(parts) < 2: continue
                i = next((i for i, p in enumerate(parts) 
                         if '/' in p), None)
                if i is None: continue
                subject = ' '.join(parts[:i])
                attendance = parts[i]
                percentage = parts[i+1] if i+1 < len(parts) else ''
                subjects.append(f"{subject:<20} *{attendance}* {percentage}")
            formatted.append(f"{lines[0]}\n{chr(10).join(subjects)}")
    
    return '\n\n'.join(formatted)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("Missing TELEGRAM_TOKEN environment variable")

# Initialize Flask app
flask_app = Flask(__name__)

# Initialize Bot
bot = Bot(token=TELEGRAM_TOKEN)
app = Application.builder().token(TELEGRAM_TOKEN).build()

# Initialize database
init_db()

async def start(update, context):
    """Send welcome message when /start is issued"""
    welcome_msg = (
        "👋 *Welcome to Attendance Bot\\!*\n\n"
        "1️⃣ Set up permanent access:\n"
        "`/set username password keyword`\n\n"
        "2️⃣ One\\-time check:\n"
        "`/check username password`\n\n"
        "3️⃣ Quick access:\n"
        "Send your saved keyword"
    )
    await update.message.reply_text(welcome_msg, parse_mode='MarkdownV2')

async def set_credentials(update, context):
    """Handle /set command"""
    try:
        # Check arguments
        if len(context.args) != 3:
            await update.message.reply_text(
                "❌ *Invalid Format*\n\nUse: `/set username password keyword`",
                parse_mode='MarkdownV2'
            )
            return

        username, password, keyword = context.args
        user_id = str(update.effective_user.id)
        keyword = keyword.lower()
        
        # Save credentials
        save_user(user_id, username, password, keyword)
        
        await update.message.reply_text(
            f"✅ *Account Setup Successful\\!*\n\n"
            f"Your keyword is: `{keyword}`\n"
            "Send your keyword anytime to check attendance",
            parse_mode='MarkdownV2'
        )
        logging.info(f"Saved credentials for user {user_id}")
        
    except Exception as e:
        logging.error(f"Error in set command: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def check_attendance(update, context):
    """Handle /check command"""
    try:
        if len(context.args) != 2:
            await update.message.reply_text(
                "❌ *Invalid Format*\n\nUse: `/check username password`",
                parse_mode='MarkdownV2'
            )
            return

        status_msg = await update.message.reply_text(
            "🔄 *Fetching\\.\\.\\.*",
            parse_mode='MarkdownV2'
        )
        
        # Run in thread pool
        report = await asyncio.get_running_loop().run_in_executor(
            executor, 
            get_attendance_report,
            *context.args
        )
        
        # Format report (cached)
        escaped_report = format_report_for_markdown(report).translate(MARKDOWN_ESCAPE_TABLE)
        
        await status_msg.edit_text(
            f"📊 *Attendance Report*\n\n{escaped_report}",
            parse_mode='MarkdownV2'
        )
        
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def handle_message(update, context):
    """Handle regular messages (keywords)"""
    try:
        user_id = str(update.effective_user.id)
        user = get_user(user_id)
        
        if user and update.message.text.lower() == user[3]:
            status_msg = await update.message.reply_text(
                "🔄 *Fetching\\.\\.\\.*",
                parse_mode='MarkdownV2'
            )
            
            # Run in thread pool
            report = await asyncio.get_running_loop().run_in_executor(
                executor,
                get_attendance_report,
                user[1], user[2]
            )
            
            # Format report (cached)
            escaped_report = format_report_for_markdown(report).translate(MARKDOWN_ESCAPE_TABLE)
            
            await status_msg.edit_text(
                f"📊 *Attendance Report*\n\n{escaped_report}",
                parse_mode='MarkdownV2'
            )
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await update.message.reply_text(f"❌ Error: {str(e)}")

@flask_app.route("/")
async def index():
    """Health check endpoint"""
    return {"status": "online", "bot": bot.username}

def run_flask():
    """Run Flask app"""
    flask_app.run(host='0.0.0.0', port=5000)

def main():
    """Start both Flask and Telegram bot"""
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set", set_credentials))
    app.add_handler(CommandHandler("check", check_attendance))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start Flask in a separate thread
    from threading import Thread
    Thread(target=run_flask).start()
    
    # Start the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
