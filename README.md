# 🧘 AI Wellness Activity Recommender

A complete AI-powered application that generates personalized wellness tips using multimodal input (text, audio, photo) and AWS Bedrock Claude.

## 📋 Project Structure

```
clean_project/
├── backend/                    # FastAPI Backend Server
│   ├── backend_api.py         # Main FastAPI application
│   ├── model_analyzer.py      # AWS Bedrock Claude integration
│   ├── report.py              # Report generation with Supabase
│   ├── preprocessor.py        # Audio transcription + Emotion detection
│   └── requirements.txt        # Python dependencies
│
└── frontend/                   # React Frontend
    ├── src/
    │   ├── pages/
    │   │   ├── Login.jsx
    │   │   ├── Signup.jsx
    │   │   ├── ProfileForm.jsx
    │   │   └── MoodEntry.jsx
    │   ├── App.jsx
    │   └── main.jsx
    ├── package.json
    ├── vite.config.js
    └── index.html
```

## 🚀 Quick Start

### Backend Setup

cd backend
pip install -r requirements.txt
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
python backend_api.py

Backend: http://localhost:8000

### Frontend Setup

cd frontend
npm install
npm run dev

Frontend: http://localhost:5173

## 📱 Key Features

✅ User Profile Management
✅ Multimodal Input (Text + Audio + Photo)
✅ Audio Transcription (Whisper)
✅ Emotion Detection from Photos
✅ AWS Bedrock Claude AI Analysis
✅ 5 Personalized Wellness Tips
✅ Report Generation & Tracking

## 🔄 User Flow

1. Signup/Login
2. Fill Profile Form → Save to Supabase
3. Enter Daily Mood (Text + Audio + Photo)
4. AI Processing (Transcription + Emotion + Analysis)
5. Display 5 Personalized Wellness Tips

## 📡 Main API Endpoints

POST /api/profile - Save user profile
POST /api/mood - Submit mood entry + get tips

## 🗄️ Database

- Supabase habit table: User lifestyle information
- Supabase report table: Initial and combined reports

## 🔧 Tech Stack

Backend: FastAPI, AWS Bedrock, Whisper, Supabase
Frontend: React, Vite, Axios, Tailwind CSS

## ⚙️ Environment Variables

AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=<key>
AWS_SECRET_ACCESS_KEY=<secret>
SUPABASE_URL=<url>
SUPABASE_KEY=<key>

---
Version: 2.0.0 | Ready to Deploy ✨
