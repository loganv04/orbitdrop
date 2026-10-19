"""Headless interaction checks. Set QT_QPA_PLATFORM=offscreen on CI."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import math
from pathlib import Path
import tempfile
import time
import unittest

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from orbitdrop.app import Editor, MainWindow, STYLE
from test_core import text_pdf


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'sample.png'
        Image.new('RGBA', (320, 200), (20, 100, 210, 255)).save(self.source)
        self.window = MainWindow()
        self.window.output_dir = self.root / 'exports'
        self.window.show()
        self.app.processEvents()

    def settle(self, window=None):
        window = window or self.window
        deadline = time.monotonic() + 10
        while window.worker and window.worker.isRunning():
            self.app.processEvents()
            QTest.qWait(10)
            if time.monotonic() > deadline:
                self.fail('Worker timeout')
        self.app.processEvents()
        QTest.qWait(20)
        self.app.processEvents()

    def tearDown(self):
        self.settle()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.temp.cleanup()

    def wheel_point(self, index):
        center, radius = self.window.wheel.geometry_values()
        angle = math.radians(index * 45 - 90)
        return (center + QPointF(math.cos(angle) * radius * .74, math.sin(angle) * radius * .74)).toPoint()

    def test_choose_file_click_format_and_export(self):
        self.window.add_files([self.source])
        self.settle()
        self.assertFalse(self.window.preview_label.pixmap().isNull())
        QTest.mouseClick(self.window.wheel, Qt.MouseButton.LeftButton, pos=self.wheel_point(1))
        self.assertEqual(self.window.target, 'JPG')
        QTest.mouseClick(self.window.convert_button, Qt.MouseButton.LeftButton)
        self.settle()
        output = self.window.output_dir / 'sample.jpg'
        self.assertTrue(output.is_file())
        with Image.open(output) as image:
            self.assertEqual(image.size, (320, 200))

    def test_shift_drop_onto_wheel_converts_only_dropped_files(self):
        other = self.root / 'existing.png'
        Image.new('RGB', (20, 20)).save(other)
        self.window.add_files([other])
        self.settle()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.source))])
        position = self.wheel_point(2)  # WEBP
        enter = QDragEnterEvent(position, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
        QApplication.sendEvent(self.window.wheel, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(position), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier)
        QApplication.sendEvent(self.window.wheel, drop)
        self.settle()
        self.assertTrue((self.window.output_dir / 'sample.webp').is_file())
        self.assertFalse((self.window.output_dir / 'existing.webp').exists())

    def test_mixed_queue_disables_unsupported_targets(self):
        pdf = self.root / 'text.pdf'
        text_pdf(pdf)
        self.window.add_files([pdf])
        self.settle()
        self.assertIn('TXT', self.window.wheel.available)
        self.window.choose_target('TXT')
        self.window.add_files([self.source])
        self.settle()
        self.assertNotIn('TXT', self.window.wheel.available)
        self.assertNotIn('PDF', self.window.wheel.available)
        self.assertEqual(self.window.target, 'PNG')

    def test_crop_drag_frame_and_export(self):
        editor = Editor(Image.open(self.source).convert('RGBA'), self.source, self.window.output_dir, self.window)
        editor.show()
        self.app.processEvents()
        rect = editor.canvas.image_rect()
        start = QPoint(round(rect.left() + rect.width() * .25), round(rect.top() + rect.height() * .25))
        end = QPoint(round(rect.left() + rect.width() * .75), round(rect.top() + rect.height() * .75))
        QTest.mousePress(editor.canvas, Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(editor.canvas, end)
        QTest.mouseRelease(editor.canvas, Qt.MouseButton.LeftButton, pos=end)
        self.assertIsNotNone(editor.canvas.selection)
        box = editor.canvas.selection
        QTest.mouseClick(editor.crop_button, Qt.MouseButton.LeftButton)
        self.assertEqual(editor.canvas.image.size, (box[2] - box[0], box[3] - box[1]))
        editor.padding.setValue(20)
        QTest.mouseClick(editor.save_button, Qt.MouseButton.LeftButton)
        self.settle(editor)
        with Image.open(self.window.output_dir / 'sample_edited.png') as image:
            self.assertEqual(image.size, (editor.canvas.image.width + 40, editor.canvas.image.height + 40))
        editor.close()


if __name__ == '__main__':
    unittest.main()
