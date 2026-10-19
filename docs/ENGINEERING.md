# Engineering guide

## The basic flow

The UI collects file paths and an output format. `formats_for()` determines the formats available for each input. For a queue, the UI enables the intersection of those formats so the chosen operation is valid for every queued file.

`convert()` validates the input and delegates to one of three paths:

1. **Image conversion:** Pillow decodes the first frame, applies EXIF orientation, and encodes the selected output format.
2. **PDF rendering:** PDFium rasterizes every PDF page at the chosen DPI. Each page is exported separately.
3. **PDF text export:** pypdf extracts selectable text; the app writes UTF-8 text or creates Word paragraphs using python-docx.

The editor uses the same image export helper as the converter. It edits an in-memory copy and exports a separate PNG.

## Why the radial menu works

The menu finds the mouse position relative to the circle's center. `atan2(y, x)` gives the angle; dividing the circle into eight 45-degree sectors identifies the output format. An inner and outer radius keep the center and outside area from acting as format choices. Qt's drop event supplies the file URLs and modifier keys, so the app can detect Shift without installing a global keyboard hook.

## Why conversion runs in a thread

Decoding and encoding can take longer than one UI frame. A `QThread` worker performs file operations while the main thread handles painting and input. Worker completion is received by a Qt slot on the main window or editor; that slot updates widgets after the thread finishes. The interface disables conflicting operations while a job is active.

PDFium is not thread-safe. `PDF_LOCK` serializes PDFium use, including rendering and page counting. A future parallel converter should use isolated worker processes for PDF rendering, or maintain this lock, rather than call PDFium simultaneously from multiple threads.

## Why existing files are protected

`exclusive_output()` opens the proposed output path with `xb`, which fails if the file already exists. It tries a numbered suffix until it reserves a new path. This avoids the race in a separate “does this file exist?” check followed by normal writing. Source paths are only opened for reading.

If saving fails, the newly created incomplete output is deleted. If a later PDF page fails, earlier outputs from that input are removed too. A batch retains successful outputs from other inputs and reports individual failures.

## Crop coordinates

The crop canvas fits the source image into the available preview area. The displayed image may be much smaller than the original. Mouse positions are converted from display coordinates to source-image pixel coordinates before cropping. This avoids exporting a low-resolution screenshot of the preview.

## Transparency and metadata

PNG, WEBP, and TIFF can retain the alpha channel in this app. Formats exported as RGB are composited onto white. EXIF orientation is applied before export, and a fresh image object removes inherited metadata. This also means original ICC color profiles and other metadata are not carried over.

## Test coverage

- Actual exports are reopened to check dimensions, transparency, and page count.
- Multiple conversions into the source folder verify that the original bytes remain unchanged.
- Concurrent output reservations check for filename collisions.
- A simulated failed write verifies that partial outputs are deleted.
- A simulated failure on PDF page two verifies rollback of page one.
- GUI tests click a real format slice and export a file.
- A synthetic Qt drag/drop event checks that Shift-drop converts only newly dropped files.
- A GUI test drags a crop rectangle, applies it, exports a frame, and checks its final size.

## Useful next improvements

- **Page selection:** expose the `page_number` argument in `render_pdf_page()` through the editor.
- **Cancellation:** add a cancellation flag checked between inputs/pages and a clear policy for retained outputs.
- **History:** keep a local JSON or SQLite log of conversion status without retaining file contents.
- **OCR:** add an explicitly optional OCR engine and make scanned-document handling a separate operation.
- **Native desktop overlay:** implement platform-specific Finder/Explorer drag integration. This is a separate feature from the current in-window Qt drop target.
