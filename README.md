# qa-avito-test
 описание 
## Стек 
- Python 3.10+
- `pytest`
- `requests`

## Project files
- `api_client.py` - апи клиент для взаимодействия с тестируемым API
- `tests/fixtures.py` - фикстуры и утилиты для тестов
- `tests/test_post_item.py` - тесты из testcases.md
- `requirements.txt` - необходимые зависимости
- `pytest.ini` - конфигурация pytest

## Установка зависимостей
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Запуск всех тестов при помощи pytest 
```bat
pytest -v
```

Запуск только E2E тестов:
```bat
pytest -v -m e2e
```

## Allure отчеты (есть готовый отчет allure-example.html в корне проекта) 

### Установка Allure CLI (Windows) или иным способом
```bat
choco install allure
allure --version
```

### Запуск тестов с сохранением результатов Allure (`allure-pytest` уже включён в `requirements.txt`.)
```bat
pytest -v --alluredir=allure-results
```

### Генерация отчета в файл html
```bat
allure generate allure-results -o allure-report --clean --single-file
```