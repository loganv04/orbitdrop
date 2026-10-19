import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from docx import Document

from orbitdrop.core import (
    ConversionError, Options, add_frame, convert, crop_image, load_image,
    preview, render_pdf_page, save_image,
)


def text_pdf(path):
    writer = PdfWriter()
    for text in ("OrbitDrop sample document", "Second page: local conversion"):
        page = writer.add_blank_page(width=300, height=200)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f'BT /F1 16 Tf 20 100 Td ({text}) Tj ET'.encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    with Path(path).open('wb') as handle:
        writer.write(handle)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'transparent.png'
        image = Image.new('RGBA', (80, 60), (20, 100, 200, 255))
        image.putpixel((0, 0), (0, 0, 0, 0))
        image.save(self.source)
        self.output = self.root / 'output'
        self.pdf = self.root / 'document.pdf'
        text_pdf(self.pdf)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_image_targets_and_preserved_source(self):
        before = self.source.read_bytes()
        for target in ('PNG', 'JPG', 'WEBP', 'TIFF', 'BMP', 'PDF'):
            with self.subTest(target=target):
                result = convert(self.source, target, self.output)[0]
                if target == 'PDF':
                    self.assertEqual(len(PdfReader(result).pages), 1)
                else:
                    with Image.open(result) as image:
                        self.assertEqual(image.size, (80, 60))
                        if target in ('PNG', 'WEBP', 'TIFF'):
                            self.assertEqual(image.convert('RGBA').getpixel((0, 0))[3], 0)
                        if target == 'BMP':
                            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(before, self.source.read_bytes())

    def test_same_folder_never_overwrites(self):
        original = self.source.read_bytes()
        one = convert(self.source, 'PNG', self.root)[0]
        two = convert(self.source, 'PNG', self.root)[0]
        self.assertNotEqual(one, two)
        self.assertNotEqual(one, self.source)
        self.assertEqual(self.source.read_bytes(), original)

    def test_concurrent_filename_reservation(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda _: convert(self.source, 'PNG', self.output)[0], range(8)))
        self.assertEqual(len(set(paths)), 8)
        self.assertTrue(all(path.stat().st_size > 0 for path in paths))

    def test_pdf_all_pages_and_dpi(self):
        paths = convert(self.pdf, 'PNG', self.output, Options(dpi=144))
        self.assertEqual(len(paths), 2)
        with Image.open(paths[0]) as image:
            self.assertEqual(image.size, (600, 400))
        self.assertIn('page_002', paths[1].name)

    def test_pdf_text_and_word_exports(self):
        txt = convert(self.pdf, 'TXT', self.output)[0].read_text()
        self.assertIn('OrbitDrop sample document', txt)
        self.assertIn('Second page', txt)
        path = convert(self.pdf, 'DOCX', self.output)[0]
        paragraphs = '\n'.join(p.text for p in Document(path).paragraphs)
        self.assertIn('Second page', paragraphs)

    def test_scanned_pdf_explains_ocr(self):
        path = convert(self.source, 'PDF', self.output)[0]
        with self.assertRaisesRegex(ConversionError, 'OCR'):
            convert(path, 'TXT', self.output)
        self.assertEqual(list(self.output.glob('*.txt')), [])

    def test_crop_and_gradient(self):
        image = load_image(self.source)
        cropped = crop_image(image, (10, 10, 60, 40))
        self.assertEqual(cropped.size, (50, 30))
        framed = add_frame(cropped, padding=20, radius=5, palette='Ocean')
        self.assertEqual(framed.size, (90, 70))
        self.assertNotEqual(framed.getpixel((0, 0)), framed.getpixel((0, 69)))
        self.assertEqual(framed.getpixel((45, 35))[:3], (20, 100, 200))

    def test_invalid_crop_settings_and_format(self):
        image = load_image(self.source)
        for box in ((0, 0, 0, 0), (-1, 0, 10, 10), (0, 0, 100, 100)):
            with self.assertRaises(ConversionError):
                crop_image(image, box)
        with self.assertRaises(ConversionError):
            convert(self.source, 'TXT', self.output)
        with self.assertRaises(ConversionError):
            convert(self.source, 'PNG', self.output, Options(quality=101))

    def test_corrupt_input_leaves_no_output(self):
        broken = self.root / 'broken.png'
        broken.write_bytes(b'not an image')
        with self.assertRaises(Exception):
            convert(broken, 'JPG', self.output)
        self.assertFalse(self.output.exists())

    def test_failed_write_cleans_partial_file(self):
        with patch('PIL.Image.Image.save', side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):
                save_image(load_image(self.source), self.output, 'partial', 'PNG')
        self.assertEqual(list(self.output.iterdir()), [])

    def test_failed_second_pdf_page_rolls_back_first(self):
        first = render_pdf_page(self.pdf)
        with patch('orbitdrop.core.render_pdf_page', side_effect=[first, OSError('Read error')]):
            with self.assertRaises(OSError):
                convert(self.pdf, 'PNG', self.output)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_encrypted_pdf_and_resource_limits(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('secret')
        locked = self.root / 'locked.pdf'
        with locked.open('wb') as handle:
            writer.write(handle)
        with self.assertRaises(ConversionError):
            convert(locked, 'TXT', self.output)
        with patch('orbitdrop.core.MAX_PIXELS', 20):
            with self.assertRaises(ConversionError):
                load_image(self.source)
        with patch('orbitdrop.core.MAX_PAGES', 1):
            with self.assertRaises(ConversionError):
                convert(self.pdf, 'PNG', self.output)

    def test_preview_and_exif_orientation(self):
        self.assertLessEqual(max(preview(self.pdf).size), 640)
        path = self.root / 'rotated.jpg'
        image = Image.new('RGB', (40, 20), 'red')
        exif = image.getexif()
        exif[274] = 6
        image.save(path, exif=exif)
        self.assertEqual(load_image(path).size, (20, 40))


if __name__ == '__main__':
    unittest.main()
