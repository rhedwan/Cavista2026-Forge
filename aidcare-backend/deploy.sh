#!/bin/bash

# AidCare Backend - Railway Deployment Script

echo "🚂 AidCare Backend - Railway Deployment"
echo "========================================"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found!"
    echo ""
    echo "Installing Railway CLI..."
    npm install -g @railway/cli

    if [ $? -ne 0 ]; then
        echo "❌ Failed to install Railway CLI"
        echo "Please install manually: npm install -g @railway/cli"
        exit 1
    fi
    echo "✅ Railway CLI installed!"
fi

echo "✅ Railway CLI found"
echo ""

# Check if logged in
railway whoami &> /dev/null
if [ $? -ne 0 ]; then
    echo "🔐 You need to login to Railway..."
    railway login

    if [ $? -ne 0 ]; then
        echo "❌ Login failed"
        exit 1
    fi
fi

echo "✅ Logged in to Railway"
echo ""

# Check if project is linked
if [ ! -f ".railway" ] && [ ! -d ".railway" ]; then
    echo "🔗 No Railway project linked. Let's create one!"
    echo ""
    railway init

    if [ $? -ne 0 ]; then
        echo "❌ Failed to initialize Railway project"
        exit 1
    fi
    echo "✅ Railway project initialized!"
    echo ""
fi

# Check environment variables
echo "🔍 Checking environment variables..."
echo ""

# Read GOOGLE_API_KEY from .env if exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

if [ -z "$GOOGLE_API_KEY" ]; then
    echo "⚠️  GOOGLE_API_KEY not found in .env"
    echo ""
    read -p "Enter your Google API Key: " GOOGLE_API_KEY

    if [ -z "$GOOGLE_API_KEY" ]; then
        echo "❌ API Key is required"
        exit 1
    fi
fi

echo "📝 Setting environment variables..."
railway variables set GOOGLE_API_KEY="$GOOGLE_API_KEY"
railway variables set MAX_GEMINI_REQUESTS_PER_MINUTE=50
railway variables set MAX_GEMINI_REQUESTS_PER_DAY=1000
railway variables set ENABLE_GEMINI_CACHING=true
railway variables set CACHE_TTL_SECONDS=3600
railway variables set GEMINI_MODEL_EXTRACTION="gemini-3-flash-preview"
railway variables set GEMINI_MODEL_RECOMMEND="gemini-3-flash-preview"
railway variables set GEMINI_MODEL_CLINICAL_EXTRACT="gemini-3-pro-preview"
railway variables set GEMINI_MODEL_CLINICAL_SUPPORT="gemini-3-pro-preview"

echo "✅ Environment variables set!"
echo ""

# Deploy
echo "🚀 Deploying to Railway..."
echo ""
railway up

if [ $? -ne 0 ]; then
    echo "❌ Deployment failed"
    echo "Check logs with: railway logs"
    exit 1
fi

echo ""
echo "✅ Deployment successful!"
echo ""

# Get domain
echo "📋 Your deployment URL:"
railway domain

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Test your API: railway open"
echo "2. View logs: railway logs"
echo "3. Check health: curl \$(railway domain)/health"
echo "4. Copy the URL and update your frontend .env.local:"
echo "   NEXT_PUBLIC_FASTAPI_URL=<your-railway-url>"
echo ""
