#!/bin/bash

# Exit immediately on error
set -e

INPUT_DIR="$1"
OUTPUT_DIR="$2"
LANG="eng"

if [[ -z "$INPUT_DIR" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: $0 <input_folder> <output_folder>"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

for file in "$INPUT_DIR"/*.{png,jpg,jpeg,tiff,tif,bmp}; do
  [[ -e "$file" ]] || continue

  filename=$(basename "$file")
  name="${filename%.*}"

  echo "Processing: $filename"
  tesseract "$file" "$OUTPUT_DIR/$name" -l "$LANG"
done

echo "OCR completed."

