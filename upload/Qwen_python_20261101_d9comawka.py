# scripts/auto_build.py
import os
import sys
from pathlib import Path
from datetime import datetime

# Простая и надежная логика: если есть Pandoc, используем его. 
# Это самый стабильный способ конвертации Markdown -> DOCX без галлюцинаций AI в коде.
def main():
    version = os.environ.get("DOC_VERSION", "1.6")
    content_dir = Path("content")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    output_file = output_dir / f"sigil_btb_documentation_v{version}.docx"
    
    print(f"🚀 [AUTO] Начало сборки версии {version}...")
    
    # 1. Собираем все .md файлы из папки content
    md_files = sorted(content_dir.glob("*.md"))
    if not md_files:
        print("❌ [AUTO] Ошибка: В папке content/ нет .md файлов!")
        sys.exit(1)
        
    combined_md = output_dir / "temp_combined.md"
    with open(combined_md, "w", encoding="utf-8") as out:
        out.write(f"---\ntitle: Sigil BTB Documentation\nversion: {version}\ndate: {datetime.now().strftime('%Y-%m-%d')}\n---\n\n")
        for md_file in md_files:
            out.write(f"\n\\newpage\n\n")
            out.write(md_file.read_text(encoding="utf-8"))
            
    print(f"✅ [AUTO] Контент объединен ({len(md_files)} файлов).")
    
    # 2. Запускаем Pandoc (он должен быть установлен в системе)
    # Если Pandoc нет, скрипт честно об этом скажет, и AI поймет, что нужно предложить его установить
    import subprocess
    cmd = [
        "pandoc", str(combined_md), "-o", str(output_file),
        "--toc", "--toc-depth=3", "--number-sections"
    ]
    
    print(f"⚙️ [AUTO] Запуск pandoc...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ [AUTO] Ошибка сборки:\n{result.stderr}")
        sys.exit(1)
        
    # 3. Самопроверка (Auto-verify)
    if output_file.exists() and output_file.stat().st_size > 10000:
        print(f"🎉 [AUTO] УСПЕХ! Документ создан: {output_file.resolve()}")
        print(f"📊 [AUTO] Размер: {output_file.stat().st_size / 1024:.1f} KB")
    else:
        print("❌ [AUTO] Ошибка: Файл создан, но он пустой или слишком маленький.")
        sys.exit(1)
        
    # 4. Уборка
    combined_md.unlink(missing_ok=True)

if __name__ == "__main__":
    main()