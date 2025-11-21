from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import httpx
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
if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ Missing Supabase Credentials")
    
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    logger.error(f"❌ Failed to init Supabase: {e}")

# Telegram API base URL
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ========================
# PYDANTIC MODELS
# ========================
class UserJoinTask(BaseModel):
    user_id: int
    task_id: int
    channel_username: str 

class UserRejoinTask(BaseModel):
    user_id: int
    task_id: int

# ========================
# HELPER FUNCTIONS
# ========================

def get_safe_telegram_url(channel_username: str) -> str:
    """
    Generates a valid Telegram URL.
    Returns empty string if username is invalid.
    """
    if not channel_username:
        return ""
        
    clean_name = str(channel_username).strip()
    
    # If it is already a full URL, return it
    if clean_name.startswith("http"):
        return clean_name
    
    # Remove '@' and build link
    username = clean_name.replace("@", "")
    if not username:
        return ""
        
    return f"https://t.me/{username}"

async def check_channel_membership(user_id: int, channel_username: str) -> bool:
    """
    Check if user is member of channel using Telegram Bot API.
    """
    try:
        if not channel_username:
            return False

        # Ensure username has @ for the API call (but not for the link)
        chat_identifier = channel_username
        if not chat_identifier.startswith("@") and not chat_identifier.startswith("-") and not chat_identifier.isdigit():
             chat_identifier = f"@{chat_identifier}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{TELEGRAM_API}/getChatMember",
                params={"chat_id": chat_identifier, "user_id": user_id}
            )
            data = response.json()
            
            if data.get("ok"):
                status = data["result"]["status"]
                # Member, administrator, or creator = still in channel
                return status in ["member", "administrator", "creator"]
            
            logger.warning(f"Check membership failed for {channel_username}: {data.get('description')}")
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
        
        # FIX: Only add reply_markup if inline_keyboard is valid and not empty
        if inline_keyboard and len(inline_keyboard) > 0:
            payload["reply_markup"] = {
                "inline_keyboard": inline_keyboard
            }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
            data = response.json()
            
            if data.get("ok"):
                return data["result"]["message_id"]
            else:
                logger.error(f"Telegram API Error (Send): {data}")
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
    """
    Attempt to delete message after delay.
    Note: On Serverless, long sleeps usually get killed. 
    Ideally handled by an external cron, but kept here for logic flow.
    """
    await asyncio.sleep(86400) # 24 hours
    await delete_telegram_message(user_id, message_id)

# ========================
# API ENDPOINTS
# ========================

@app.get("/")
def read_root():
    return {
        "status": "active", 
        "message": "Telegram Task Verification API is running", 
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/index.py")
def read_root_alias():
    """Handle direct file access alias commonly used in Vercel configs"""
    return read_root()

@app.post("/api/user-joined-task")
async def user_joined_task(data: UserJoinTask):
    try:
        # Verify task exists
        task = supabase.table("tasks").select("*").eq("id", data.task_id).single().execute()
        
        if not task.data:
            raise HTTPException(status_code=404, detail="Task not found")
        
        user_task_data = {
            "user_id": data.user_id,
            "task_id": data.task_id,
            "channel_username": data.channel_username, 
            "status": "completed",
            "joined_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat()
        }
        
        supabase.table("user_tasks").upsert(user_task_data).execute()
        return {"success": True, "message": "Task join recorded"}
    
    except Exception as e:
        logger.error(f"Error in user_joined_task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/check-user-left")
async def check_user_left(background_tasks: BackgroundTasks):
    """
    Cron job endpoint: Check if users left channels before 7 days.
    Call this via Vercel Cron.
    """
    try:
        seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
        
        # Fetch completed tasks that haven't been penalized yet
        result = supabase.table("user_tasks")\
            .select("*, tasks(reward, channel_username)")\
            .eq("status", "completed")\
            .gte("joined_at", seven_days_ago)\
            .eq("penalty_applied", False)\
            .execute()
        
        if not result.data:
            return {"checked": 0, "penalized": 0}
        
        penalized_count = 0
        
        for user_task in result.data:
            user_id = user_task["user_id"]
            
            # Prefer username from Tasks table, fallback to user_tasks
            task_data = user_task.get("tasks") or {}
            channel_username = task_data.get("channel_username")
            
            if not channel_username and "channel_username" in user_task:
                 channel_username = user_task["channel_username"]

            if not channel_username:
                logger.warning(f"Skipping check for user {user_id}: No channel username found")
                continue

            reward = float(task_data.get("reward", 0))
            
            # Check if user is still in channel
            is_member = await check_channel_membership(user_id, channel_username)
            
            if not is_member:
                # User left! Apply penalty
                deduct_user_balance(user_id, reward)
                
                safe_url = get_safe_telegram_url(channel_username)
                
                text = (
                    f"⚠️ <b>Warning: Early Exit Detected</b>\n\n"
                    f"You left a channel task before the required 7-day period.\n\n"
                    f"💰 <b>{reward} coins deducted</b> from your balance.\n\n"
                    f"Click below to rejoin and restore your task perks:"
                )
                
                # FIX: Only add button if URL is strictly valid
                inline_keyboard = []
                if safe_url and safe_url.startswith("http"):
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
                
                # Attempt to schedule deletion (might not persist on serverless)
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
    try:
        user_task = supabase.table("user_tasks")\
            .select("*, tasks(reward, channel_username)")\
            .eq("user_id", data.user_id)\
            .eq("task_id", data.task_id)\
            .single()\
            .execute()
        
        if not user_task.data:
            raise HTTPException(status_code=404, detail="Task record not found")
        
        task_data = user_task.data.get("tasks") or {}
        channel_username = task_data.get("channel_username")
        reward = float(task_data.get("reward", 0))
        
        if not channel_username:
             raise HTTPException(status_code=400, detail="Channel username missing")

        is_member = await check_channel_membership(data.user_id, channel_username)
        
        if not is_member:
            return {"success": False, "message": "Please join the channel first"}
        
        restore_user_balance(data.user_id, reward)
        
        supabase.table("user_tasks").update({
            "status": "restored",
            "penalty_applied": False,
            "joined_at": datetime.utcnow().isoformat()
        }).eq("user_id", data.user_id).eq("task_id", data.task_id).execute()
        
        if user_task.data.get("warning_message_id"):
            await delete_telegram_message(data.user_id, user_task.data["warning_message_id"])
        
        await send_telegram_message(
            data.user_id,
            f"✅ <b>Task Restored!</b>\n\n{reward} coins have been restored to your balance.\n\nThank you for rejoining! 🎉"
        )
        
        return {"success": True, "message": "Task perks restored"}
    
    except Exception as e:
        logger.error(f"Error in user_rejoined_task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ========================
# VERCEL HANDLER
# ========================
handler = app
