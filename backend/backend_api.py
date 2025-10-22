"""
FastAPI Backend for Wellness Activity Recommender
Serves HTML/JS frontend and provides API endpoints for AI analysis via AWS Bedrock Claude
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from pathlib import Path
import json
from datetime import datetime
import logging
from typing import Optional
import jwt

# Import local modules
try:
    from model_analyzer import ModelAnalyzer
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️ Could not import ModelAnalyzer: {str(e)}")
    ModelAnalyzer = None

try:
    from report import process_user
except Exception as e:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"⚠️ Could not import process_user: {str(e)}")
    def process_user(*args, **kwargs):
        pass

# Removed: MultimodalPreprocessor causes threading crash with torch
# Only needed for mood processing endpoints, not auth
MultimodalPreprocessor = None

from supabase import create_client, Client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Supabase - REQUIRED environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables are required")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize FastAPI app
app = FastAPI(
    title="Wellness Activity Recommender API",
    description="AI-powered personalized activity suggestions using AWS Bedrock Claude",
    version="2.0.0"
)

# Add CORS middleware - configure allowed origins via environment variable
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SCRIPT_DIR = Path(__file__).parent / "script"
TEMP_DIR = Path(__file__).parent / "temp_uploads"
TEMP_DIR.mkdir(exist_ok=True)

# Initialize models
preprocessor = None
analyzer = None

def initialize_models():
    """Initialize preprocessor and analyzer"""
    global preprocessor, analyzer
    try:
        logger.info("Initializing models...")
        
        # Initialize preprocessor with error handling
        try:
            from preprocessor import MultimodalPreprocessor
            preprocessor = MultimodalPreprocessor(whisper_model="base")
            logger.info("✓ Preprocessor initialized (Whisper)")
        except Exception as e:
            logger.warning(f"Preprocessor initialization failed: {str(e)}")
            preprocessor = None
        
        # Initialize analyzer with error handling
        try:
            from model_analyzer import ModelAnalyzer
            analyzer = ModelAnalyzer(
                supabase_url=SUPABASE_URL,
                supabase_key=SUPABASE_KEY
            )
            logger.info("✓ Analyzer initialized (AWS Bedrock Claude 3.5 Sonnet)")
        except Exception as e:
            logger.warning(f"Analyzer initialization failed: {str(e)}")
            analyzer = None
        
        if preprocessor and analyzer:
            logger.info("✓ All ML models initialized successfully")
        else:
            logger.warning("⚠️ Some ML models failed to initialize - will use fallback analysis")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error initializing models: {str(e)}")
        return False
# Add these imports at the top of backend_api.py
from pydantic import BaseModel, EmailStr
import hashlib
import secrets
import jwt as pyjwt
from datetime import timedelta

# JWT Configuration - REQUIRED environment variable
SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET environment variable is required")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Pydantic models for auth
class UserRegister(BaseModel):
    id: str
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Helper functions
def hash_password(password: str) -> str:
    # Use SHA-256 with salt for simplicity
    salt = secrets.token_hex(16)
    return f"{salt}:{hashlib.sha256((password + salt).encode()).hexdigest()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        # Check if it's the new format (salt:hash)
        if ":" in hashed_password:
            salt, hash_part = hashed_password.split(":", 1)
            return hashlib.sha256((plain_password + salt).encode()).hexdigest() == hash_part
        else:
            # Old bcrypt format - for now, just return False to force re-registration
            # In production, you'd want to migrate old passwords
            return False
    except:
        return False

def create_access_token(user_id: str) -> str:
    """Create JWT token with user_id as string"""
    expire = datetime.now() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": str(user_id), "exp": expire}  # Ensure it's a string
    return pyjwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ============================================
# AUTHENTICATION ENDPOINTS
# ============================================

@app.post("/api/auth/register")
async def register(user: UserRegister):
    """Register a new user"""
    try:
        logger.info(f"Registering new user: {user.email}")
        
        # Check if id already exists
        existing_id = supabase.table("users").select("*").eq("id", user.id).execute()
        if existing_id.data:
            raise HTTPException(status_code=400, detail="User ID already taken")
        
        # Check if email already exists
        existing_email = supabase.table("users").select("*").eq("email", user.email).execute()
        if existing_email.data:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user in Supabase
        user_data = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "password": hash_password(user.password),
            "created_at": datetime.now().isoformat()
        }
        
        response = supabase.table("users").insert(user_data).execute()
        
        logger.info(f"User registered successfully: {user.email}")
        return JSONResponse({
            "status": "success",
            "message": "User registered successfully"
        })
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/api/auth/login")
async def login(credentials: UserLogin):
    """Login user and return JWT token"""
    try:
        logger.info(f"Login attempt for: {credentials.email}")
        
        # Fetch user from Supabase
        user_response = supabase.table("users").select("*").eq("email", credentials.email).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        user = user_response.data[0]
        
        # Verify password
        if not verify_password(credentials.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Get user id
        user_id = user["id"]
        
        # Check if user has profile
        try:
            profile_response = supabase.table("habit").select("id").eq("id", user_id).execute()
            has_profile = bool(profile_response.data)
            logger.info(f"Profile check for {user_id}: {has_profile}")
        except Exception as e:
            logger.warning(f"Profile check failed: {str(e)}")
            has_profile = False
        
        # Create JWT token with user id
        token = create_access_token(user_id)
        
        logger.info(f"Login successful for: {credentials.email} (id: {user_id})")
        return JSONResponse({
            "token": token,
            "id": user_id,
            "hasProfile": has_profile,
            "user": {
                "id": user_id,
                "email": user["email"],
                "name": user["name"],
                "hasProfile": has_profile
            }
        })
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# Update the verify_token function to decode JWT properly
def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """Verify JWT token from header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        # Extract token from "Bearer <token>"
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        
        # Decode JWT token
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return {"user_id": email, "token": token}
        
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/api/auth/me")
async def get_current_user(user_id_obj: dict = Depends(verify_token)):
    """Get current user information"""
    try:
        user_id = user_id_obj["user_id"]
        
        # Get user from database by id
        user_response = supabase.table("users").select("*").eq("id", user_id).execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = user_response.data[0]
        
        # Check if user has profile
        try:
            profile_response = supabase.table("habit").select("id").eq("id", user_id).execute()
            has_profile = bool(profile_response.data)
        except Exception as e:
            logger.warning(f"Profile check failed: {str(e)}")
            has_profile = False
        
        return JSONResponse({
            "id": user_id,
            "email": user["email"],
            "name": user["name"],
            "hasProfile": has_profile
        })
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting user info: {str(e)}")

# Update the verify_token function to decode JWT properly
def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """Verify JWT token from header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        # Extract token from "Bearer <token>"
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        
        # Decode JWT token
        payload = pyjwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        return {"user_id": email, "token": token}
        
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")
# Initialize on startup
@app.on_event("startup")
async def startup_event():
    """Initialize models on startup"""
    if not initialize_models():
        logger.warning("Models not initialized at startup - will try on first request")

def verify_token(authorization: Optional[str] = Header(None)) -> dict:
    """Verify JWT token from header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    try:
        # Extract token from "Bearer <token>"
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization scheme")
        
        # Verify with Supabase (simplified - in production use proper JWT verification)
        # For now, we'll treat the token as user_id
        return {"user_id": token, "token": token}
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

# ============================================
# STATIC FILES - SERVE HTML/JS FRONTEND
# ============================================

@app.get("/")
async def root():
    """Redirect to API info"""
    return {"message": "Wellness Activity Recommender API", "version": "2.0.0"}

# Mount static files from script folder
if SCRIPT_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(SCRIPT_DIR), html=True), name="frontend")
    logger.info(f"✓ Frontend mounted from {SCRIPT_DIR}")
else:
    logger.warning(f"⚠️ Script directory not found: {SCRIPT_DIR}")

# ============================================
# HEALTH CHECK ENDPOINTS
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "service": "wellness-recommender-api",
        "models": {
            "preprocessor": "Whisper (Audio + Emotion)",
            "analyzer": "AWS Bedrock Claude 3.5 Sonnet",
            "region": "us-east-1"
        }
    }

# ============================================
# PROFILE ENDPOINTS

@app.post("/api/profile")
async def save_profile(
    id: str = Form(...),
    user_id_obj: dict = Depends(verify_token),
    screetime_daily: str = Form(...),
    job_description: str = Form(...),
    free_hr_activities: str = Form(...),
    travelling_hr: str = Form(...),
    weekend_mood: str = Form(...),
    week_day_mood: str = Form(...),
    free_hr_mrg: str = Form(...),
    free_hr_eve: str = Form(...),
    sleep_time: str = Form(...),
    preferred_exercise: str = Form(...),
    social_preference: str = Form(...),
    energy_level_rating: str = Form(...),
    sleep_pattern: str = Form(...),
    hobbies: str = Form(...),
    work_schedule: str = Form(...),
    meal_preferences: str = Form(...),
    relaxation_methods: str = Form(...)
):
    """Save user profile to Supabase habit table and generate initial report"""
    try:
        # Use the id from the form parameter directly
        logger.info(f"Saving profile for user {id}")
        
        # Prepare profile data
        profile_data = {
            "id": id,
            "screetime_daily": screetime_daily,
            "job_description": job_description,
            "free_hr_activities": free_hr_activities,
            "travelling_hr": travelling_hr,
            "weekend_mood": weekend_mood,
            "week_day_mood": week_day_mood,
            "free_hr_mrg": free_hr_mrg,
            "free_hr_eve": free_hr_eve,
            "sleep_time": sleep_time,
            "preferred_exercise": preferred_exercise,
            "social_preference": social_preference,
            "energy_level_rating": energy_level_rating,
            "sleep_pattern": sleep_pattern,
            "hobbies": hobbies,
            "work_schedule": work_schedule,
            "meal_preferences": meal_preferences,
            "relaxation_methods": relaxation_methods,
            "created_at": datetime.now().isoformat()
        }
        
        # Save to Supabase habit table
        response = supabase.table("habit").upsert(profile_data).execute()
        logger.info(f"Profile saved successfully for user {id}")
        
        # Generate initial report without preprocessed data
        logger.info(f"Generating initial report for user {id}")
        process_user(id, preprocessed_data=None)
        
        return JSONResponse({
            "status": "success",
            "message": "Profile saved successfully",
            "user_id": id,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error saving profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Profile save error: {str(e)}")

@app.post("/api/mood")
async def submit_mood(
    id: str = Form(...),
    user_id_obj: dict = Depends(verify_token),
    mood_text: str = Form(...),
    mood_audio: UploadFile = File(None),
    mood_image: UploadFile = File(None)
):
    """Submit mood entry with text, audio, and image - full ML processing"""
    try:
        # Use the id from the form parameter directly
        logger.info(f"Processing mood entry for user: {id}")
        
        # Save uploaded files (if provided)
        audio_path = None
        image_path = None
        
        if mood_audio and mood_audio.filename:
            audio_path = TEMP_DIR / f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{mood_audio.filename}"
            with open(audio_path, "wb") as f:
                f.write(await mood_audio.read())
            logger.info(f"Audio file saved: {audio_path}")
        
        if mood_image and mood_image.filename:
            image_path = TEMP_DIR / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{mood_image.filename}"
            with open(image_path, "wb") as f:
                f.write(await mood_image.read())
            logger.info(f"Image file saved: {image_path}")
        
        # Try to use ML models if available
        if preprocessor and analyzer:
            logger.info("Using ML models for mood analysis")
            try:
                # Preprocess with ML models
                # Note: analyze=True means preprocessor will automatically:
                # 1. Call analyzer.analyze(id, preprocessed_data)
                # 2. Call process_user(id, preprocessed_data) to update report
                preprocessed_data = preprocessor.preprocess(
                    audio_path=str(audio_path) if audio_path else None,
                    image_path=str(image_path) if image_path else None,
                    text_input=mood_text,
                    user_id=id,
                    analyze=True
                )
                
                # Extract actual recommendations from analysis result
                analysis_result = preprocessed_data.get("analysis_result", {})
                
                # Debug logging
                logger.info(f"Preprocessed data keys: {list(preprocessed_data.keys())}")
                logger.info(f"Analysis result: {analysis_result is not None}")
                
                if analysis_result:
                    logger.info(f"Analysis result keys: {list(analysis_result.keys())}")
                    rec_preview = str(analysis_result.get('analysis', ''))[:100]
                    logger.info(f"Recommendations preview: {rec_preview}...")
                    recommendations = analysis_result.get("analysis", "")
                else:
                    logger.warning("⚠️ No analysis_result found - analysis may have failed")
                    recommendations = ""
                
                # Fallback if no recommendations generated
                if not recommendations or recommendations == "":
                    recommendations = "Analysis in progress - recommendations will be available in your report shortly."
                    logger.warning("Using fallback recommendation message")
                
                # Save mood entry to database
                mood_data = {
                    "id": id,
                    "mood_text": mood_text,
                    "audio_transcript": preprocessed_data.get("audio_transcript", ""),
                    "emotion": preprocessed_data.get("emotion", ""),
                    "emotion_confidence": preprocessed_data.get("emotion_confidence", 0),
                    "recommendations": recommendations,
                    "created_at": datetime.now().isoformat()
                }
                
                supabase.table("mood_entries").insert(mood_data).execute()
                logger.info("Mood entry saved to database and report updated")
                
                return JSONResponse({
                    "status": "success",
                    "message": "Mood processed successfully with ML models and report updated",
                    "data": {
                        "user_id": id,
                        "mood_text": mood_text,
                        "audio_transcript": preprocessed_data.get("audio_transcript", ""),
                        "emotion": preprocessed_data.get("emotion", ""),
                        "emotion_confidence": preprocessed_data.get("emotion_confidence", 0),
                        "recommendations": recommendations,
                        "mood": analysis_result.get("mood", "") if analysis_result else "",
                        "stress_level": analysis_result.get("stress_level", 0) if analysis_result else 0,
                        "stress_day": analysis_result.get("stress_day", 0) if analysis_result else 0,
                        "stress_alert": analysis_result.get("stress_alert", None) if analysis_result else None,
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
            except Exception as ml_error:
                logger.warning(f"ML processing failed, falling back to simple analysis: {str(ml_error)}")
        
        # Fallback to simple analysis
        logger.info("Using simple mood analysis (ML models not available)")
        mood_analysis = analyze_mood_text(mood_text)
        
        # Create preprocessed data structure for report generation
        preprocessed_data = {
            "text": mood_text,
            "audio_transcript": "Audio processing not available",
            "emotion": mood_analysis["emotion"],
            "emotion_confidence": mood_analysis["confidence"],
            "emotion_details": {},
            "has_text": True,
            "has_audio": False,
            "has_image": False
        }
        
        # Save mood entry to database
        mood_data = {
            "id": id,
            "mood_text": mood_text,
            "audio_transcript": "Audio processing not available",
            "emotion": mood_analysis["emotion"],
            "emotion_confidence": mood_analysis["confidence"],
            "recommendations": str(mood_analysis["recommendations"]),
            "created_at": datetime.now().isoformat()
        }
        
        try:
            supabase.table("mood_entries").insert(mood_data).execute()
            logger.info("Mood entry saved to database")
        except Exception as e:
            logger.warning(f"Could not save to database: {str(e)}")
        
        # Update report with the mood data (fallback case)
        try:
            logger.info(f"Updating report for user {id} with fallback mood data")
            process_user(id, preprocessed_data=preprocessed_data)
            logger.info("Report updated successfully in fallback mode")
        except Exception as e:
            logger.warning(f"Could not update report: {str(e)}")
        
        return JSONResponse({
            "status": "success",
            "message": "Mood processed successfully and report updated",
            "data": {
                "user_id": id,
                "mood_text": mood_text,
                "audio_transcript": "Audio processing not available",
                "emotion": mood_analysis["emotion"],
                "emotion_confidence": mood_analysis["confidence"],
                "recommendations": mood_analysis["recommendations"],
                "timestamp": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error processing mood: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Mood processing error: {str(e)}")

def analyze_mood_text(text: str) -> dict:
    """Simple mood analysis based on keywords"""
    text_lower = text.lower()
    
    # Basic emotion detection
    positive_words = ["happy", "good", "great", "amazing", "wonderful", "excited", "joy", "love", "fantastic"]
    negative_words = ["sad", "bad", "terrible", "awful", "angry", "frustrated", "hate", "depressed", "anxious"]
    neutral_words = ["okay", "fine", "normal", "average", "neutral"]
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    neutral_count = sum(1 for word in neutral_words if word in text_lower)
    
    if positive_count > negative_count and positive_count > neutral_count:
        emotion = "Positive"
        confidence = min(0.8, 0.5 + (positive_count * 0.1))
    elif negative_count > positive_count and negative_count > neutral_count:
        emotion = "Negative"
        confidence = min(0.8, 0.5 + (negative_count * 0.1))
    else:
        emotion = "Neutral"
        confidence = 0.6
    
    # Basic recommendations
    if emotion == "Positive":
        recommendations = [
            "Keep up the great energy! Consider sharing your positive mood with others.",
            "This is a perfect time to tackle challenging tasks or help someone else.",
            "Consider journaling about what's making you feel good today.",
            "Use this positive energy for physical activity or creative projects.",
            "Share your happiness - it's contagious and benefits everyone around you."
        ]
    elif emotion == "Negative":
        recommendations = [
            "Take some deep breaths and remember this feeling is temporary.",
            "Consider talking to a friend or family member about how you're feeling.",
            "Try some gentle physical activity like walking or stretching.",
            "Practice self-care with activities you enjoy.",
            "Consider professional support if these feelings persist."
        ]
    else:
        recommendations = [
            "A neutral mood is a good foundation - consider what might bring you joy today.",
            "Try something new or different to add some excitement to your day.",
            "Connect with others - social interaction can boost your mood.",
            "Consider what activities usually make you feel more positive.",
            "Take a moment to appreciate the small things around you."
        ]
    
    return {
        "emotion": emotion,
        "confidence": confidence,
        "recommendations": recommendations
    }

# ============================================
# API ENDPOINTS FOR ANALYSIS
# ============================================

@app.post("/api/analyze-text")
async def analyze_text(
    user_id: str = Form(...),
    text_input: str = Form(...),
    emotion: str = Form(default=""),
    emotion_confidence: float = Form(default=0.0)
):
    """Analyze text input and generate recommendations"""
    try:
        if not analyzer:
            initialize_models()
        
        logger.info(f"Analyzing text for user {user_id}")
        
        # Prepare preprocessed data
        preprocessed_data = {
            "text": text_input,
            "audio_transcript": "",
            "emotion": emotion or "Neutral",
            "emotion_confidence": emotion_confidence,
            "emotion_details": {},
            "has_text": True,
            "has_audio": False,
            "has_image": False
        }
        
        # Analyze
        result = analyzer.analyze(user_id, preprocessed_data)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "user_id": user_id,
                "analysis": result["analysis"],
                "timestamp": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing text: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")

@app.post("/api/analyze-audio")
async def analyze_audio(
    user_id: str = Form(...),
    audio_file: UploadFile = File(...)
):
    """Analyze audio file and generate recommendations"""
    try:
        if not preprocessor or not analyzer:
            initialize_models()
        
        logger.info(f"Analyzing audio for user {user_id}")
        
        # Save uploaded file
        file_path = TEMP_DIR / f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{audio_file.filename}"
        with open(file_path, "wb") as f:
            f.write(await audio_file.read())
        
        # Preprocess audio
        preprocessed_data = preprocessor.preprocess(
            audio_path=str(file_path),
            image_path=None,
            text_input=None
        )
        
        # Analyze
        result = analyzer.analyze(user_id, preprocessed_data)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "user_id": user_id,
                "audio_transcript": preprocessed_data.get("audio_transcript", ""),
                "emotion": preprocessed_data.get("emotion", ""),
                "emotion_confidence": preprocessed_data.get("emotion_confidence", 0),
                "analysis": result["analysis"],
                "timestamp": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Audio analysis error: {str(e)}")

@app.post("/api/analyze-photo")
async def analyze_photo(
    user_id: str = Form(...),
    photo_file: UploadFile = File(...)
):
    """Analyze photo (emotion detection) and generate recommendations"""
    try:
        if not preprocessor or not analyzer:
            initialize_models()
        
        logger.info(f"Analyzing photo for user {user_id}")
        
        # Save uploaded file
        file_path = TEMP_DIR / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo_file.filename}"
        with open(file_path, "wb") as f:
            f.write(await photo_file.read())
        
        # Preprocess photo (emotion detection)
        preprocessed_data = preprocessor.preprocess(
            audio_path=None,
            image_path=str(file_path),
            text_input=None
        )
        
        # Analyze
        result = analyzer.analyze(user_id, preprocessed_data)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "user_id": user_id,
                "emotion": preprocessed_data.get("emotion", ""),
                "emotion_confidence": preprocessed_data.get("emotion_confidence", 0),
                "emotion_details": preprocessed_data.get("emotion_details", {}),
                "analysis": result["analysis"],
                "timestamp": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing photo: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Photo analysis error: {str(e)}")

@app.post("/api/analyze-multimodal")
async def analyze_multimodal(
    user_id: str = Form(...),
    text_input: str = Form(default=""),
    audio_file: UploadFile = File(default=None),
    photo_file: UploadFile = File(default=None)
):
    """Analyze multimodal input (text + audio + photo) and generate recommendations"""
    try:
        if not preprocessor or not analyzer:
            initialize_models()
        
        logger.info(f"Analyzing multimodal input for user {user_id}")
        
        audio_path = None
        image_path = None
        
        # Save audio if provided
        if audio_file:
            audio_path = TEMP_DIR / f"audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{audio_file.filename}"
            with open(audio_path, "wb") as f:
                f.write(await audio_file.read())
        
        # Save photo if provided
        if photo_file:
            image_path = TEMP_DIR / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{photo_file.filename}"
            with open(image_path, "wb") as f:
                f.write(await photo_file.read())
        
        # Preprocess all inputs
        preprocessed_data = preprocessor.preprocess(
            audio_path=str(audio_path) if audio_path else None,
            image_path=str(image_path) if image_path else None,
            text_input=text_input if text_input else None
        )
        
        # Analyze
        result = analyzer.analyze(user_id, preprocessed_data)
        
        return JSONResponse({
            "status": "success",
            "data": {
                "user_id": user_id,
                "text_input": text_input,
                "audio_transcript": preprocessed_data.get("audio_transcript", ""),
                "emotion": preprocessed_data.get("emotion", ""),
                "emotion_confidence": preprocessed_data.get("emotion_confidence", 0),
                "analysis": result["analysis"],
                "timestamp": datetime.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error analyzing multimodal input: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Multimodal analysis error: {str(e)}")

@app.post("/api/update-report")
async def update_report(user_id: str = Form(...)):
    """Update user report"""
    try:
        logger.info(f"Updating report for user {user_id}")
        
        # Process user and generate report
        process_user(user_id)
        
        return JSONResponse({
            "status": "success",
            "message": f"Report updated for user {user_id}",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error updating report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report update error: {str(e)}")

# ============================================
# STRESS NOTIFICATION ENDPOINTS
# ============================================

@app.get("/api/check-stress/{user_id}")
async def check_user_stress(user_id: str):
    """Check stress level and get notification for a specific user"""
    try:
        from stress_notification_system import StressNotificationSystem
        
        logger.info(f"Checking stress level for user {user_id}")
        
        notification_system = StressNotificationSystem()
        result = notification_system.check_user_stress(user_id)
        
        return JSONResponse({
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error checking stress: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stress check error: {str(e)}")

@app.get("/api/stress-notifications/all")
async def check_all_stress_levels():
    """Check stress levels for all users and send notifications"""
    try:
        from stress_notification_system import StressNotificationSystem
        
        logger.info("Checking stress levels for all users")
        
        notification_system = StressNotificationSystem()
        results = notification_system.check_all_users()
        
        return JSONResponse({
            "status": "success",
            "data": results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error checking all stress levels: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stress check error: {str(e)}")

@app.get("/api/stress-notifications/history/{user_id}")
async def get_notification_history(user_id: str, limit: int = 10):
    """Get notification history for a user"""
    try:
        logger.info(f"Fetching notification history for user {user_id}")
        
        result = supabase.table("notification_log")\
            .select("*")\
            .eq("id", user_id)\
            .order("sent_at", desc=True)\
            .limit(limit)\
            .execute()
        
        return JSONResponse({
            "status": "success",
            "data": {
                "user_id": user_id,
                "notifications": result.data,
                "count": len(result.data)
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching notification history: {str(e)}")
        raise HTTPException(status_code=500, detail=f"History fetch error: {str(e)}")

# ============================================
# INFO ENDPOINTS
# ============================================

@app.get("/api/info")
async def api_info():
    """Get API information"""
    return {
        "name": "Wellness Activity Recommender API",
        "version": "2.0.0",
        "description": "AI-powered personalized activity suggestions using AWS Bedrock Claude",
        "endpoints": {
            "frontend": "/app - HTML/JS interface",
            "health": "/health - Health check",
            "profile": "POST /api/profile - Save user profile",
            "mood": "POST /api/mood - Submit mood entry",
            "text_analysis": "POST /api/analyze-text",
            "audio_analysis": "POST /api/analyze-audio",
            "photo_analysis": "POST /api/analyze-photo",
            "multimodal_analysis": "POST /api/analyze-multimodal",
            "update_report": "POST /api/update-report"
        },
        "models": {
            "preprocessor": "OpenAI Whisper (Audio Transcription + Emotion Detection)",
            "analyzer": "AWS Bedrock Claude 3.5 Sonnet",
            "model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
        },
        "features": [
            "Text analysis",
            "Audio transcription and emotion detection",
            "Photo emotion detection",
            "Multimodal analysis",
            "User profile management",
            "Personalized recommendations",
            "Report generation"
        ]
    }

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8000))
    
    logger.info("🚀 Starting Wellness Activity Recommender API...")
    logger.info(f"📍 Frontend: http://localhost:{port}/app")
    logger.info(f"📍 API: http://localhost:{port}/api")
    logger.info(f"📍 Health: http://localhost:{port}/health")
    logger.info(f"📍 Info: http://localhost:{port}/api/info")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
