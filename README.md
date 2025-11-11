# font_compress
this compresses bitmap fonts

Branch Changes:

Optimize `compress_to_bits` with bytearray
- Replace list-based bit packing with bytearray
- Pre-allocate memory instead of dynamic growth


```
usage: font_compress.py [-h] [-f {rust,c,bin}] [-o OUTPUT] [--grid GRID]
                 [--char-size CHAR_SIZE] [--solid] [--raw]
                 [--threshold THRESHOLD] [--stats] [--preview PREVIEW]
                 [--verify] [--batch BATCH [BATCH ...]] [--list-fonts]
                 image

Compress bitmap fonts for embedded systems

positional arguments:
  image                 Input font spritesheet image

optional arguments:
  -h, --help            show this help message and exit
  -f {rust,c,bin}, --format {rust,c,bin}
                        Output format (default: rust)
  -o OUTPUT, --output OUTPUT
                        Output file (default: stdout)
  --grid GRID           Manual grid size (e.g., 18x7)
  --char-size CHAR_SIZE
                        Manual character size (e.g., 7x9)
  --solid               Generate solid character at position 127
  --raw                 Skip compression
  --threshold THRESHOLD
                        Binarization threshold 0-255 (default: 128)
  --stats               Print compression statistics
  --preview PREVIEW     Save preview image (e.g., preview.png)
  --verify              Verify compression by decompressing
  --batch BATCH [BATCH ...]
                        Process multiple images (e.g., *.png)
  --list-fonts          List characters in the font
```

The script loads the font image and converts to grayscale, automatically detects character grid layout or uses manual specifications, if required, converts grayscale to black and white using a threshold, packs 8 monochrome pixels into a single byte (8:1 compression), compresses runs of identical bytes, particularly effective for the empty spaces in fonts.   
     
