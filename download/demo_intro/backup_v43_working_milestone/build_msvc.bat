@echo off
REM ===================================================================
REM build_msvc.bat - Build the demo intro with MSVC (Visual Studio).
REM -------------------------------------------------------------------
REM Prerequisites:
REM   * Visual Studio 2022 (or Build Tools for VS) installed.
REM   * Run this from inside "x64 Native Tools Command Prompt for VS 2022"
REM     (found in Start Menu). This sets up cl.exe, link.exe in PATH.
REM
REM After success, you'll get demo_intro.exe in this folder.
REM ===================================================================

echo Building demo_intro.exe with MSVC...
echo Target architecture: %VSCMD_ARG_TGT_ARCH%
echo (empty = run from "x64 Native Tools Command Prompt for VS 2022")

REM Compile + link in one go. We link against:
REM   user32.lib  - Win32 API (window, message loop, etc.)
REM   gdi32.lib   - GDI (DeviceContext, SetPixelFormat, etc.)
REM   opengl32.lib - OpenGL base functions
REM
REM Флаги:
REM   /O2        - оптимизация (максимальная)
REM   /EHsc      - exception handling (C++ стандартное)
REM   /W3        - warning level 3
REM   /MT        - статическая CRT (без vcruntime140.dll зависимости)
REM   /std:c++17 - C++17 стандарт
REM   /Zc:__cplusplus - правильное значение __cplusplus макроса
REM   /utf-8     - исходники в UTF-8 (Cyrillic комментарии)
REM   /nologo    - без баннера MSVC
REM   /F8388608  - стек 8 МБ (дефолт MSVC 1 МБ; страховка от stack overflow)
cl /O2 /EHsc /W3 /MT /std:c++17 /Zc:__cplusplus /utf-8 /nologo /F8388608 /Fe:demo_intro.exe ^
   main.cpp ^
   /link user32.lib gdi32.lib opengl32.lib

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build FAILED with error level %ERRORLEVEL%
    exit /b 1
)

echo.
echo Build OK. Run demo_intro.exe to start.
