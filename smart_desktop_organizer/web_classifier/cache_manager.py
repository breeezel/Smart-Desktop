# -*- coding: utf-8 -*-
import json
import os
import time
import logging

logger = logging.getLogger('SmartDesktopOrganizer')

# Путь к файлу кэша в корневой директории проекта
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CACHE_FILE_PATH = os.path.join(PROJECT_ROOT_DIR, 'classifier_cache.json')

class CacheManager:
    def __init__(self, cache_file=CACHE_FILE_PATH, settings_manager=None):
        self.cache_file = cache_file
        self.settings_manager = settings_manager
        self.cache_ttl_days = 7 # Значение по умолчанию
        if self.settings_manager:
            self.cache_ttl_days = self.settings_manager.get_setting('googling_cache_ttl_days', 7)
        self.cache_data = self._load_cache()

    def _load_cache(self):
        # Загрузка кэша из файла
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f'Кэш классификатора успешно загружен из {self.cache_file}')
                    return data
            except json.JSONDecodeError:
                logger.warning(f'Ошибка декодирования JSON в файле кэша {self.cache_file}. Создается новый кэш.')
                return {}
            except Exception as e:
                logger.error(f'Не удалось загрузить кэш из {self.cache_file}: {e}. Создается новый кэш.')
                return {}
        else:
            logger.info(f'Файл кэша {self.cache_file} не найден. Будет создан новый.')
            return {}

    def _save_cache(self):
        # Сохранение кэша в файл
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=4)
            logger.debug(f'Кэш классификатора успешно сохранен в {self.cache_file}')
        except Exception as e:
            logger.error(f'Не удалось сохранить кэш в {self.cache_file}: {e}')

    def get(self, key):
        # Получение значения из кэша
        # Ключ может быть, например, именем файла или хешем его пути
        cached_item = self.cache_data.get(key)
        if cached_item:
            timestamp = cached_item.get('timestamp', 0)
            if time.time() - timestamp < self.cache_ttl_days * 24 * 60 * 60:
                logger.debug(f'Значение для ключа "{key}" найдено в кэше и актуально.')
                return cached_item.get('value')
            else:
                logger.debug(f'Значение для ключа "{key}" найдено в кэше, но устарело.')
                self.remove(key) # Удаляем устаревшую запись
        return None

    def set(self, key, value):
        # Добавление/обновление значения в кэше
        self.cache_data[key] = {
            'value': value,
            'timestamp': time.time()
        }
        self._save_cache()
        logger.debug(f'Значение для ключа "{key}" сохранено в кэше.')

    def remove(self, key):
        # Удаление значения из кэша
        if key in self.cache_data:
            del self.cache_data[key]
            self._save_cache()
            logger.debug(f'Значение для ключа "{key}" удалено из кэша.')

    def clear_cache(self):
        # Очистка всего кэша
        self.cache_data = {}
        self._save_cache()
        logger.info('Кэш классификатора очищен.')
