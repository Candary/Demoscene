@echo off
REM build_demo_runtime.bat — сборка demo_runtime.cpp (MSVC)
REM Выход: demo_runtime.exe
REM Запуск: demo_runtime.exe demo.smt

REM Очищаем старый трейс, чтобы видеть только свежий запуск.
if exist trace.log del trace.log

cl /std:c++17 /EHsc /O2 /W3 ^
    demo_runtime.cpp ^
    /I. ^
    /link opengl32.lib user32.lib gdi32.lib

echo.
echo Build complete: demo_runtime.exe
echo Run: demo_runtime.exe demo.smt
echo (trace.log will be created fresh on each run)
