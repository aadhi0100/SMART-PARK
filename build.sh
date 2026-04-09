#!/usr/bin/env bash
# Render build script

echo "🚀 Starting SmartPark build process..."

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Set up database
echo "🗄️ Setting up database..."
python -c "
import os
os.environ.setdefault('FLASK_ENV', 'production')
from app.core.database import init_db
init_db()
print('✅ Database initialized')
"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p static/uploads

echo "✅ Build completed successfully!"
echo "🌐 SmartPark is ready for deployment"