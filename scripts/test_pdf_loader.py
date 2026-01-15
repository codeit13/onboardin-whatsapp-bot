"""
Test script for PDF loader using LangChain PyPDFLoader

Usage:
    python scripts/test_pdf_loader.py <path_to_pdf_file>
    
Example:
    python scripts/test_pdf_loader.py "data/documents/Attendance Policy.pdf"
    python scripts/test_pdf_loader.py data/documents/Attendance\\ Policy.pdf
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from io import StringIO

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

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

# Try to import langchain_community directly to check if it's available
try:
    import langchain_community
    print_and_save(f"✅ langchain-community found: {langchain_community.__version__}")
    from langchain_community.document_loaders import PyPDFLoader
    print_and_save("✅ PyPDFLoader import successful")
    print_and_save()
except ImportError as e:
    print_and_save(f"❌ langchain-community import failed: {str(e)}")
    print_and_save()
    print_and_save("💡 Troubleshooting:")
    print_and_save(f"   1. Current Python: {sys.executable}")
    print_and_save("   2. Make sure you're in the correct virtual environment")
    print_and_save("   3. Try: pip install langchain-community")
    print_and_save("   4. Or: pip install -r requirements.txt")
    print_and_save()
    sys.exit(1)

import logging
from app.services.rag.document_processor import DocumentProcessor
from app.core.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def test_pdf_loader(pdf_path: str, output_file: str = None):
    """
    Test PDF loader with a given PDF file
    
    Args:
        pdf_path: Path to the PDF file
        output_file: Optional path to save full output markdown file
    """
    print_and_save("=" * 80)
    print_and_save("📄 PDF Loader Test Script")
    print_and_save("=" * 80)
    print_and_save()
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print_and_save(f"❌ Error: File not found: {pdf_path}")
        return
    
    if not pdf_path.lower().endswith('.pdf'):
        print_and_save(f"⚠️  Warning: File doesn't have .pdf extension: {pdf_path}")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    print_and_save(f"📁 PDF File: {pdf_path}")
    file_size = os.path.getsize(pdf_path)
    print_and_save(f"📊 File Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
    print_and_save()
    
    try:
        # Initialize document processor
        print_and_save("🔄 Initializing DocumentProcessor...")
        processor = DocumentProcessor()
        print_and_save("✅ DocumentProcessor initialized")
        print_and_save()
        
        # Process PDF file
        print_and_save("📖 Processing PDF file...")
        result = processor.process_file(pdf_path)
        print_and_save("✅ PDF processed successfully")
        print_and_save()
        
        # Display results
        extracted_text = result.get("text", "")
        text_length = len(extracted_text)
        
        print_and_save("=" * 80)
        print_and_save("📊 EXTRACTION RESULTS")
        print_and_save("=" * 80)
        print_and_save(f"File Type: {result.get('file_ext', 'unknown')}")
        print_and_save(f"MIME Type: {result.get('mime_type', 'unknown')}")
        print_and_save(f"Extracted Text Length: {text_length:,} characters")
        print_and_save(f"Extracted Text Length: {text_length / 1024:.2f} KB")
        print_and_save()
        
        # Show FULL text (no truncation)
        print_and_save("=" * 80)
        print_and_save("📝 FULL EXTRACTED TEXT")
        print_and_save("=" * 80)
        print_and_save("```")
        print_and_save(extracted_text)
        print_and_save("```")
        print_and_save()
        
        # Test chunking
        print_and_save("=" * 80)
        print_and_save("✂️  CHUNKING TEST")
        print_and_save("=" * 80)
        print_and_save("Testing text chunking with LangChain RecursiveCharacterTextSplitter...")
        print_and_save()
        
        chunks = processor.chunk_text(extracted_text, title="Test Document")
        
        print_and_save(f"✅ Created {len(chunks)} chunks")
        print_and_save()
        
        # Display chunk statistics
        if chunks:
            chunk_lengths = [len(chunk["text"]) for chunk in chunks]
            avg_length = sum(chunk_lengths) / len(chunk_lengths)
            min_length = min(chunk_lengths)
            max_length = max(chunk_lengths)
            
            print_and_save("📊 Chunk Statistics:")
            print_and_save(f"   Total Chunks: {len(chunks)}")
            print_and_save(f"   Average Length: {avg_length:.0f} characters")
            print_and_save(f"   Min Length: {min_length} characters")
            print_and_save(f"   Max Length: {max_length} characters")
            print_and_save()
            
            # Show ALL chunks (no truncation)
            print_and_save("=" * 80)
            print_and_save("📄 ALL CHUNKS (FULL CONTENT)")
            print_and_save("=" * 80)
            print_and_save()
            
            for i, chunk in enumerate(chunks):
                print_and_save(f"## Chunk {i + 1} (Index: {chunk['chunk_index']})")
                print_and_save(f"**Length:** {len(chunk['text'])} characters")
                print_and_save(f"**Start:** {chunk.get('start', 'N/A')}, **End:** {chunk.get('end', 'N/A')}")
                print_and_save()
                print_and_save("```")
                print_and_save(chunk["text"])
                print_and_save("```")
                print_and_save()
                print_and_save("---")
                print_and_save()
        
        print_and_save("=" * 80)
        print_and_save("✅ TEST COMPLETED SUCCESSFULLY")
        print_and_save("=" * 80)
        
        # Save to markdown file
        if output_file is None:
            # Generate output filename based on PDF filename
            pdf_name = Path(pdf_path).stem
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = project_root / "scripts" / f"pdf_test_output_{pdf_name}_{timestamp}.md"
        
        output_path = Path(output_file)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        
        # Create markdown content
        md_content = f"""# PDF Loader Test Results

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**PDF File:** `{pdf_path}`
**File Size:** {file_size:,} bytes ({file_size / 1024:.2f} KB)

---

{output_buffer.getvalue()}
"""
        
        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print_and_save()
        print_and_save(f"💾 Full output saved to: {output_path}")
        print_and_save()
        
    except ImportError as e:
        print_and_save(f"❌ Import Error: {str(e)}")
        print_and_save()
        print_and_save("💡 Troubleshooting:")
        print_and_save(f"   Current Python: {sys.executable}")
        print_and_save("   1. Make sure you're in the correct virtual environment")
        print_and_save("   2. Activate venv: source venv/bin/activate")
        print_and_save("   3. Install: pip install langchain-community langchain-text-splitters")
        print_and_save("   4. Or: pip install -r requirements.txt")
        print_and_save()
        print_and_save("   Check if installed:")
        print_and_save("   python -c 'import langchain_community; print(langchain_community.__version__)'")
        print_and_save()
        
        # Save error to file
        error_output = project_root / "scripts" / f"pdf_test_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(error_output, 'w', encoding='utf-8') as f:
            f.write(f"# PDF Loader Test Error\n\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{output_buffer.getvalue()}")
        print_and_save(f"💾 Error log saved to: {error_output}")
        print_and_save()
        
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error processing PDF: {str(e)}")
        logger.exception("Detailed error information:")
        print()


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_pdf_loader.py <path_to_pdf_file> [output_file.md]")
        print()
        print("Examples:")
        print('  python scripts/test_pdf_loader.py "data/documents/Attendance Policy.pdf"')
        print("  python scripts/test_pdf_loader.py data/documents/Attendance\\ Policy.pdf")
        print("  python scripts/test_pdf_loader.py file.pdf output.md")
        print()
        print("Available PDF files in data/ directory:")
        
        # List available PDFs
        data_dir = project_root / "data"
        if data_dir.exists():
            pdf_files = list(data_dir.rglob("*.pdf"))
            if pdf_files:
                for pdf_file in pdf_files[:10]:  # Show first 10
                    rel_path = pdf_file.relative_to(project_root)
                    print(f"  - {rel_path}")
                if len(pdf_files) > 10:
                    print(f"  ... and {len(pdf_files) - 10} more")
            else:
                print("  (No PDF files found)")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    test_pdf_loader(pdf_path, output_file)


if __name__ == "__main__":
    main()
