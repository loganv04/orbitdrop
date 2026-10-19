"""Desktop interface. All document loading/export runs in one worker at a time."""

import math
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QPointF, QRectF, QThread, Signal, Slot, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from .core import (
    Options, PALETTES, add_frame, convert, crop_image,
    formats_for, load_image, preview, render_pdf_page, save_image, validate_source,
)


STYLE = """
QWidget { background: #f6f4ef; color: #282a31; font-family: 'Arial'; font-size: 13px; }
QMainWindow { background: #f6f4ef; }
QLabel { background: transparent; }
QLabel#eyebrow { color: #9b5b3b; font-size: 10px; font-weight: bold; }
QLabel#title { font-size: 31px; font-weight: bold; }
QLabel#muted { color: #747780; }
QLabel#status { background: #ece9e2; padding: 12px; border-radius: 9px; }
QFrame#panel { background: #ffffff; border: 1px solid #e6e2d9; border-radius: 14px; }
QPushButton { background: #ffffff; border: 1px solid #dedbd3; border-radius: 8px; padding: 10px 15px; }
QPushButton:hover { border-color: #e47848; background: #fff5ed; }
QPushButton:disabled { color: #aaa9a6; background: #efede7; }
QPushButton#primary { background: #e77442; border: 0; color: #ffffff; font-weight: bold; }
QPushButton#primary:hover { background: #d36030; }
QPushButton#primary:disabled { background: #d3bcae; }
QListWidget { background: #ffffff; border: 0; outline: 0; }
QListWidget::item { padding: 12px 8px; border-radius: 6px; }
QListWidget::item:selected { background: #fff0e6; color: #a74a22; }
QComboBox, QSpinBox { background: white; padding: 7px; border: 1px solid #dedbd3; border-radius: 6px; }
QSlider::groove:horizontal { height: 5px; background: #e2ddd4; border-radius: 2px; }
QSlider::handle:horizontal { width: 15px; margin: -5px 0; background: #e77442; border-radius: 7px; }
QCheckBox { spacing: 8px; }
"""


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    return widget


def pixmap(image):
    image = image.convert("RGBA")
    qimage = QImage(image.tobytes(), image.width, image.height, image.width * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


def local_paths(event):
    return [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]


class Worker(QThread):
    progress = Signal(str)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.value = None
        self.error = None

    def run(self):
        try:
            self.value = self.task(self.progress.emit)
        except Exception as exc:
            self.error = str(exc) or type(exc).__name__


class FormatWheel(QWidget):
    chosen = Signal(str)
    filesDropped = Signal(list, str)
    formats = ["PNG", "JPG", "WEBP", "PDF", "TIFF", "BMP", "TXT", "DOCX"]

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 350)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.available = set(self.formats)
        self.selected = "PNG"
        self.hovered = None
        self.count = 0

    def geometry_values(self):
        return QPointF(self.width() / 2, self.height() / 2), min(self.width(), self.height()) * 0.44

    def sector_at(self, point):
        center, radius = self.geometry_values()
        x, y = point.x() - center.x(), point.y() - center.y()
        if not radius * 0.46 <= math.hypot(x, y) <= radius:
            return None
        return self.formats[int(((math.degrees(math.atan2(y, x)) + 112.5) % 360) // 45)]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        center, radius = self.geometry_values()
        for index, fmt in enumerate(self.formats):
            start = index * 45 - 112.5 + 1.5
            end = start + 42
            path = QPainterPath()
            for j in range(25):
                angle = math.radians(start + (end - start) * j / 24)
                point = center + QPointF(math.cos(angle) * radius, math.sin(angle) * radius)
                path.moveTo(point) if j == 0 else path.lineTo(point)
            for j in range(25):
                angle = math.radians(end - (end - start) * j / 24)
                path.lineTo(center + QPointF(math.cos(angle) * radius * 0.46, math.sin(angle) * radius * 0.46))
            path.closeSubpath()
            active = fmt in self.available
            selected = fmt == self.selected and active
            color = "#e77442" if selected else "#f3d5be" if fmt == self.hovered and active else "#f1e4d6" if active else "#eeece7"
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawPath(path)
            angle = math.radians(index * 45 - 90)
            position = center + QPointF(math.cos(angle) * radius * 0.74, math.sin(angle) * radius * 0.74)
            p.setPen(QColor("white" if selected else "#42382f" if active else "#b2b0aa"))
            p.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            p.drawText(QRectF(position.x() - 32, position.y() - 13, 64, 26), Qt.AlignmentFlag.AlignCenter, fmt)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(center, radius * 0.41, radius * 0.41)
        p.setPen(QColor("#dc6f3e"))
        p.setFont(QFont("Arial", 23, QFont.Weight.Bold))
        p.drawText(QRectF(center.x() - 55, center.y() - 34, 110, 40), Qt.AlignmentFlag.AlignCenter, "↓")
        p.setPen(QColor("#6f716f"))
        p.setFont(QFont("Arial", 10))
        text = f"{self.count} file{'s' if self.count != 1 else ''} ready" if self.count else "Drop files"
        p.drawText(QRectF(center.x() - 60, center.y() + 5, 120, 25), Qt.AlignmentFlag.AlignCenter, text)

    def mouseMoveEvent(self, event):
        self.hovered = self.sector_at(event.position())
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.hovered in self.available else Qt.CursorShape.ArrowCursor)
        self.update()

    def leaveEvent(self, event):
        self.hovered = None
        self.update()

    def mousePressEvent(self, event):
        fmt = self.sector_at(event.position())
        if event.button() == Qt.MouseButton.LeftButton and fmt in self.available:
            self.selected = fmt
            self.chosen.emit(fmt)
            self.update()

    def dragEnterEvent(self, event):
        if self.isEnabled() and local_paths(event):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        self.hovered = self.sector_at(event.position())
        self.update()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.hovered = None
        self.update()

    def dropEvent(self, event):
        fmt = self.sector_at(event.position()) if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else None
        self.filesDropped.emit(local_paths(event), fmt or "")
        self.hovered = None
        self.update()
        event.acceptProposedAction()


class CropCanvas(QWidget):
    """Selection is stored in source-image pixels, not display coordinates."""
    changed = Signal()

    def __init__(self, image):
        super().__init__()
        self.setMinimumSize(440, 360)
        self.image = image
        self.selection = None
        self.anchor = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def image_rect(self):
        scale = min((self.width() - 32) / self.image.width, (self.height() - 32) / self.image.height)
        width, height = self.image.width * scale, self.image.height * scale
        return QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)

    def source_point(self, position):
        rect = self.image_rect()
        return (max(0, min(self.image.width, round((position.x() - rect.x()) / rect.width() * self.image.width))),
                max(0, min(self.image.height, round((position.y() - rect.y()) / rect.height() * self.image.height))))

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#e8e5de"))
        rect = self.image_rect()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(rect.toRect(), pixmap(self.image))
        if self.selection:
            left, top, right, bottom = self.selection
            crop_rect = QRectF(rect.x() + left / self.image.width * rect.width(), rect.y() + top / self.image.height * rect.height(),
                               (right - left) / self.image.width * rect.width(), (bottom - top) / self.image.height * rect.height())
            shade = QPainterPath()
            shade.addRect(rect)
            shade.addRect(crop_rect)
            shade.setFillRule(Qt.FillRule.OddEvenFill)
            p.fillPath(shade, QColor(0, 0, 0, 100))
            p.setPen(QPen(QColor("#ff8c54"), 2))
            p.drawRect(crop_rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.image_rect().contains(event.position()):
            self.anchor = self.source_point(event.position())
            self.selection = None

    def mouseMoveEvent(self, event):
        if self.anchor is not None and event.buttons() & Qt.MouseButton.LeftButton:
            x, y = self.source_point(event.position())
            ax, ay = self.anchor
            self.selection = (min(x, ax), min(y, ay), max(x, ax), max(y, ay))
            self.update()
            self.changed.emit()

    def mouseReleaseEvent(self, event):
        self.anchor = None


class Editor(QDialog):
    def __init__(self, image, source, output_dir, parent):
        super().__init__(parent)
        self.setWindowTitle("OrbitDrop · Crop & frame")
        self.resize(900, 620)
        self.original = image.copy()
        self.source = source
        self.output_dir = output_dir
        self.worker = None
        layout = QVBoxLayout(self)
        layout.addWidget(label("Make it presentation-ready.", "title"))
        layout.addWidget(label("Drag a rectangle to crop. The source file stays untouched.", "muted"))
        row = QHBoxLayout()
        self.canvas = CropCanvas(image)
        row.addWidget(self.canvas, 1)
        panel = QVBoxLayout()
        panel.addWidget(label("01  /  CROP", "eyebrow"))
        self.crop_button = QPushButton("Apply selection")
        self.crop_button.clicked.connect(self.crop)
        panel.addWidget(self.crop_button)
        reset = QPushButton("Reset image")
        reset.clicked.connect(self.reset)
        panel.addWidget(reset)
        panel.addSpacing(22)
        panel.addWidget(label("02  /  BACKGROUND", "eyebrow"))
        self.frame_check = QCheckBox("Add a gradient frame")
        self.frame_check.setChecked(True)
        panel.addWidget(self.frame_check)
        self.palette = QComboBox()
        self.palette.addItems(PALETTES)
        panel.addWidget(self.palette)
        panel.addWidget(label("Padding (pixels)", "muted"))
        self.padding = QSpinBox()
        self.padding.setRange(0, 400)
        self.padding.setValue(80)
        panel.addWidget(self.padding)
        panel.addWidget(label("Corner radius (pixels)", "muted"))
        self.radius = QSpinBox()
        self.radius.setRange(0, 200)
        self.radius.setValue(24)
        panel.addWidget(self.radius)
        self.frame_preview = QLabel()
        self.frame_preview.setFixedSize(200, 135)
        self.frame_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel.addWidget(self.frame_preview)
        panel.addStretch()
        row.addLayout(panel)
        layout.addLayout(row, 1)
        self.status = label("Edits export as a new PNG.", "muted")
        layout.addWidget(self.status)
        self.save_button = QPushButton("Export edited PNG")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save)
        layout.addWidget(self.save_button)
        for signal in (self.palette.currentTextChanged, self.padding.valueChanged, self.radius.valueChanged, self.frame_check.toggled):
            signal.connect(self.update_preview)
        self.update_preview()

    def crop(self):
        if not self.canvas.selection:
            self.status.setText("Draw a crop rectangle on the image first.")
            return
        try:
            self.canvas.image = crop_image(self.canvas.image, self.canvas.selection)
            self.canvas.selection = None
            self.canvas.update()
            self.update_preview()
            self.status.setText(f"Cropped to {self.canvas.image.width} × {self.canvas.image.height} pixels.")
        except ValueError as exc:
            self.status.setText(str(exc))

    def reset(self):
        self.canvas.image = self.original.copy()
        self.canvas.selection = None
        self.canvas.update()
        self.update_preview()

    def update_preview(self, *_):
        image = self.canvas.image.copy()
        factor = min(1, 200 / max(image.size))
        image.thumbnail((200, 200))
        if self.frame_check.isChecked():
            image = add_frame(image, round(self.padding.value() * factor), round(self.radius.value() * factor), self.palette.currentText())
        self.frame_preview.setPixmap(pixmap(image).scaled(200, 135, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def save(self):
        if self.worker is not None and self.worker.isRunning():
            return
        image = self.canvas.image.copy()
        framed, padding, radius, palette = self.frame_check.isChecked(), self.padding.value(), self.radius.value(), self.palette.currentText()
        def task(progress):
            result = add_frame(image, padding, radius, palette) if framed else image
            return save_image(result, self.output_dir, self.source.stem + "_edited", "PNG")
        self.save_button.setEnabled(False)
        self.status.setText("Exporting…")
        if self.worker is not None:
            self.worker.deleteLater()
        self.worker = Worker(task, self)
        self.worker.finished.connect(self.finish_export)
        self.worker.start()

    @Slot()
    def finish_export(self):
        self.worker.wait()
        if self.worker.error:
            self.status.setText("Export failed. Check the output folder and try again.")
            QMessageBox.warning(self, "Export failed", self.worker.error)
        else:
            self.status.setText(f"Saved: {self.worker.value.name}")
        self.save_button.setEnabled(True)

    def reject(self):
        if self.worker is None or not self.worker.isRunning():
            super().reject()

    def closeEvent(self, event):
        if self.worker is not None and self.worker.isRunning():
            event.ignore()
        else:
            super().closeEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OrbitDrop · Local file converter")
        self.resize(1060, 850)
        self.setMinimumSize(960, 780)
        self.setAcceptDrops(True)
        self.output_dir = Path.home() / "Downloads" / "OrbitDrop"
        self.worker = None
        self.paths = []
        self.target = "PNG"
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 24, 28, 20)
        outer.setSpacing(18)
        header = QHBoxLayout()
        brand = label("◉  ORBITDROP")
        brand.setStyleSheet("font-size: 18px; font-weight: bold; letter-spacing: 2px;")
        header.addWidget(brand)
        header.addStretch()
        header.addWidget(label("LOCAL FILES.  NEW POSSIBILITIES.", "eyebrow"))
        outer.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(24)
        sidebar = QFrame()
        sidebar.setObjectName("panel")
        sidebar.setFixedWidth(280)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 20, 18, 18)
        side.addWidget(label("YOUR WORKSPACE", "eyebrow"))
        side.addWidget(label("Drop something in.", "title"))
        sidebar.findChild(QLabel, "title").setStyleSheet("font-size: 20px; font-weight: bold;")
        intro = label("Images and PDFs, processed\nentirely on your computer.", "muted")
        side.addWidget(intro)
        self.add_button = QPushButton("+  Choose files")
        self.add_button.clicked.connect(self.choose_files)
        side.addWidget(self.add_button)
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(130)
        self.file_list.currentRowChanged.connect(self.select_file)
        side.addWidget(self.file_list, 1)
        self.remove_button = QPushButton("Remove selected")
        self.remove_button.clicked.connect(self.remove_selected)
        side.addWidget(self.remove_button)
        self.preview_label = QLabel("Your preview appears here")
        self.preview_label.setFixedSize(242, 150)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background: #f5f3ef; border-radius: 8px; color: #92928c;")
        side.addWidget(self.preview_label)
        self.edit_button = QPushButton("Crop & frame selected")
        self.edit_button.clicked.connect(self.edit_selected)
        self.edit_button.setEnabled(False)
        side.addWidget(self.edit_button)
        body.addWidget(sidebar)
        main = QVBoxLayout()
        main.setSpacing(7)
        main.addWidget(label("01  /  CHOOSE YOUR FORMAT", "eyebrow"))
        main.addWidget(label("A new format.\nOne small orbit.", "title"))
        main.addWidget(label("Click a format, then convert. Or hold Shift and drop onto a slice.", "muted"))
        self.wheel = FormatWheel()
        self.wheel.chosen.connect(self.choose_target)
        self.wheel.filesDropped.connect(self.drop_files)
        main.addWidget(self.wheel, 1)
        self.format_note = label("PNG preserves transparency. Originals are never overwritten.", "muted")
        self.format_note.setWordWrap(True)
        main.addWidget(self.format_note)
        settings = QHBoxLayout()
        settings.addWidget(label("JPG / WEBP quality"))
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(10, 100)
        self.quality.setValue(90)
        self.quality.setFixedWidth(120)
        settings.addWidget(self.quality)
        self.quality_value = label("90")
        self.quality.valueChanged.connect(lambda n: self.quality_value.setText(str(n)))
        settings.addWidget(self.quality_value)
        settings.addStretch()
        settings.addWidget(label("PDF DPI"))
        self.dpi = QComboBox()
        self.dpi.addItems(["72", "144", "200", "300"])
        self.dpi.setCurrentText("144")
        settings.addWidget(self.dpi)
        main.addLayout(settings)
        self.convert_button = QPushButton("Convert to PNG")
        self.convert_button.setObjectName("primary")
        self.convert_button.setMinimumHeight(46)
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(lambda: self.convert_files())
        main.addWidget(self.convert_button)
        body.addLayout(main, 1)
        outer.addLayout(body, 1)
        output = QHBoxLayout()
        output.addWidget(label("SAVE TO", "eyebrow"))
        self.folder_label = label(str(self.output_dir), "muted")
        self.folder_label.setWordWrap(True)
        output.addWidget(self.folder_label, 1)
        self.folder_button = QPushButton("Change folder")
        self.folder_button.clicked.connect(self.choose_folder)
        output.addWidget(self.folder_button)
        self.open_button = QPushButton("Open folder ↗")
        self.open_button.clicked.connect(self.open_folder)
        output.addWidget(self.open_button)
        outer.addLayout(output)
        self.status = label("Ready when you are. Drop an image or PDF into this window.", "status")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        footer = label("No uploads  ·  No account  ·  PNG / JPG / WEBP / BMP / TIFF / PDF input", "muted")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(footer)

    def busy(self):
        return self.worker is not None and self.worker.isRunning()

    def set_busy(self, busy):
        for widget in (self.wheel, self.add_button, self.remove_button, self.file_list, self.folder_button, self.quality, self.dpi):
            widget.setEnabled(not busy)
        self.convert_button.setEnabled(not busy and bool(self.paths))
        self.edit_button.setEnabled(not busy and self.file_list.currentRow() >= 0)

    def run_task(self, task, done):
        if self.busy():
            return
        self.set_busy(True)
        if self.worker is not None:
            self.worker.deleteLater()
        self.task_done = done
        self.worker = Worker(task, self)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished.connect(self.finish_task)
        self.worker.start()

    @Slot()
    def finish_task(self):
        self.worker.wait()
        if self.worker.error:
            self.show_error(self.worker.error)
        else:
            self.task_done(self.worker.value)
        self.set_busy(False)

    def show_error(self, message):
        self.status.setText("Could not complete that operation.")
        QMessageBox.warning(self, "OrbitDrop", message)

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Choose files", "", "Images and PDFs (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.pdf)")
        self.add_files([Path(path) for path in files])

    def add_files(self, paths, show_preview=True):
        accepted, rejected = [], []
        for path in paths:
            try:
                path = validate_source(path).resolve()
                accepted.append(path)
                if path not in self.paths:
                    self.paths.append(path)
                    item = QListWidgetItem(path.name)
                    item.setToolTip(str(path))
                    self.file_list.addItem(item)
            except Exception as exc:
                rejected.append(f"{path.name}: {exc}")
        self.refresh_formats()
        if accepted and show_preview:
            row = self.paths.index(accepted[-1])
            if self.file_list.currentRow() == row:
                self.select_file(row)
            else:
                self.file_list.setCurrentRow(row)
        if rejected:
            QMessageBox.warning(self, "Some files were skipped", "\n".join(rejected[:8]))
        return accepted

    def refresh_formats(self):
        allowed = set.intersection(*(set(formats_for(path)) for path in self.paths)) if self.paths else set(self.wheel.formats)
        self.wheel.available = allowed
        self.wheel.count = len(self.paths)
        if self.target not in allowed:
            self.choose_target("PNG")
        else:
            self.choose_target(self.target)
        self.wheel.update()
        self.convert_button.setEnabled(bool(self.paths) and not self.busy())

    def choose_target(self, target):
        self.target = target
        self.wheel.selected = target
        self.wheel.update()
        self.convert_button.setText(f"Convert {len(self.paths) or ''} file{'s' if len(self.paths) != 1 else ''} to {target}")
        notes = {
            "PNG": "PNG preserves transparency. PDF pages become separate images.",
            "JPG": "JPG uses a white background for transparent areas. Adjust quality below.",
            "WEBP": "WEBP supports transparency. Adjust quality to balance size and detail.",
            "PDF": "Each image becomes its own single-page PDF.",
            "TXT": "Extract selectable PDF text. Scans need OCR; formatting is not preserved.",
            "DOCX": "Extract PDF text into Word paragraphs. Original layouts are not preserved.",
            "BMP": "BMP flattens transparency onto white and can produce large files.",
            "TIFF": "Export a single-frame TIFF for each image or PDF page.",
        }
        self.format_note.setText(notes[target])

    def select_file(self, row):
        if row < 0 or row >= len(self.paths) or self.busy():
            return
        path = self.paths[row]
        self.preview_label.setText("Loading preview…")
        self.status.setText(f"Reading {path.name}…")
        def ready(image):
            self.preview_label.setPixmap(pixmap(image).scaled(230, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.status.setText(f"{path.name} ready. Choose a format or edit the selected file.")
        self.run_task(lambda progress: preview(path), ready)

    def remove_selected(self):
        row = self.file_list.currentRow()
        if row >= 0:
            self.file_list.blockSignals(True)
            self.paths.pop(row)
            self.file_list.takeItem(row)
            self.file_list.blockSignals(False)
            self.refresh_formats()
            self.choose_target(self.target)
            if self.paths:
                self.select_file(self.file_list.currentRow())
            else:
                self.preview_label.setText("Your preview appears here")
                self.edit_button.setEnabled(False)
                self.status.setText("Workspace cleared. Drop in another file.")

    def choose_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Choose output folder", str(self.output_dir.parent))
        if directory:
            self.output_dir = Path(directory)
            self.folder_label.setText(directory)

    def open_folder(self):
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_dir)))
        except OSError as exc:
            self.show_error(str(exc))

    def convert_files(self, paths=None, target=None):
        paths = list(paths or self.paths)
        target = target or self.target
        options = Options(self.quality.value(), int(self.dpi.currentText()))
        directory = self.output_dir
        if not paths or self.busy():
            return
        self.status.setText("Converting…")
        def task(progress):
            results, errors = [], []
            for index, path in enumerate(paths):
                progress(f"Converting {index + 1}/{len(paths)} · {path.name}")
                try:
                    results.extend(convert(path, target, directory, options, progress))
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
            return results, errors
        def done(result):
            results, errors = result
            self.status.setText(f"Saved {len(results)} new file{'s' if len(results) != 1 else ''} to {directory}." + (f" {len(errors)} input(s) failed." if errors else " Originals preserved."))
            if errors:
                QMessageBox.warning(self, "Some conversions failed", "\n".join(errors[:12]))
        self.run_task(task, done)

    def edit_selected(self):
        row = self.file_list.currentRow()
        if row < 0:
            return
        path = self.paths[row]
        dpi = int(self.dpi.currentText())
        self.status.setText("Opening editor…")
        def task(progress):
            return render_pdf_page(path, dpi=dpi) if path.suffix.lower() == ".pdf" else load_image(path)
        def ready(image):
            self.editor = Editor(image, path, self.output_dir, self)
            self.editor.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.editor.open()
            self.status.setText("Editing first page / frame. Export saves a new PNG.")
        self.run_task(task, ready)

    def dragEnterEvent(self, event):
        if not self.busy() and local_paths(event):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if not self.busy():
            self.drop_files(local_paths(event), "")
            event.acceptProposedAction()

    def drop_files(self, paths, target):
        if self.busy():
            return
        accepted = self.add_files(paths, show_preview=not bool(target))
        if target and accepted:
            if all(target in formats_for(path) for path in accepted):
                self.convert_files(accepted, target)
            else:
                self.show_error(f"{target} is not available for all dropped files. Choose an enabled format.")

    def closeEvent(self, event):
        if self.busy():
            self.status.setText("Please wait for the current operation to finish before closing.")
            event.ignore()
        else:
            super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("OrbitDrop")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
