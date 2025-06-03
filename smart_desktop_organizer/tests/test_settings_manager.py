# -*- coding: utf-8 -*-
import unittest
import os
import json
import shutil
from unittest.mock import patch, mock_open

# Добавляем корень проекта в sys.path для корректного импорта модулей приложения
import sys
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.config_manager.settings import SettingsManager, DEFAULT_SETTINGS
# REAL_SETTINGS_FILE_PATH is not used in these tests, so removed import
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging # Import logging for setUpClass configuration

# Для тестов будем использовать временный файл настроек
TEST_SETTINGS_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_config_settings') # Unique name
TEST_SETTINGS_FILE = os.path.join(TEST_SETTINGS_DIR, 'test_settings.json')

class TestSettingsManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Настройка логгера для тестов (можно отключить вывод в консоль)
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1) # Effectively disable logging for tests if needed
        os.makedirs(TEST_SETTINGS_DIR, exist_ok=True)

    def setUp(self):
        # Этот метод будет вызываться перед каждым тестом
        # Убедимся, что тестовый файл настроек не существует перед тестом
        if os.path.exists(TEST_SETTINGS_FILE):
            os.remove(TEST_SETTINGS_FILE)
        # Передаем путь к тестовому файлу в SettingsManager
        self.settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE)

    def tearDown(self):
        # Этот метод будет вызываться после каждого теста
        if os.path.exists(TEST_SETTINGS_FILE):
            os.remove(TEST_SETTINGS_FILE)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_SETTINGS_DIR):
            shutil.rmtree(TEST_SETTINGS_DIR)

    def test_01_initialization_creates_default_settings_file(self):
        # Проверяем, что файл создается с настройками по умолчанию, если он не существует
        self.assertTrue(os.path.exists(TEST_SETTINGS_FILE))
        with open(TEST_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data, DEFAULT_SETTINGS)
        self.assertEqual(self.settings_manager.settings, DEFAULT_SETTINGS)

    def test_02_load_existing_settings(self):
        # Создаем тестовый файл с измененными настройками
        custom_settings = DEFAULT_SETTINGS.copy()
        custom_settings['log_level'] = 'DEBUG'
        custom_settings['delete_to_recycle_bin'] = False
        with open(TEST_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(custom_settings, f)

        # Инициализируем новый SettingsManager, он должен загрузить эти настройки
        sm = SettingsManager(settings_file=TEST_SETTINGS_FILE)
        self.assertEqual(sm.get_setting('log_level'), 'DEBUG')
        self.assertEqual(sm.get_setting('delete_to_recycle_bin'), False)

    def test_03_get_setting(self):
        self.assertEqual(self.settings_manager.get_setting('log_level'), DEFAULT_SETTINGS['log_level'])
        self.assertEqual(self.settings_manager.get_setting('non_existent_key', 'default_val'), 'default_val')

    def test_04_set_setting_saves_to_file(self):
        new_log_level = 'WARNING'
        self.settings_manager.set_setting('log_level', new_log_level)
        self.assertEqual(self.settings_manager.get_setting('log_level'), new_log_level)

        # Проверяем, что изменение сохранилось в файл
        with open(TEST_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data['log_level'], new_log_level)

        # Проверяем изменение другой настройки
        self.settings_manager.set_setting('enable_googling', False)
        self.assertEqual(self.settings_manager.get_setting('enable_googling'), False)
        with open(TEST_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data['enable_googling'], False)

    def test_05_reset_to_defaults(self):
        # Сначала изменим какую-нибудь настройку
        self.settings_manager.set_setting('log_level', 'CRITICAL')
        self.assertNotEqual(self.settings_manager.get_setting('log_level'), DEFAULT_SETTINGS['log_level'])

        # Теперь сбрасываем
        self.settings_manager.reset_to_defaults()
        self.assertEqual(self.settings_manager.settings, DEFAULT_SETTINGS)

        # Проверяем, что файл тоже обновился
        with open(TEST_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
        self.assertEqual(loaded_data, DEFAULT_SETTINGS)

    def test_06_load_corrupted_settings_file(self):
        # Создаем поврежденный JSON файл
        with open(TEST_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write('this is not a valid json string {')

        # Инициализируем SettingsManager, он должен загрузить настройки по умолчанию
        sm = SettingsManager(settings_file=TEST_SETTINGS_FILE)
        self.assertEqual(sm.settings, DEFAULT_SETTINGS)
        # В текущей реализации SettingsManager (v2), если файл поврежден, он использует дефолтные,
        # но НЕ перезаписывает файл автоматически при загрузке. Это произойдет при вызове _save_settings.
        # Проверим, что используются дефолтные настройки
        self.assertEqual(sm.get_setting('log_level'), DEFAULT_SETTINGS['log_level'])
        # Если бы мы хотели проверить перезапись файла:
        # sm.save_settings() # Принудительно сохраняем (это должно перезаписать поврежденный файл)
        # with open(TEST_SETTINGS_FILE, 'r', encoding='utf-8') as f:
        #     loaded_data_after_save = json.load(f)
        # self.assertEqual(loaded_data_after_save, DEFAULT_SETTINGS)


    def test_07_load_settings_with_missing_keys(self):
        # Создаем файл настроек, где отсутствуют некоторые ключи
        partial_settings = {'log_level': 'DEBUG'} # 'delete_to_recycle_bin' отсутствует
        with open(TEST_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(partial_settings, f)

        sm = SettingsManager(settings_file=TEST_SETTINGS_FILE)
        # Проверяем, что загруженная настройка применена
        self.assertEqual(sm.get_setting('log_level'), 'DEBUG')
        # Проверяем, что отсутствующие ключи взяты из DEFAULT_SETTINGS
        self.assertEqual(sm.get_setting('delete_to_recycle_bin'), DEFAULT_SETTINGS['delete_to_recycle_bin'])
        self.assertEqual(sm.get_setting('enable_googling'), DEFAULT_SETTINGS['enable_googling'])
        # Также проверяем, что полный набор настроек теперь содержит все ключи
        self.assertTrue('delete_to_recycle_bin' in sm.settings)


if __name__ == '__main__':
    # Это позволяет запускать тесты напрямую из этого файла: python test_settings_manager.py
    # Однако, предпочтительнее использовать unittest discover
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
