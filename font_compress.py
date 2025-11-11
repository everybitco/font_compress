import sys
import argparse
from PIL import Image
import struct
from pathlib import Path

def load_image(path):
    img = Image.open(path).convert('L')  # Convert to grayscale
    return img

def detect_grid(img, threshold=128):
    """Auto detect character grid by finding empty rows/colms"""
    pixels = img.load()
    w, h = img.size
    
    # Find vertical separators (empty columns)
    v_seps = []
    for x in range(w):
        if all(pixels[x, y] < threshold for y in range(h)):
            v_seps.append(x)
    
    # Find horizontal separators (empty rows)
    h_seps = []
    for y in range(h):
        if all(pixels[x, y] < threshold for x in range(w)):
            h_seps.append(y)
    
    # Calculate grid from separators
    if v_seps and h_seps:
        char_width = v_seps[1] - v_seps[0] if len(v_seps) > 1 else w
        char_height = h_seps[1] - h_seps[0] if len(h_seps) > 1 else h
        cols = len(v_seps) - 1 if len(v_seps) > 1 else 1
        rows = len(h_seps) - 1 if len(h_seps) > 1 else 1
        return cols, rows, char_width, char_height
    
    return None

def binarize_image(img, threshold=128):
    """Convert grayscale to pure black/white"""
    pixels = img.load()
    w, h = img.size
    binary = []
    for y in range(h):
        for x in range(w):
            binary.append(0x00 if pixels[x, y] < threshold else 0xFF)
    return binary

def compress_to_bits(pixels):
    """Pack 8 monochrome pixels into 1 byte"""
    assert len(pixels) % 8 == 0, "Pixel count must be divisible by 8"
    
    # Pre-allocate bytearray for better performance and memory efficiency
    compressed = bytearray(len(pixels) // 8)
    
    for i in range(0, len(pixels), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | (1 if pixels[i + j] == 0xFF else 0)
        compressed[i // 8] = byte  # Direct index assignment
    
    return compressed

def rle_compress(data):
    """Custom RLE: 0x00 followed by count byte for zero runs"""
    result = []
    i = 0
    n = len(data)
    
    while i < n:
        result.append(data[i])
        
        if data[i] == 0x00:
            i += 1
            count = 1
            while i < n and data[i] == 0x00 and count < 255:
                i += 1
                count += 1
            result.append(count)
        else:
            i += 1
    
    return result

def generate_solid_char(pixels, w, h, cols, rows, char_w, char_h):
    """Generate solid character at position 95 (127 - 32)"""
    index = 95  # Character 127 (DEL) at position 95 in ASCII printable range
    x0 = (index % cols) * char_w
    y0 = (index // cols) * char_h
    
    for dy in range(char_h):
        for dx in range(char_w):
            x = x0 + dx
            y = y0 + dy
            if 0 <= x < w and 0 <= y < h:
                pixels[y * w + x] = 0xFF

def format_rust(data, name="COMPRESSED_FONT"):
    lines = [
        "// https://github.com/everybitco/font_compress",
        "",
        f"const {name}: [u8; {len(data)}] = ["
    ]
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        line = "    " + ", ".join(f"{b:#04x}" for b in chunk) + ","
        lines.append(line)
    lines.append("];")
    return "\n".join(lines)

def format_c(data, name="COMPRESSED_FONT"):
    lines = [
        "// https://github.com/everybitco/font_compress",
        "",
        f"const unsigned char {name}[{len(data)}] = {{"
    ]
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        line = "    " + ", ".join(f"{b:#04x}" for b in chunk) + ","
        lines.append(line)
    lines.append("};")
    return "\n".join(lines)

def format_binary(data):
    return bytes(data)

def print_stats(original_size, compressed_size, img_w, img_h, cols, rows, char_w, char_h):
    ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
    print("=" * 50, file=sys.stderr)
    print(f"📊 COMPRESSION STATS", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print(f"Image:      {img_w}×{img_h} pixels", file=sys.stderr)
    print(f"Grid:       {cols} cols × {rows} rows", file=sys.stderr)
    print(f"Char size:  {char_w}×{char_h} pixels", file=sys.stderr)
    print(f"Characters: {cols * rows}", file=sys.stderr)
    print("-" * 50, file=sys.stderr)
    print(f"Original:   {original_size:,} bytes", file=sys.stderr)
    print(f"Compressed: {compressed_size:,} bytes", file=sys.stderr)
    print(f"Reduction:  {ratio:.1f}%", file=sys.stderr)
    print(f"Ratio:      {original_size/compressed_size:.2f}:1", file=sys.stderr)
    print("=" * 50, file=sys.stderr)
    print("", file=sys.stderr)

def save_preview(pixels, w, h, output_path):
    img = Image.new('L', (w, h))
    img.putdata(pixels)
    img.save(output_path)
    print(f"Preview saved: {output_path}", file=sys.stderr)

def decompress_and_verify(compressed, original_size):
    result = []
    i = 0
    while i < len(compressed):
        if compressed[i] == 0x00:
            if i + 1 < len(compressed):
                count = compressed[i + 1]
                result.extend([0x00] * count)
                i += 2
            else:
                result.append(0x00)
                i += 1
        else:
            result.append(compressed[i])
            i += 1
    
    # Unpack bits
    unpacked = []
    for byte in result:
        for bit in range(8):
            unpacked.append(0xFF if (byte & (1 << (7 - bit))) else 0x00)
    
    return unpacked[:original_size]

def main():
    parser = argparse.ArgumentParser(
        description="Compress bitmap fonts",
        epilog="Example: python font_compress.py font.png --stats -f rust -o font.rs"
    )
    parser.add_argument("image", help="Input font spritesheet image")
    parser.add_argument("-f", "--format", choices=["rust", "c", "bin"], default="rust",
                       help="Output format (default: rust)")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--grid", help="Manual grid size (e.g., 18x7)")
    parser.add_argument("--char-size", help="Manual character size (e.g., 7x9)")
    parser.add_argument("--solid", action="store_true", help="Generate solid character at position 127")
    parser.add_argument("--raw", action="store_true", help="Skip compression")
    parser.add_argument("--threshold", type=int, default=128, 
                       help="Binarization threshold 0-255 (default: 128)")
    parser.add_argument("--stats", action="store_true", help="Print compression statistics")
    parser.add_argument("--preview", help="Save preview image (e.g., preview.png)")
    parser.add_argument("--verify", action="store_true", help="Verify compression by decompressing")
    parser.add_argument("--batch", nargs="+", help="Process multiple images (e.g., *.png)")
    parser.add_argument("--list-fonts", action="store_true", help="List characters in the font")
    
    args = parser.parse_args()
    
    # Batch mode
    if args.batch:
        for img_path in args.batch:
            print(f"\n{'='*60}", file=sys.stderr)
            print(f"Processing: {img_path}", file=sys.stderr)
            print(f"{'='*60}", file=sys.stderr)
            output_path = args.output or str(Path(img_path).stem) + ".rs"
            process_image(img_path, args, output_path)
        return
    
    # Single image mode
    if not args.image:
        parser.print_help()
        return
    
    process_image(args.image, args, args.output)

def process_image(image_path, args, output_path):
    img = load_image(image_path)
    w, h = img.size
    
    # Determine grid layout
    if args.grid and args.char_size:
        cols, rows = map(int, args.grid.split('x'))
        char_w, char_h = map(int, args.char_size.split('x'))
    elif args.grid:
        cols, rows = map(int, args.grid.split('x'))
        char_w = w // cols
        char_h = h // rows
    elif args.char_size:
        char_w, char_h = map(int, args.char_size.split('x'))
        cols = w // char_w
        rows = h // char_h
    else:
        # Autodetect
        detected = detect_grid(img, args.threshold)
        if detected:
            cols, rows, char_w, char_h = detected
        else:
            # Fallback: assume standard ASCII printable (95 chars)
            cols = 16
            rows = (95 + cols - 1) // cols
            char_w = w // cols
            char_h = h // rows
    
    if w % char_w != 0 or h % char_h != 0:
        print(f"Warning: Image size {w}×{h} not evenly divisible by char size {char_w}×{char_h}", 
              file=sys.stderr)
    
    pixels = binarize_image(img, args.threshold)
    original_size = len(pixels)
    
    if args.solid:
        generate_solid_char(pixels, w, h, cols, rows, char_w, char_h)
    
    if args.raw:
        compressed = pixels
    else:
        bit_packed = compress_to_bits(pixels)
        compressed = rle_compress(bit_packed)
    
    if args.stats:
        print_stats(original_size, len(compressed), w, h, cols, rows, char_w, char_h)
    
    if hasattr(args, 'list_fonts') and args.list_fonts:
        char_count = cols * rows
        print(f"Font contains {char_count} characters:", file=sys.stderr)
        print(f"ASCII range: {32} to {32 + char_count - 1}", file=sys.stderr)
        print(f"Printable: '{chr(32)}' to '{chr(min(32 + char_count - 1, 126))}'", file=sys.stderr)
    
    if args.preview:
        save_preview(pixels, w, h, args.preview)
    
    # Verify compression
    if args.verify and not args.raw:
        decompressed = decompress_and_verify(compressed, len(pixels))
        if decompressed == pixels:
            print("Compression verified successfully", file=sys.stderr)
        else:
            print("Compression verification failed!", file=sys.stderr)
            sys.exit(1)
    
    if args.format == "rust":
        output = format_rust(compressed)
    elif args.format == "c":
        output = format_c(compressed)
    else:  # bin
        output = format_binary(compressed)
    
    if output_path:
        mode = 'wb' if args.format == 'bin' else 'w'
        with open(output_path, mode) as f:
            if isinstance(output, bytes):
                f.write(output)
            else:
                f.write(output)
        print(f"Output saved to: {output_path}", file=sys.stderr)
    else:
        if isinstance(output, bytes):
            sys.stdout.buffer.write(output)
        else:
            print(output)

if __name__ == "__main__":
    main()
