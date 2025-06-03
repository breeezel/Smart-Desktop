# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import sys
from unittest.mock import patch, MagicMock, call

# Добавляем корень проекта в sys.path
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.desktop_manager import file_operations # Import the module itself
from smart_desktop_organizer.config_manager.settings import SettingsManager
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging

TEST_FILE_OPS_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_file_ops_tests')
TEST_SETTINGS_FILE_FOR_FILE_OPS = os.path.join(TEST_FILE_OPS_DIR, 'test_settings_for_file_ops.json')

class TestFileOperations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1)
        os.makedirs(TEST_FILE_OPS_DIR, exist_ok=True)

    def setUp(self):
        self.test_file1 = os.path.join(TEST_FILE_OPS_DIR, 'file1_to_delete.txt')
        self.test_folder1 = os.path.join(TEST_FILE_OPS_DIR, 'folder1_to_delete')
        self.test_file_in_folder = os.path.join(self.test_folder1, 'inner_file.txt')

        if os.path.exists(self.test_file1): os.remove(self.test_file1)
        if os.path.exists(self.test_folder1): shutil.rmtree(self.test_folder1)

        open(self.test_file1, 'w').close()
        os.makedirs(self.test_folder1, exist_ok=True)
        open(self.test_file_in_folder, 'w').close()

        if os.path.exists(TEST_SETTINGS_FILE_FOR_FILE_OPS):
            os.remove(TEST_SETTINGS_FILE_FOR_FILE_OPS)
        self.settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE_FOR_FILE_OPS)

    def tearDown(self):
        if os.path.exists(self.test_file1): os.remove(self.test_file1)
        if os.path.exists(self.test_folder1): shutil.rmtree(self.test_folder1)
        if os.path.exists(TEST_SETTINGS_FILE_FOR_FILE_OPS): os.remove(TEST_SETTINGS_FILE_FOR_FILE_OPS)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_FILE_OPS_DIR):
            shutil.rmtree(TEST_FILE_OPS_DIR)

    @patch('smart_desktop_organizer.desktop_manager.file_operations.os.remove')
    @patch('smart_desktop_organizer.desktop_manager.file_operations.shutil.rmtree')
    def test_01_delete_items_permanently(self, mock_rmtree, mock_os_remove):
        items_to_delete = [{'path': self.test_file1}, {'path': self.test_folder1}]
        deleted_count, errors = file_operations.delete_items(items_to_delete, to_recycle_bin=False, settings_manager=self.settings_manager)

        self.assertEqual(deleted_count, 2)
        self.assertEqual(len(errors), 0)
        mock_os_remove.assert_called_once_with(self.test_file1)
        mock_rmtree.assert_called_once_with(self.test_folder1)

    @patch.object(file_operations, 'winshell') # Patch the module-level 'winshell' attribute
    def test_02_delete_items_to_recycle_bin_windows_success(self, mock_winshell_module):
        # Configure the mock for winshell.delete_file
        mock_winshell_module.delete_file = MagicMock()

        items_to_delete = [{'path': self.test_file1}, {'path': self.test_folder1}]
        self.settings_manager.set_setting('delete_to_recycle_bin', True)

        with patch.object(sys, 'platform', 'win32'), \
             patch.object(file_operations, 'PYWIN32_AVAILABLE_FOR_RECYCLE', True):
             # This PYWIN32_AVAILABLE_FOR_RECYCLE patch might be redundant if winshell mock implies availability
             # but kept for explicitness matching the module's internal logic.
            deleted_count, errors = file_operations.delete_items(items_to_delete, settings_manager=self.settings_manager)

        self.assertEqual(deleted_count, 2)
        self.assertEqual(len(errors), 0)
        mock_winshell_module.delete_file.assert_has_calls([
            call(self.test_file1, silent=True, no_confirm=True),
            call(self.test_folder1, silent=True, no_confirm=True)
        ], any_order=True)

    @patch('smart_desktop_organizer.desktop_manager.file_operations.os.remove')
    @patch('smart_desktop_organizer.desktop_manager.file_operations.shutil.rmtree')
    @patch.object(file_operations, 'winshell')
    def test_03_delete_items_to_recycle_bin_non_windows_falls_back_to_permanent(self, mock_winshell_module, mock_rmtree, mock_os_remove):
        mock_winshell_module.delete_file = MagicMock() # Setup mock attribute
        items_to_delete = [{'path': self.test_file1}]
        self.settings_manager.set_setting('delete_to_recycle_bin', True)

        with patch.object(sys, 'platform', 'linux'):
            # Explicitly set the module's PYWIN32_AVAILABLE_FOR_RECYCLE to False for this test path
            with patch.object(file_operations, 'PYWIN32_AVAILABLE_FOR_RECYCLE', False):
                 # Also ensure winshell object itself is None for this path as per module logic
                 with patch.object(file_operations, 'winshell', None):
                    deleted_count, errors = file_operations.delete_items(items_to_delete, settings_manager=self.settings_manager)

        self.assertEqual(deleted_count, 1)
        self.assertEqual(len(errors), 0)
        mock_os_remove.assert_called_once_with(self.test_file1)
        mock_winshell_module.delete_file.assert_not_called()
        mock_rmtree.assert_not_called()

    @patch('smart_desktop_organizer.desktop_manager.file_operations.os.remove', side_effect=OSError('Permission denied'))
    def test_04_delete_items_error_handling(self, mock_os_remove):
        items_to_delete = [{'path': self.test_file1}]
        deleted_count, errors = file_operations.delete_items(items_to_delete, to_recycle_bin=False, settings_manager=self.settings_manager)
        self.assertEqual(deleted_count, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['path'], self.test_file1)
        self.assertIn('Permission denied', errors[0]['error'])

    def test_05_delete_non_existent_item(self):
        non_existent_path = os.path.join(TEST_FILE_OPS_DIR, 'non_existent_file.txt')
        items_to_delete = [{'path': non_existent_path}]
        deleted_count, errors = file_operations.delete_items(items_to_delete, to_recycle_bin=False, settings_manager=self.settings_manager)
        self.assertEqual(deleted_count, 0)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]['path'], non_existent_path)
        self.assertEqual(errors[0]['error'], 'Файл или папка не найдены')

    @patch('smart_desktop_organizer.desktop_manager.file_operations.os.remove')
    @patch('smart_desktop_organizer.desktop_manager.file_operations.shutil.rmtree')
    @patch.object(file_operations, 'winshell') # Patch the module-level 'winshell'
    def test_06_delete_items_uses_settings_manager_for_recycle_option(self, mock_winshell_module, mock_rmtree, mock_os_remove):
        mock_winshell_module.delete_file = MagicMock() # Setup mock attribute

        self.settings_manager.set_setting('delete_to_recycle_bin', False)
        items_to_delete = [{'path': self.test_file1}]
        file_operations.delete_items(items_to_delete, settings_manager=self.settings_manager)
        mock_os_remove.assert_called_once_with(self.test_file1)

        mock_os_remove.reset_mock()
        self.settings_manager.set_setting('delete_to_recycle_bin', True)

        with patch.object(sys, 'platform', 'win32'), \
             patch.object(file_operations, 'PYWIN32_AVAILABLE_FOR_RECYCLE', True):
            # Ensure the mocked winshell module itself is not None for this path
            # The patch.object(file_operations, 'winshell') already replaces it with a MagicMock
            file_operations.delete_items(items_to_delete, settings_manager=self.settings_manager)
            mock_winshell_module.delete_file.assert_called_once_with(self.test_file1, silent=True, no_confirm=True)
            mock_os_remove.assert_not_called()

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
