# Start here, Logan

This folder is the full **OrbitDrop** project. It is source code, not a prebuilt `.app` or `.exe`.

## 1. Run it on your Mac

1. Download and unzip the project.
2. Put the extracted `orbitdrop` folder in your **Downloads** folder.
3. Install Python 3.12 from https://www.python.org/downloads/ if needed.
4. Open **Terminal**.
5. Paste these commands one at a time:

```bash
cd ~/Downloads/orbitdrop
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

The dependency install can take a few minutes. If `python3 --version` shows a different installed version and installation fails, install Python 3.12 and use `python3.12 -m venv .venv` to create a new environment.

Next time, open Terminal and run:

```bash
cd ~/Downloads/orbitdrop
.venv/bin/python run.py
```

If your folder is somewhere else, type `cd `, drag the extracted folder into Terminal, then press Return. This inserts its real path.

## 2. Or run it on Windows

1. Install Python 3.12 from https://www.python.org/downloads/.
2. Unzip the project into your Downloads folder.
3. Open PowerShell and run:

```powershell
cd "$HOME\Downloads\orbitdrop"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

These commands do not require changing PowerShell's execution policy.

## 3. Try these three things

1. Choose `samples/sample-card.png`. Click **JPG**, then **Convert**. Open the output folder.
2. Remove that image, add `samples/sample-document.pdf`, and convert to **PNG**. You should get two page images. Try **TXT** to see the extracted text.
3. Select the sample image, click **Crop & frame selected**, drag a crop rectangle, click **Apply selection**, and export a styled PNG.

You can also drag a file over a format slice, hold Shift, and release it to convert immediately. This shortcut works inside the app window.

## 4. Put the project on GitHub

1. Sign in to GitHub and create a new repository named `orbitdrop`.
2. Use this description: **Local desktop file converter with a radial menu, PDF export, and image editing.**
3. Choose **Public** if you want recruiters to view it.
4. Upload the contents of the extracted project folder, not just the ZIP.
5. Keep `README.md` at the repository root so GitHub displays the overview and screenshots.
6. Do **not** upload `.venv`, `__pycache__`, or your personal files.

For a complete upload including the hidden workflow folder, use Git from inside the project folder:

```bash
git init
git add .
git commit -m "Add OrbitDrop desktop converter"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/orbitdrop.git
git push -u origin main
```

Replace `YOUR-USERNAME` with your real GitHub username. Create an empty repository first, without adding a second README or license on GitHub. Git may prompt you to sign in or configure your name/email. The included `.gitignore` excludes the virtual environment and temporary files.

## 5. Describe it on your resume

After running the app, reviewing the code, and making your own changes, use a project entry such as:

**OrbitDrop — Desktop File Converter | Python, PySide6, Pillow**

- Developed a desktop utility for local image conversion, PDF page rendering, and PDF text extraction using a radial drag-and-drop interface.
- Implemented image cropping, gradient backgrounds, background processing, and non-overwriting exports; validated behavior with 17 automated conversion and UI tests.

Add your real repository URL. Read `docs/ENGINEERING.md` so you can explain how the project works. Good first personal improvements: add a page selector for PDF editing, add a conversion history panel, or add a cancel button. Update the bullets to reflect the version you actually run and maintain.

## Troubleshooting

- **Module not found:** install requirements with the same `.venv` Python you use to launch the app.
- **Folder not found:** confirm the extracted folder is named `orbitdrop`, or change the `cd` command to its real location.
- **TXT/DOCX is gray:** those formats require PDF input. Remove image files from the queue to enable them.
- **PDF says no selectable text:** it is likely scanned. OCR is not included.
- **Image too large:** lower the PDF DPI or use a smaller source image.
- **Nothing appears on the desktop when I press Shift:** OrbitDrop's shortcut works inside its own window, not globally over Finder or Explorer.
- **The output file is larger:** a format change or quality setting does not guarantee smaller output. Try JPG or WEBP and reduce quality.
