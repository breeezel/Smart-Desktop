# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import sys
import time
from unittest.mock import patch, MagicMock, mock_open

# Добавляем корень проекта в sys.path
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.desktop_manager import desktop_scanner
from smart_desktop_organizer.config_manager.settings import SettingsManager
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging

TEST_SCANNER_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_scanner_tests') # Unique name
TEST_DESKTOP_DIR = os.path.join(TEST_SCANNER_DIR, 'TestDesktop')
TEST_SETTINGS_FILE_FOR_SCANNER = os.path.join(TEST_SCANNER_DIR, 'test_settings_for_scanner.json')

class TestDesktopScanner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1) # Disable logging for tests
        os.makedirs(TEST_SCANNER_DIR, exist_ok=True)
        os.makedirs(TEST_DESKTOP_DIR, exist_ok=True)

    def setUp(self):
        # Очистка тестового рабочего стола
        for item in os.listdir(TEST_DESKTOP_DIR):
            item_path = os.path.join(TEST_DESKTOP_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

        if os.path.exists(TEST_SETTINGS_FILE_FOR_SCANNER):
            os.remove(TEST_SETTINGS_FILE_FOR_SCANNER)
        self.settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE_FOR_SCANNER)

    def tearDown(self):
        if os.path.exists(TEST_SETTINGS_FILE_FOR_SCANNER):
            os.remove(TEST_SETTINGS_FILE_FOR_SCANNER)
        # Очистка тестового рабочего стола после каждого теста также (на всякий случай)
        for item in os.listdir(TEST_DESKTOP_DIR):
            item_path = os.path.join(TEST_DESKTOP_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)


    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_SCANNER_DIR):
            shutil.rmtree(TEST_SCANNER_DIR)

    @patch.object(desktop_scanner, 'PYWIN32_AVAILABLE', True) # Assume PYWIN32 is available for some tests
    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.winshell')
    @patch('os.path.expanduser')
    @patch('os.path.exists') # Mock os.path.exists for get_desktop_path
    def test_01_get_desktop_path(self, mock_os_path_exists, mock_expanduser, mock_winshell):
        # Сценарий 1: Windows, winshell доступен и возвращает путь
        with patch.object(sys, 'platform', 'win32'):
            mock_winshell.desktop.return_value = 'C:\\Users\\TestUser\\Desktop'
            # We don't need to mock os.path.exists for this specific sub-case as winshell path is returned directly
            self.assertEqual(desktop_scanner.get_desktop_path(), 'C:\\Users\\TestUser\\Desktop')

        # Сценарий 2: Не Windows, используется os.path.expanduser
        with patch.object(sys, 'platform', 'linux'), patch.object(desktop_scanner, 'PYWIN32_AVAILABLE', False):
            mock_expanduser.return_value = '/home/testuser'
            # mock_os_path_exists applies to the path constructed from expanduser
            mock_os_path_exists.return_value = True
            self.assertEqual(desktop_scanner.get_desktop_path(), '/home/testuser/Desktop')
            mock_os_path_exists.assert_called_with('/home/testuser/Desktop')


        # Сценарий 3: Стандартный Desktop не найден, используется sandbox_desktop_for_tests
        with patch.object(sys, 'platform', 'linux'), patch.object(desktop_scanner, 'PYWIN32_AVAILABLE', False):
            mock_expanduser.return_value = '/home/testuser_no_desktop'
            mock_os_path_exists.return_value = False # /home/testuser_no_desktop/Desktop НЕ существует

            # Mock os.getcwd() to ensure predictable sandbox_path if it uses relative paths like '.'
            with patch('os.getcwd', return_value=PROJECT_ROOT_FOR_TESTS): # Or any known root for tests
                 sandbox_path = os.path.join(PROJECT_ROOT_FOR_TESTS, 'sandbox_desktop_for_tests')
                 with patch('os.makedirs') as mock_makedirs:
                    self.assertEqual(desktop_scanner.get_desktop_path(), sandbox_path)
                    mock_makedirs.assert_called_with(sandbox_path, exist_ok=True)

    @patch.object(desktop_scanner, 'PYWIN32_AVAILABLE', True) # Assume available for these sub-tests
    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.Dispatch')
    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.pythoncom')
    def test_02_get_lnk_target(self, mock_pythoncom, mock_dispatch):
        mock_shell = MagicMock()
        mock_shortcut = MagicMock()
        mock_dispatch.return_value = mock_shell
        mock_shell.CreateShortCut.return_value = mock_shortcut

        with patch.object(sys, 'platform', 'win32'):
            mock_shortcut.TargetPath = 'C:\\Target\\Path.exe'
            self.assertEqual(desktop_scanner.get_lnk_target('fake.lnk'), 'C:\\Target\\Path.exe')
            mock_pythoncom.CoInitialize.assert_called_once()
            mock_pythoncom.CoUninitialize.assert_called_once()
            mock_pythoncom.reset_mock()
            mock_dispatch.reset_mock() # Reset for next call

            mock_shortcut.TargetPath = ''
            self.assertIsNone(desktop_scanner.get_lnk_target('fake_empty.lnk'))
            mock_pythoncom.reset_mock()
            mock_dispatch.reset_mock()

            mock_dispatch.side_effect = Exception('COM Error')
            self.assertIsNone(desktop_scanner.get_lnk_target('fake_error.lnk'))
            mock_pythoncom.CoUninitialize.assert_called()
            mock_dispatch.side_effect = None
            mock_pythoncom.reset_mock()
            mock_dispatch.reset_mock()

        with patch.object(sys, 'platform', 'linux'):
            self.assertIsNone(desktop_scanner.get_lnk_target('fake.lnk'))

        with patch.object(sys, 'platform', 'win32'), patch.object(desktop_scanner, 'PYWIN32_AVAILABLE', False):
             self.assertIsNone(desktop_scanner.get_lnk_target('fake.lnk'))


    def test_03_find_invalid_shortcuts(self):
        valid_target_path = os.path.join(TEST_DESKTOP_DIR, 'valid_target.exe')
        open(valid_target_path, 'w').close()

        lnk1_path = os.path.join(TEST_DESKTOP_DIR, 'valid_shortcut.lnk')
        lnk2_path = os.path.join(TEST_DESKTOP_DIR, 'invalid_shortcut.lnk') # Target won't exist
        lnk3_path = os.path.join(TEST_DESKTOP_DIR, 'excluded_shortcut.lnk')
        lnk4_path = os.path.join(TEST_DESKTOP_DIR, 'empty_target_shortcut.lnk') # Target is empty string

        open(lnk1_path, 'w').close() # Dummy file
        open(lnk2_path, 'w').close() # Dummy file
        open(lnk3_path, 'w').close() # Dummy file
        open(lnk4_path, 'w').close() # Dummy file

        self.settings_manager.set_setting('excluded_files', ['excluded_shortcut.lnk'])

        def mock_get_lnk_target_side_effect(path):
            if path == lnk1_path: return valid_target_path
            if path == lnk2_path: return 'C:\\NonExistent\\Target.exe'
            if path == lnk4_path: return '' # Empty target path
            return None

        # Patch os.path.exists globally for this test, simpler than multiple contexts
        with patch.object(desktop_scanner, 'get_lnk_target', side_effect=mock_get_lnk_target_side_effect), \
             patch('os.path.exists') as mock_os_path_exists:

            # os.path.exists for the target of lnk files
            mock_os_path_exists.side_effect = lambda p: p == valid_target_path

            # For PYWIN32_AVAILABLE check inside find_invalid_shortcuts for empty target case
            with patch.object(desktop_scanner, 'PYWIN32_AVAILABLE', True), \
                 patch.object(sys, 'platform', 'win32'): # Simulate Windows for full .lnk logic
                invalid_shortcuts = desktop_scanner.find_invalid_shortcuts(TEST_DESKTOP_DIR, self.settings_manager)

            self.assertEqual(len(invalid_shortcuts), 2)
            found_invalid_paths = [s['path'] for s in invalid_shortcuts]
            self.assertIn(lnk2_path, found_invalid_paths) # Target C:\NonExistent... doesn't exist
            self.assertIn(lnk4_path, found_invalid_paths) # Target is empty string, considered invalid by current logic if PYWIN32_AVAILABLE
            self.assertNotIn(lnk1_path, found_invalid_paths)
            self.assertNotIn(lnk3_path, found_invalid_paths)


    def test_04_find_empty_folders(self):
        empty_folder_path = os.path.join(TEST_DESKTOP_DIR, 'EmptyFolder')
        non_empty_folder_path = os.path.join(TEST_DESKTOP_DIR, 'NonEmptyFolder')
        excluded_folder_path = os.path.join(TEST_DESKTOP_DIR, 'ExcludedFolder')
        folder_with_system_file = os.path.join(TEST_DESKTOP_DIR, 'FolderWithSystemFile')

        os.makedirs(empty_folder_path)
        os.makedirs(non_empty_folder_path)
        open(os.path.join(non_empty_folder_path, 'file.txt'), 'w').close()
        os.makedirs(excluded_folder_path)
        os.makedirs(folder_with_system_file)
        open(os.path.join(folder_with_system_file, 'desktop.ini'), 'w').close()

        self.settings_manager.set_setting('excluded_folders', ['ExcludedFolder', 'excludedfolder'])

        empty_folders = desktop_scanner.find_empty_folders(TEST_DESKTOP_DIR, self.settings_manager)
        self.assertEqual(len(empty_folders), 2)
        found_paths = [f['path'] for f in empty_folders]
        self.assertIn(empty_folder_path, found_paths)
        self.assertIn(folder_with_system_file, found_paths) # desktop.ini is ignored
        self.assertNotIn(excluded_folder_path, found_paths)


    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.win32print')
    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.win32gui')
    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.win32api')
    @patch('smart_desktop_organizer.desktop_manager.desktop_scanner.get_monitors')
    def test_05_get_screen_resolution_and_dpi(self, mock_get_monitors, mock_win32api, mock_win32gui, mock_win32print):
        # Scenario 1: screeninfo works
        mock_monitor = MagicMock()
        mock_monitor.is_primary = True
        mock_monitor.width = 1920; mock_monitor.height = 1080
        mock_monitor.width_mm = None; mock_monitor.height_mm = None # To test default DPI
        mock_get_monitors.return_value = [mock_monitor]
        with patch.object(desktop_scanner, 'SCREENINFO_AVAILABLE', True), \
             patch.object(desktop_scanner, 'PYWIN32_MONITOR_INFO_AVAILABLE', False):
            res, dpi = desktop_scanner.get_screen_resolution_and_dpi()
            self.assertEqual(res, {'width': 1920, 'height': 1080})
            self.assertEqual(dpi, {'x': 96, 'y': 96})

        # Scenario 2: pywin32 works (screeninfo fails to find primary or returns no monitors)
        mock_get_monitors.return_value = []
        mock_win32api.GetSystemMetrics.side_effect = lambda n: 1600 if n == 0 else 900
        mock_win32gui.GetDC.return_value = 123 # hDC
        mock_win32print.GetDeviceCaps.side_effect = lambda dc, idx: 144 if idx == 88 else (144 if idx == 90 else 0)
        with patch.object(desktop_scanner, 'SCREENINFO_AVAILABLE', True), \
             patch.object(desktop_scanner, 'PYWIN32_MONITOR_INFO_AVAILABLE', True), \
             patch.object(sys, 'platform', 'win32'):
            res, dpi = desktop_scanner.get_screen_resolution_and_dpi()
            self.assertEqual(res, {'width': 1600, 'height': 900})
            self.assertEqual(dpi, {'x': 144, 'y': 144})
            mock_win32gui.ReleaseDC.assert_called_with(0, 123)

        # Scenario 3: Neither available
        with patch.object(desktop_scanner, 'SCREENINFO_AVAILABLE', False), \
             patch.object(desktop_scanner, 'PYWIN32_MONITOR_INFO_AVAILABLE', False):
            res, dpi = desktop_scanner.get_screen_resolution_and_dpi()
            self.assertEqual(res, {'width': 1920, 'height': 1080}) # Defaults
            self.assertEqual(dpi, {'x': 96, 'y': 96})


    def test_06_get_desktop_items(self):
        file1_path = os.path.join(TEST_DESKTOP_DIR, 'file1.txt'); open(file1_path, 'w').close(); time.sleep(0.01)
        folder1_path = os.path.join(TEST_DESKTOP_DIR, 'Folder1'); os.makedirs(folder1_path); time.sleep(0.01)
        lnk1_path = os.path.join(TEST_DESKTOP_DIR, 'shortcut.lnk'); open(lnk1_path, 'w').close()
        excluded_file_path = os.path.join(TEST_DESKTOP_DIR, 'excluded.dat'); open(excluded_file_path, 'w').close()

        self.settings_manager.set_setting('excluded_files', ['excluded.dat'])
        self.settings_manager.set_setting('excluded_folders', ['NonExistentExcludedFolder'])

        with patch.object(desktop_scanner, 'get_lnk_target', return_value='C:\\Target.exe') as mock_get_target:
            items = desktop_scanner.get_desktop_items(TEST_DESKTOP_DIR, self.settings_manager)
            self.assertEqual(len(items), 3)
            mock_get_target.assert_called_with(lnk1_path)

            item_names = sorted([item['name'] for item in items]) # Sort for predictable order
            self.assertListEqual(item_names, ['Folder1', 'file1.txt', 'shortcut.lnk'])
            self.assertNotIn('excluded.dat', item_names)

            for item in items:
                self.assertIn('name', item); self.assertIn('path', item); self.assertIn('type', item)
                self.assertIn('extension', item); self.assertIn('date_modified', item)
                self.assertIn('target_path', item); self.assertIn('coords', item)
                if item['name'] == 'shortcut.lnk':
                    self.assertEqual(item['target_path'], 'C:\\Target.exe')

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
