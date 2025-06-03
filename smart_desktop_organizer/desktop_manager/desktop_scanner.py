# -*- coding: utf-8 -*-
import os
import logging
import sys

logger = logging.getLogger('SmartDesktopOrganizer')

# Для работы с .lnk файлами и специальными папками Windows
try:
    import pythoncom # Обязательно для pywin32 в некоторых случаях
    from win32com.client import Dispatch
    import winshell # Для получения пути к рабочему столу и другим спец. папкам
    PYWIN32_AVAILABLE = True
except ImportError:
    logger.warning('Библиотека pywin32 (winshell, pywin32) не найдена. Функционал работы с ярлыками и специальными папками Windows будет ограничен.')
    PYWIN32_AVAILABLE = False

def get_desktop_path():
    # Получение пути к рабочему столу пользователя
    if PYWIN32_AVAILABLE and sys.platform == 'win32':
        try:
            # Инициализация COM должна быть на потоке, который его использует
            pythoncom.CoInitialize()
            desktop = winshell.desktop()
            pythoncom.CoUninitialize()
            logger.debug(f"Desktop path (winshell): {desktop}")
            return desktop
        except Exception as e:
            logger.error(f'Ошибка при получении пути к рабочему столу через winshell: {e}')
            # Попытка деинициализировать COM в случае ошибки, если он был инициализирован
            try:
                pythoncom.CoUninitialize()
            except Exception as com_e:
                logger.error(f'Ошибка при CoUninitialize после ошибки winshell: {com_e}')

    # Запасной вариант для других ОС или если winshell не сработал
    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    logger.debug(f"Desktop path (fallback): {desktop_path}")

    # В песочнице может не быть рабочего стола, или он может быть недоступен.
    # Для целей тестирования в такой среде создадим/используем локальную папку.
    # `PROJECT_ROOT_DIR` (из logger или settings) это /app.
    # Мы хотим, чтобы sandbox_desktop был в /app, а не в /app/smart_desktop_organizer/desktop_manager
    # Лучше использовать абсолютный путь или путь относительно известной точки, например, CWD.
    # Если CWD /app, то './sandbox_desktop_for_tests' будет /app/sandbox_desktop_for_tests

    # Проверяем, существует ли стандартный путь к рабочему столу
    if not os.path.exists(desktop_path) and not (PYWIN32_AVAILABLE and sys.platform == 'win32'):
        # Если мы не на Windows (где winshell мог бы дать реальный путь)
        # и стандартный ~/Desktop не существует, то используем песочницу.
        # На Windows, если winshell не сработал, но ~/Desktop существует, его и вернем.
        # Если winshell сработал, то он уже вернул путь.
        sandbox_desktop_parent_dir = os.path.abspath('.') # Предполагаем, что CWD это /app
        sandbox_desktop = os.path.join(sandbox_desktop_parent_dir, 'sandbox_desktop_for_tests')

        os.makedirs(sandbox_desktop, exist_ok=True)
        logger.info(f'Стандартный рабочий стол ({desktop_path}) не найден или недоступен, используется/создана тестовая папка: {sandbox_desktop}')
        return sandbox_desktop

    if not os.path.exists(desktop_path) and (PYWIN32_AVAILABLE and sys.platform == 'win32'):
        # Если это Windows, winshell не сработал, и ~/Desktop не существует
        # Это очень странная ситуация, но все же создадим песочницу.
        sandbox_desktop_parent_dir = os.path.abspath('.')
        sandbox_desktop = os.path.join(sandbox_desktop_parent_dir, 'sandbox_desktop_for_tests')
        os.makedirs(sandbox_desktop, exist_ok=True)
        logger.warning(f'Winshell не вернул путь и стандартный рабочий стол ({desktop_path}) не найден на Windows. Используется тестовая папка: {sandbox_desktop}')
        return sandbox_desktop

    return desktop_path

def get_lnk_target(lnk_path):
    # Получение пути, на который ссылается .lnk файл
    if not PYWIN32_AVAILABLE or not sys.platform == 'win32':
        logger.debug(f'pywin32 не доступен или платформа не Windows, не удается получить цель ярлыка {lnk_path}.')
        return None
    try:
        pythoncom.CoInitialize() # Инициализация COM для потока
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(lnk_path)
        target = shortcut.TargetPath
        pythoncom.CoUninitialize() # Деинициализация COM
        logger.debug(f"Target for {lnk_path}: {target}")
        return target if target else None # Возвращаем None, если TargetPath пуст
    except Exception as e:
        logger.error(f'Ошибка при разрешении ярлыка {lnk_path}: {e}')
        try:
            pythoncom.CoUninitialize() # Убедимся, что COM деинициализирован в случае ошибки
        except Exception as com_e:
            logger.error(f'Ошибка при CoUninitialize после ошибки Dispatch: {com_e}')
        return None

def find_invalid_shortcuts(desktop_path, settings_manager=None):
    # Поиск недействительных ярлыков на рабочем столе
    invalid_shortcuts = []
    excluded_files = settings_manager.get_setting('excluded_files', []) if settings_manager else []
    logger.info(f'Поиск недействительных ярлыков в: {desktop_path}')
    if not os.path.isdir(desktop_path):
        logger.warning(f'Директория рабочего стола не найдена: {desktop_path}')
        return invalid_shortcuts

    for item_name in os.listdir(desktop_path):
        if item_name.lower() in [name.lower() for name in excluded_files]:
            logger.debug(f'Файл {item_name} исключен из проверки ярлыков.')
            continue

        item_path = os.path.join(desktop_path, item_name)
        if item_name.lower().endswith('.lnk') and os.path.isfile(item_path):
            logger.debug(f"Проверка ярлыка: {item_path}")
            target_path = get_lnk_target(item_path)
            if target_path: # Ярлык действителен и вернул путь
                if not os.path.exists(target_path):
                    invalid_shortcuts.append({'path': item_path, 'target': target_path, 'reason': 'Цель не существует'})
                    logger.debug(f'Недействительный ярлык: {item_path} (цель: {target_path} не найдена)')
            elif PYWIN32_AVAILABLE and sys.platform == 'win32': # get_lnk_target вернул None на Windows
                # Это может быть "пустой" ярлык, системный ярлык без явной цели (редко), или ошибка чтения
                invalid_shortcuts.append({'path': item_path, 'target': 'N/A', 'reason': 'Не удалось определить цель или ярлык пуст/поврежден'})
                logger.debug(f'Потенциально недействительный ярлык (не удалось определить цель или пуст): {item_path}')
            # Если PYWIN32_AVAILABLE is False, get_lnk_target всегда вернет None, и мы не можем судить о валидности.
            # Такие файлы .lnk на не-Windows системах просто файлы, а не ярлыки.
            # Поэтому дополнительная проверка не нужна.

    logger.info(f'Найдено недействительных ярлыков: {len(invalid_shortcuts)}')
    return invalid_shortcuts

def find_empty_folders(desktop_path, settings_manager=None):
    # Поиск пустых папок на рабочем столе
    empty_folders = []
    default_excluded_content = ['desktop.ini', 'thumbs.db'] # Файлы, которые не считаются 'содержимым' папки
    excluded_folders_config = settings_manager.get_setting('excluded_folders', []) if settings_manager else []
    logger.info(f'Поиск пустых папок в: {desktop_path}')
    if not os.path.isdir(desktop_path):
        logger.warning(f'Директория рабочего стола не найдена: {desktop_path}')
        return empty_folders

    for item_name in os.listdir(desktop_path):
        item_path = os.path.join(desktop_path, item_name)
        if os.path.isdir(item_path):
            # Проверка на исключенные папки
            if item_name.lower() in [name.lower() for name in excluded_folders_config]:
                logger.debug(f'Папка {item_name} исключена из проверки на пустоту.')
                continue

            # Проверка на пустоту (игнорируя системные файлы типа desktop.ini)
            try:
                folder_contents = [f for f in os.listdir(item_path) if f.lower() not in default_excluded_content]
                if not folder_contents:
                    empty_folders.append({'path': item_path, 'reason': 'Папка пуста'})
                    logger.debug(f'Найдена пустая папка: {item_path}')
            except OSError as e:
                logger.warning(f"Не удалось прочитать содержимое папки {item_path}: {e}")

    logger.info(f'Найдено пустых папок: {len(empty_folders)}')
    return empty_folders

# --- Новые функции для сбора информации о рабочем столе и экране ---

try:
    from screeninfo import get_monitors
    SCREENINFO_AVAILABLE = True
except ImportError:
    logger.warning('Библиотека screeninfo не найдена. Функционал получения разрешения экрана будет ограничен.')
    SCREENINFO_AVAILABLE = False

if PYWIN32_AVAILABLE and sys.platform == 'win32': # PYWIN32_AVAILABLE был определен в начале файла
    try:
        import win32api
        import win32print
        import win32gui
        PYWIN32_MONITOR_INFO_AVAILABLE = True
    except ImportError:
        logger.warning('Некоторые модули pywin32 (win32api, win32print, win32gui) не найдены. Получение DPI может быть недоступно.')
        PYWIN32_MONITOR_INFO_AVAILABLE = False
else:
    PYWIN32_MONITOR_INFO_AVAILABLE = False

def get_screen_resolution_and_dpi():
    # Получение разрешения экрана и DPI основного монитора
    resolution = {'width': None, 'height': None}
    dpi = {'x': 96, 'y': 96}  # Стандартное значение DPI по умолчанию
    primary_monitor = None

    if SCREENINFO_AVAILABLE:
        try:
            monitors = get_monitors()
            for monitor in monitors:
                if hasattr(monitor, 'is_primary') and monitor.is_primary: # Проверка атрибута is_primary
                    primary_monitor = monitor
                    break
            if not primary_monitor and monitors: # Если нет явного основного, берем первый
                primary_monitor = monitors[0]
                logger.info('Основной монитор не определен явно, взят первый из списка.')

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
                logger.warning('Не удалось определить основной монитор через screeninfo.')
        except Exception as e:
            logger.error(f'Ошибка при получении разрешения через screeninfo: {e}')

    # Попытка получить DPI через pywin32, если доступно (только для Windows)
    if PYWIN32_MONITOR_INFO_AVAILABLE and sys.platform == 'win32':
        try:
            # Если screeninfo не дал разрешение, пробуем через win32api
            if resolution['width'] is None or resolution['height'] is None:
                resolution['width'] = win32api.GetSystemMetrics(0) # SM_CXSCREEN
                resolution['height'] = win32api.GetSystemMetrics(1) # SM_CYSCREEN
                logger.info(f'Разрешение основного монитора (win32api): {resolution["width"]}x{resolution["height"]}')

            hDC = win32gui.GetDC(0) # Получаем DC для всего экрана
            dpi_x_win32 = win32print.GetDeviceCaps(hDC, 88)  # LOGPIXELSX
            dpi_y_win32 = win32print.GetDeviceCaps(hDC, 90)  # LOGPIXELSY
            win32gui.ReleaseDC(0, hDC)
            # Обновляем DPI только если screeninfo не смог их рассчитать (или дал стандартные 96)
            if (dpi['x'] == 96 and dpi['y'] == 96) or not SCREENINFO_AVAILABLE:
                 dpi['x'] = dpi_x_win32
                 dpi['y'] = dpi_y_win32
            logger.info(f'DPI системы (pywin32): X={dpi["x"]}, Y={dpi["y"]}')
        except Exception as e:
            logger.error(f'Ошибка при получении разрешения/DPI через pywin32: {e}')

    if resolution['width'] is None or resolution['height'] is None: # Если все еще нет разрешения
        logger.warning('Не удалось получить разрешение экрана. Используются значения по умолчанию (1920x1080).')
        resolution['width'] = 1920 # Запасные значения
        resolution['height'] = 1080

    return resolution, dpi

def get_desktop_items(desktop_path, settings_manager=None):
    # Получение списка всех элементов на рабочем столе с их свойствами
    items = []
    excluded_files_list = settings_manager.get_setting('excluded_files', []) if settings_manager else []
    excluded_folders_list = settings_manager.get_setting('excluded_folders', []) if settings_manager else []
    # Приводим к нижнему регистру для сравнения без учета регистра
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
        is_file = os.path.isfile(item_path) # Включая ярлыки

        # Проверка на исключения
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
                target_path = get_lnk_target(item_path) # Эта функция уже логирует свои действия

            items.append({
                'name': item_name,
                'path': item_path,
                'type': item_type,
                'extension': extension,
                'date_modified': date_modified,
                'target_path': target_path, # Для .lnk файлов
                'coords': {'x': None, 'y': None} # Заглушка для координат
            })
        except Exception as e:
            logger.error(f'Ошибка при сборе информации об элементе {item_path}: {e}')

    logger.info(f'Собрана информация о {len(items)} элементах на рабочем столе.')
    return items
