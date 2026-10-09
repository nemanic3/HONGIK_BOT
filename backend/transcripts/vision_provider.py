"""Optional local Apple Vision OCR adapter: PNG bytes in, JSON metadata out."""
from io import BytesIO
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile

from PIL import Image, UnidentifiedImageError

MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_OUTPUT_BYTES = 1024 * 1024


def recognize_png(png_bytes):
    """Recognize one PNG using the bundled Swift Vision request."""
    if platform.system() != 'Darwin':
        raise RuntimeError('Apple Vision OCR requires macOS; enter courses manually.')
    swift = shutil.which('swift')
    if not swift:
        raise RuntimeError('Apple Vision OCR requires Swift command-line tools; enter courses manually.')
    if not isinstance(png_bytes, bytes) or not png_bytes:
        raise ValueError('Apple Vision OCR requires nonempty PNG bytes.')
    if len(png_bytes) > MAX_INPUT_BYTES:
        raise ValueError('PNG input exceeds the 10 MiB limit.')
    try:
        with Image.open(BytesIO(png_bytes)) as decoded:
            if decoded.format != 'PNG':
                raise ValueError('Apple Vision OCR requires PNG input.')
            if decoded.width * decoded.height > MAX_PIXELS:
                raise ValueError('PNG dimensions exceed the 20-megapixel limit.')
            decoded.verify()
    except (OSError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError('Invalid PNG input.') from exc
    script = Path(__file__).resolve().parent.parent / 'scripts' / 'vision_ocr.swift'
    with tempfile.TemporaryDirectory(prefix='hongik-vision-', dir=os.environ.get('TMPDIR')) as directory:
        image = Path(directory) / 'input.png'
        image.write_bytes(png_bytes)
        image.chmod(0o600)
        with tempfile.TemporaryFile(dir=directory) as stdout, \
                tempfile.TemporaryFile(dir=directory) as stderr:
            try:
                completed = subprocess.run(
                    [swift, '-module-cache-path', str(Path(directory) / 'module-cache'),
                     str(script), str(image)],
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                    shell=False, timeout=90, check=False,
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError('Apple Vision OCR timed out after 90 seconds; enter courses manually.') from None
            except OSError:
                raise RuntimeError('Apple Vision OCR cannot launch Swift; check command-line tools or enter courses manually.') from None
            if completed.returncode:
                stderr.seek(0)
                diagnostic = stderr.read(1024).decode('utf-8', errors='replace')
                raise RuntimeError(f'Apple Vision OCR failed (exit {completed.returncode}): {diagnostic}')
            stdout.seek(0)
            output = stdout.read(MAX_OUTPUT_BYTES + 1)
            if len(output) > MAX_OUTPUT_BYTES:
                raise RuntimeError('Apple Vision OCR output exceeds the 1 MiB limit.')
            try:
                result = json.loads(output)
            except (ValueError, UnicodeError):
                raise RuntimeError('Apple Vision OCR returned invalid JSON output.') from None
            if (not isinstance(result, dict) or not isinstance(result.get('text'), str)
                    or result.get('provider') != 'apple_vision'):
                raise RuntimeError('Apple Vision OCR returned an invalid provider response.')
            if not result['text'].strip():
                raise RuntimeError('Apple Vision OCR recognized no text; enter courses manually.')
            return result
