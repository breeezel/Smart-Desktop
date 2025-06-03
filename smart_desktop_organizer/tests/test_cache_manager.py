# -*- coding: utf-8 -*-
import unittest
import os
import json
import time
import shutil
from unittest.mock import MagicMock, patch

# Добавляем корень проекта в sys.path для корректного импорта модулей приложения
import sys
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.web_classifier.cache_manager import CacheManager
from smart_desktop_organizer.config_manager.settings import SettingsManager # Нужен для теста влияния настроек
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging

# Для тестов будем использовать временный файл кэша и настроек
TEST_CACHE_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_cache_mgr') # Unique name
TEST_CACHE_FILE = os.path.join(TEST_CACHE_DIR, 'test_cache.json')
TEST_SETTINGS_FILE_FOR_CACHE_TESTS = os.path.join(TEST_CACHE_DIR, 'test_settings_for_cache.json')

class TestCacheManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1) # Disable logging for tests
        os.makedirs(TEST_CACHE_DIR, exist_ok=True)

    def setUp(self):
        if os.path.exists(TEST_CACHE_FILE):
            os.remove(TEST_CACHE_FILE)
        if os.path.exists(TEST_SETTINGS_FILE_FOR_CACHE_TESTS):
            os.remove(TEST_SETTINGS_FILE_FOR_CACHE_TESTS)

        self.mock_settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE_FOR_CACHE_TESTS)
        self.mock_settings_manager.set_setting('googling_cache_ttl_days', 7) # Default for most tests

        # Ensure CacheManager uses the fresh settings for TTL in its constructor for each test
        self.cache_manager = CacheManager(cache_file=TEST_CACHE_FILE, settings_manager=self.mock_settings_manager)


    def tearDown(self):
        if os.path.exists(TEST_CACHE_FILE):
            os.remove(TEST_CACHE_FILE)
        if os.path.exists(TEST_SETTINGS_FILE_FOR_CACHE_TESTS):
            os.remove(TEST_SETTINGS_FILE_FOR_CACHE_TESTS)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_CACHE_DIR):
            shutil.rmtree(TEST_CACHE_DIR)

    def test_01_initialization_creates_empty_cache_file_if_not_exists(self):
        # setUp already creates cache_manager, which in turn tries to load/create the file.
        # If it didn't exist, _load_cache returns {}, and then _save_cache (if called by set) would create it.
        # The CacheManager itself doesn't save an empty cache on init if file not found, only if corrupted.
        # Let's ensure it's empty if we just initialize it
        self.assertEqual(self.cache_manager.cache_data, {})
        # And if we save it, the file is created
        self.cache_manager._save_cache()
        self.assertTrue(os.path.exists(TEST_CACHE_FILE))
        with open(TEST_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data, {})


    def test_02_set_and_get_item(self):
        key, value = 'test_key', 'test_value'
        self.cache_manager.set(key, value)
        retrieved_value = self.cache_manager.get(key)
        self.assertEqual(retrieved_value, value)

        with open(TEST_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertIn(key, data)
        self.assertEqual(data[key]['value'], value)
        self.assertTrue(isinstance(data[key]['timestamp'], float))

    def test_03_get_non_existent_item(self):
        self.assertIsNone(self.cache_manager.get('non_existent_key'))

    def test_04_item_expires_after_ttl(self):
        key, value = 'ttl_key', 'ttl_value'

        # 1. Set TTL to 1 day using the existing mock_settings_manager
        self.mock_settings_manager.set_setting('googling_cache_ttl_days', 1)

        # 2. Re-initialize CacheManager so it picks up the new TTL from settings_manager
        # This is crucial because cache_ttl_days is set in CacheManager's __init__
        self.cache_manager = CacheManager(cache_file=TEST_CACHE_FILE, settings_manager=self.mock_settings_manager)
        self.assertEqual(self.cache_manager.cache_ttl_days, 1) # Verify TTL is 1

        # 3. Set the item
        self.cache_manager.set(key, value)

        # 4. Manually change the timestamp in the cache_data and save it
        # This simulates the passage of time
        two_days_ago = time.time() - (2 * 24 * 60 * 60)
        self.cache_manager.cache_data[key]['timestamp'] = two_days_ago
        self.cache_manager._save_cache()

        # 5. Create a new CacheManager instance to force reloading from the modified file
        reloaded_cache_manager = CacheManager(cache_file=TEST_CACHE_FILE, settings_manager=self.mock_settings_manager)

        # 6. Now, get(key) should return None because the item is expired
        self.assertIsNone(reloaded_cache_manager.get(key), 'Запись должна была устареть и вернуться как None')
        self.assertNotIn(key, reloaded_cache_manager.cache_data, 'Устаревшая запись должна быть удалена из self.cache_data при get')


    def test_05_remove_item(self):
        key, value = 'remove_key', 'remove_value'
        self.cache_manager.set(key, value)
        self.assertIsNotNone(self.cache_manager.get(key))

        self.cache_manager.remove(key)
        self.assertIsNone(self.cache_manager.get(key))
        with open(TEST_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertNotIn(key, data)

    def test_06_clear_cache(self):
        self.cache_manager.set('key1', 'value1')
        self.cache_manager.set('key2', 'value2')
        self.assertNotEqual(self.cache_manager.cache_data, {})

        self.cache_manager.clear_cache()
        self.assertEqual(self.cache_manager.cache_data, {})
        self.assertIsNone(self.cache_manager.get('key1'))

        with open(TEST_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data, {})

    def test_07_load_corrupted_cache_file(self):
        with open(TEST_CACHE_FILE, 'w', encoding='utf-8') as f:
            f.write('this is not json {')

        cm = CacheManager(cache_file=TEST_CACHE_FILE, settings_manager=self.mock_settings_manager)
        self.assertEqual(cm.cache_data, {})
        with open(TEST_CACHE_FILE, 'r', encoding='utf-8') as f: # Check file not overwritten
            content = f.read()
        self.assertEqual(content, 'this is not json {')
        # If we now save, it should save the empty (default) cache
        cm._save_cache()
        with open(TEST_CACHE_FILE, 'r', encoding='utf-8') as f:
            content_after_save = json.load(f)
        self.assertEqual(content_after_save, {})


    def test_08_ttl_from_settings_manager(self):
        self.mock_settings_manager.set_setting('googling_cache_ttl_days', 3)
        # Re-init for new TTL
        cm_with_custom_ttl = CacheManager(cache_file=TEST_CACHE_FILE, settings_manager=self.mock_settings_manager)
        self.assertEqual(cm_with_custom_ttl.cache_ttl_days, 3)

        key, value = 'custom_ttl_key', 'custom_ttl_value'
        cm_with_custom_ttl.set(key, value)

        four_days_ago = time.time() - (4 * 24 * 60 * 60)
        cm_with_custom_ttl.cache_data[key]['timestamp'] = four_days_ago
        cm_with_custom_ttl._save_cache()

        reloaded_cm = CacheManager(cache_file=TEST_CACHE_FILE, settings_manager=self.mock_settings_manager)
        self.assertIsNone(reloaded_cm.get(key), 'Запись должна была устареть с TTL=3 дня')

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
