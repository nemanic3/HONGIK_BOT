"""Synthetic fixtures only; real Vision tests never access a database."""
from contextlib import contextmanager
from io import BytesIO
import os
from pathlib import Path
import platform
import shutil
import tempfile
import unittest
from unittest.mock import patch

from . import vision_provider

from PIL import Image, ImageDraw, ImageFont


def synthetic_png():
    """Discover an installed font and label the generated non-student image."""
    roots = [Path('/System/Library/Fonts'), Path('/Library/Fonts')]
    candidates = [root / 'Helvetica.ttc' for root in roots]
    candidates += [path for root in roots if root.exists()
                   for path in root.rglob('*')
                   if path.suffix.lower() in {'.ttf', '.ttc', '.otf'}]
    for path in candidates:
        try:
            font = ImageFont.truetype(str(path), 48)
            break
        except OSError:
            continue
    else:
        raise unittest.SkipTest('Real OCR fixture blocked: no usable installed font')
    image = Image.new('RGB', (1400, 360), 'white')
    draw = ImageDraw.Draw(image)
    for number, line in enumerate([
        'SYNTHETIC OCR FIXTURE', 'ENGLISH COURSE 3 A+', 'NOT STUDENT DATA',
    ]):
        draw.text((45, 40 + number * 95), line, fill='black', font=font)
    output = BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


@contextmanager
def stub_swift(stdout=b'{"text":"fixture","provider":"apple_vision"}',
               stderr=b'', returncode=0, effect=None):
    """Only simulate process boundaries; never claim stub text is real OCR."""
    def run(argv, **kwargs):
        if effect:
            return effect(argv, **kwargs)
        if 'stdout' in kwargs:
            kwargs['stdout'].write(stdout)
            kwargs['stderr'].write(stderr)
        return vision_provider.subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    with patch('platform.system', return_value='Darwin'), \
            patch('shutil.which', return_value='/usr/bin/swift'), \
            patch.object(vision_provider.subprocess, 'run', side_effect=run) as mocked:
        yield mocked


class VisionProviderTests(unittest.TestCase):
    def test_invalid_or_oversized_png_is_rejected_before_subprocess(self):
        huge_dimensions = BytesIO()
        Image.new('1', (20_000_001, 1)).save(huge_dimensions, format='PNG')
        jpeg = BytesIO()
        Image.new('RGB', (20, 20)).save(jpeg, format='JPEG')
        inputs = [b'', 'not bytes', bytearray(synthetic_png()), b'not PNG',
                  b'\x89PNG\r\n\x1a\ntruncated', jpeg.getvalue(),
                  b'\x89PNG\r\n\x1a\n' + b'x' * (10 * 1024 * 1024),
                  huge_dimensions.getvalue()]
        with stub_swift() as run:
            for value in inputs:
                with self.subTest(kind=type(value).__name__, length=len(value)):
                    with self.assertRaisesRegex(ValueError, 'PNG|bytes|limit'):
                        vision_provider.recognize_png(value)
            run.assert_not_called()

    def test_process_is_bounded_and_private_under_explicit_tmpdir(self):
        observed = []
        png = synthetic_png()
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
            def process(argv, **kwargs):
                directory = Path(argv[-1]).parent
                observed.append(directory)
                self.assertEqual(directory.parent, Path(root))
                self.assertEqual(directory.stat().st_mode & 0o077, 0)
                self.assertEqual(Path(argv[-1]).stat().st_mode & 0o077, 0)
                self.assertEqual(Path(argv[-1]).read_bytes(), png)
                self.assertEqual(argv[0], '/usr/bin/swift')
                self.assertEqual(argv[1], '-module-cache-path')
                self.assertEqual(kwargs['timeout'], 90)
                self.assertIs(kwargs['shell'], False)
                self.assertEqual(kwargs['stdin'], vision_provider.subprocess.DEVNULL)
                self.assertNotIn('capture_output', kwargs)
                self.assertTrue(hasattr(kwargs['stdout'], 'write'))
                self.assertTrue(hasattr(kwargs['stderr'], 'write'))
                kwargs['stdout'].write(b'{"text":"fixture","provider":"apple_vision"}')
                return vision_provider.subprocess.CompletedProcess(argv, 0)
            with patch.dict(os.environ, {'TMPDIR': root}), stub_swift(effect=process):
                result = vision_provider.recognize_png(png)
            self.assertEqual(result['text'], 'fixture')
            self.assertEqual(len(observed), 1)
            self.assertFalse(observed[0].exists())

    def test_timeout_is_explicit_and_cleans_private_files(self):
        observed = []
        def timeout(argv, **kwargs):
            observed.append(Path(argv[-1]).parent)
            raise vision_provider.subprocess.TimeoutExpired(argv, 90, stderr=b'x' * 5000)
        with stub_swift(effect=timeout):
            with self.assertRaises(Exception) as raised:
                vision_provider.recognize_png(synthetic_png())
            self.assertIsInstance(raised.exception, RuntimeError)
            self.assertRegex(str(raised.exception), 'timed out.*90')
        self.assertFalse(observed[0].exists())

    def test_nonzero_exit_has_bounded_error_and_no_fake_text(self):
        with stub_swift(stderr=b'synthetic failure ' + b'x' * 5000, returncode=7):
            with self.assertRaises(RuntimeError) as raised:
                vision_provider.recognize_png(synthetic_png())
        self.assertIn('exit 7', str(raised.exception))
        self.assertIn('synthetic failure', str(raised.exception))
        self.assertLessEqual(len(str(raised.exception)), 1200)

    def test_invalid_or_oversized_provider_output_is_an_explicit_blocker(self):
        outputs = [b'not JSON', b'\xff', b'[]', b'{}',
                   b'{"text":5,"provider":"apple_vision"}',
                   b'{"text":"text","provider":"not_vision"}',
                   b'{"text":"   ","provider":"apple_vision"}',
                   b'{"text":"' + b'x' * (1024 * 1024) +
                   b'","provider":"apple_vision"}']
        for stdout in outputs:
            with self.subTest(length=len(stdout)), stub_swift(stdout=stdout):
                with self.assertRaises(Exception) as raised:
                    vision_provider.recognize_png(synthetic_png())
                self.assertIsInstance(raised.exception, RuntimeError)
                self.assertRegex(str(raised.exception), 'output|text|response')
                self.assertLessEqual(len(str(raised.exception)), 1200)

    def test_language_fallback_provenance_is_exercised_by_real_swift(self):
        swift = shutil.which('swift')
        if platform.system() != 'Darwin' or not swift:
            self.skipTest('Language-selection Swift probe blocked: macOS/Swift required')
        script = Path(vision_provider.__file__).resolve().parent.parent / 'scripts' / 'vision_ocr.swift'
        source = script.read_text()
        self.assertIn('// OCR entry point', source,
                      'Swift provider must expose a testable language-selection boundary')
        harness = source.split('// OCR entry point')[0] + '''
let all = try selectRecognitionLanguages(requested: ["ko-KR", "en-US"],
                                         supported: ["en-US", "ko-KR"])
assert(all == ["ko-KR", "en-US"])
let fallback = try selectRecognitionLanguages(requested: ["ko-KR", "en-US"],
                                              supported: ["en-US"])
assert(fallback == ["en-US"])
var blocked = false
do { _ = try selectRecognitionLanguages(requested: ["ko-KR", "en-US"],
                                         supported: ["fr-FR"]) }
catch { blocked = true }
assert(blocked)
print("REAL_SWIFT_LANGUAGE_PROBE=ko-KR,en-US; fallback=en-US; unsupported=blocked")
'''
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as root:
            path = Path(root) / 'language_probe.swift'
            path.write_text(harness)
            result = vision_provider.subprocess.run(
                [swift, '-module-cache-path', str(Path(root) / 'cache'), str(path)],
                capture_output=True, timeout=90, shell=False, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr[:1024].decode(errors='replace'))
        self.assertIn(b'fallback=en-US; unsupported=blocked', result.stdout)
        print(result.stdout.decode().strip())

    def test_swift_launch_error_remains_an_explicit_tool_blocker(self):
        for failure in (FileNotFoundError('fixture swift disappeared'),
                        PermissionError('fixture executable unavailable')):
            with self.subTest(kind=type(failure).__name__):
                def launch_failure(argv, **kwargs):
                    raise failure
                with stub_swift(effect=launch_failure):
                    with self.assertRaises(Exception) as raised:
                        vision_provider.recognize_png(synthetic_png())
                    self.assertIsInstance(raised.exception, RuntimeError)
                    self.assertIn('Swift', str(raised.exception))
                    self.assertNotIn('fixture', str(raised.exception))

    def test_non_macos_has_explicit_blocker_without_subprocess(self):
        with patch('platform.system', return_value='Linux'), \
                patch.object(vision_provider.subprocess, 'run', return_value=
                             vision_provider.subprocess.CompletedProcess(
                                 [], 0, b'{"text":"","provider":"apple_vision"}')) as run:
            with self.assertRaisesRegex(RuntimeError, 'macOS'):
                vision_provider.recognize_png(synthetic_png())
            run.assert_not_called()

    def test_missing_swift_has_explicit_blocker_without_subprocess(self):
        with patch('platform.system', return_value='Darwin'), \
                patch('shutil.which', return_value=None), \
                patch.object(vision_provider.subprocess, 'run', return_value=
                             vision_provider.subprocess.CompletedProcess(
                                 [], 0, b'{"text":"","provider":"apple_vision"}')) as run:
            with self.assertRaisesRegex(RuntimeError, 'Swift'):
                vision_provider.recognize_png(synthetic_png())
            run.assert_not_called()

    @unittest.skipUnless(platform.system() == 'Darwin',
                         'Real Apple Vision OCR blocked: macOS is required')
    @unittest.skipUnless(shutil.which('swift'),
                         'Real Apple Vision OCR blocked: Swift is missing')
    def test_real_swift_recognizes_labeled_synthetic_png(self):
        try:
            from .vision_provider import recognize_png
        except ImportError:
            self.fail('Optional Apple Vision PNG provider has not been implemented')
        result = recognize_png(synthetic_png())
        self.assertEqual(result['provider'], 'apple_vision')
        self.assertIn('SYNTHETIC OCR FIXTURE', result['text'])
        self.assertIn('ENGLISH COURSE 3 A+', result['text'])
        self.assertIn('NOT STUDENT DATA', result['text'])
        self.assertEqual(result.get('recognition_level'), 'accurate')
        self.assertEqual(result.get('requested_languages'), ['ko-KR', 'en-US'])
        supported = result.get('supported_languages', [])
        selected = [language for language in ['ko-KR', 'en-US'] if language in supported]
        unsupported = [language for language in ['ko-KR', 'en-US'] if language not in supported]
        self.assertEqual(result.get('recognition_languages'), selected)
        self.assertEqual(result.get('unsupported_languages'), unsupported)
        self.assertEqual(bool(result.get('warnings')), bool(unsupported))
        self.assertIsInstance(result.get('revision'), int)
        print('REAL_VISION_RESULT=' + repr(result))
