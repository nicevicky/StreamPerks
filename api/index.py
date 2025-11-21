from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import httpx
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import asyncio

# ========================
# CONFIGURATION & LOGGING
# ========================
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title="Telegram Task Verification API")

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Global variable to store Bot Username
BOT_USERNAME = None

# ========================
# STARTUP EVENT (FETCH USERNAME)
# ========================
@app.on_event("startup")
async def startup_event():
    """
    Fetch the Bot's username on startup so we can create valid deep links.
    """
    global BOT_USERNAME
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TELEGRAM_API}/getMe")
            data = response.json()
            if data.get("ok"):
                BOT_USERNAME = data["result"]["username"]
                logger.info(f"✅ Bot Username loaded: @{BOT_USERNAME}")
            else:
                logger.error(f"❌ Failed to fetch bot username: {data}")
    except Exception as e:
        logger.error(f"❌ Error fetching bot username: {e}")

# ========================
# PYDANTIC MODELS
# ========================
class UserJoinTask(BaseModel):
    user_id: int
    task_id: int
    channel_id: str

class UserRejoinTask(BaseModel):
    user_id: int
    task_id: int

# ========================
# HELPER FUNCTIONS
# ========================
def get_safe_telegram_url(channel_identifier: str) -> str:
    """
    Generates a valid Telegram URL.
    - If username (@channel), returns https://t.me/channel
    - If numeric ID (-100xyz), returns a link to the Bot (Fixed logic)
    """
    clean_id = str(channel_identifier).strip()
    
    # If it looks like a numeric ID (private channel) or contains invalid characters
    if clean_id.startswith("-") or clean_id.isdigit():
        # FIXED: Use the fetched BOT_USERNAME
        if BOT_USERNAME:
            return f"https://t.me/{BOT_USERNAME}"
        else:
            # Fallback if startup fetch failed (prevents 400 error by linking to telegram main)
            return "https://t.me/telegram" 
    
    # Standard username handling
    username = clean_id.replace("@", "")
    return f"https://t.me/{username}"

async def check_channel_membership(user_id: int, channel_id: str) -> bool:
    """Check if user is member of channel using Telegram Bot API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TELEGRAM_API}/getChatMember",
                params={"chat_id": channel_id, "user_id": user_id}
            )
            data = response.json()
            
            if data.get("ok"):
                status = data["result"]["status"]
                # Member, administrator, or creator = still in channel
                return status in ["member", "administrator", "creator"]
            
            # If bot is kicked or chat not found, assume user left or verify failed
            logger.warning(f"Check membership failed: {data.get('description')}")
            return False
    except Exception as e:
        logger.error(f"Error checking membership: {e}")
        return False

async def send_telegram_message(user_id: int, text: str, inline_keyboard: Optional[list] = None) -> Optional[int]:
    """Send message via Telegram Bot API"""
    try:
        payload = {
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if inline_keyboard:
            # Ensure the structure is strictly correct for Telegram
            payload["reply_markup"] = {
                "inline_keyboard": inline_keyboard
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
            data = response.json()
            
            if data.get("ok"):
                return data["result"]["message_id"]
            else:
                logger.error(f"Telegram API Error: {data}")
                return None
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return None

async def delete_telegram_message(user_id: int, message_id: int):
    """Delete a Telegram message"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{TELEGRAM_API}/deleteMessage",
                json={"chat_id": user_id, "message_id": message_id}
            )
    except Exception as e:
        logger.error(f"Error deleting message: {e}")

def deduct_user_balance(user_id: int, amount: float):
    """Deduct balance from user"""
    try:
        # Get current balance
        user = supabase.table("users").select("balance").eq("telegram_id", user_id).single().execute()
        
        if user.data:
            new_balance = max(0, float(user.data["balance"]) - amount)
            supabase.table("users").update({"balance": new_balance}).eq("telegram_id", user_id).execute()
            logger.info(f"Deducted {amount} from user {user_id}. New balance: {new_balance}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deducting balance: {e}")
        return False

def restore_user_balance(user_id: int, amount: float):
    """Restore balance to user"""
    try:
        user = supabase.table("users").select("balance").eq("telegram_id", user_id).single().execute()
        
        if user.data:
            new_balance = float(user.data["balance"]) + amount
            supabase.table("users").update({"balance": new_balance}).eq("telegram_id", user_id).execute()
            logger.info(f"Restored {amount} to user {user_id}. New balance: {new_balance}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error restoring balance: {e}")
        return False

async def schedule_message_deletion(user_id: int, message_id: int):
    """Background task to delete message after 24 hours"""
    await asyncio.sleep(86400)  # 24 hours in seconds
    await delete_telegram_message(user_id, message_id)

# ========================
# API ENDPOINTS
# ========================
@app.get("/")
def read_root():
    return {"status": "ok", "message": "Telegram Task Verification API is running", "bot_user": BOT_USERNAME}

@app.post("/api/user-joined-task")
async def user_joined_task(data: UserJoinTask):
    """
    Called when user joins a channel task
    Saves user_id, task_id, channel_id, and joined_at timestamp
    """
    try:
        # Verify task exists and get reward
        task = supabase.table("tasks").select("*").eq("id", data.task_id).single().execute()
        
        if not task.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Insert or update user_task record
        user_task_data = {
            "user_id": data.user_id,
            "task_id": data.task_id,
            "channel_id": data.channel_id,
            "status": "completed",
            "joined_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("user_tasks").upsert(user_task_data).execute()
        
        logger.info(f"User {data.user_id} joined task {data.task_id} (channel: {data.channel_id})")
        
        return {"success": True, "message": "Task join recorded"}
    
    except Exception as e:
        logger.error(f"Error in user_joined_task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/check-user-left")
async def check_user_left(background_tasks: BackgroundTasks):
    """
    Cron job endpoint: Check if users left channels before 7 days
    """
    try:
        # Get all completed tasks that are within the 7-day window
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        result = supabase.table("user_tasks")\
            .select("*, tasks(reward)")\
            .eq("status", "completed")\
            .gte("joined_at", seven_days_ago)\
            .eq("penalty_applied", False)\
            .execute()
        
        if not result.data:
            return {"checked": 0, "penalized": 0}
        
        penalized_count = 0
        
        for user_task in result.data:
            user_id = user_task["user_id"]
            task_id = user_task["task_id"]
            channel_id = user_task["channel_id"]
            reward = float(user_task["tasks"]["reward"])
            
            # Check if user is still in channel
            is_member = await check_channel_membership(user_id, channel_id)
            
            if not is_member:
                # User left! Apply penalty
                logger.warning(f"User {user_id} left channel {channel_id} before 7 days")
                
                # Deduct balance
                deduct_user_balance(user_id, reward)
                
                # Generate Safe URL
                safe_url = get_safe_telegram_url(channel_id)
                
                # Send warning message with rejoin button
                text = (
                    f"⚠️ <b>Warning: Early Exit Detected</b>\n\n"
                    f"You left a channel task before the required 7-day period.\n\n"
                    f"💰 <b>{reward} coins deducted</b> from your balance.\n\n"
                    f"Click below to rejoin and restore your task perks:"
                )
                
                inline_keyboard = [[
                    {
                        "text": "🔁 Rejoin & Restore Task Perks",
                        "url": safe_url
                    }
                ]]
                
                message_id = await send_telegram_message(user_id, text, inline_keyboard)
                
                # Update user_task record
                supabase.table("user_tasks").update({
                    "status": "left",
                    "left_at": datetime.utcnow().isoformat(),
                    "penalty_applied": True,
                    "warning_sent": True,
                    "warning_message_id": message_id
                }).eq("id", user_task["id"]).execute()
                
                # Schedule message deletion after 24 hours
                if message_id:
                    background_tasks.add_task(schedule_message_deletion, user_id, message_id)
                
                penalized_count += 1
        
        return {
            "checked": len(result.data),
            "penalized": penalized_count
        }
    
    except Exception as e:
        logger.error(f"Error in check_user_left: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/user-rejoined-task")
async def user_rejoined_task(data: UserRejoinTask):
    """
    Called when user clicks rejoin button and rejoins the channel
    Restores their balance and perks
    """
    try:
        # Get user_task record
        user_task = supabase.table("user_tasks")\
            .select("*, tasks(reward)")\
            .eq("user_id", data.user_id)\
            .eq("task_id", data.task_id)\
            .single()\
            .execute()
        
        if not user_task.data:
            raise HTTPException(status_code=404, detail="Task record not found")
        
        channel_id = user_task.data["channel_id"]
        reward = float(user_task.data["tasks"]["reward"])
        
        # Verify user actually rejoined
        is_member = await check_channel_membership(data.user_id, channel_id)
        
        if not is_member:
            return {"success": False, "message": "Please join the channel first"}
        
        # Restore balance
        restore_user_balance(data.user_id, reward)
        
        # Update status
        supabase.table("user_tasks").update({
            "status": "restored",
            "penalty_applied": False,
            "joined_at": datetime.utcnow().isoformat()  # Reset join time
        }).eq("user_id", data.user_id).eq("task_id", data.task_id).execute()
        
        # Delete warning message if exists
        if user_task.data.get("warning_message_id"):
            await delete_telegram_message(data.user_id, user_task.data["warning_message_id"])
        
        # Send success message
        await send_telegram_message(
            data.user_id,
            f"✅ <b>Task Restored!</b>\n\n{reward} coins have been restored to your balance.\n\nThank you for rejoining! 🎉"
        )
        
        logger.info(f"User {data.user_id} rejoined and restored task {data.task_id}")
        
        return {"success": True, "message": "Task perks restored"}
    
    except Exception as e:
        logger.error(f"Error in user_rejoined_task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================
# BACKGROUND SCHEDULER (Optional)
# ========================
scheduler = BackgroundScheduler()

def scheduled_check():
    """Run check_user_left every 6 hours"""
    # Note: In a real server context, ensure loops are handled correctly
    import asyncio
    asyncio.run(check_user_left(BackgroundTasks()))

# scheduler.add_job(scheduled_check, 'interval', hours=6)
# scheduler.start()

# ========================
# VERCEL HANDLER
# ========================
handler = app
