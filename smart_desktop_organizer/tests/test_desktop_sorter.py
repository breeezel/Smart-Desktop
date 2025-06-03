# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import sys
import time
from datetime import datetime
from unittest.mock import MagicMock, patch

# Добавляем корень проекта в sys.path
PROJECT_ROOT_FOR_TESTS = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT_FOR_TESTS)

from smart_desktop_organizer.desktop_manager.desktop_sorter import DesktopSorter, DEFAULT_ICON_SIZE
from smart_desktop_organizer.config_manager.settings import SettingsManager, DEFAULT_SETTINGS
from smart_desktop_organizer.web_classifier.classifier import WebClassifier
from smart_desktop_organizer.logger.logger_setup import setup_logger
import logging

TEST_SORTER_DIR = os.path.join(PROJECT_ROOT_FOR_TESTS, 'test_temp_sorter_tests') # Unique name
TEST_SETTINGS_FILE_FOR_SORTER = os.path.join(TEST_SORTER_DIR, 'test_settings_for_sorter.json')
TEST_CACHE_FILE_FOR_SORTER_CLASSIFIER = os.path.join(TEST_SORTER_DIR, 'test_cache_for_sorter_classifier.json')

class TestDesktopSorter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.logger = setup_logger()
        # cls.logger.setLevel(logging.CRITICAL + 1)
        os.makedirs(TEST_SORTER_DIR, exist_ok=True)

    def setUp(self):
        if os.path.exists(TEST_SETTINGS_FILE_FOR_SORTER):
            os.remove(TEST_SETTINGS_FILE_FOR_SORTER)
        if os.path.exists(TEST_CACHE_FILE_FOR_SORTER_CLASSIFIER):
            os.remove(TEST_CACHE_FILE_FOR_SORTER_CLASSIFIER)

        self.settings_manager = SettingsManager(settings_file=TEST_SETTINGS_FILE_FOR_SORTER)
        self.settings_manager.set_setting('icon_spacing', {'horizontal': 80, 'vertical': 90})
        self.settings_manager.set_setting('enable_googling', True)
        # Ensure default sorting rules are present if DesktopSorter relies on them directly
        # For this test, we'll mock classifier, so specific rule content might not be critical yet,
        # but it's good practice if the sorter directly reads from settings_manager.get_setting('sorting_rules')
        self.settings_manager.set_setting('sorting_rules', DEFAULT_SETTINGS['sorting_rules'])


        # WebClassifier needs a cache_file_path for its CacheManager.
        # We pass the test-specific cache path here.
        self.mock_web_classifier = WebClassifier(
            settings_manager=self.settings_manager,
            cache_file_path=TEST_CACHE_FILE_FOR_SORTER_CLASSIFIER
        )

        self.sorter = DesktopSorter(self.settings_manager, self.mock_web_classifier)
        self.screen_res = {'width': 1920, 'height': 1080}
        self.dpi_info = {'x': 96, 'y': 96}
        # Initial call to set_screen_info to calculate grid_dimensions based on default settings
        self.sorter.set_screen_info(self.screen_res, self.dpi_info)


    def tearDown(self):
        if os.path.exists(TEST_SETTINGS_FILE_FOR_SORTER):
            os.remove(TEST_SETTINGS_FILE_FOR_SORTER)
        if os.path.exists(TEST_CACHE_FILE_FOR_SORTER_CLASSIFIER):
            os.remove(TEST_CACHE_FILE_FOR_SORTER_CLASSIFIER)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_SORTER_DIR):
            shutil.rmtree(TEST_SORTER_DIR)

    def _create_test_item(self, name, type, extension, date_modified_offset_secs, target_path=None):
        return {
            'name': name, 'path': f'/fake/path/{name}', 'type': type, 'extension': extension,
            'date_modified': time.time() - date_modified_offset_secs, 'target_path': target_path,
            'coords': {'x': 0, 'y': 0}
        }

    def test_01_initialization_and_settings_load(self):
        self.assertEqual(self.sorter.effective_icon_cell_size['width'], 80)
        self.assertEqual(self.sorter.effective_icon_cell_size['height'], 90)
        # grid_dimensions are calculated in set_screen_info, which is called in setUp
        expected_grid_width = 1920 // 80
        expected_grid_height = 1080 // 90
        self.assertEqual(self.sorter.grid_dimensions['width'], expected_grid_width)
        self.assertEqual(self.sorter.grid_dimensions['height'], expected_grid_height)


    def test_02_set_screen_info(self):
        self.sorter.set_screen_info({'width': 1600, 'height': 900}, {'x': 144, 'y': 144})
        self.assertEqual(self.sorter.screen_resolution, {'width': 1600, 'height': 900})
        self.assertAlmostEqual(self.sorter.dpi_scale['x'], 1.5)
        self.assertAlmostEqual(self.sorter.dpi_scale['y'], 1.5)
        # Check grid_dimensions recalculation
        expected_grid_width = 1600 // 80 # Icon size from settings (80x90)
        expected_grid_height = 900 // 90
        self.assertEqual(self.sorter.grid_dimensions['width'], expected_grid_width)
        self.assertEqual(self.sorter.grid_dimensions['height'], expected_grid_height)


    def test_03_classify_and_prepare_items(self):
        item_game = self._create_test_item('Game.exe', 'file', '.exe', 100)
        item_prog = self._create_test_item('Prog.lnk', 'file', '.lnk', 200)
        item_folder = self._create_test_item('MyFolder', 'folder', None, 50)
        item_text = self._create_test_item('Doc.txt', 'file', '.txt', 300)
        item_other = self._create_test_item('Archive.zip', 'file', '.zip', 150)
        desktop_items = [item_game, item_prog, item_folder, item_text, item_other]

        def mock_classify_side_effect(name, path=None):
            if 'Game' in name: return 'game'
            if 'Prog' in name: return 'program'
            return 'unknown'
        self.mock_web_classifier.classify_item = MagicMock(side_effect=mock_classify_side_effect)

        prepared = self.sorter._classify_and_prepare_items(desktop_items)
        self.assertEqual(len(prepared), 5)

        # Default sort order in _classify_and_prepare_items is NOT applied anymore.
        # Sorting happens per-category in _calculate_grid_positions.
        # Here we just check categories and datetime_modified presence.

        categories = {p['name']: p['category'] for p in prepared}
        self.assertEqual(categories['Game.exe'], 'games')
        self.assertEqual(categories['Prog.lnk'], 'programs')
        self.assertEqual(categories['MyFolder'], 'folders')
        self.assertEqual(categories['Doc.txt'], 'text_files')
        self.assertEqual(categories['Archive.zip'], 'other')

        for item in prepared:
            self.assertIsInstance(item['datetime_modified'], datetime)


    def test_04_calculate_grid_positions_simplified(self):
        # Simpler test for _calculate_grid_positions focusing on one zone and direction
        items = [self._create_test_item(f'Item{i}', 'file', '.txt', i*10) for i in range(3)] # 3 items
        self.sorter.effective_icon_cell_size = {'width': 100, 'height': 100} # Simpler icon size

        # Zone: top-left quarter of a 800x600 screen
        zone_def = {
            'x_start_ratio': 0.0, 'y_start_ratio': 0.0,
            'width_ratio': 0.5, 'height_ratio': 0.5, # Zone is 400x300
            'fill_direction': 'left_to_right_top_to_bottom',
            'sort_order': 'name_asc' # Items are already Item0, Item1, Item2
        }
        self.sorter.screen_resolution = {'width': 800, 'height': 600}

        positions = self.sorter._calculate_grid_positions(items, zone_def, "test_zone_simple")
        self.assertEqual(len(positions), 3)
        # Expected: zone is 400x300. Icon 100x100. Max 4 in a row.
        # Item0: x=0, y=0
        # Item1: x=100, y=0
        # Item2: x=200, y=0
        expected_coords = [{'x': 0, 'y': 0}, {'x': 100, 'y': 0}, {'x': 200, 'y': 0}]
        for i, pos_item in enumerate(positions):
            self.assertEqual(pos_item['new_coords'], expected_coords[i], f'Mismatch for Item{i}')


    def test_05_arrange_items(self):
        item_game = self._create_test_item('Game.exe', 'file', '.exe', 100)
        item_prog = self._create_test_item('Prog.lnk', 'file', '.lnk', 200)
        item_folder = self._create_test_item('MyFolder', 'folder', None, 50)
        # Add one more folder to test sorting within category
        item_folder2 = self._create_test_item('AFolder', 'folder', None, 60)
        desktop_items = [item_game, item_prog, item_folder, item_folder2]

        def mock_classify_side_effect(name, path=None):
            if 'Game' in name: return 'game'
            if 'Prog' in name: return 'program'
            return 'unknown'
        self.mock_web_classifier.classify_item = MagicMock(side_effect=mock_classify_side_effect)

        # Use default sorting_rules from settings_manager
        arrangement_plan = self.sorter.arrange_items(desktop_items, self.screen_res, self.dpi_info)
        self.assertEqual(len(arrangement_plan), 4)

        for item in arrangement_plan:
            self.assertIn('new_coords', item)
            self.assertTrue(isinstance(item['new_coords']['x'], int))
            self.assertTrue(isinstance(item['new_coords']['y'], int))
            self.assertIn('category', item)

        game_item = next(p for p in arrangement_plan if p['name'] == 'Game.exe')
        folder_item1 = next(p for p in arrangement_plan if p['name'] == 'MyFolder')
        folder_item2 = next(p for p in arrangement_plan if p['name'] == 'AFolder')
        prog_item = next(p for p in arrangement_plan if p['name'] == 'Prog.lnk')

        # Basic zone checks (assuming default layout from DesktopSorter)
        # Games: top_right -> x > W/2, y < H/2
        self.assertTrue(game_item['new_coords']['x'] >= self.screen_res['width'] * 0.75) # Based on default zone
        self.assertTrue(game_item['new_coords']['y'] < self.screen_res['height'] * 0.5)

        # Folders: bottom_right -> x > W/2, y > H/2
        # Default sort for folders is 'name_asc'. So AFolder should be before MyFolder if in same row/col start.
        self.assertTrue(folder_item1['new_coords']['x'] >= self.screen_res['width'] * 0.75)
        self.assertTrue(folder_item1['new_coords']['y'] >= self.screen_res['height'] * 0.5)
        self.assertTrue(folder_item2['new_coords']['x'] >= self.screen_res['width'] * 0.75)
        self.assertTrue(folder_item2['new_coords']['y'] >= self.screen_res['height'] * 0.5)

        # Check sort order for folders (name_asc, fill right_to_left_bottom_to_top)
        # AFolder should be to the right of MyFolder if on same row, or on a row below.
        # Since fill is right_to_left, AFolder (first in name_asc) will be at the rightmost.
        # MyFolder will be to its left.
        if folder_item1['new_coords']['y'] == folder_item2['new_coords']['y']: # Same row
             self.assertTrue(folder_item2['new_coords']['x'] > folder_item1['new_coords']['x'])
        else: # Different rows (AFolder should be on a "later" row in fill order, which is higher Y)
             self.assertTrue(folder_item2['new_coords']['y'] < folder_item1['new_coords']['y'])


        # Programs: left_top -> x < W/2, y < H/2 (more or less, depends on zone width)
        self.assertTrue(prog_item['new_coords']['x'] < self.screen_res['width'] * 0.25) # Based on default zone

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
