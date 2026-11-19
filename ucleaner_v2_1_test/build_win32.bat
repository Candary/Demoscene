@echo off
REM ============================================================
REM  uCleaner v63 — Win32+wgl dev build (MSVC, CONSOLE subsystem)
REM
REM  Output: demo_uncompressed.exe
REM  Prints colored pipeline checkmarks to console.
REM
REM  Requirements:
REM    - Visual Studio 2019+ (cl.exe in PATH)
REM    - Run from "x64 Native Tools Command Prompt for VS"
REM
REM  Run from this directory:
REM    build_win32.bat
REM ============================================================

setlocal enabledelayedexpansion

REM Dev build: /SUBSYSTEM:CONSOLE so colored checkmarks are visible.
REM Compo build (silent): see package_64k.bat
REM /D_CRT_SECURE_NO_WARNINGS: silence C4996 "fopen unsafe" deprecation warning.
set CXXFLAGS=/O2 /EHsc /std:c++17 /W3 /nologo /MT /D_CRT_SECURE_NO_WARNINGS
set INCLUDES=/I.
REM Check for nxGen-generated scene.uc
if exist scene.uc (
    echo [info] scene.uc found (nxGen-generated^), copying to demo_v63.uc
    copy /Y scene.uc demo_v63.uc >nul
) else (
    echo [info] using hand-written demo_v63.uc
)
set LIBS=opengl32.lib user32.lib gdi32.lib
set LINKFLAGS=/SUBSYSTEM:CONSOLE /OPT:REF /OPT:ICF

echo.
echo === uCleaner v63 Win32 dev build ===
echo.

REM ---- Step 1: compile sources to .obj ----
echo [1/2] Compiling sources...

cl %CXXFLAGS% %INCLUDES% /c d9_main_loop_win32.cpp /Fo:d9_main_loop_win32.obj
if errorlevel 1 (
    echo FAIL: d9_main_loop_win32.cpp compile
    exit /b 1
)

cl %CXXFLAGS% %INCLUDES% /c ucleaner_c.cpp /Fo:ucleaner_c.obj
if errorlevel 1 (
    echo FAIL: ucleaner_c.cpp compile
    exit /b 1
)

REM ---- Step 2: link (CONSOLE for visible colored checkmarks) ----
echo [2/2] Linking...

link /NOLOGO /OUT:demo_uncompressed.exe ^
    d9_main_loop_win32.obj ^
    ucleaner_c.obj ^
    %LIBS% ^
    %LINKFLAGS%

if errorlevel 1 (
    echo FAIL: link
    exit /b 1
)

echo.
echo === Build OK ===
echo Output: demo_uncompressed.exe
echo.

for %%A in (demo_uncompressed.exe) do echo Size: %%~zA bytes ^(%%~zA / 1024 KB^)

echo.
echo Run:
echo   demo_uncompressed.exe [width] [height] [demo_path] [time_scale]
echo.
echo Defaults: 1280x720, demo_v63.uc, time_scale=1.0 (real-time, 45s demo)
echo.
echo Examples:
echo   demo_uncompressed.exe                          REM 1280x720, real-time
echo   demo_uncompressed.exe 1920 1080                REM 1080p window
echo   demo_uncompressed.exe 1280 720 demo_v63.uc 2.0 REM 2x speed (22.5s demo)
echo   demo_uncompressed.exe 1280 720 demo_v63.uc 0.5 REM slow-mo (90s demo)
echo.
echo Press ESC or close window to exit early.
echo.
echo Expected output (every 30 frames = ~0.5s at 60fps):
echo   [Uroboros[v]][SceneMgr[v]][Motus[v]][CozyEng[v]][ColorMatrix[v]][Synth[v]] f=  0 t= 0.00 scene=0 shader=dawn            beat=0.00 bpm=128 I=1.1
echo   [Uroboros[v]][SceneMgr[v]][Motus[v]][CozyEng[v]][ColorMatrix[v]][Synth[v]] f= 30 t= 0.50 scene=0 shader=dawn            beat=0.12 bpm=128 I=1.1
echo   ...
echo   [D9-Win32] scene switch → idx=1 shader=trans_crossfade (tf=12.00s)
echo   ...
echo   [D9-Win32] scene switch → idx=2 shader=spire (tf=16.50s)
echo   ...
echo   [D9-Win32] scene switch → idx=3 shader=trans_bloom (tf=28.50s)
echo   ...
echo   [D9-Win32] scene switch → idx=4 shader=fall (tf=33.00s)
echo   ...
echo   [D9-Win32] demo ended at tf=45.00s (wall=45.00s)
echo   [D9-Win32] demo complete: rendered=2700 frames, scene_switches=5, wall_time=45.00s, fps=60.0
echo.
echo To package for 64K compo with Crinkler (silent, no console):
echo   package_64k.bat

endlocal
