#!/bin/bash
# Quick Start Script for Unified Document Management System

echo "================================================"
echo "🚀 Unified Document Management System Setup"
echo "================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check for Groq API key
if [ -z "$GROQ_API_KEY" ]; then
    echo ""
    echo "⚠️  GROQ_API_KEY not found in environment"
    echo "Please set it with: export GROQ_API_KEY='your_key_here'"
    echo ""
fi

# Check if Supabase is running
echo ""
echo "🔍 Checking Supabase..."
if command -v supabase &> /dev/null; then
    echo "✓ Supabase CLI found"
    
    # Check if Supabase is running
    if supabase status &> /dev/null; then
        echo "✓ Supabase is running"
    else
        echo "⚠️  Supabase is not running"
        echo "Starting Supabase..."
        supabase start
    fi
    
    # Apply migrations
    echo ""
    echo "📊 Applying database migrations..."
    supabase db reset --db-url postgresql://postgres:postgres@127.0.0.1:54422/postgres
    
else
    echo "⚠️  Supabase CLI not found"
    echo "Install with: npm install -g supabase"
    echo ""
    echo "Or start manually:"
    echo "  supabase start"
fi

echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "Quick Start Commands:"
echo ""
echo "1. Process a PDF:"
echo "   python unified_document_manager.py process document.pdf"
echo ""
echo "2. Search documents:"
echo '   python unified_document_manager.py search "find my registration"'
echo ""
echo "3. Analyze folders:"
echo "   python unified_document_manager.py analyze-folders"
echo ""
echo "4. View statistics:"
echo "   python unified_document_manager.py stats"
echo ""
echo "5. View help:"
echo "   python unified_document_manager.py --help"
echo ""
echo "Supabase Studio: http://127.0.0.1:54423"
echo ""
