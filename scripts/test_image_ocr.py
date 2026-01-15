"""
Test script for Image OCR with orientation detection

Usage:
    python scripts/test_image_ocr.py <path_to_image_file> [output_file.md]
    
Example:
    python scripts/test_image_ocr.py "data/Sample Documents/Sample driving license 1.jpg"
    python scripts/test_image_ocr.py image.jpg output.md
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from io import StringIO

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"✅ Loaded .env file from: {env_path}")
else:
    print(f"⚠️  .env file not found at: {env_path}")
    print("   Using system environment variables only")

# Import config after loading .env
from app.core.config import get_settings
settings = get_settings()

# Create output buffer to capture all output
output_buffer = StringIO()

def print_and_save(*args, **kwargs):
    """Print to console and save to buffer"""
    message = ' '.join(str(arg) for arg in args)
    print(*args, **kwargs)
    output_buffer.write(message + '\n')

# Check Python environment first
print_and_save(f"🐍 Python: {sys.executable}")
print_and_save(f"📁 Project Root: {project_root}")
print_and_save()

# Check required dependencies
try:
    from PIL import Image
    print_and_save("✅ PIL/Pillow found")
    print_and_save()
except ImportError as e:
    print_and_save(f"❌ Missing dependency: {str(e)}")
    print_and_save()
    print_and_save("💡 Install required packages:")
    print_and_save("   pip install Pillow")
    print_and_save()
    sys.exit(1)

import logging
from app.services.rag.document_processor import DocumentProcessor
from app.services.rag.text_enhancer import TextEnhancer
from app.core.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def test_image_ocr(image_path: str, output_file: str = None):
    """
    Test image OCR using DocumentProcessor
    
    Args:
        image_path: Path to the image file
        output_file: Optional path to save full output markdown file
    """
    print_and_save("=" * 80)
    print_and_save("🖼️  Image OCR Test Script")
    print_and_save("=" * 80)
    print_and_save()
    
    # Check if file exists
    if not os.path.exists(image_path):
        print_and_save(f"❌ Error: File not found: {image_path}")
        return
    
    # Check if it's an image file
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp']
    file_ext = Path(image_path).suffix.lower()
    if file_ext not in image_extensions:
        print_and_save(f"⚠️  Warning: File doesn't appear to be an image: {image_path}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    print_and_save(f"📁 Image File: {image_path}")
    file_size = os.path.getsize(image_path)
    print_and_save(f"📊 File Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print_and_save(f"📄 File Extension: {file_ext}")
    print_and_save()
    
    try:
        # Load and analyze image (basic info only)
        print_and_save("=" * 80)
        print_and_save("📐 IMAGE ANALYSIS")
        print_and_save("=" * 80)
        
        image = Image.open(image_path)
        width, height = image.size
        mode = image.mode
        
        print_and_save(f"Dimensions: {width} x {height} pixels")
        print_and_save(f"Mode: {mode}")
        print_and_save(f"Aspect Ratio: {width/height:.2f}")
        print_and_save()
        
        # Show configuration
        print_and_save("=" * 80)
        print_and_save("⚙️  CONFIGURATION")
        print_and_save("=" * 80)
        print_and_save(f"TEXT_ENHANCEMENT_ENABLED: {settings.TEXT_ENHANCEMENT_ENABLED}")
        print_and_save(f"TEXT_ENHANCEMENT_TEMPERATURE: {settings.TEXT_ENHANCEMENT_TEMPERATURE}")
        print_and_save(f"GROQ_API_KEY: {'Set' if settings.GROQ_API_KEY else 'Not set'}")
        print_and_save(f"GROQ_MODEL_NAME: {settings.GROQ_MODEL_NAME}")
        print_and_save(f"OCR_ENABLED: {settings.OCR_ENABLED}")
        print_and_save(f"OCR_LANGUAGE: {settings.OCR_LANGUAGE}")
        print_and_save()
        
        # Initialize text enhancer (for LLM-based enhancement)
        print_and_save("=" * 80)
        print_and_save("🤖 INITIALIZING TEXT ENHANCER")
        print_and_save("=" * 80)
        print_and_save("🔄 Initializing TextEnhancer (LLM-based enhancement)...")
        try:
            text_enhancer = TextEnhancer()
            if text_enhancer.enabled:
                print_and_save("✅ TextEnhancer initialized (LLM enhancement enabled)")
                print_and_save(f"   Using: {text_enhancer.llm_service.__class__.__name__}")
                print_and_save(f"   Model: {settings.GROQ_MODEL_NAME}")
                print_and_save(f"   Temperature: {text_enhancer.temperature}")
            else:
                print_and_save("ℹ️  TextEnhancer initialized (LLM enhancement disabled)")
                print_and_save("   Reason: TEXT_ENHANCEMENT_ENABLED=False or GROQ_API_KEY not set")
            print_and_save()
        except Exception as e:
            print_and_save(f"⚠️  TextEnhancer initialization failed: {str(e)}")
            print_and_save("   OCR will proceed without LLM enhancement")
            print_and_save()
            print_and_save("💡 Troubleshooting:")
            print_and_save("   1. Check if GROQ_API_KEY is set in .env file")
            print_and_save("   2. Verify TEXT_ENHANCEMENT_ENABLED=True in .env")
            print_and_save("   3. Ensure langchain-community is installed")
            print_and_save()
            text_enhancer = None
        
        # Get raw OCR text first (for comparison) - using document processor
        print_and_save("=" * 80)
        print_and_save("📖 RAW OCR EXTRACTION (Before Enhancement)")
        print_and_save("=" * 80)
        print_and_save("📖 Extracting raw OCR text using DocumentProcessor (without LLM enhancement)...")
        
        try:
            # Create processor without enhancer to get raw OCR
            raw_processor = DocumentProcessor(text_enhancer=None)
            raw_result = raw_processor.process_file(image_path)
            raw_text = raw_result.get("text", "")
            raw_text_length = len(raw_text)
            
            print_and_save(f"✅ Raw OCR extraction completed ({raw_text_length:,} characters)")
            print_and_save()
            
            if raw_text.strip():
                print_and_save("📝 Raw OCR Text (first 500 chars):")
                print_and_save("```")
                print_and_save(raw_text[:500] if raw_text_length > 500 else raw_text)
                if raw_text_length > 500:
                    print_and_save("... (truncated)")
                print_and_save("```")
                print_and_save()
        except Exception as e:
            print_and_save(f"⚠️  Error extracting raw OCR: {str(e)}")
            raw_text = ""
            raw_text_length = 0
        
        # Initialize document processor with text enhancer
        print_and_save("=" * 80)
        print_and_save("🔄 INITIALIZING DOCUMENT PROCESSOR (With Enhancement)")
        print_and_save("=" * 80)
        print_and_save("🔄 Initializing DocumentProcessor with TextEnhancer...")
        processor = DocumentProcessor(text_enhancer=text_enhancer)
        print_and_save("✅ DocumentProcessor initialized")
        if text_enhancer and text_enhancer.enabled:
            print_and_save("   (Text enhancer integrated for OCR text enhancement)")
        print_and_save()
        
        # Process image with OCR and enhancement using DocumentProcessor
        print_and_save("=" * 80)
        print_and_save("📖 OCR PROCESSING (With LLM Enhancement)")
        print_and_save("=" * 80)
        print_and_save("📖 Processing image with OCR and LLM enhancement using DocumentProcessor...")
        print_and_save(f"   Using image: {image_path}")
        print_and_save()
        
        try:
            result = processor.process_file(image_path)
            print_and_save("✅ OCR processing with enhancement completed")
            print_and_save()
        except Exception as e:
            print_and_save(f"❌ Error processing image: {str(e)}")
            raise
        
        # Extract results
        extracted_text = result.get("text", "")
        extracted_length = len(extracted_text)
        
        # Enhancement comparison
        print_and_save("=" * 80)
        print_and_save("✨ ENHANCEMENT COMPARISON")
        print_and_save("=" * 80)
        print_and_save(f"Raw OCR Length: {raw_text_length} characters")
        print_and_save(f"Enhanced Length: {extracted_length} characters")
        if raw_text_length > 0:
            difference = extracted_length - raw_text_length
            percentage = (difference / raw_text_length * 100) if raw_text_length > 0 else 0
            print_and_save(f"Difference: {difference:+d} characters ({percentage:+.1f}%)")
        print_and_save()
        
        # Display results
        print_and_save("=" * 80)
        print_and_save("📊 OCR RESULTS")
        print_and_save("=" * 80)
        print_and_save(f"File Type: {result.get('file_ext', 'unknown')}")
        print_and_save(f"MIME Type: {result.get('mime_type', 'unknown')}")
        print_and_save(f"Extracted Text Length: {extracted_length} characters")
        print_and_save(f"Extracted Text Length: {extracted_length / 1024:.2f} KB")
        print_and_save()
        
        print_and_save("=" * 80)
        print_and_save("📝 FULL EXTRACTED TEXT")
        print_and_save("=" * 80)
        if text_enhancer and text_enhancer.enabled:
            print_and_save("(This text has been enhanced using LLM)")
        print_and_save("```")
        print_and_save(extracted_text)
        print_and_save("```")
        print_and_save()
        
        # Text statistics
        lines = extracted_text.split('\n')
        words = extracted_text.split()
        print_and_save("📊 Text Statistics:")
        print_and_save(f"   Total Characters: {extracted_length}")
        print_and_save(f"   Total Lines: {len(lines)}")
        print_and_save(f"   Total Words: {len(words)}")
        print_and_save(f"   Average Words per Line: {len(words) / len(lines):.1f}" if lines else "   Average Words per Line: 0")
        print_and_save()
        
        # Before/After comparison
        print_and_save("=" * 80)
        print_and_save("📊 BEFORE/AFTER COMPARISON")
        print_and_save("=" * 80)
        print_and_save()
        
        print_and_save("### Raw OCR Text (Before Enhancement):")
        print_and_save("```")
        print_and_save(raw_text if raw_text.strip() else "(No text extracted)")
        print_and_save("```")
        print_and_save()
        
        print_and_save("### Enhanced Text (After LLM Enhancement):")
        print_and_save("```")
        print_and_save(extracted_text if extracted_text.strip() else "(No text extracted)")
        print_and_save("```")
        print_and_save()
        
        if text_enhancer and text_enhancer.enabled:
            print_and_save("### Enhancement Features Applied:")
            print_and_save("  ✓ Fixed OCR character recognition errors (rn→m, 0→O, etc.)")
            print_and_save("  ✓ Structured information into logical sections/fields")
            print_and_save("  ✓ Organized text into readable format")
            print_and_save("  ✓ Fixed spacing and formatting issues")
            print_and_save("  ✓ Preserved all numbers, dates, and identifiers")
            print_and_save()
        
        # Check if processed image was saved by DocumentProcessor
        processed_image_path = Path(settings.DOCUMENTS_STORAGE_PATH) / "processed_images" / f"{Path(image_path).stem}_processed{Path(image_path).suffix}"
        image_files_section = ""
        if processed_image_path.exists():
            # Try to get relative path, fallback to absolute if not under project root
            try:
                rel_path = processed_image_path.relative_to(project_root)
            except ValueError:
                rel_path = processed_image_path
            
            image_files_section = f"""
## Generated Image Files

- **Processed Image:** `{rel_path}` (final image used for OCR, after all corrections)

---
"""
        
        # Create markdown content with raw text included if available
        raw_text_section = ""
        if raw_text.strip():
            raw_text_section = f"""
## Raw OCR Text (Before Enhancement)

```text
{raw_text}
```

---
"""
        
        md_content = f"""# Image OCR Test Results

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Image File:** `{image_path}`
**File Size:** {file_size:,} bytes ({file_size / 1024:.2f} KB)
**Image Dimensions:** {width} x {height} pixels
**Image Mode:** {mode}
**LLM Enhancement:** {'Enabled' if text_enhancer and text_enhancer.enabled else 'Disabled'}

{image_files_section}
{raw_text_section}
---

{output_buffer.getvalue()}
"""
        
        # Write to file
        if output_file:
            output_path = Path(output_file)
        else:
            output_path = project_root / f"{Path(image_path).stem}_ocr_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print_and_save()
        print_and_save(f"💾 Full output saved to: {output_path}")
        print_and_save()
        
        print_and_save("=" * 80)
        print_and_save("✅ TEST COMPLETED SUCCESSFULLY")
        print_and_save("=" * 80)
        
    except ImportError as e:
        print_and_save(f"❌ Import Error: {str(e)}")
        print_and_save()
        print_and_save("💡 Troubleshooting:")
        print_and_save(f"   Current Python: {sys.executable}")
        print_and_save("   1. Make sure you're in the correct virtual environment")
        print_and_save("   2. Install: pip install pytesseract Pillow")
        print_and_save("   3. Make sure Tesseract OCR is installed on your system:")
        print_and_save("      - macOS: brew install tesseract")
        print_and_save("      - Ubuntu: sudo apt-get install tesseract-ocr")
        print_and_save("      - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        print_and_save()
        
        # Save error to file
        error_output = project_root / "scripts" / f"ocr_test_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(error_output, 'w', encoding='utf-8') as f:
            f.write(f"# Image OCR Test Error\n\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{output_buffer.getvalue()}")
        print_and_save(f"💾 Error log saved to: {error_output}")
        print_and_save()
        
        sys.exit(1)
    except Exception as e:
        print_and_save(f"❌ Error processing image: {str(e)}")
        logger.exception("Detailed error information:")
        print_and_save()
        
        # Save error to file
        error_output = project_root / "scripts" / f"ocr_test_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(error_output, 'w', encoding='utf-8') as f:
            f.write(f"# Image OCR Test Error\n\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{output_buffer.getvalue()}")
        print_and_save(f"💾 Error log saved to: {error_output}")
        print_and_save()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_image_ocr.py <path_to_image_file> [output_file.md]")
        print()
        print("Examples:")
        print('  python scripts/test_image_ocr.py "data/Sample Documents/Sample driving license 1.jpg"')
        print("  python scripts/test_image_ocr.py image.jpg output.md")
        print()
        print("Available image files in data/ directory:")
        
        # List available images
        data_dir = project_root / "data"
        if data_dir.exists():
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
            image_files = []
            for ext in image_extensions:
                image_files.extend(list(data_dir.rglob(f"*{ext}")))
                image_files.extend(list(data_dir.rglob(f"*{ext.upper()}")))
            
            if image_files:
                for img_file in image_files[:15]:  # Show first 15
                    rel_path = img_file.relative_to(project_root)
                    print(f"  - {rel_path}")
                if len(image_files) > 15:
                    print(f"  ... and {len(image_files) - 15} more")
            else:
                print("  (No image files found)")
        sys.exit(1)
    
    image_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    test_image_ocr(image_path, output_file)


if __name__ == "__main__":
    main()
