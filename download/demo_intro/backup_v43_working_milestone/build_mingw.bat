@echo off
REM ===================================================================
REM build_mingw.bat - Build the demo intro with MinGW-w64 (g++).
REM -------------------------------------------------------------------
REM Prerequisites:
REM   * MinGW-w64 installed (e.g., from https://www.mingw-w64.org/
REM     or via MSYS2:  pacman -S mingw-w64-x86_64-gcc).
REM   * g++ should be in your PATH (open cmd and type "g++ --version"
REM     to check).
REM
REM After success, you'll get demo_intro.exe in this folder.
REM ===================================================================

echo Building demo_intro.exe with MinGW g++...

REM Compile + link in one go. Linked libraries:
REM   -luser32   - Win32 API (window, message loop, etc.)
REM   -lgdi32    - GDI (DeviceContext, SetPixelFormat, etc.)
REM   -lopengl32 - OpenGL base functions
REM
REM -static -static-libgcc -static-libstdc++:
REM   полностью статическая линковка CRT/libstdc++/libgcc —
REM   exe НЕ требует libstdc++-6.dll / libgcc_s_seh-1.dll рядом
REM   (фикс Task 22, восстановлен в v39b).
REM -Wl,--stack,8388608 - стек 8 МБ (паритет с MSVC-сборкой, страховка)
g++ -O3 -std=c++17 -Wall -Wextra -static -static-libgcc -static-libstdc++ -Wl,--stack,8388608 -o demo_intro.exe main.cpp ^
    -luser32 -lgdi32 -lopengl32

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build FAILED with error level %ERRORLEVEL%
    exit /b 1
)

echo.
echo Build OK. Run demo_intro.exe to start.
