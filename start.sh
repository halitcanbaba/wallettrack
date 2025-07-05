#!/bin/bash

# TRON Wallet Monitor Startup Script

echo "🚀 Starting TRON Wallet Monitor..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Start the application
echo "🌟 Starting FastAPI server..."
echo "🌐 Open http://localhost:8000 in your browser"
echo "⏹️  Press Ctrl+C to stop the server"

python main.py
