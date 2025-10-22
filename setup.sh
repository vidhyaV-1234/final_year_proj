#!/bin/bash

echo "🚀 Setting up AI Wellness Activity Recommender..."
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backend setup
echo -e "${BLUE}=== BACKEND SETUP ===${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}✓ Backend setup complete!${NC}"
echo ""

# Frontend setup
echo -e "${BLUE}=== FRONTEND SETUP ===${NC}"
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    npm install
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

echo -e "${GREEN}✓ Frontend setup complete!${NC}"
echo ""

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "To start the application:"
echo -e "${YELLOW}Terminal 1 (Backend):${NC}"
echo "cd backend && source venv/bin/activate && python backend_api.py"
echo ""
echo -e "${YELLOW}Terminal 2 (Frontend):${NC}"
echo "cd frontend && npm run dev"
echo ""
echo -e "Backend: ${BLUE}http://localhost:8000${NC}"
echo -e "Frontend: ${BLUE}http://localhost:5173${NC}"
