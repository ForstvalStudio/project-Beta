@echo off
REM ============================================================
REM Project Beta — Nuitka Compilation Script
REM Produces: dist/main-x86_64-pc-windows-msvc.exe
REM Run from: sidecar/ directory with venv ACTIVE
REM ============================================================

echo [Build] Compiling sidecar with Nuitka...
echo [Build] Output: ..\src-tauri\binaries\main-x86_64-pc-windows-msvc.exe

REM Install Nuitka if not present
python -m pip show nuitka >nul 2>&1 || (
    echo [Build] Installing Nuitka...
    python -m pip install nuitka
)

REM Ensure output directory exists
if not exist "..\src-tauri\binaries" mkdir "..\src-tauri\binaries"

python -m nuitka ^
    --standalone ^
    --onefile ^
    --output-dir="..\src-tauri\binaries" ^
    --output-filename="main-x86_64-pc-windows-msvc.exe" ^
    --include-package=fastapi ^
    --include-package=uvicorn ^
    --include-package=uvicorn.protocols ^
    --include-package=uvicorn.lifespan ^
    --include-package=uvicorn.loops ^
    --include-package=starlette ^
    --include-package=llama_cpp ^
    --include-package=lancedb ^
    --include-package=sentence_transformers ^
    --include-package=transformers ^
    --include-package=polars ^
    --include-package=pydantic ^
    --include-package=pydantic_core ^
    --include-package=openpyxl ^
    --include-package=platformdirs ^
    --include-package=anyio ^
    --include-package=httpx ^
    --include-package=multipart ^
    --nofollow-import-to=transformers.cli ^
    --nofollow-import-to=google.generativeai ^
    --nofollow-import-to=google.ai ^
    --nofollow-import-to=tensorflow ^
    --nofollow-import-to=torch ^
    --nofollow-import-to=notebook ^
    --nofollow-import-to=IPython ^
    --assume-yes-for-downloads ^
    --windows-console-mode=disable ^
    --company-name="ForstvalStudio" ^
    --product-name="Project Beta Sidecar" ^
    --file-version=0.1.0.0 ^
    main.py

if %ERRORLEVEL% == 0 (
    echo [Build] SUCCESS — binary created at ..\src-tauri\binaries\main-x86_64-pc-windows-msvc.exe
) else (
    echo [Build] FAILED with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)
