# -*- coding: utf-8 -*-
import sys
import os
import time # Needed for dummy item creation for sorter test
# PyQt5 import will be moved into main()

from smart_desktop_organizer.logger.logger_setup import setup_logger
from smart_desktop_organizer.config_manager.settings import SettingsManager
# from smart_desktop_organizer.gui.main_window import MainWindow # Moved into main()
# Импорты для тестирования desktop_manager
from smart_desktop_organizer.desktop_manager import (
    get_desktop_path, find_invalid_shortcuts, find_empty_folders, delete_items,
    get_screen_resolution_and_dpi, get_desktop_items, get_lnk_target, DesktopSorter
)
from smart_desktop_organizer.web_classifier import WebClassifier # Ensured import

settings_manager = SettingsManager()
logger = setup_logger(settings_manager)

# Попытка инициализировать COM для всего приложения, если используется Windows
PYWIN32_AVAILABLE_MAIN = False
if sys.platform == 'win32':
    try:
        import pythoncom
        pythoncom.CoInitialize()
        PYWIN32_AVAILABLE_MAIN = True
        logger.info("COM инициализирован глобально для приложения.")
    except ImportError:
        logger.warning("pythoncom не найден в main.py. COM-операции могут быть недоступны или работать нестабильно.")
    except Exception as e:
        logger.error(f"Ошибка при глобальной инициализации COM в main.py: {e}")

def test_desktop_operations(): # This function remains for potential future testing
    logger.info('--- Тестирование операций с рабочим столом и информацией о системе ---')
    desktop_path = get_desktop_path()
    logger.info(f'Путь к рабочему столу: {desktop_path}')

    resolution, dpi = get_screen_resolution_and_dpi()
    logger.info(f'Разрешение экрана: {resolution}, DPI: {dpi}')

    is_sandbox_path = 'sandbox_desktop_for_tests' in desktop_path
    if is_sandbox_path or sys.platform != 'win32':
        logger.info(f'Creating test items in folder: {desktop_path}')
        os.makedirs(desktop_path, exist_ok=True)
        os.makedirs(os.path.join(desktop_path, 'Empty Test Folder'), exist_ok=True)
        non_empty_folder_path = os.path.join(desktop_path, 'NonEmpty Test Folder')
        os.makedirs(non_empty_folder_path, exist_ok=True)
        with open(os.path.join(non_empty_folder_path, 'internal_file.txt'), 'w', encoding='utf-8') as f:
            f.write('test content')
        with open(os.path.join(desktop_path, 'existing_file.txt'), 'w', encoding='utf-8') as f:
            f.write('test')
        with open(os.path.join(desktop_path, 'invalid_shortcut.lnk'), 'w', encoding='utf-8') as f:
            f.write('fake lnk content for a non-existent target or invalid format')
        with open(os.path.join(desktop_path, 'valid_shortcut_to_existing.lnk'), 'w', encoding='utf-8') as f:
            f.write('fake lnk content pointing to existing_file.txt')

    invalid_shortcuts = find_invalid_shortcuts(desktop_path, settings_manager)
    logger.info(f'Найденные недействительные ярлыки: {invalid_shortcuts}')

    empty_folders = find_empty_folders(desktop_path, settings_manager)
    logger.info(f'Найденные пустые папки: {empty_folders}')

    desktop_items = get_desktop_items(desktop_path, settings_manager)
    logger.info(f'Все элементы на рабочем столе ({len(desktop_items)}):')
    for item in desktop_items:
        logger.info(f'  - {item["name"]} (Тип: {item["type"]}, Расширение: {item["extension"]}, Цель: {item.get("target_path")})')

    logger.warning('Тестовое удаление закомментировано для безопасности.')

    logger.info('--- Тестирование WebClassifier ---')
    classifier = WebClassifier(settings_manager=settings_manager)

    test_items_for_classification = [
        {'name': 'Doom Eternal.exe', 'path': os.path.join(desktop_path, 'Games', 'Doom Eternal', 'Doom Eternal.exe')},
        {'name': 'Photoshop.lnk', 'path': os.path.join(desktop_path, 'Graphics Software', 'Photoshop.lnk')},
        {'name': 'My Summer Car.exe', 'path': os.path.join(desktop_path, 'Indie Games', 'My Summer Car.exe')},
        {'name': 'Документ Word.docx', 'path': os.path.join(desktop_path, 'Документ Word.docx')},
        {'name': 'steam.exe', 'path': os.path.join(desktop_path, 'Steam', 'steam.exe')},
        {'name': 'some_utility.exe', 'path': os.path.join(desktop_path, 'Tools', 'some_utility.exe')},
        {'name': 'ярлык_на_неизвестное.lnk', 'path': os.path.join(desktop_path, 'ярлык_на_неизвестное.lnk')},
    ]

    if is_sandbox_path or sys.platform != 'win32':
        os.makedirs(os.path.join(desktop_path, 'Games', 'Doom Eternal'), exist_ok=True)
        os.makedirs(os.path.join(desktop_path, 'Graphics Software'), exist_ok=True)
        os.makedirs(os.path.join(desktop_path, 'Indie Games'), exist_ok=True)
        os.makedirs(os.path.join(desktop_path, 'Steam'), exist_ok=True)
        os.makedirs(os.path.join(desktop_path, 'Tools'), exist_ok=True)

    for item_info in test_items_for_classification:
        if not (item_info['name'].lower().endswith('.exe') or item_info['name'].lower().endswith('.lnk')):
            logger.info(f'Пропуск классификации для {item_info["name"]} (не .exe/.lnk)')
            continue
        category = classifier.classify_item(item_info['name'], item_info['path'])
        logger.info(f'Элемент: "{item_info["name"]}", Путь: "{item_info["path"]}" -> Классификация: {category}')

    logger.info('--- Конец тестирования WebClassifier ---')

    logger.info('--- Тестирование DesktopSorter ---')
    sorter = DesktopSorter(settings_manager, classifier)

    current_desktop_items_for_sorter = desktop_items
    if not current_desktop_items_for_sorter:
        logger.info('desktop_items пуст, создаем тестовые элементы для DesktopSorter')
        current_desktop_items_for_sorter = [
            {'name': 'Test Folder A', 'path': os.path.join(desktop_path, 'Test Folder A'), 'type': 'folder', 'extension': None, 'date_modified': time.time() - 1000, 'target_path': None},
            {'name': 'Test Game.exe', 'path': os.path.join(desktop_path, 'Test Game.exe'), 'type': 'file', 'extension': '.exe', 'date_modified': time.time() - 2000, 'target_path': None},
            {'name': 'Test Program.lnk', 'path': os.path.join(desktop_path, 'Test Program.lnk'), 'type': 'file', 'extension': '.lnk', 'date_modified': time.time() - 500, 'target_path': 'C:\\Program Files\\App\\app.exe'},
            {'name': 'MyNotes.txt', 'path': os.path.join(desktop_path, 'MyNotes.txt'), 'type': 'file', 'extension': '.txt', 'date_modified': time.time() - 1500, 'target_path': None},
            {'name': 'backup.zip', 'path': os.path.join(desktop_path, 'backup.zip'), 'type': 'file', 'extension': '.zip', 'date_modified': time.time() - 2500, 'target_path': None},
        ]
        classifier.cache_manager.set('Test Game', 'game')
        classifier.cache_manager.set('Test Program', 'program')

    effective_resolution = resolution
    effective_dpi = dpi
    if not resolution or not resolution.get('width'):
        effective_resolution = {'width': 1920, 'height': 1080}
        effective_dpi = {'x': 96, 'y': 96}
        logger.info(f'Используется разрешение по умолчанию для теста сортировщика: {effective_resolution}')

    arrangement_plan = sorter.arrange_items(current_desktop_items_for_sorter, effective_resolution, effective_dpi)
    logger.info(f'План размещения ({len(arrangement_plan)} элементов):')
    for item_plan in arrangement_plan:
        logger.info(f'  - Элемент: {item_plan["name"]:<30} Категория: {item_plan.get("category", "N/A"):<10} Новые коорд.: {item_plan.get("new_coords")}')

    logger.info('--- Конец тестирования DesktopSorter ---')
    logger.info('--- Конец тестирования операций с рабочим столом ---')


def main():
    logger.info('Запуск приложения Smart Desktop Organizer с GUI')

    # Инициализация WebClassifier (он нужен для окна настроек - очистка кэша)
    web_classifier = WebClassifier(settings_manager=settings_manager)

    # test_desktop_operations() # Закомментировано для запуска GUI

    from PyQt5.QtWidgets import QApplication
    from smart_desktop_organizer.gui.main_window import MainWindow
    app = QApplication(sys.argv)

    plugin_path_found = False
    existing_plugin_path = os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH')
    if existing_plugin_path:
        logger.debug(f"QT_QPA_PLATFORM_PLUGIN_PATH уже установлен: {existing_plugin_path}")
        plugin_path_found = True
    else:
        potential_paths = [
            os.path.join(os.path.dirname(sys.executable), 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins', 'platforms'),
            os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages', 'PyQt5', 'Qt5', 'plugins', 'platforms'),
        ]
        # QApplication.libraryPaths() может быть вызван только после QApplication(sys.argv)
        # Поэтому, если мы здесь, app уже должен быть инициализирован, если бы мы не перемещали импорты.
        # Для безопасности, можно добавить проверку, но здесь это для определения пути.
        # if QApplication.instance(): # Check if an instance already exists
        #     lib_paths = QApplication.libraryPaths()
        #     if lib_paths:
        #         potential_paths.append(str(lib_paths[0]))
        # else: # Create a temporary app to get paths if needed, then clean up. This is not ideal.
        #     temp_app_for_paths = QApplication.instance() if QApplication.instance() else QApplication(sys.argv)
        #     lib_paths = temp_app_for_paths.libraryPaths()
        #     if lib_paths: potential_paths.append(str(lib_paths[0]))
            # del temp_app_for_paths # Clean up temporary app if created
            # This part is tricky if app is not yet created. For now, assume it's okay or paths are standard.


        for path_to_check in potential_paths:
            if path_to_check and (os.path.exists(os.path.join(path_to_check, 'qwindows.dll')) or \
                                  os.path.exists(os.path.join(path_to_check, 'libqxcb.so'))):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = path_to_check
                logger.info(f"QT_QPA_PLATFORM_PLUGIN_PATH установлен на: {path_to_check}")
                plugin_path_found = True
                break
        if not plugin_path_found:
            logger.warning(f"Не удалось автоматически определить QT_QPA_PLATFORM_PLUGIN_PATH. Приложение может не запуститься корректно.")

    main_win = MainWindow(settings_manager, web_classifier_instance=web_classifier) # Pass web_classifier
    main_win.show()

    logger.info('Главное окно отображено. Запуск цикла обработки событий Qt.')
    exit_code = app.exec_()
    logger.info(f'Приложение Smart Desktop Organizer завершило работу с кодом {exit_code}')
    sys.exit(exit_code)

if __name__ == '__main__':
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # test_desktop_operations() # Закомментировано для запуска GUI
    main() # Активируем запуск GUI
