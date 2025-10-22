import os
import json
import boto3
from botocore.exceptions import ClientError
from supabase import create_client, Client
from datetime import datetime

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL","https://cswobvpopxypghwjolnb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY","eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNzd29idnBvcHh5cGdod2pvbG5iIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjA4NzQ5ODMsImV4cCI6MjA3NjQ1MDk4M30.P_E9zrpgOAI-mDVCCSWQDYLbfSXbng67EIApxujhNtQ")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize AWS Bedrock client
BEDROCK_CLIENT = boto3.client("bedrock-runtime", region_name="us-east-1")
MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"

print(f"✓ AWS Bedrock client initialized")
print(f"  → API: AWS Bedrock")
print(f"  → Model: Claude 3.5 Sonnet")

# Define column descriptions for better context (used only for first report) 
COLUMN_DESCRIPTIONS = {
    "id": "User's unique identifier",
    "created_at": "The date and time when the user created their account",
    "screetime_daily": "User's daily screen time measured in hours",
    "job_description": "User's work role or description of their job responsibilities",
    "free_hr_activities": "Activities the user typically engages in during their free time",
    "travelling_hr": "Number of minutes the user spends traveling per day",
    "weekend_mood": "User's typical mood state during weekends",
    "week_day_mood": "User's typical mood state during weekdays",
    "free_hr_mrg": "Number of minutes the user is typically free in the morning",
    "free_hr_eve": "Number of minutes the user is typically free in the evening",
    "sleep_time": "The time when the user typically goes to sleep",
    "preferred_exercise": "Types of physical activities the user prefers",
    "social_preference": "Whether the user prefers solo or group activities",
    "energy_level_rating": "User's self-reported energy levels throughout the day, rated on a scale of 1 to 5",
    "sleep_pattern": "Average number of hours the user sleeps per day",
    "hobbies": "List of the user's hobbies and interests",
    "work_schedule": "Number of hours the user works daily",
    "meal_preferences": "User's dietary preferences and eating schedule",
    "relaxation_methods": "Methods the user typically uses to relax or unwind"
}

def generate_summary_with_prompt(text, prompt_type="first", column_descriptions=None):
    """
    Generate a summary using a custom prompt for the LLM via AWS Bedrock.
    
    Args:
        text: The text to summarize
        prompt_type: "first" for initial report, "combined" for ongoing reports
        column_descriptions: Dictionary mapping column names to their descriptions
    """
    # Add column descriptions context if provided
    column_context = ""
    if column_descriptions:
        column_context = "\n**Data Field Descriptions:**\n"
        for col, desc in column_descriptions.items():
            column_context += f"- {col}: {desc}\n"
    
    if prompt_type == "first":
        system_prompt = """
You are a wellness data analyst. Create a concise, structured summary of the user's habit data.

The summary must include:
1. **General Activity Preferences**
2. **Free Hour Patterns**
3. **Mood Patterns**
4. **Energy Levels**
5. **Social vs Solo Activities**

Keep the summary short, direct, and well-organized.

Do not include:
- Any extra introductions or explanations
- Any markdown headings, tables, emojis, or decorative symbols
- Any meta text like "As a wellness data analyst..." or "Here is the report..."
- Any additional data or commentary outside the summary
-no any other tables or images or any other formatting
"""
    else:  # combined
        system_prompt = """
You are a wellness data analyst. Generate a concise updated summary based on new user activity data and their previous data.

The summary must include:
1. **Activity Trends**
2. **Mood Progression**
3. **Energy & Food Patterns**
4. **Free Hour Patterns**
5. **Consistency**
6. **Areas of Focus**

Keep the summary short, coherent, and focused only on the provided data.

Do not include:
- Any introductions, explanations, or extra commentary
- Any markdown headings, tables, emojis, or decorative symbols
- Any meta text like "As a wellness data analyst..." or "Here is the report..."
- Any additional data or commentary outside the summary
"""


    user_prompt = f"""{column_context}
User Data to Analyze:

{text}

Please provide a detailed, structured report based on the above data."""

    try:
        # Prepare request payload in the native Messages API format
        native_request = {
            "anthropic_version": "bedrock-2023-05-31",  # Required for Claude models
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
            ],
            "max_tokens": 1000,
            "temperature": 0.7
        }
        
        # Invoke the model
        response = BEDROCK_CLIENT.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(native_request)
        )
        
        # Decode the response
        model_response = json.loads(response["body"].read())
        
        # Extract text from the model's response
        # Bedrock returns: {"content": [{"type": "text", "text": "..."}], ...}
        response_text = model_response["content"][0]["text"]
        
        return response_text
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_msg = e.response['Error']['Message']
        print(f"❌ AWS Error: {error_code}")
        print(f"Message: {error_msg}")
        return f"Error generating report: {error_msg}"
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return f"Error generating report: {str(e)}"

def process_user(user_id, preprocessed_data=None):
    """Process user data and generate/update reports
    
    Args:
        user_id: User's unique identifier
        preprocessed_data: (Optional) Preprocessed data from preprocessor.py
                          If provided, uses this instead of fetching from database
    """
    print(f"\n{'='*70}")
    print(f"Processing user ID: {user_id}")
    print(f"{'='*70}\n")
    
    # Initialize variables
    combined_text = ""
    combined_text_preprocessed = ""
    
    # ALWAYS fetch habit data from database (needed for first report)
    print("📝 Fetching user habit/profile data from database...")
    
    user_response = supabase.table("habit").select("*").eq("id", user_id).execute()
    if not user_response.data:
        print("❌ User not found in habit table.")
        return

    # Structure user data for analysis
    for record in user_response.data:
        combined_text += f"\n--- Habit Entry (ID: {record.get('id')}) ---\n"
        for key, value in record.items():
            if key != 'id':  # Skip ID in the text
                combined_text += f"{key.replace('_', ' ').title()}: {value}\n"
    
    # If preprocessed data is provided, also format it for combined report updates
    if preprocessed_data:
        print("📝 Also preparing preprocessed mood data for report update...")
        
        # Format preprocessed data as text
        combined_text_preprocessed = f"""
=== CURRENT SESSION INPUT ===
Timestamp: {datetime.now().isoformat()}

Text Input: {preprocessed_data.get('text', 'Not provided')}

Audio Transcript: {preprocessed_data.get('audio_transcript', 'Not provided')}

Emotion Detected: {preprocessed_data.get('emotion', 'Not detected')}
Emotion Confidence: {preprocessed_data.get('emotion_confidence', 0):.2%}

Emotion Details:
{json.dumps(preprocessed_data.get('emotion_details', {}), indent=2)}

Input Flags:
- Has Text: {preprocessed_data.get('has_text', False)}
- Has Audio: {preprocessed_data.get('has_audio', False)}
- Has Image: {preprocessed_data.get('has_image', False)}
"""

    print("✓ User data prepared\n")

    # Check if a report already exists
    report_response = supabase.table("report").select("*").eq("id", user_id).execute()

    if not report_response.data:
        # New user: create first detailed summary WITH column descriptions
        # Always use habit data (combined_text) for initial profile report
        print("📝 Generating initial user profile report...")
        print("ℹ️  Using habit data with column descriptions for context...\n")
        
        summary = generate_summary_with_prompt(
            combined_text, 
            prompt_type="first",
            column_descriptions=COLUMN_DESCRIPTIONS  # Always use column descriptions for first report
        )
        
        supabase.table("report").insert({
            "id": user_id,
            "1st_report": summary,
            "stress_day": 0,
            "combined_report": None
        }).execute()
        
        print("✅ New user report created successfully!\n")
        print("="*70)
        print("INITIAL REPORT:")
        print("="*70)
        print(summary)
        print("="*70)
        
        # If this is triggered by a mood entry, ALSO update combined_report immediately
        if preprocessed_data and combined_text_preprocessed:
            print("\n📝 First mood entry detected - updating combined_report...")
            print("ℹ️  Adding initial mood data to combined report...\n")
            
            # For first mood entry, combine profile with the mood data
            text_for_summary = f"""
=== INITIAL PROFILE (Baseline) ===
{summary}

=== PREVIOUS ACTIVITY LOGS ===
No previous logs available.

=== NEW ACTIVITY DATA (Current Input from Preprocessor) ===
{combined_text_preprocessed}
"""
            
            first_combined = generate_summary_with_prompt(
                text_for_summary, 
                prompt_type="combined",
                column_descriptions=None
            )
            
            # Update the just-created report with combined_report
            supabase.table("report").update({
                "combined_report": first_combined,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            print("✅ First combined report created successfully!\n")
            print("="*70)
            print("FIRST COMBINED REPORT:")
            print("="*70)
            print(first_combined)
            print("="*70)
        
    else:
        # Existing user: Only update combined report if there's new mood data
        if preprocessed_data and combined_text_preprocessed:
            print("📝 Updating existing user report with new mood data...")
            print("ℹ️  Analyzing based on profile and activity history...\n")
            
            existing_report = report_response.data[0]
            previous_combined = existing_report.get("combined_report", "")
            first_report = existing_report.get("1st_report", "")

            # Combine all data for comprehensive analysis
            text_for_summary = f"""
=== INITIAL PROFILE (Baseline) ===
{first_report}

=== PREVIOUS ACTIVITY LOGS ===
{previous_combined if previous_combined else "No previous logs available."}

=== NEW ACTIVITY DATA (Current Input from Preprocessor) ===
{combined_text_preprocessed}
"""
            
            new_combined = generate_summary_with_prompt(
                text_for_summary, 
                prompt_type="combined",
                column_descriptions=None  # Do NOT use column descriptions for combined report
            )

            # Update only the combined_report column
            supabase.table("report").update({
                "combined_report": new_combined,
                "updated_at": datetime.now().isoformat()
            }).eq("id", user_id).execute()
            
            print("✅ User report updated successfully!\n")
            print("="*70)
            print("UPDATED COMBINED REPORT:")
            print("="*70)
            print(new_combined)
            print("="*70)
        else:
            print("ℹ️  Report already exists, no new mood data to update.")
            print("   Skipping combined report update.")

# Example usage
if __name__ == "__main__":
    print("\n" + "="*70)
    print("USER REPORT GENERATOR WITH CUSTOM AI PROMPTS")
    print("="*70)
    
    user_id = int(input("\nEnter user ID: "))
    process_user(user_id)