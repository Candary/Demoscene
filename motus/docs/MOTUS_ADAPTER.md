# Motus adapter для Uroboros

## Что делает

Добавляет в Uroboros операцию `motus.scene`, которая:

1. принимает текст motus (`query`);
2. создаёт `motus.Runtime`;
3. вызывает `submit(query)`;
4. для каждого `t` из `times` вызывает `frame(t)`;
5. возвращает JSON-снимки: матрицы, параметры, эмиттеры, post-эффекты, статистику.

Uroboros при этом сохраняет кеш, approval, журнал и историю запусков.

## Установка

```bash
# A рядом с B
export PYTHONPATH="$PWD/../motus:$PYTHONPATH"

# или установить A как пакет
pip install -e ../motus

# B
pip install -e .
python -m uroboros patches