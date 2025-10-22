"""
Stress Notification System
Monitors stress_day in report table and sends notifications based on thresholds
"""
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cswobvpopxypghwjolnb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", 
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzd29idnBvcHh5cGdod2pvbG5iIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA4NzQ5ODMsImV4cCI6MjA3NjQ1MDk4M30.P_E9zrpgOAI-mDVCCSWQDYLbfSXbng67EIApxujhNtQ")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Notification messages for different stress levels
STRESS_MESSAGES = {
    "level_1": [
        "Calm down yourself - take a moment to breathe",
        "Take a deep breath - inhale peace, exhale stress",
        "Take a glass of water - stay hydrated and refreshed"
    ],
    "level_2": "You are stressed for a long time. Get time and make rest. Your well-being matters.",
    "level_3": "⚠️ HIGH STRESS ALERT: Please consider visiting a doctor. Your health is important."
}

class StressNotificationSystem:
    """Manages stress-based notifications for users"""
    
    def __init__(self):
        self.supabase = supabase
        logger.info("Stress Notification System initialized")
    
    def is_notification_time(self):
        """Check if current time is between 7 AM and 9 AM"""
        now = datetime.now()
        current_hour = now.hour
        return 7 <= current_hour < 9
    
    def should_send_notification(self, user_id, notification_type):
        """
        Check if notification should be sent (2-hour cooldown)
        
        Args:
            user_id: User's ID
            notification_type: Type of notification (level_1, level_2, level_3)
        
        Returns:
            bool: True if notification can be sent
        """
        try:
            # Check last notification time from notification_log table
            result = self.supabase.table("notification_log")\
                .select("*")\
                .eq("id", user_id)\
                .eq("notification_type", notification_type)\
                .order("sent_at", desc=True)\
                .limit(1)\
                .execute()
            
            if not result.data:
                return True  # No previous notification
            
            last_sent = datetime.fromisoformat(result.data[0]["sent_at"])
            time_diff = datetime.now() - last_sent
            
            # Allow notification if 2 hours have passed
            return time_diff >= timedelta(hours=2)
            
        except Exception as e:
            logger.warning(f"Error checking notification history: {str(e)}")
            return True  # Allow notification if check fails
    
    def log_notification(self, user_id, notification_type, message, stress_day):
        """Log sent notification to database"""
        try:
            self.supabase.table("notification_log").insert({
                "id": user_id,
                "notification_type": notification_type,
                "message": message,
                "stress_day": stress_day,
                "sent_at": datetime.now().isoformat()
            }).execute()
            logger.info(f"Notification logged for user {user_id}")
        except Exception as e:
            logger.error(f"Error logging notification: {str(e)}")
    
    def get_notification_message(self, stress_day):
        """
        Determine notification message based on stress_day level
        
        Args:
            stress_day: Current stress_day value
        
        Returns:
            tuple: (notification_type, message, priority)
        """
        if stress_day > 50:
            # Critical stress level
            return ("level_3", STRESS_MESSAGES["level_3"], "critical")
        elif stress_day > 10:
            # High stress level
            return ("level_2", STRESS_MESSAGES["level_2"], "high")
        elif stress_day > 5:
            # Moderate stress level - random message
            message = random.choice(STRESS_MESSAGES["level_1"])
            return ("level_1", message, "moderate")
        else:
            # No notification needed
            return (None, None, None)
    
    def check_user_stress(self, user_id):
        """
        Check a specific user's stress level and send notification if needed
        
        Args:
            user_id: User's ID to check
        
        Returns:
            dict: Notification status
        """
        try:
            # Fetch user's stress_day from report table
            result = self.supabase.table("report")\
                .select("id, stress_day")\
                .eq("id", user_id)\
                .execute()
            
            if not result.data:
                logger.info(f"No report found for user {user_id}")
                return {
                    "status": "no_report",
                    "message": "User has no report data"
                }
            
            stress_day = result.data[0].get("stress_day", 0)
            logger.info(f"User {user_id} stress_day: {stress_day}")
            
            # Get appropriate notification
            notification_type, message, priority = self.get_notification_message(stress_day)
            
            if not notification_type:
                return {
                    "status": "ok",
                    "message": "Stress level is normal",
                    "stress_day": stress_day
                }
            
            # For level_1 (moderate stress), check time window
            if notification_type == "level_1" and not self.is_notification_time():
                return {
                    "status": "outside_time_window",
                    "message": "Level 1 notifications only sent between 7-9 AM",
                    "stress_day": stress_day,
                    "current_hour": datetime.now().hour
                }
            
            # Check if we should send notification (2-hour cooldown)
            if not self.should_send_notification(user_id, notification_type):
                return {
                    "status": "cooldown",
                    "message": "Notification sent recently, waiting for cooldown",
                    "stress_day": stress_day
                }
            
            # Log and return notification
            self.log_notification(user_id, notification_type, message, stress_day)
            
            return {
                "status": "notification_sent",
                "notification_type": notification_type,
                "priority": priority,
                "message": message,
                "stress_day": stress_day,
                "sent_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking stress for user {user_id}: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }
    
    def check_all_users(self):
        """
        Check stress levels for all users and send notifications as needed
        
        Returns:
            dict: Summary of notifications sent
        """
        try:
            # Get all users with reports
            result = self.supabase.table("report")\
                .select("id, stress_day")\
                .execute()
            
            if not result.data:
                logger.info("No users found in report table")
                return {
                    "total_users": 0,
                    "notifications_sent": 0,
                    "results": []
                }
            
            notifications_sent = 0
            results = []
            
            for user_report in result.data:
                user_id = user_report["id"]
                notification_result = self.check_user_stress(user_id)
                results.append({
                    "user_id": user_id,
                    "result": notification_result
                })
                
                if notification_result["status"] == "notification_sent":
                    notifications_sent += 1
            
            return {
                "total_users": len(result.data),
                "notifications_sent": notifications_sent,
                "timestamp": datetime.now().isoformat(),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error checking all users: {str(e)}")
            return {
                "status": "error",
                "message": str(e)
            }


def create_notification_log_table():
    """
    SQL to create notification_log table in Supabase
    Run this in Supabase SQL Editor:
    """
    sql = """
    -- Create notification_log table if it doesn't exist
    CREATE TABLE IF NOT EXISTS notification_log (
        log_id BIGSERIAL PRIMARY KEY,
        user_id TEXT NOT NULL,
        notification_type TEXT NOT NULL,
        message TEXT NOT NULL,
        stress_day INTEGER NOT NULL,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Create index for faster queries
    CREATE INDEX IF NOT EXISTS idx_notification_log_user_type 
    ON notification_log(user_id, notification_type, sent_at DESC);
    """
    print("="*70)
    print("CREATE notification_log TABLE")
    print("="*70)
    print("\nRun this SQL in Supabase Dashboard → SQL Editor:\n")
    print(sql)
    print("="*70)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("STRESS NOTIFICATION SYSTEM")
    print("="*70)
    
    # First, show how to create the table
    create_notification_log_table()
    
    print("\n\nAfter creating the table, test the system:")
    print("-"*70)
    
    # Initialize system
    notification_system = StressNotificationSystem()
    
    # Check all users
    print("\n🔍 Checking stress levels for all users...")
    results = notification_system.check_all_users()
    
    print(f"\n📊 Summary:")
    print(f"  Total Users: {results.get('total_users', 0)}")
    print(f"  Notifications Sent: {results.get('notifications_sent', 0)}")
    print(f"  Timestamp: {results.get('timestamp', 'N/A')}")
    
    if results.get('results'):
        print("\n📋 Detailed Results:")
        for result in results.get('results', []):
            user_id = result['user_id']
            status = result['result']['status']
            stress_day = result['result'].get('stress_day', 0)
            print(f"\n  User: {user_id}")
            print(f"  Stress Day: {stress_day}")
            print(f"  Status: {status}")
            if status == "notification_sent":
                print(f"  Priority: {result['result']['priority']}")
                print(f"  Message: {result['result']['message']}")
    
    print("\n" + "="*70)

