# -*- coding: utf-8 -*-
import json
import os
import logging

logger = logging.getLogger('SmartDesktopOrganizer')

# Определяем путь к корневой папке проекта и файлу настроек
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # Путь к корневой папке проекта (на два уровня выше)
SETTINGS_FILE_PATH = os.path.join(PROJECT_ROOT_DIR, 'settings.json')

DEFAULT_SETTINGS = {
    'log_level': 'INFO',
    'delete_to_recycle_bin': True,  # По умолчанию удалять в корзину
    'default_delete_confirmation': True, # По умолчанию запрашивать подтверждение удаления
    'excluded_folders': ['Корзина', 'Мой компьютер', 'Сетевое окружение', 'Панель управления'],
    'excluded_files': ['desktop.ini', 'thumbs.db'],
    'enable_googling': True,
    'googling_cache_ttl_days': 7,
    'sorting_rules': {
        'folders': {'enabled': True, 'position': 'bottom_right', 'sort_order': 'name_asc'},
        'games': {'enabled': True, 'position': 'top_right', 'sort_order': 'name_asc'},
        'programs': {'enabled': True, 'position': 'left_top', 'sort_order': 'date_desc'},
        'text_files': {'enabled': True, 'position': 'bottom_right_above_folders', 'sort_order': 'name_asc'},
        'other': {'enabled': True, 'position': 'center', 'sort_order': 'date_desc'}
    },
    'icon_spacing': {'horizontal': 75, 'vertical': 75}, # Отступы между иконками в пикселях
    'grid_size': {'width': 0, 'height': 0} # Размеры сетки для иконок, 0 - автоопределение
}

class SettingsManager:
    def __init__(self, settings_file=SETTINGS_FILE_PATH):
        self.settings_file = settings_file
        self.settings = self.load_settings()

    def load_settings(self):
        # Загрузка настроек из файла
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Проверка на наличие всех ключей из DEFAULT_SETTINGS
                    settings = DEFAULT_SETTINGS.copy() # Начинаем с настроек по умолчанию
                    settings.update(loaded_settings) # Обновляем значениями из файла
                    logger.info(f'Настройки успешно загружены из {self.settings_file}')
                    return settings
            except json.JSONDecodeError:
                logger.warning(f'Ошибка декодирования JSON в файле {self.settings_file}. Используются настройки по умолчанию.')
                return DEFAULT_SETTINGS.copy()
            except Exception as e:
                logger.error(f'Не удалось загрузить настройки из {self.settings_file}: {e}. Используются настройки по умолчанию.')
                return DEFAULT_SETTINGS.copy()
        else:
            logger.info(f'Файл настроек {self.settings_file} не найден. Создан новый файл с настройками по умолчанию.')
            self.save_settings(DEFAULT_SETTINGS.copy()) # Сохраняем настройки по умолчанию, если файл не существует
            return DEFAULT_SETTINGS.copy()

    def save_settings(self, settings_to_save=None):
        # Сохранение текущих настроек в файл
        data_to_save = settings_to_save if settings_to_save is not None else self.settings
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
            logger.info(f'Настройки успешно сохранены в {self.settings_file}')
        except Exception as e:
            logger.error(f'Не удалось сохранить настройки в {self.settings_file}: {e}')

    def get_setting(self, key, default=None):
        # Получение значения настройки по ключу
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        # Установка значения настройки
        self.settings[key] = value
        self.save_settings() # Автоматическое сохранение при изменении

    def reset_to_defaults(self):
        # Сброс настроек к значениям по умолчанию
        self.settings = DEFAULT_SETTINGS.copy()
        self.save_settings()
        logger.info('Настройки сброшены к значениям по умолчанию.')

# Пример использования (можно раскомментировать для проверки):
# if __name__ == '__main__':
#     # Убедимся, что логгер инициализирован до менеджера настроек, если запускаем этот файл напрямую
#     # Это важно, так как SettingsManager использует logger
#     # В реальном приложении logger будет инициализирован в main.py

#     # Создаем экземпляр менеджера настроек
#     settings_manager = SettingsManager()

#     # Получаем настройку
#     print(f"Текущий уровень логирования: {settings_manager.get_setting('log_level')}")
#     print(f"Удалять в корзину: {settings_manager.get_setting('delete_to_recycle_bin')}")

#     # Изменяем настройку
#     settings_manager.set_setting('log_level', 'DEBUG')
#     print(f"Новый уровень логирования: {settings_manager.get_setting('log_level')}")

#     # Проверяем, что файл settings.json создался/обновился в корне проекта
#     print(f"Файл настроек находится здесь: {SETTINGS_FILE_PATH}")

#     # Сброс настроек
#     # settings_manager.reset_to_defaults()
#     # print(f"Уровень логирования после сброса: {settings_manager.get_setting('log_level')}")
