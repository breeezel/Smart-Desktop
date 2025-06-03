# -*- coding: utf-8 -*-
import os
import logging
import sys
import re # Import re, was missing from previous overwrite for classifier but needed here

logger = logging.getLogger('SmartDesktopOrganizer')

# Initialize potentially imported names to None
winshell = None
pythoncom = None
Dispatch = None
win32api = None
win32print = None
win32gui = None
get_monitors = None # For screeninfo

PYWIN32_AVAILABLE = False
SCREENINFO_AVAILABLE = False
PYWIN32_MONITOR_INFO_AVAILABLE = False

try:
    import pythoncom as actual_pythoncom
    from win32com.client import Dispatch as actual_Dispatch
    import winshell as actual_winshell

    pythoncom = actual_pythoncom
    Dispatch = actual_Dispatch
    winshell = actual_winshell
    PYWIN32_AVAILABLE = True
    logger.debug("pywin32 (winshell, pythoncom, Dispatch) loaded.")
except ImportError:
    logger.warning('Библиотека pywin32 (winshell, pythoncom, Dispatch) не найдена. Функционал работы с ярлыками и специальными папками Windows будет ограничен.')
    # PYWIN32_AVAILABLE remains False

if PYWIN32_AVAILABLE: # Only attempt these if the base pywin32 components loaded
    try:
        import win32api as actual_win32api
        import win32print as actual_win32print
        import win32gui as actual_win32gui
        win32api = actual_win32api
        win32print = actual_win32print
        win32gui = actual_win32gui
        PYWIN32_MONITOR_INFO_AVAILABLE = True
        logger.debug("pywin32 (win32api, win32print, win32gui) for monitor info loaded.")
    except ImportError:
        logger.warning('Некоторые модули pywin32 (win32api, win32print, win32gui) не найдены. Получение DPI и расширенной информации о мониторе может быть недоступно.')
        # PYWIN32_MONITOR_INFO_AVAILABLE remains False
else:
    # PYWIN32_MONITOR_INFO_AVAILABLE remains False if PYWIN32_AVAILABLE is False
    pass


try:
    from screeninfo import get_monitors as actual_get_monitors
    get_monitors = actual_get_monitors
    SCREENINFO_AVAILABLE = True
    logger.debug("screeninfo loaded.")
except ImportError:
    logger.warning('Библиотека screeninfo не найдена. Функционал получения разрешения экрана будет ограничен.')
    # SCREENINFO_AVAILABLE remains False


def get_desktop_path():
    if PYWIN32_AVAILABLE and sys.platform == 'win32' and winshell:
        try:
            if pythoncom: pythoncom.CoInitialize()
            desktop = winshell.desktop()
            if pythoncom: pythoncom.CoUninitialize()
            logger.debug(f"Desktop path (winshell): {desktop}")
            return desktop
        except Exception as e:
            logger.error(f'Ошибка при получении пути к рабочему столу через winshell: {e}')
            if pythoncom:
                try: pythoncom.CoUninitialize()
                except Exception: pass

    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    logger.debug(f"Desktop path (fallback): {desktop_path}")

    use_sandbox = False
    if sys.platform == 'win32':
        if not PYWIN32_AVAILABLE or not winshell: # If on Windows but winshell failed to load/work
            if not os.path.exists(desktop_path):
                use_sandbox = True
                logger.warning(f'Winshell не доступен/не сработал и стандартный рабочий стол ({desktop_path}) не найден на Windows.')
        # If winshell worked, its path is used. If it failed but ~/Desktop exists, that's used.
    else: # Not on Windows
        if not os.path.exists(desktop_path):
            use_sandbox = True
            logger.info(f'Стандартный рабочий стол ({desktop_path}) не найден или недоступен.')

    if use_sandbox:
        sandbox_desktop_parent_dir = os.path.abspath(os.getcwd()) # CWD is /app for tests
        sandbox_desktop = os.path.join(sandbox_desktop_parent_dir, 'sandbox_desktop_for_tests')
        os.makedirs(sandbox_desktop, exist_ok=True)
        logger.info(f'Используется/создана тестовая папка для рабочего стола: {sandbox_desktop}')
        return sandbox_desktop

    return desktop_path


def get_lnk_target(lnk_path):
    if not (PYWIN32_AVAILABLE and sys.platform == 'win32' and pythoncom and Dispatch):
        logger.debug(f'pywin32/COM не доступен или платформа не Windows, не удается получить цель ярлыка {lnk_path}.')
        return None
    try:
        pythoncom.CoInitialize()
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(lnk_path)
        target = shortcut.TargetPath
        pythoncom.CoUninitialize()
        logger.debug(f"Target for {lnk_path}: {target}")
        return target if target else None
    except Exception as e:
        logger.error(f'Ошибка при разрешении ярлыка {lnk_path}: {e}')
        try: pythoncom.CoUninitialize()
        except Exception: pass
        return None

def find_invalid_shortcuts(desktop_path, settings_manager=None):
    invalid_shortcuts = []
    excluded_files_list = settings_manager.get_setting('excluded_files', []) if settings_manager else []
    excluded_files = [name.lower() for name in excluded_files_list]
    logger.info(f'Поиск недействительных ярлыков в: {desktop_path}')
    if not os.path.isdir(desktop_path):
        logger.warning(f'Директория рабочего стола не найдена: {desktop_path}')
        return invalid_shortcuts

    for item_name in os.listdir(desktop_path):
        if item_name.lower() in excluded_files:
            logger.debug(f'Файл {item_name} исключен из проверки ярлыков.')
            continue

        item_path = os.path.join(desktop_path, item_name)
        if item_name.lower().endswith('.lnk') and os.path.isfile(item_path):
            logger.debug(f"Проверка ярлыка: {item_path}")
            target_path = get_lnk_target(item_path)
            if target_path:
                if not os.path.exists(target_path):
                    invalid_shortcuts.append({'path': item_path, 'target': target_path, 'reason': 'Цель не существует'})
                    logger.debug(f'Недействительный ярлык: {item_path} (цель: {target_path} не найдена)')
            elif PYWIN32_AVAILABLE and sys.platform == 'win32':
                invalid_shortcuts.append({'path': item_path, 'target': 'N/A', 'reason': 'Не удалось определить цель или ярлык пуст/поврежден'})
                logger.debug(f'Потенциально недействительный ярлык (не удалось определить цель или пуст): {item_path}')

    logger.info(f'Найдено недействительных ярлыков: {len(invalid_shortcuts)}')
    return invalid_shortcuts

def find_empty_folders(desktop_path, settings_manager=None):
    empty_folders = []
    default_excluded_content = ['desktop.ini', 'thumbs.db']
    excluded_folders_list = settings_manager.get_setting('excluded_folders', []) if settings_manager else []
    excluded_folders = [name.lower() for name in excluded_folders_list]
    logger.info(f'Поиск пустых папок в: {desktop_path}')
    if not os.path.isdir(desktop_path):
        logger.warning(f'Директория рабочего стола не найдена: {desktop_path}')
        return empty_folders

    for item_name in os.listdir(desktop_path):
        item_path = os.path.join(desktop_path, item_name)
        if os.path.isdir(item_path):
            if item_name.lower() in excluded_folders:
                logger.debug(f'Папка {item_name} исключена из проверки на пустоту.')
                continue
            try:
                folder_contents = [f for f in os.listdir(item_path) if f.lower() not in default_excluded_content]
                if not folder_contents:
                    empty_folders.append({'path': item_path, 'reason': 'Папка пуста'})
                    logger.debug(f'Найдена пустая папка: {item_path}')
            except OSError as e:
                logger.warning(f"Не удалось прочитать содержимое папки {item_path}: {e}")

    logger.info(f'Найдено пустых папок: {len(empty_folders)}')
    return empty_folders

def get_screen_resolution_and_dpi():
    resolution = {'width': None, 'height': None}
    dpi = {'x': 96, 'y': 96}
    primary_monitor = None

    if SCREENINFO_AVAILABLE and get_monitors:
        try:
            monitors = get_monitors()
            for monitor in monitors:
                if hasattr(monitor, 'is_primary') and monitor.is_primary:
                    primary_monitor = monitor
                    break
            if not primary_monitor and monitors:
                primary_monitor = monitors[0]
                logger.info('Основной монитор не определен явно screeninfo, взят первый из списка.')

            if primary_monitor:
                resolution['width'] = primary_monitor.width
                resolution['height'] = primary_monitor.height
                logger.info(f'Разрешение основного монитора (screeninfo): {resolution["width"]}x{resolution["height"]}')
                if hasattr(primary_monitor, 'width_mm') and hasattr(primary_monitor, 'height_mm') and \
                   primary_monitor.width_mm and primary_monitor.height_mm :
                    dpi['x'] = round((primary_monitor.width / primary_monitor.width_mm) * 25.4)
                    dpi['y'] = round((primary_monitor.height / primary_monitor.height_mm) * 25.4)
                    logger.info(f'DPI (screeninfo, расчетный): X={dpi["x"]}, Y={dpi["y"]}')
            else:
                logger.warning('Не удалось определить основной монитор через screeninfo (список мониторов пуст или нет primary).')
        except Exception as e:
            logger.error(f'Ошибка при получении разрешения через screeninfo: {e}')

    if PYWIN32_MONITOR_INFO_AVAILABLE and sys.platform == 'win32' and win32api and win32gui and win32print:
        try:
            if resolution['width'] is None or resolution['height'] is None:
                resolution['width'] = win32api.GetSystemMetrics(0)
                resolution['height'] = win32api.GetSystemMetrics(1)
                logger.info(f'Разрешение основного монитора (win32api): {resolution["width"]}x{resolution["height"]}')

            hDC = win32gui.GetDC(0)
            dpi_x_win32 = win32print.GetDeviceCaps(hDC, 88)
            dpi_y_win32 = win32print.GetDeviceCaps(hDC, 90)
            win32gui.ReleaseDC(0, hDC)
            if (dpi['x'] == 96 and dpi['y'] == 96) or not SCREENINFO_AVAILABLE: # Prioritize screeninfo calculated DPI if available
                 dpi['x'] = dpi_x_win32
                 dpi['y'] = dpi_y_win32
            logger.info(f'DPI системы (pywin32): X={dpi["x"]}, Y={dpi["y"]}')
        except Exception as e:
            logger.error(f'Ошибка при получении разрешения/DPI через pywin32: {e}')

    if resolution['width'] is None or resolution['height'] is None:
        logger.warning('Не удалось получить разрешение экрана. Используются значения по умолчанию (1920x1080).')
        resolution['width'] = 1920
        resolution['height'] = 1080

    return resolution, dpi

def get_desktop_items(desktop_path, settings_manager=None):
    items = []
    excluded_files_list = settings_manager.get_setting('excluded_files', []) if settings_manager else []
    excluded_folders_list = settings_manager.get_setting('excluded_folders', []) if settings_manager else []
    excluded_files = [name.lower() for name in excluded_files_list]
    excluded_folders = [name.lower() for name in excluded_folders_list]

    logger.info(f'Сбор информации об элементах в: {desktop_path}')

    if not os.path.isdir(desktop_path):
        logger.warning(f'Директория рабочего стола не найдена: {desktop_path}')
        return items

    for item_name in os.listdir(desktop_path):
        item_path = os.path.join(desktop_path, item_name)
        item_name_lower = item_name.lower()
        is_dir = os.path.isdir(item_path)
        is_file = os.path.isfile(item_path)

        if is_dir and item_name_lower in excluded_folders:
            logger.debug(f'Папка {item_name} исключена из сбора информации.')
            continue
        if is_file and item_name_lower in excluded_files:
            logger.debug(f'Файл {item_name} исключен из сбора информации.')
            continue

        try:
            stat_info = os.stat(item_path)
            date_modified = stat_info.st_mtime
            item_type = 'folder' if is_dir else 'file'
            extension = os.path.splitext(item_name)[1].lower() if is_file else None

            target_path = None
            if extension == '.lnk':
                target_path = get_lnk_target(item_path)

            items.append({
                'name': item_name,
                'path': item_path,
                'type': item_type,
                'extension': extension,
                'date_modified': date_modified,
                'target_path': target_path,
                'coords': {'x': None, 'y': None}
            })
        except Exception as e:
            logger.error(f'Ошибка при сборе информации об элементе {item_path}: {e}')

    logger.info(f'Собрана информация о {len(items)} элементах на рабочем столе.')
    return items
