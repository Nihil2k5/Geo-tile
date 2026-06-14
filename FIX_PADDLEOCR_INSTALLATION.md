# Fix PaddleOCR Installation Issue

## Problem
Error: `No module named 'paddle'`

This means PaddleOCR is installed but its dependency **PaddlePaddle** is missing.

## Solution

### Step 1: Install PaddlePaddle

PaddleOCR requires PaddlePaddle as a dependency. Install it:

```bash
# Make sure your virtual environment is activated
source venv/bin/activate  # On macOS/Linux
# or
# venv\Scripts\activate  # On Windows

# Install PaddlePaddle (CPU version)
pip install paddlepaddle

# Or if you have a GPU and want GPU support:
# pip install paddlepaddle-gpu
```

### Step 2: Reinstall PaddleOCR (Optional but Recommended)

```bash
pip install --upgrade paddleocr
```

### Step 3: Verify Installation

Test if PaddleOCR can be imported:

```bash
python -c "from paddleocr import PaddleOCR; print('PaddleOCR installed successfully!')"
```

If you see "PaddleOCR installed successfully!", the installation is correct.

### Step 4: Restart Django Server

**IMPORTANT**: After installing new packages, you MUST restart your Django server:

1. Stop the server (Ctrl+C in the terminal where `python manage.py runserver` is running)
2. Start it again:
   ```bash
   python manage.py runserver
   ```

### Step 5: Test AI Extract Feature

1. Go to: http://127.0.0.1:8000/registrar/register-land/
2. Check "This is a legacy record"
3. Upload a document
4. Click "AI Extract"

## Troubleshooting

### If installation fails:

1. **Check Python version**: PaddleOCR requires Python 3.7-3.11
   ```bash
   python --version
   ```

2. **Upgrade pip**:
   ```bash
   pip install --upgrade pip
   ```

3. **Install with specific version**:
   ```bash
   pip install paddlepaddle==2.5.2
   pip install paddleocr==2.7.0
   ```

4. **Check virtual environment**: Make sure you're in the correct virtual environment
   ```bash
   which python  # Should show path to venv/bin/python
   ```

### If still not working:

Check Django server logs for detailed error messages. The error should show exactly what's missing.
