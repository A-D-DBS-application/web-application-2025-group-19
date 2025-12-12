# Deployment Guide for Render.com

This guide will help you deploy the web application to Render.com.

## Prerequisites

1. A GitHub account with this repository
2. A Render.com account (free tier available)

## Deployment Steps

### Option 1: Using render.yaml (Recommended)

1. **Push the code to GitHub** (if not already done)
   ```bash
   git add .
   git commit -m "Add Render.com deployment configuration"
   git push
   ```

2. **Go to Render.com Dashboard**
   - Visit https://dashboard.render.com
   - Sign up or log in

3. **Create New Web Service**
   - Click "New +" → "Blueprint"
   - Connect your GitHub repository
   - Select the repository: `web-application-2025-group-19`
   - Render will automatically detect the `render.yaml` file

4. **Configure Environment Variables**
   After the service is created, go to Environment and set:
   - `MAPBOX_ACCESS_TOKEN`: Your Mapbox API token (already in code, but you can override)
   - `SECRET_KEY`: A secure random string (Render can generate this)
   - `USE_SQLITE`: Set to `0` (use PostgreSQL)
   - `PG_DRIVER`: Set to `psycopg2`

5. **Database Setup**
   - If using Render's PostgreSQL: The `render.yaml` includes a database service
   - If using Supabase: Set these environment variables:
     - `SUPABASE_USER`: Your Supabase username
     - `SUPABASE_PASSWORD`: Your Supabase password
     - `SUPABASE_HOST`: Your Supabase host
     - `SUPABASE_DB`: Your Supabase database name

6. **Deploy**
   - Render will automatically deploy when you push to the main branch
   - Or click "Manual Deploy" → "Deploy latest commit"

### Option 2: Manual Setup (Without render.yaml)

1. **Create Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository

2. **Configure Settings**
   - **Name**: `web-application-2025-group-19`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app --bind 0.0.0.0:$PORT`

3. **Set Environment Variables** (same as Option 1)

4. **Create Database** (if using Render's PostgreSQL)
   - Click "New +" → "PostgreSQL"
   - Choose free tier
   - Note the connection details
   - Add `DATABASE_URL` to your web service environment variables

## Post-Deployment

1. **Run Database Migrations**
   - After first deployment, you may need to run migrations
   - Use Render's Shell feature or add a build script

2. **Verify Deployment**
   - Visit your Render URL (e.g., `https://web-application-2025-group-19.onrender.com`)
   - Test the application functionality

## Troubleshooting

- **Build fails**: Check that all dependencies are in `requirements.txt`
- **Database connection errors**: Verify `DATABASE_URL` or Supabase credentials
- **App crashes**: Check logs in Render dashboard → Logs tab
- **Port issues**: Ensure using `$PORT` environment variable (Render sets this automatically)

## Notes

- Free tier services spin down after 15 minutes of inactivity
- First request after spin-down may take 30-60 seconds
- Consider upgrading to paid tier for always-on service

