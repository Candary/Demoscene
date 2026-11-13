# 1. Поставить проект
pip install -e .

# 2. Прогнать тесты
pip install -e ".[test]"
pytest -q

# 3. Сгенерировать пример и выполнить
python -m uroboros example --kind validation --out plan.json
python -m uroboros run --plan plan.json --auto-approve

# 4. Посмотреть сохранённый run
python -m uroboros inspect --run <id>

# 5. Статистика кеша
python -m uroboros cache-stats