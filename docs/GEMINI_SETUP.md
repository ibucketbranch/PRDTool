# Gemini API Key Setup - REQUIRED

## ⚠️ CRITICAL: Gemini is the PRIMARY Provider

**The system is configured to use Gemini FIRST, Groq as fallback.**

If `GEMINI_API_KEY` is not set, the system will only use Groq, which violates the intended configuration.

## How to Set GEMINI_API_KEY

### Option 1: Environment Variable (Recommended)

**Temporary (for current session):**
```bash
export GEMINI_API_KEY='your-gemini-api-key-here'
```

**Permanent (add to your shell profile):**
```bash
# Add to ~/.zshrc or ~/.bash_profile
echo 'export GEMINI_API_KEY="your-gemini-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### Option 2: .env File (For this project)

Create `.env` file in project root:
```bash
cd /Users/michaelvalderrama/Websites/TheConversation
echo 'GEMINI_API_KEY=your-gemini-api-key-here' > .env
echo 'GROQ_API_KEY=your-groq-api-key-here' >> .env
```

The code will automatically load `.env` using `python-dotenv`.

### Option 3: Pass Directly to Script

You can pass it directly when running:
```bash
GEMINI_API_KEY='your-key' python3 scripts/reprocess_by_priority.py --category resumes
```

## Verify It's Working

After setting the key, verify:
```bash
cd /Users/michaelvalderrama/Websites/TheConversation
source venv/bin/activate
python3 -c "from document_processor import DocumentProcessor; p = DocumentProcessor(); print('Gemini:', p.gemini_client is not None); print('Groq:', p.groq_client is not None); print('Order:', p._get_provider_order())"
```

**Expected output:**
```
✅ Gemini client initialized (PRIMARY provider)
✅ Groq client initialized (FALLBACK provider)
✅ Provider order configured: ['gemini', 'groq'] (Gemini first, Groq fallback)
Gemini: True
Groq: True
Order: ['gemini', 'groq']
```

## Current Issue

**Without GEMINI_API_KEY set:**
- ❌ Gemini client: None
- ✅ Groq client: Available
- ❌ Provider order: `['groq']` (WRONG - should be `['gemini', 'groq']`)
- ❌ System uses Groq only (violates intended configuration)

**With GEMINI_API_KEY set:**
- ✅ Gemini client: Available (PRIMARY)
- ✅ Groq client: Available (FALLBACK)
- ✅ Provider order: `['gemini', 'groq']` (CORRECT)
- ✅ System tries Gemini first, falls back to Groq if needed

## Get Your Gemini API Key

1. Go to https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Create a new API key
4. Copy the key and set it as `GEMINI_API_KEY`

## Priority Order (Fixed)

The code now ensures:
1. **Gemini is ALWAYS first** (if available)
2. **Groq is ALWAYS fallback** (if Gemini fails or unavailable)
3. Provider order is `['gemini', 'groq']` regardless of `LLM_PROVIDER` setting
