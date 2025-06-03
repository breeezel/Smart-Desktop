# -*- coding: utf-8 -*-
import logging
import os
import sys

# Определение корневой директории проекта
# Это путь к папке, содержащей папку smart_desktop_organizer, settings.json и app.log
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
LOG_FILE_PATH = os.path.join(PROJECT_ROOT_DIR, 'app.log')

# Глобальная переменная для хранения инстанса логгера
_logger_instance = None

def setup_logger(settings_manager=None):
    global _logger_instance
    if _logger_instance is not None:
        # Если логгер уже настроен и есть settings_manager, возможно, нужно перенастроить уровень
        if settings_manager:
            log_level_str = settings_manager.get_setting('log_level', 'INFO').upper()
            numeric_log_level = getattr(logging, log_level_str, logging.INFO)
            _logger_instance.setLevel(numeric_log_level)
            for handler in _logger_instance.handlers:
                handler.setLevel(numeric_log_level)
        return _logger_instance

    logger = logging.getLogger('SmartDesktopOrganizer')

    # Получаем уровень логирования из настроек, если SettingsManager доступен
    log_level_str = 'INFO' # Уровень по умолчанию, если настройки не доступны
    if settings_manager:
        log_level_str = settings_manager.get_setting('log_level', 'INFO').upper()

    numeric_log_level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(numeric_log_level)

    # Предотвращаем дублирование обработчиков, если функция вызывается повторно
    if logger.hasHandlers():
        logger.handlers.clear()

    # Обработчик для записи логов в файл
    try:
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8')
        file_handler.setLevel(numeric_log_level) # Уровень для файла соответствует общему уровню
    except Exception as e:
        # В случае ошибки при создании файлового обработчика (например, нет прав на запись)
        # выводим сообщение в stderr и продолжаем без файлового логирования.
        sys.stderr.write(f'Ошибка при создании файлового обработчика логов ({LOG_FILE_PATH}): {e}\n')
        file_handler = None

    # Обработчик для вывода логов в консоль
    console_handler = logging.StreamHandler(sys.stdout) # Используем sys.stdout
    # Уровень для консоли можно сделать более высоким, если нужно меньше деталей в консоли
    # Например, logging.INFO, даже если общий уровень DEBUG
    console_handler.setLevel(numeric_log_level)

    # Форматтер для логов
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')
    if file_handler: file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру
    if file_handler: logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _logger_instance = logger
    return logger
