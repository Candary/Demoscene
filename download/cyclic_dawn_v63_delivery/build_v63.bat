@echo off
REM path: cyclic_dawn_v63/build_v63.bat
REM Build demo_runtime_v63.exe for Windows. Requires VS 2022 Build Tools (cl.exe in PATH).
REM Reuses v61.2 runtime: sm_runtime.hpp, gl_executor.hpp, opengl_loader.h (no changes).
REM Run from "x64 Native Tools Command Prompt for VS 2022".

setlocal enabledelayedexpansion

set SRC=demo_runtime_v63.cpp
set OUT=demo_runtime_v63.exe
set INCLUDES=/I.
set LIBS=opengl32.lib user32.lib gdi32.lib
set FLAGS=/std:c++17 /EHsc /O2 /W3 /MT /nologo
set CFLAGS=%FLAGS%

echo [build] compiling %SRC% ...
cl %CFLAGS% %INCLUDES% %SRC% /link %LIBS% /OUT:%OUT%
if errorlevel 1 (
    echo [build] FAILED: cl exited with error %errorlevel%
    exit /b 1
)

echo [build] OK: %OUT%
echo [run]   %OUT% demo_v63.smt
echo [run]   %OUT% demo_v63.smt --still 6.0 --out still_dawn.png --repeat 3

endlocal
