# Installing Tesseract OCR

This application uses **Tesseract OCR** (via `pytesseract`) - a lightweight, open-source OCR engine for extracting text from documents.

## Installation

### Step 1: Install Tesseract OCR (System-Level)

Tesseract OCR must be installed on your system before you can use `pytesseract`.

#### macOS
```bash
brew install tesseract
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

For additional languages (e.g., Hindi, Tamil):
```bash
sudo apt-get install tesseract-ocr-hin tesseract-ocr-tam tesseract-ocr-tel
```

#### Windows
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

Make sure to add Tesseract to your PATH or configure pytesseract to find it.

### Step 2: Install Python Package

```bash
pip install pytesseract
```

Or add to `requirements.txt`:
```
pytesseract
```

### Step 3: Install Language Data (Optional)

For Indian languages and other non-English languages, you may need to install additional language data files.

**macOS:**
```bash
brew install tesseract-lang
```

**Ubuntu/Debian:**
```bash
# Install all language packs
sudo apt-get install tesseract-ocr-all

# Or install specific languages
sudo apt-get install tesseract-ocr-hin  # Hindi
sudo apt-get install tesseract-ocr-tam  # Tamil
sudo apt-get install tesseract-ocr-tel  # Telugu
sudo apt-get install tesseract-ocr-kan  # Kannada
sudo apt-get install tesseract-ocr-mal  # Malayalam
sudo apt-get install tesseract-ocr-mar  # Marathi
sudo apt-get install tesseract-ocr-guj  # Gujarati
sudo apt-get install tesseract-ocr-ben  # Bengali
sudo apt-get install tesseract-ocr-urd  # Urdu
sudo apt-get install tesseract-ocr-pan  # Punjabi
sudo apt-get install tesseract-ocr-ori  # Odia
```

**Windows:**
Language data files are usually included in the installer. Make sure to select them during installation.

### Step 4: Verify Installation

Test that Tesseract is working:

```python
import pytesseract
from PIL import Image

# Test with a simple image
# pytesseract.image_to_string(Image.open('test.png'))
```

Or from command line:
```bash
tesseract --version
tesseract --list-langs
```

## Supported Languages

Tesseract supports 100+ languages. Common language codes:

- `eng` - English
- `hin` - Hindi (हिंदी)
- `tam` - Tamil (தமிழ்)
- `tel` - Telugu (తెలుగు)
- `kan` - Kannada (ಕನ್ನಡ)
- `mal` - Malayalam (മലയാളം)
- `mar` - Marathi (मराठी)
- `guj` - Gujarati (ગુજરાતી)
- `ben` - Bengali (বাংলা)
- `urd` - Urdu (اردو)
- `pan` - Punjabi (ਪੰਜਾਬੀ)
- `ori` - Odia (ଓଡ଼ିଆ)
- `chi_sim` - Simplified Chinese
- `chi_tra` - Traditional Chinese
- `jpn` - Japanese
- `kor` - Korean

For multiple languages, use `+` to combine them, e.g., `eng+hin` for English and Hindi.

## Usage in Application

```python
from land_registry.utils.document_processor import DocumentProcessor

# Single language
processor = DocumentProcessor(lang='eng')  # English
processor = DocumentProcessor(lang='hin')  # Hindi

# Multiple languages
processor = DocumentProcessor(lang='eng+hin')  # English + Hindi

# Process a document
extracted_data = processor.process_document('path/to/document.pdf')
```

## Troubleshooting

### Issue: "tesseract is not installed or it's not in your PATH"

**Solution:**
1. Make sure Tesseract is installed on your system
2. On Windows, you may need to set the path explicitly:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```
3. On Linux/macOS, make sure Tesseract is in your PATH

### Issue: "Failed loading language 'hin'"

**Solution:**
Install the language data for the language you're trying to use (see Step 3 above).

### Issue: OCR accuracy is poor

**Solution:**
1. Ensure images are high quality (300 DPI or higher)
2. Images should have good contrast
3. Text should be clearly visible
4. The preprocessing functions in the code help improve accuracy

### Issue: PDF processing fails

**Solution:**
Make sure `poppler` is installed:
- macOS: `brew install poppler`
- Ubuntu/Debian: `sudo apt-get install poppler-utils`
- Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases/

## Benefits of Tesseract OCR

1. **Lightweight**: Small footprint, fast installation
2. **Open Source**: Free and actively maintained
3. **Multi-Language**: Supports 100+ languages
4. **Mature**: Stable and widely used
5. **Easy to Use**: Simple Python API via pytesseract
