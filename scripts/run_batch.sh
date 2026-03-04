#!/bin/bash
# Run batch processor with GROQ API key

# Check if GROQ_API_KEY is set
if [ -z "$GROQ_API_KEY" ]; then
    echo "⚠️  GROQ_API_KEY not set"
    echo ""
    echo "Please run:"
    echo "  export GROQ_API_KEY=\"your_key_here\""
    echo ""
    echo "Or add to ~/.zshrc:"
    echo "  echo 'export GROQ_API_KEY=\"your_key_here\"' >> ~/.zshrc"
    echo "  source ~/.zshrc"
    echo ""
    exit 1
fi

echo "✅ GROQ_API_KEY is set"
echo ""

# Activate virtual environment
source venv/bin/activate

# Run batch processor
python3 batch_processor.py "$@"
