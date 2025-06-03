# -*- coding: utf-8 -*-
import os
import shutil
import logging
import sys

logger = logging.getLogger('SmartDesktopOrganizer')

# Initialize winshell to None so it always exists as a module attribute
winshell = None
PYWIN32_AVAILABLE_FOR_RECYCLE = False

try:
    import winshell as actual_winshell # Import with an alias
    winshell = actual_winshell # Assign to the module-level variable
    PYWIN32_AVAILABLE_FOR_RECYCLE = True
    logger.debug("winshell loaded for recycle bin functionality.")
except ImportError:
    logger.warning('winshell не найден. Удаление в корзину будет недоступно, только безвозвратное удаление.')
    # PYWIN32_AVAILABLE_FOR_RECYCLE remains False and winshell remains None

def delete_items(items_to_delete, to_recycle_bin=False, settings_manager=None):
    deleted_count = 0
    errors = []

    if settings_manager is not None:
        effective_to_recycle_bin = settings_manager.get_setting('delete_to_recycle_bin', to_recycle_bin)
    else:
        effective_to_recycle_bin = to_recycle_bin

    # Check if winshell object itself is None, not just PYWIN32_AVAILABLE_FOR_RECYCLE
    if effective_to_recycle_bin and (not winshell or not sys.platform == 'win32'):
        logger.warning('Удаление в корзину запрошено, но winshell не доступен или платформа не Windows. Будет выполнено безвозвратное удаление.')
        effective_to_recycle_bin = False

    for item_info in items_to_delete:
        item_path = item_info.get('path')
        if not item_path:
            logger.warning(f'Путь к элементу не указан в {item_info}, пропуск удаления.')
            errors.append({'path': 'N/A', 'error': 'Путь не указан'})
            continue
        if not os.path.exists(item_path): # Check existence before attempting to check type
            logger.warning(f'Элемент {item_path} не найден, пропуск удаления.')
            errors.append({'path': item_path, 'error': 'Файл или папка не найдены'})
            continue

        try:
            if effective_to_recycle_bin and winshell: # Ensure winshell is not None here
                winshell.delete_file(item_path, silent=True, no_confirm=True)
                logger.info(f'Элемент {item_path} перемещен в корзину.')
            else:
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

    return deleted_count, errors
