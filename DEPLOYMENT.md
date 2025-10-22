# 🚢 Deployment Guide

## Prerequisites

- AWS Account with Bedrock access
- Supabase account
- Git account (for CI/CD)

## Environment Variables Required

```
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
PORT=8000 (optional)
```

## Backend Deployment Options

### Option 1: Railway (Recommended)

1. Push code to GitHub
2. Connect Railway to your GitHub repo
3. Set environment variables in Railway dashboard
4. Deploy!

### Option 2: Render

1. Push code to GitHub
2. Create new Web Service on render.com
3. Connect GitHub repo
4. Set environment variables
5. Deploy!

### Option 3: AWS EC2

```bash
# SSH into EC2
ssh -i your-key.pem ec2-user@your-instance

# Install dependencies
sudo yum update
sudo yum install python3 python3-pip

# Clone repo and setup
git clone your-repo-url
cd clean_project/backend
pip install -r requirements.txt

# Set environment variables
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export SUPABASE_URL=your-url
export SUPABASE_KEY=your-key

# Run with PM2 for persistence
npm install -g pm2
pm2 start "python backend_api.py" --name "wellness-api"
pm2 startup
pm2 save
```

## Frontend Deployment Options

### Option 1: Vercel

1. Push code to GitHub
2. Import project on vercel.com
3. Set environment variables:
   - VITE_API_URL=http://your-backend-url:8000
4. Deploy!

### Option 2: Netlify

1. Push code to GitHub
2. Import project on netlify.com
3. Build command: `npm run build`
4. Publish directory: `dist`
5. Set environment variables
6. Deploy!

### Option 3: GitHub Pages

```bash
cd frontend
npm run build
# Push dist folder to GitHub Pages
```

## Environment Variables for Frontend

Create `.env` file in frontend folder:

```
VITE_API_URL=http://localhost:8000
```

For production:
```
VITE_API_URL=https://your-backend-url.com
```

## CI/CD Pipeline Example (GitHub Actions)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Deploy Backend
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd clean_project/backend
            git pull origin main
            pip install -r requirements.txt
            pm2 restart wellness-api
      
      - name: Deploy Frontend
        run: |
          cd frontend
          npm install
          npm run build
```

## Database Migration

### Supabase Setup

1. Create Supabase project
2. Create tables:

```sql
-- habit table
CREATE TABLE habit (
  id TEXT PRIMARY KEY,
  screetime_daily FLOAT,
  job_description TEXT,
  free_hr_activities TEXT,
  travelling_hr INT,
  weekend_mood TEXT,
  week_day_mood TEXT,
  free_hr_mrg INT,
  free_hr_eve INT,
  sleep_time TIME,
  preferred_exercise TEXT,
  social_preference TEXT,
  energy_level_rating INT,
  sleep_pattern FLOAT,
  hobbies TEXT,
  work_schedule FLOAT,
  meal_preferences TEXT,
  relaxation_methods TEXT,
  created_at TIMESTAMP
);

-- report table
CREATE TABLE report (
  id TEXT PRIMARY KEY,
  1st_report TEXT,
  combined_report TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Security Checklist

- [ ] Set strong environment variables
- [ ] Enable HTTPS
- [ ] Configure CORS for specific domains
- [ ] Implement proper JWT token verification
- [ ] Enable database encryption
- [ ] Set up rate limiting
- [ ] Monitor API usage
- [ ] Regular backups enabled

## Monitoring

### Backend Monitoring

Use:
- PM2 Plus (for process monitoring)
- CloudWatch (AWS)
- Sentry (error tracking)
- DataDog (APM)

### Frontend Monitoring

Use:
- Sentry
- Bugsnag
- LogRocket

## Scaling Considerations

1. Use CDN for frontend static files
2. Implement caching for API responses
3. Use database connection pooling
4. Consider horizontal scaling for backend
5. Implement background job queue for heavy processing

## Support

For deployment issues, check:
1. Environment variables are set correctly
2. AWS/Supabase credentials are valid
3. Ports are open and accessible
4. Database migrations completed
5. Dependencies installed correctly

