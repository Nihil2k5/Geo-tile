import os
import re
import tempfile
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.conf import settings

# Import pytesseract - lightweight OCR library
try:
    import pytesseract
except ImportError:
    raise ImportError(
        "pytesseract is not installed. "
        "Please install it using: pip install pytesseract\n"
        "Also ensure Tesseract OCR is installed on your system:\n"
        "  - macOS: brew install tesseract\n"
        "  - Ubuntu/Debian: sudo apt-get install tesseract-ocr\n"
        "  - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
        "Make sure you're in the correct virtual environment and restart your Django server after installation."
    )

class DocumentProcessor:
    """
    Utility class for processing legacy land registry documents using OCR
    to extract sensitive information like owner details, coordinates, area, etc.
    
    Uses Tesseract OCR (via pytesseract) - a lightweight, open-source OCR engine.
    Supports multiple languages including English and Indian languages.
    Requires pytesseract and Tesseract OCR to be installed.
    """
    
    # Common patterns for land registry documents (multi-language support)
    # Supports English and Indian languages
    PATTERNS = {
        'owner_name': r'(?:owner|proprietor|name|मालिक|स्वामी|உரிமையாளர்|మాలిక్|ಮಾಲಿಕ್|ഉടമ|માલિક|মালিক|مالک|ਪ੍ਰੋਪ੍ਰਾਈਟਰ)[\s:]+([A-Za-z\s\.\u0900-\u097F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0D80-\u0DFF\u0E00-\u0E7F\u0E80-\u0EFF\u0F00-\u0FFF\u0980-\u09FF]+)',
        'coordinates': r'(?:coordinates|location|gps|अक्षांश|देशांतर|ஆயங்கள்|నిరూపకాలు|ನಿರ್ದೇಶಾಂಕಗಳು|കോർഡിനേറ്റുകൾ|સંકલન|স্থানাঙ্ক|متناسقات|ਨਿਰਦੇਸ਼ਾਂਕ)[\s:]+([0-9\.,\s]+)',
        'area': r'(?:area|size|extent|क्षेत्र|பரப்பளவு|వైశాల్యం|ವಿಸ್ತೀರ್ಣ|വിസ്തീർണ്ണം|વિસ્તાર|ক্ষেত্রফল|رقبہ|ਖੇਤਰ)[\s:]+([0-9\.]+\s*(?:acres|hectares|sq\.?\s*(?:ft|m)|एकड़|हेक्टेयर|ஏக்கர்|ఎకరాలు|ಎಕರೆ|ഏക്കർ|એકર|একর|ایکڑ|ਏਕੜ))',
        'address': r'(?:address|location|situated at|पता|முகவரி|చిరునామా|ವಿಳಾಸ|വിലാസം|સરનામું|ঠিকানা|پتہ|ਪਤਾ)[\s:]+([A-Za-z0-9\s\.,#\-\u0900-\u097F\u0A80-\u0AFF\u0B00-\u0B7F\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0D80-\u0DFF\u0E00-\u0E7F\u0E80-\u0EFF\u0F00-\u0FFF\u0980-\u09FF]+)',
        'id_number': r'(?:id|identification|document|पहचान|அடையாள|గుర్తింపు|ಗುರುತು|ഐഡി|આઈડી|আইডি|شناخت|ਆਈ.ਡੀ)[\s:]+([A-Z0-9\-]+)',
    }
    
    # Document types for classification
    DOCUMENT_TYPES = [
        'deed', 'title', 'survey', 'certificate', 'transfer', 'map'
    ]
    
    def __init__(self, lang='eng'):
        """
        Initialize DocumentProcessor with language support.
        
        Args:
            lang: Tesseract language code for OCR. Common codes:
                - 'eng' (English) - default
                - 'hin' (Hindi)
                - 'tam' (Tamil)
                - 'tel' (Telugu)
                - 'kan' (Kannada)
                - 'mal' (Malayalam)
                - 'mar' (Marathi)
                - 'guj' (Gujarati)
                - 'ben' (Bengali)
                - 'urd' (Urdu)
                - 'pan' (Punjabi)
                - 'ori' (Odia)
                - 'chi_sim' (Simplified Chinese)
                - 'chi_tra' (Traditional Chinese)
                - 'jpn' (Japanese)
                - 'kor' (Korean)
                For multiple languages, use '+' e.g., 'eng+hin' for English and Hindi
        """
        # Map common language codes to Tesseract codes
        lang_map = {
            'en': 'eng',
            'hi': 'hin',
            'ta': 'tam',
            'te': 'tel',
            'kn': 'kan',
            'ml': 'mal',
            'mr': 'mar',
            'gu': 'guj',
            'bn': 'ben',
            'ur': 'urd',
            'pa': 'pan',
            'or': 'ori',
            'multi': 'eng+hin',  # Default multi-language: English + Hindi
        }
        
        self.lang = lang_map.get(lang, lang) if lang in lang_map else lang
        print(f"Initialized Tesseract OCR with language: {self.lang}")
        
        # Initialize the TF-IDF vectorizer for document classification
        self.vectorizer = TfidfVectorizer(stop_words='english')
        
        # Train the vectorizer with sample document type descriptions
        sample_docs = [
            "land deed property transfer ownership legal document",
            "title certificate proof ownership land property document",
            "survey map measurement land property boundaries coordinates",
            "ownership certificate official document land registry",
            "property transfer document legal ownership change",
            "land map geographical representation coordinates boundaries"
        ]
        self.type_vectors = self.vectorizer.fit_transform(sample_docs)
    
    def process_document(self, file_path):
        """
        Process a document file and extract relevant information
        
        Args:
            file_path: Path to the document file (PDF, JPG, PNG)
            
        Returns:
            dict: Extracted information including document type and fields
        """
        # Extract text from document
        text = self._extract_text(file_path)
        
        # Classify document type
        doc_type = self._classify_document(text)
        
        # Extract fields based on patterns
        extracted_data = self._extract_fields(text)
        extracted_data['document_type'] = doc_type
        
        return extracted_data
    
    def _extract_text(self, file_path):
        """
        Extract text from document using Tesseract OCR.
        
        Args:
            file_path: Path to the document file (PDF, JPG, PNG, etc.)
            
        Returns:
            str: Extracted text from the document
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        text = ""
        
        if file_ext == '.pdf':
            try:
                # Convert PDF to images
                images = convert_from_path(file_path)
                for img in images:
                    # Preprocess image for better OCR results
                    img = self._preprocess_image(img)
                    # Extract text using pytesseract
                    page_text = pytesseract.image_to_string(img, lang=self.lang)
                    text += page_text + "\n"
            except Exception as e:
                # Handle Poppler error
                if "poppler" in str(e).lower() or "poppler" in str(e):
                    raise Exception("Unable to process PDF: Poppler is required but not installed or not in PATH")
                else:
                    raise Exception(f"PDF processing error: {str(e)}")
        else:
            # Process image file directly
            try:
                img = Image.open(file_path)
                # Preprocess image for better OCR results
                img = self._preprocess_image(img)
                # Extract text using pytesseract
                text = pytesseract.image_to_string(img, lang=self.lang)
            except Exception as e:
                raise Exception(f"Image processing error: {str(e)}")
        
        return text.strip()
    
    def _preprocess_image(self, img):
        """
        Preprocess image to improve OCR accuracy.
        Converts to grayscale, applies thresholding, and noise reduction.
        
        Args:
            img: PIL Image object
            
        Returns:
            PIL Image: Preprocessed image
        """
        # Convert PIL Image to numpy array for OpenCV processing
        img_array = np.array(img)
        
        # Convert RGB to grayscale if needed
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        
        # Apply thresholding to get binary image
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Convert back to PIL Image
        img_processed = Image.fromarray(thresh)
        
        return img_processed
    
    def _classify_document(self, text):
        """Classify document type based on content"""
        if not text:
            return "unknown"
            
        # Create vector for the document text
        text_vector = self.vectorizer.transform([text])
        
        # Calculate similarity with each document type
        similarities = cosine_similarity(text_vector, self.type_vectors)[0]
        
        # Return the most similar document type
        max_index = np.argmax(similarities)
        return self.DOCUMENT_TYPES[max_index]
    
    def _extract_fields(self, text):
        """Extract fields from text using regex patterns"""
        result = {}
        
        for field, pattern in self.PATTERNS.items():
            matches = re.search(pattern, text, re.IGNORECASE)
            if matches:
                result[field] = matches.group(1).strip()
            else:
                result[field] = None
                
        return result