@echo off
REM build_nxgen.bat - build nxGen standalone CLI tool (MSVC)
REM Run from x64 Native Tools Command Prompt for VS
setlocal
cl /O2 /EHsc /std:c++17 /I. /utf-8 /D_CRT_SECURE_NO_WARNINGS ^
   nxgen\main.cpp ^
   /Fe:build\nxgen.exe /link /SUBSYSTEM:CONSOLE
if errorlevel 1 (echo [error] nxgen build failed & exit /b 1)
echo [ok] nxgen built: build\nxgen.exe
echo run: build\nxgen.exe run --preset text_to_scene --text "epic cold city" --out out\demo
endlocal
