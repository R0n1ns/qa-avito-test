# qa-avito-test

Инструкция по запуску тестов для тестового задания QA Avito

Для запуска тестов локально необходимо выполнить следующие ниже шаги (установить зависимости для python и запустить тесты ), либо запустить github actions workflow (тесты без allure) https://github.com/R0n1ns/qa-avito-test/actions/workflows/api-tests.yml

Для просмотра отчета allure можно испольщовать файл allure-example.html (или index.html) в корне проекта, либо посмотреть его же по ссылке (в github pages) https://r0n1ns.github.io/qa-avito-test/

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

## Allure отчеты 

есть готовый отчет allure-example.html в корне проекта, либо по ссылке https://r0n1ns.github.io/qa-avito-test/

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