@echo off
REM build_demo_runtime.bat — сборка demo_runtime.cpp (MSVC)
REM Выход: demo_runtime.exe
REM Запуск: demo_runtime.exe demo.smt
REM Опции: demo_runtime.exe demo.smt --still 2.0 --out still.png [--repeat N]

REM Очищаем старый трейс, чтобы видеть только свежий запуск.
if exist trace.log del trace.log

cl /std:c++17 /EHsc /O2 /W3 ^
    demo_runtime.cpp ^
    /I. ^
    /link opengl32.lib user32.lib gdi32.lib

REM P1 fix: проверяем exit code компилятора. Раньше bat-файл всегда писал
REM "Build complete" даже при провале сборки — вводило в заблуждение.
if errorlevel 1 (
    echo.
    echo ========================================
    echo BUILD FAILED — see compiler errors above
    echo ========================================
    exit /b 1
)

if not exist demo_runtime.exe (
    echo.
    echo ========================================
    echo BUILD FAILED — demo_runtime.exe was not created
    echo ========================================
    exit /b 1
)

echo.
echo ========================================
echo Build complete: demo_runtime.exe
echo Run: demo_runtime.exe demo.smt
echo Still frame:  demo_runtime.exe demo.smt --still 2.0 --out still.png
echo (trace.log will be created fresh on each run)
echo ========================================
