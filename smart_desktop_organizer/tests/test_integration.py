# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import sys
import time
from unittest.mock import MagicMock, patch

# Добавляем корень проекта в sys.path
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.config_manager.settings import SettingsManager, DEFAULT_SETTINGS
from smart_desktop_organizer.web_classifier.classifier import WebClassifier
from smart_desktop_organizer.web_classifier.cache_manager import CacheManager
from smart_desktop_organizer.desktop_manager.desktop_sorter import DesktopSorter
from smart_desktop_organizer.desktop_manager import desktop_scanner # Для get_desktop_items
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging

TEST_INTEGRATION_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_integration_tests') # Unique name
TEST_SETTINGS_FILE_INTEGRATION = os.path.join(TEST_INTEGRATION_DIR, 'test_settings_integration.json')
TEST_CACHE_FILE_INTEGRATION = os.path.join(TEST_INTEGRATION_DIR, 'test_cache_integration.json')
TEST_DESKTOP_DIR_INTEGRATION = os.path.join(TEST_INTEGRATION_DIR, 'TestDesktopIntegration')

class TestIntegrationSorterAndClassifier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1)
        os.makedirs(TEST_INTEGRATION_DIR, exist_ok=True)
        os.makedirs(TEST_DESKTOP_DIR_INTEGRATION, exist_ok=True)

    def setUp(self):
        for item in os.listdir(TEST_DESKTOP_DIR_INTEGRATION):
            item_path = os.path.join(TEST_DESKTOP_DIR_INTEGRATION, item)
            if os.path.isdir(item_path): shutil.rmtree(item_path)
            else: os.remove(item_path)

        if os.path.exists(TEST_SETTINGS_FILE_INTEGRATION): os.remove(TEST_SETTINGS_FILE_INTEGRATION)
        if os.path.exists(TEST_CACHE_FILE_INTEGRATION): os.remove(TEST_CACHE_FILE_INTEGRATION)

        self.settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE_INTEGRATION)
        self.settings_manager.set_setting('enable_googling', True)
        self.settings_manager.set_setting('googling_cache_ttl_days', 1)
        self.settings_manager.set_setting('icon_spacing', DEFAULT_SETTINGS['icon_spacing'].copy()) # Use copy
        self.settings_manager.set_setting('sorting_rules', DEFAULT_SETTINGS['sorting_rules'].copy()) # Use copy
        self.settings_manager.set_setting('grid_size', DEFAULT_SETTINGS['grid_size'].copy()) # Use copy


        self.web_classifier = WebClassifier(
            settings_manager=self.settings_manager,
            cache_file_path=TEST_CACHE_FILE_INTEGRATION # Crucial for test isolation
        )

        self.mock_search_patcher = patch.object(self.web_classifier, '_mock_search_google')
        self.mock_search_google = self.mock_search_patcher.start()

        self.sorter = DesktopSorter(self.settings_manager, self.web_classifier)
        self.screen_res = {'width': 1920, 'height': 1080}
        self.dpi_info = {'x': 96, 'y': 96}
        # Initialize sorter's screen info, which also calculates grid dimensions
        self.sorter.set_screen_info(self.screen_res, self.dpi_info)


    def tearDown(self):
        self.mock_search_patcher.stop()
        if os.path.exists(TEST_SETTINGS_FILE_INTEGRATION): os.remove(TEST_SETTINGS_FILE_INTEGRATION)
        if os.path.exists(TEST_CACHE_FILE_INTEGRATION): os.remove(TEST_CACHE_FILE_INTEGRATION)
        for item in os.listdir(TEST_DESKTOP_DIR_INTEGRATION): # Clean up test desktop again
            item_path = os.path.join(TEST_DESKTOP_DIR_INTEGRATION, item)
            if os.path.isdir(item_path): shutil.rmtree(item_path)
            else: os.remove(item_path)


    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_INTEGRATION_DIR): shutil.rmtree(TEST_INTEGRATION_DIR)

    def _create_file_on_test_desktop(self, name, content=''):
        path = os.path.join(TEST_DESKTOP_DIR_INTEGRATION, name)
        # Create parent directory if it's a path like 'Games/MyGame.exe'
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        # Set modification time slightly apart for consistent sorting if tests depend on it
        # For this test, date_modified is read by get_desktop_items.
        # We can also directly provide it if we construct items manually.
        # For now, let's rely on file system mtime.
        time.sleep(0.02) # Increased delay slightly
        return path

    def test_full_sorting_flow_with_classification_and_caching(self):
        # 1. Создаем тестовые файлы на 'рабочем столе'
        self._create_file_on_test_desktop('MyGame.exe')
        self._create_file_on_test_desktop('MySoft.lnk')
        test_folder_path = os.path.join(TEST_DESKTOP_DIR_INTEGRATION, 'TestFolder')
        os.makedirs(test_folder_path)
        time.sleep(0.02)
        self._create_file_on_test_desktop('info.txt')

        # 2. Настраиваем мок для _mock_search_google
        def search_side_effect(query):
            query_lower = query.lower()
            if 'mygame' in query_lower: return 'This is a game for sure'
            if 'mysoft' in query_lower: return 'This is some software utility'
            return 'Unknown content'
        self.mock_search_google.side_effect = search_side_effect

        # 3. Получаем элементы с 'рабочего стола'
        with patch.object(desktop_scanner, 'get_lnk_target', return_value='C:\\fake_target_for_MySoft.exe'):
            desktop_items = desktop_scanner.get_desktop_items(TEST_DESKTOP_DIR_INTEGRATION, self.settings_manager)

        self.assertEqual(len(desktop_items), 4) # Ensure all items are scanned

        # 4. Запускаем arrange_items (первый раз - классификация и запись в кэш)
        arrangement_plan1 = self.sorter.arrange_items(desktop_items, self.screen_res, self.dpi_info)

        self.assertEqual(len(arrangement_plan1), 4)
        # MyGame.exe (.exe), MySoft.lnk (.lnk) should be classified
        self.assertEqual(self.mock_search_google.call_count, 2)

        cat_game = next(item['category'] for item in arrangement_plan1 if item['name'] == 'MyGame.exe')
        cat_soft = next(item['category'] for item in arrangement_plan1 if item['name'] == 'MySoft.lnk')
        self.assertEqual(cat_game, 'games')
        self.assertEqual(cat_soft, 'programs')

        self.assertTrue(os.path.exists(TEST_CACHE_FILE_INTEGRATION))
        # WebClassifier._clean_name uses .lower(), so keys are 'mygame', 'mysoft'
        # WebClassifier's cache stores the direct result of classification (singular)
        self.assertEqual(self.web_classifier.cache_manager.get('mygame'), 'game')
        self.assertEqual(self.web_classifier.cache_manager.get('mysoft'), 'program')

        # 5. Сбрасываем мок и запускаем arrange_items снова (данные должны взяться из кэша)
        self.mock_search_google.reset_mock()
        # Ensure desktop_items are fetched again or use the same list if mtimes are not critical for this part
        # For this test, we reuse desktop_items as their content and classification shouldn't change
        arrangement_plan2 = self.sorter.arrange_items(desktop_items, self.screen_res, self.dpi_info)

        self.assertEqual(len(arrangement_plan2), 4)
        self.mock_search_google.assert_not_called()

        plan1_dict = {item['name']: (item['category'], item['new_coords']) for item in arrangement_plan1}
        plan2_dict = {item['name']: (item['category'], item['new_coords']) for item in arrangement_plan2}
        self.assertEqual(plan1_dict, plan2_dict)

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
