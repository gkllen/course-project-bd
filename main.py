"""
Точка входа для запуска из PyCharm (Shift+F10).

Применяет миграции и запускает dev-сервер на http://127.0.0.1:8000/.
Эквивалент:  python manage.py migrate && python manage.py runserver
"""
import os
import sys

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    execute_from_command_line([sys.argv[0], "migrate", "--noinput"])
    execute_from_command_line([sys.argv[0], "runserver", "127.0.0.1:8000"])
