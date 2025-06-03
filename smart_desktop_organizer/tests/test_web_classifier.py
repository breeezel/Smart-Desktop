# -*- coding: utf-8 -*-
import unittest
import os
import shutil
from unittest.mock import MagicMock, patch

# Добавляем корень проекта в sys.path для корректного импорта модулей приложения
import sys
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.web_classifier.classifier import WebClassifier
from smart_desktop_organizer.web_classifier.cache_manager import CacheManager
from smart_desktop_organizer.config_manager.settings import SettingsManager, DEFAULT_SETTINGS
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging

TEST_CLASSIFIER_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_classifier_tests')
TEST_CACHE_FILE_FOR_CLASSIFIER = os.path.join(TEST_CLASSIFIER_DIR, 'test_cache_for_classifier.json')
TEST_SETTINGS_FILE_FOR_CLASSIFIER = os.path.join(TEST_CLASSIFIER_DIR, 'test_settings_for_classifier.json')

class TestWebClassifier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1)
        os.makedirs(TEST_CLASSIFIER_DIR, exist_ok=True)

    def setUp(self):
        if os.path.exists(TEST_CACHE_FILE_FOR_CLASSIFIER):
            os.remove(TEST_CACHE_FILE_FOR_CLASSIFIER)
        if os.path.exists(TEST_SETTINGS_FILE_FOR_CLASSIFIER):
            os.remove(TEST_SETTINGS_FILE_FOR_CLASSIFIER)

        self.settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE_FOR_CLASSIFIER)
        self.settings_manager.set_setting('enable_googling', True)
        self.settings_manager.set_setting('googling_cache_ttl_days', 7)

        self.classifier = WebClassifier(
            settings_manager=self.settings_manager,
            cache_file_path=TEST_CACHE_FILE_FOR_CLASSIFIER
        )

    def tearDown(self):
        if os.path.exists(TEST_CACHE_FILE_FOR_CLASSIFIER):
            os.remove(TEST_CACHE_FILE_FOR_CLASSIFIER)
        if os.path.exists(TEST_SETTINGS_FILE_FOR_CLASSIFIER):
            os.remove(TEST_SETTINGS_FILE_FOR_CLASSIFIER)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_CLASSIFIER_DIR):
            shutil.rmtree(TEST_CLASSIFIER_DIR)

    def test_01_clean_name(self):
        self.assertEqual(self.classifier._clean_name('Doom Eternal.exe'), 'doom eternal')
        self.assertEqual(self.classifier._clean_name('Photoshop.lnk'), 'photoshop')
        self.assertEqual(self.classifier._clean_name('VSCode - Ярлык'), 'vscode')
        self.assertEqual(self.classifier._clean_name('VSCode - Shortcut'), 'vscode')
        self.assertEqual(self.classifier._clean_name('setup_v1.2.3.exe'), 'setup')
        self.assertEqual(self.classifier._clean_name('My Game v2.0 (x64).exe'), 'my game')
        self.assertEqual(self.classifier._clean_name('  My Game Name  '), 'my game name')

    def test_02_parse_search_results(self):
        self.assertEqual(self.classifier._parse_search_results('This is a great game, download game now! Gaming fun.'), 'game')
        self.assertEqual(self.classifier._parse_search_results('Official website for this amazing software utility tool.'), 'program')
        self.assertEqual(self.classifier._parse_search_results('This is a game and a software application.'), 'program')

        self.classifier.game_keywords = ['game']
        self.classifier.program_keywords = ['software', 'tool', 'utility', 'application']
        self.assertEqual(self.classifier._parse_search_results('This game is also a software tool product and utility application.'), 'program')

        # Restore default keywords for subsequent tests if needed, though setUp does this for each test
        self.classifier.game_keywords = list(WebClassifier.game_keywords_default)
        self.classifier.program_keywords = list(WebClassifier.program_keywords_default)

        self.assertEqual(self.classifier._parse_search_results('No relevant keywords here.'), 'unknown')
        self.assertEqual(self.classifier._parse_search_results('This is a game engine for software development.'), 'program')

    @patch('smart_desktop_organizer.web_classifier.classifier.WebClassifier._mock_search_google')
    def test_03_classify_item_no_cache(self, mock_search):
        mock_search.return_value = 'This is a game, lots of gaming fun.'
        category = self.classifier.classify_item('MyGame.exe', '/path/to/MyGame.exe')
        self.assertEqual(category, 'game')
        mock_search.assert_called_once()
        self.assertEqual(self.classifier.cache_manager.get('mygame'), 'game')

    @patch('smart_desktop_organizer.web_classifier.classifier.WebClassifier._mock_search_google')
    def test_04_classify_item_with_cache(self, mock_search):
        self.classifier.cache_manager.set('mycachedgame', 'game')
        category = self.classifier.classify_item('MyCachedGame.exe', '/path/to/MyCachedGame.exe')
        self.assertEqual(category, 'game')
        mock_search.assert_not_called()

    @patch('smart_desktop_organizer.web_classifier.classifier.WebClassifier._mock_search_google')
    def test_05_classify_item_parent_folder_fallback(self, mock_search):
        mock_search.side_effect = [
            'No useful info here for ObscureApp.exe.',
            'This folder CoolGameDevKit contains a game engine and a tool.' # Changed "tools" to "a tool"
        ]
        category = self.classifier.classify_item('ObscureApp.exe', '/mnt/data/CoolGameDevKit/ObscureApp.exe')
        self.assertEqual(category, 'program')
        self.assertEqual(mock_search.call_count, 2)
        self.assertEqual(self.classifier.cache_manager.get('obscureapp'), 'program')
        self.assertEqual(self.classifier.cache_manager.get('coolgamedevkit_folder_hint'), 'program')

    def test_06_classify_item_googling_disabled(self):
        self.settings_manager.set_setting('enable_googling', False)
        self.classifier = WebClassifier(
            settings_manager=self.settings_manager,
            cache_file_path=TEST_CACHE_FILE_FOR_CLASSIFIER
        )

        with patch.object(self.classifier, '_mock_search_google') as mock_search:
            category = self.classifier.classify_item('AnyApp.exe', '/path/to/AnyApp.exe')
            self.assertEqual(category, 'disabled')
            mock_search.assert_not_called()
            self.assertIsNone(self.classifier.cache_manager.get('anyapp'))

    @patch('smart_desktop_organizer.web_classifier.classifier.WebClassifier._mock_search_google')
    def test_07_classify_item_unknown_persists_in_cache(self, mock_search):
        mock_search.return_value = 'Some unrelated stuff found.'
        category = self.classifier.classify_item('VeryObscure.exe', '/path/to/VeryObscure.exe')
        self.assertEqual(category, 'unknown')
        mock_search.assert_called_once()
        self.assertEqual(self.classifier.cache_manager.get('veryobscure'), 'unknown')

        mock_search.reset_mock()
        category2 = self.classifier.classify_item('VeryObscure.exe', '/path/to/VeryObscure.exe')
        self.assertEqual(category2, 'unknown')
        mock_search.assert_not_called()

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
