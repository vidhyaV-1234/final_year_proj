-- ============================================
-- Create notification_log table
-- ============================================

-- Create notification_log table if it doesn't exist
CREATE TABLE IF NOT EXISTS notification_log (
    log_id BIGSERIAL PRIMARY KEY,
    id TEXT NOT NULL,
    notification_type TEXT NOT NULL,  -- level_1, level_2, level_3
    message TEXT NOT NULL,
    stress_day INTEGER NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_notification_log_id_type 
ON notification_log(id, notification_type, sent_at DESC);

-- Create index for user lookups
CREATE INDEX IF NOT EXISTS idx_notification_log_id_sent
ON notification_log(id, sent_at DESC);

-- Verify table was created
SELECT 
    table_name, 
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'notification_log'
ORDER BY ordinal_position;

-- Example: View all notifications
-- SELECT * FROM notification_log ORDER BY sent_at DESC LIMIT 10;

-- Example: View notifications for specific user
-- SELECT * FROM notification_log WHERE id = 'your_user_id' ORDER BY sent_at DESC;

