# -*- coding: utf-8 -*-
import os
import shutil
import logging
import sys

logger = logging.getLogger('SmartDesktopOrganizer')

try:
    # winshell.delete_file используется для удаления в корзину.
    # Он часть пакета winshell, который также используется в desktop_scanner.
    # Если winshell импортировался там, он должен быть доступен и здесь.
    import winshell
    PYWIN32_AVAILABLE_FOR_RECYCLE = True
except ImportError:
    logger.warning('winshell не найден. Удаление в корзину будет недоступно, только безвозвратное удаление.')
    PYWIN32_AVAILABLE_FOR_RECYCLE = False

def delete_items(items_to_delete, to_recycle_bin=False, settings_manager=None):
    # Удаление списка файлов или папок
    # items_to_delete: список словарей {'path': '/path/to/item'}
    deleted_count = 0
    errors = []

    # Получаем настройку удаления в корзину из SettingsManager, если он передан
    if settings_manager is not None:
        effective_to_recycle_bin = settings_manager.get_setting('delete_to_recycle_bin', to_recycle_bin)
    else:
        effective_to_recycle_bin = to_recycle_bin

    if effective_to_recycle_bin and (not PYWIN32_AVAILABLE_FOR_RECYCLE or not sys.platform == 'win32'):
        logger.warning('Удаление в корзину запрошено, но winshell не доступен или платформа не Windows. Будет выполнено безвозвратное удаление.')
        effective_to_recycle_bin = False # Принудительно отключаем, если не доступно

    for item_info in items_to_delete:
        item_path = item_info.get('path')
        if not item_path: # Проверка на None или пустую строку
            logger.warning(f'Путь к элементу не указан в {item_info}, пропуск удаления.')
            errors.append({'path': 'N/A', 'error': 'Путь не указан'})
            continue
        if not os.path.exists(item_path):
            logger.warning(f'Элемент {item_path} не найден, пропуск удаления.')
            errors.append({'path': item_path, 'error': 'Файл или папка не найдены'})
            continue

        try:
            if effective_to_recycle_bin:
                # Удаление в корзину с помощью winshell
                # winshell.delete_file() может удалять и файлы, и папки
                # silent=False (по умолчанию) - покажет диалог прогресса Windows
                # no_confirm=True - не будет запрашивать подтверждение у пользователя (но может быть глобальная настройка Windows)
                # Важно: winshell.delete_file() требует инициализации COM, если еще не сделано.
                # Обычно это делается на уровне приложения или основного потока.
                # Если нет, то pythoncom.CoInitialize() / CoUninitialize() нужны вокруг вызова.
                # Однако, winshell сам может управлять этим. Проверим поведение.
                # Если будут ошибки "CoInitialize has not been called", то нужно добавить.
                winshell.delete_file(item_path, silent=True, no_confirm=True)
                logger.info(f'Элемент {item_path} перемещен в корзину.')
            else:
                # Безвозвратное удаление
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.remove(item_path)
                    logger.info(f'Файл/ярлык {item_path} безвозвратно удален.')
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    logger.info(f'Папка {item_path} безвозвратно удалена.')
            deleted_count += 1
        except Exception as e:
            logger.error(f'Ошибка при удалении элемента {item_path}: {e}')
            errors.append({'path': item_path, 'error': str(e)})
            # Если ошибка связана с COM, можно попробовать добавить CoInitialize/CoUninitialize здесь,
            # но лучше это делать на более высоком уровне, если возможно.
            # Пример: if "CoInitialize" in str(e): logger.error("Возможно, требуется CoInitialize() перед вызовом winshell.delete_file()")

    return deleted_count, errors
