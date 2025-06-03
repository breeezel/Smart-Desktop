# -*- coding: utf-8 -*-
from .desktop_scanner import (
    get_desktop_path, find_invalid_shortcuts, find_empty_folders,
    get_screen_resolution_and_dpi, get_desktop_items, get_lnk_target
)
from .file_operations import delete_items
from .desktop_sorter import DesktopSorter # Добавляем DesktopSorter

__all__ = [
    'get_desktop_path',
    'find_invalid_shortcuts',
    'find_empty_folders',
    'delete_items',
    'get_screen_resolution_and_dpi',
    'get_desktop_items',
    'get_lnk_target',
    'DesktopSorter', # Добавляем DesktopSorter
]
