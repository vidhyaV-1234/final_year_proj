"""
Stress Notification Scheduler
Runs periodically to check stress levels and send notifications

Run this script using:
1. Manual: python stress_notification_scheduler.py
2. Cron job (Linux/Mac): Every 2 hours between 7-9 AM
   Example crontab entry:
   0 7,9 * * * cd /path/to/backend && python stress_notification_scheduler.py
3. Windows Task Scheduler
4. As a background service
"""
import time
import schedule
from datetime import datetime
import logging
from stress_notification_system import StressNotificationSystem

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stress_notifications.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def run_stress_check():
    """Run stress check for all users"""
    logger.info("="*70)
    logger.info("RUNNING SCHEDULED STRESS CHECK")
    logger.info("="*70)
    
    try:
        notification_system = StressNotificationSystem()
        results = notification_system.check_all_users()
        
        logger.info(f"Total Users Checked: {results.get('total_users', 0)}")
        logger.info(f"Notifications Sent: {results.get('notifications_sent', 0)}")
        
        # Log details for each user
        for result in results.get('results', []):
            user_id = result['user_id']
            status = result['result']['status']
            stress_day = result['result'].get('stress_day', 0)
            
            if status == "notification_sent":
                logger.info(f"✅ Notification sent to user {user_id} (stress_day: {stress_day})")
                logger.info(f"   Priority: {result['result']['priority']}")
                logger.info(f"   Message: {result['result']['message']}")
            elif status == "cooldown":
                logger.info(f"⏳ User {user_id} in cooldown period")
            elif status == "outside_time_window":
                logger.info(f"⏰ User {user_id} outside notification window")
        
        logger.info("="*70 + "\n")
        
    except Exception as e:
        logger.error(f"Error during scheduled check: {str(e)}")

def run_scheduler():
    """Run the scheduler"""
    logger.info("Stress Notification Scheduler Started")
    logger.info("Checking stress levels every 2 hours between 7-9 AM")
    
    # Schedule checks every 2 hours
    schedule.every(2).hours.do(run_stress_check)
    
    # Also run immediately on startup (for testing)
    logger.info("Running initial check...")
    run_stress_check()
    
    # Keep running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute if a job needs to run

if __name__ == "__main__":
    print("\n" + "="*70)
    print("STRESS NOTIFICATION SCHEDULER")
    print("="*70)
    print("\nOptions:")
    print("1. Run one-time check")
    print("2. Run continuous scheduler (every 2 hours)")
    print("="*70)
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        print("\nRunning one-time stress check...\n")
        run_stress_check()
    elif choice == "2":
        print("\nStarting continuous scheduler...")
        print("Press Ctrl+C to stop\n")
        try:
            run_scheduler()
        except KeyboardInterrupt:
            print("\n\nScheduler stopped by user")
    else:
        print("\nInvalid choice. Running one-time check...\n")
        run_stress_check()

