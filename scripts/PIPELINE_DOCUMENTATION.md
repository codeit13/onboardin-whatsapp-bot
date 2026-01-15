# Image OCR Processing Pipeline Documentation

## Command
```bash
python scripts/test_image_ocr.py InCorrect.jpg InCorrect.md
```

## Complete Processing Pipeline

### Phase 1: Initialization & Setup
1. **Load Environment**
   - Load `.env` file from project root
   - Initialize settings from environment variables
   - Setup logging

2. **Dependency Checks**
   - Verify PIL/Pillow is installed
   - Verify pytesseract is installed
   - Verify numpy is installed

3. **File Validation**
   - Check if `InCorrect.jpg` exists
   - Verify it's an image file (`.jpg`, `.jpeg`, `.png`, etc.)
   - Get file size and metadata

---

### Phase 2: Image Analysis
4. **Load Image**
   - Open image using PIL: `Image.open("InCorrect.jpg")`
   - Extract dimensions (width x height)
   - Get image mode (RGB, L, etc.)

5. **Image Quality Analysis**
   - Convert to grayscale for analysis
   - Calculate metrics:
     - Mean brightness
     - Standard deviation (contrast indicator)
     - Dynamic range (min-max pixel values)
     - Bright/dark pixel ratios
     - Exposure status (overexposed/underexposed/normal)

6. **EXIF Data Check**
   - Read EXIF metadata
   - Check orientation tag (tag 274)
   - Display orientation information

---

### Phase 3: Image Preprocessing
7. **Grayscale Conversion (Simple)**
   - Convert image to grayscale mode ('L')
   - **Output saved:** `scripts/preprocessed_InCorrect.jpg`
   - This is the preprocessed image (grayscale only, no other adjustments)

---

### Phase 4: Orientation Correction
8. **EXIF Orientation Correction**
   - Apply `ImageOps.exif_transpose()` to correct EXIF-based rotation
   - This handles camera orientation tags
   - **Image state:** EXIF-corrected, still in original color mode

9. **Tesseract OSD (Orientation and Script Detection)**
   - Run `pytesseract.image_to_osd()` on EXIF-corrected image
   - OSD detects text orientation automatically
   - **OSD Output contains:**
     - `Rotate: <angle>` - Amount to rotate clockwise (0, 90, 180, 270)
     - `Orientation in degrees: <angle>` - Detected orientation
     - `Orientation confidence: <0.0-1.0>` - Confidence score
     - `Script: <script_name>` - Detected script (Latin, etc.)

10. **Rotation Application**
    - **Parse OSD result:**
      - Extract rotation angle (e.g., 270)
      - Extract confidence (e.g., 0.87)
    - **Check conditions:**
      - Rotation angle != 0
      - Confidence > 0.3 (or None)
    - **Apply rotation:**
      - Tesseract OSD gives clockwise rotation
      - PIL `rotate()` rotates counter-clockwise
      - **Convert:** `pil_angle = -osd_angle`
      - Example: OSD says "Rotate: 270" → PIL rotates by -270° (or 90°)
      - Use `image.rotate(pil_angle, expand=True)`
    - **Verify rotation:**
      - Check if dimensions changed (90°/270° swap width/height)
      - Log rotation confirmation

---

### Phase 5: Final Preprocessing
11. **Grayscale Conversion (After Rotation)**
    - Convert rotated image to grayscale: `image.convert("L")`
    - This ensures consistent format for OCR

12. **Save Final Image**
    - **Output saved:** `scripts/final_ocr_image_InCorrect.jpg`
    - This is the final image used for OCR
    - Contains: EXIF correction + OSD rotation + grayscale conversion

---

### Phase 6: OCR Comparison Testing
13. **OCR on Original Image (Baseline)**
    - Apply only EXIF correction
    - Run OCR: `pytesseract.image_to_string(original_exif_corrected)`
    - Count extracted characters
    - Display preview of extracted text

14. **OCR on Processed Image (Final)**
    - Use final processed image (EXIF + rotation + grayscale)
    - Run OCR: `pytesseract.image_to_string(corrected_image)`
    - Count extracted characters
    - Compare with original OCR results
    - Show improvement/reduction percentage

---

### Phase 7: LLM Enhancement (If Enabled)
15. **Initialize Text Enhancer**
    - Check if `TEXT_ENHANCEMENT_ENABLED=True`
    - Check if `GROQ_API_KEY` is set
    - Initialize `TextEnhancer` with Groq LLM

16. **Raw OCR Extraction (Without Enhancement)**
    - Create `DocumentProcessor` without text enhancer
    - Process final image to get raw OCR text
    - Display raw OCR text (first 500 chars)

17. **OCR with LLM Enhancement**
    - Create `DocumentProcessor` with text enhancer
    - Process final image
    - LLM enhances OCR text:
      - Fixes character recognition errors
      - Structures text properly
      - Improves formatting
      - **No hallucination** - only corrects existing text

18. **Enhancement Comparison**
    - Compare raw OCR vs enhanced OCR
    - Show character count differences
    - Display enhanced text preview

---

### Phase 8: Output Generation
19. **Generate Markdown Report**
    - Create comprehensive markdown file
    - Include all processing steps
    - Include raw OCR text
    - Include enhanced OCR text
    - Include all metrics and comparisons
    - **Output saved:** `InCorrect.md` (or timestamped file)

20. **Console Output**
    - All steps logged to console in real-time
    - Detailed information for debugging
    - Clear section separators

---

## Key Files Generated

1. **`scripts/preprocessed_InCorrect.jpg`**
   - After initial grayscale conversion
   - Before orientation correction

2. **`scripts/final_ocr_image_InCorrect.jpg`**
   - **FINAL IMAGE USED FOR OCR**
   - After EXIF correction
   - After OSD rotation (if applied)
   - After grayscale conversion
   - This is what Tesseract actually processes

3. **`InCorrect.md`** (or specified output file)
   - Complete processing report
   - All metrics and comparisons
   - Raw and enhanced OCR text

---

## Rotation Logic Details

### Tesseract OSD "Rotate" Value
- **Meaning:** Amount to rotate CLOCKWISE to correct orientation
- **Values:** 0, 90, 180, 270
- **Example:** "Rotate: 270" means rotate 270° clockwise

### PIL `rotate()` Method
- **Direction:** Counter-clockwise
- **Example:** `rotate(90)` rotates 90° counter-clockwise

### Conversion Formula
```
PIL_angle = -OSD_angle
```

**Examples:**
- OSD: "Rotate: 270" → PIL: `rotate(-270)` or `rotate(90)`
- OSD: "Rotate: 90" → PIL: `rotate(-90)` or `rotate(270)`
- OSD: "Rotate: 180" → PIL: `rotate(-180)` or `rotate(180)` (same result)

### Confidence Threshold
- **Current:** 0.3 (30%)
- **Logic:** Only rotate if `confidence > 0.3` or `confidence is None`
- **Purpose:** Avoid incorrect rotations on low-confidence detections

---

## Processing Order Summary

```
Original Image
    ↓
[1] Load & Analyze
    ↓
[2] Quality Analysis
    ↓
[3] Preprocess (Grayscale) → preprocessed_*.jpg
    ↓
[4] EXIF Correction
    ↓
[5] Tesseract OSD Detection
    ↓
[6] Apply Rotation (if needed & confidence > 0.3)
    ↓
[7] Convert to Grayscale → final_ocr_image_*.jpg
    ↓
[8] OCR Extraction
    ↓
[9] LLM Enhancement (if enabled)
    ↓
[10] Generate Report → *.md
```

---

## Troubleshooting

### Rotation Not Applied?
1. Check OSD confidence value in output
2. Verify confidence > 0.3 threshold
3. Check if rotation_angle != 0
4. Verify OSD parsing succeeded (check for "Rotate: X" in output)

### Image Still Wrong Orientation?
1. Check `final_ocr_image_*.jpg` to see what Tesseract receives
2. Verify rotation was actually applied (check dimension changes)
3. Check if EXIF correction interfered with OSD rotation
4. Review OSD output for correct angle detection

### Low OCR Quality?
1. Check image quality metrics (brightness, contrast)
2. Verify grayscale conversion worked
3. Check if rotation improved or worsened results
4. Compare original vs processed OCR results
