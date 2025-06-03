# -*- coding: utf-8 -*-
import logging
import math
from datetime import datetime # Для преобразования timestamp в datetime для сортировки
import os # Needed for os.path.basename if used on target_path

logger = logging.getLogger('SmartDesktopOrganizer')

DEFAULT_ICON_SIZE = {'width': 75, 'height': 75} # Примерный размер иконки с отступами
DEFAULT_GRID_PADDING = {'x': 5, 'y': 5} # Отступы МЕЖДУ ячейками сетки (внутри icon_size)

class DesktopSorter:
    def __init__(self, settings_manager, web_classifier):
        self.settings_manager = settings_manager
        self.web_classifier = web_classifier
        self.screen_resolution = {'width': 1920, 'height': 1080} # Значения по умолчанию
        self.dpi_scale = {'x': 1.0, 'y': 1.0} # Масштаб DPI (1.0 = 100%)

        # Эти значения icon_size представляют собой ПОЛНЫЙ размер ячейки для одной иконки, ВКЛЮЧАЯ отступы.
        self.effective_icon_cell_size = DEFAULT_ICON_SIZE.copy()
        # self.grid_padding = DEFAULT_GRID_PADDING.copy() # Not used directly if icon_size includes padding

        self._load_layout_settings()

    def _load_layout_settings(self):
        # Загрузка настроек макета из SettingsManager
        icon_spacing_settings = self.settings_manager.get_setting('icon_spacing', {})
        self.effective_icon_cell_size['width'] = icon_spacing_settings.get('horizontal', DEFAULT_ICON_SIZE['width'])
        self.effective_icon_cell_size['height'] = icon_spacing_settings.get('vertical', DEFAULT_ICON_SIZE['height'])

        # grid_size из настроек определяет, сколько ячеек сетки доступно.
        # Если 0, то рассчитывается на основе разрешения экрана и размера ячейки иконки.
        self.grid_dimensions = self.settings_manager.get_setting('grid_size', {'width': 0, 'height': 0})

        logger.debug(f'Настройки макета загружены: effective_icon_cell_size={self.effective_icon_cell_size}, grid_dimensions={self.grid_dimensions}')

    def set_screen_info(self, screen_resolution, dpi_info):
        self.screen_resolution = screen_resolution
        self.dpi_scale['x'] = dpi_info.get('x', 96) / 96.0
        self.dpi_scale['y'] = dpi_info.get('y', 96) / 96.0

        # Корректируем РАЗМЕР ЯЧЕЙКИ ИКОНКИ с учетом DPI, если это предполагается (ТЗ стр. 10)
        # "Размеры иконок и отступы между ними должны быть настраиваемыми (в пикселях или % от разрешения экрана)."
        # "Учитывать системный масштаб DPI для корректного расчета пиксельных размеров."
        # Если icon_spacing в settings.json уже даны в "физических" пикселях (т.е. для 100% DPI),
        # то их нужно будет отмасштабировать. Если они даны в "логических" пикселях, то масштабирование не нужно.
        # Предположим, что настройки 'icon_spacing' даны для 100% DPI (96 DPI).
        # self.effective_icon_cell_size['width'] = int(self.effective_icon_cell_size['width'] * self.dpi_scale['x'])
        # self.effective_icon_cell_size['height'] = int(self.effective_icon_cell_size['height'] * self.dpi_scale['y'])
        # ^^^ Закомментировано, т.к. в ТЗ сказано "в пикселях", что обычно означает логические пиксели в контексте GUI.
        # Если бы это были физические пиксели, то иконки становились бы огромными на HiDPI.
        # Скорее всего, ОС сама масштабирует координаты, а размеры задаются в логических пикселях.
        # Оставляем effective_icon_cell_size как есть из настроек.

        logger.info(f'Информация об экране установлена: разрешение={self.screen_resolution}, масштаб DPI={self.dpi_scale}')
        logger.info(f'Размер ячейки иконки (из настроек): {self.effective_icon_cell_size}')

        # Рассчитываем grid_dimensions если они не заданы жестко
        if self.grid_dimensions.get('width', 0) == 0:
            self.grid_dimensions['width'] = math.floor(self.screen_resolution['width'] / self.effective_icon_cell_size['width'])
        if self.grid_dimensions.get('height', 0) == 0:
            self.grid_dimensions['height'] = math.floor(self.screen_resolution['height'] / self.effective_icon_cell_size['height'])
        logger.info(f'Расчетные/итоговые размеры сетки (кол-во ячеек): {self.grid_dimensions}')


    def _classify_and_prepare_items(self, desktop_items):
        classified_items = []
        for item in desktop_items:
            category = 'unknown'
            if item['type'] == 'folder':
                category = 'folders'
            elif item['extension'] in ['.txt', '.log', '.md', '.ini', '.cfg', '.json', '.xml', '.yaml', '.yml', '.doc', '.docx', '.pdf', '.rtf']: # Расширенный список текстовых/документов
                category = 'text_files'
            elif item['extension'] in ['.exe', '.lnk', '.app', '.bat', '.sh', '.jar']: # Расширенный список исполняемых/ярлыков
                name_to_classify = item['name']
                # if item['extension'] == '.lnk' and item.get('target_path'):
                #    name_to_classify = os.path.basename(item['target_path']) # Можно использовать имя цели

                classified_type = self.web_classifier.classify_item(name_to_classify, item['path'])
                if classified_type == 'game':
                    category = 'games'
                elif classified_type == 'program':
                    category = 'programs'
                elif classified_type == 'disabled': # Если гугление отключено
                    category = 'other' # или специальная категория 'unclassified_executables'
                else: # unknown от классификатора
                    category = 'other'
            else: # Картинки, видео, архивы и т.д.
                category = 'other'

            item_copy = item.copy()
            item_copy['category'] = category
            item_copy['datetime_modified'] = datetime.fromtimestamp(item['date_modified'])
            classified_items.append(item_copy)

        # Сортировка по умолчанию, если не указана в правилах для категории
        # classified_items.sort(key=lambda x: x['datetime_modified'], reverse=True)
        logger.debug(f'Элементы классифицированы: {len(classified_items)} шт.')
        return classified_items

    def _sort_items_for_category(self, items, sort_order_config):
        # sort_order_config: 'name_asc', 'name_desc', 'date_asc', 'date_desc'
        reverse = sort_order_config.endswith('_desc')
        if 'name' in sort_order_config:
            items.sort(key=lambda x: x['name'].lower(), reverse=reverse)
        elif 'date' in sort_order_config:
            items.sort(key=lambda x: x['datetime_modified'], reverse=reverse)
        return items

    def _calculate_grid_positions(self, items, zone_def, zone_name):
        # zone_def: {'x_start_ratio', 'y_start_ratio', 'width_ratio', 'height_ratio', 'fill_direction', 'row_limit', 'sort_order'}
        # fill_direction: 'left_to_right_top_to_bottom', 'right_to_left_top_to_bottom', etc.

        positions = []
        if not items: return positions

        # Сортируем элементы для данной категории согласно правилу
        items = self._sort_items_for_category(items, zone_def.get('sort_order', 'name_asc'))

        # Определение размеров зоны в пикселях
        zone_x_start_px = int(self.screen_resolution['width'] * zone_def['x_start_ratio'])
        zone_y_start_px = int(self.screen_resolution['height'] * zone_def['y_start_ratio'])
        zone_width_px = int(self.screen_resolution['width'] * zone_def['width_ratio'])
        zone_height_px = int(self.screen_resolution['height'] * zone_def['height_ratio'])

        # Количество ячеек в зоне
        cols_in_zone = max(1, math.floor(zone_width_px / self.effective_icon_cell_size['width']))
        rows_in_zone = max(1, math.floor(zone_height_px / self.effective_icon_cell_size['height']))

        logger.debug(f"Zone '{zone_name}': Start=({zone_x_start_px},{zone_y_start_px}), SizePx=({zone_width_px},{zone_height_px}), GridCells=({cols_in_zone}x{rows_in_zone})")

        # Определение направления заполнения
        fill = zone_def.get('fill_direction', 'left_to_right_top_to_bottom')

        # x_iter: (start_col, end_col, step), y_iter: (start_row, end_row, step)
        # primary_iter_is_rows: True если сначала заполняем колонку сверху вниз, потом переходим к следующей.
        #                       False если сначала заполняем ряд слева направо, потом переходим к следующему.

        primary_iter_is_rows = False # По умолчанию заполняем ряд, потом следующий ряд
        if fill == 'left_to_right_top_to_bottom':
            x_iter = range(cols_in_zone)
            y_iter = range(rows_in_zone)
        elif fill == 'right_to_left_top_to_bottom':
            x_iter = range(cols_in_zone -1, -1, -1)
            y_iter = range(rows_in_zone)
        elif fill == 'left_to_right_bottom_to_top':
            x_iter = range(cols_in_zone)
            y_iter = range(rows_in_zone -1, -1, -1)
        elif fill == 'right_to_left_bottom_to_top':
            x_iter = range(cols_in_zone -1, -1, -1)
            y_iter = range(rows_in_zone -1, -1, -1)
        elif fill == 'top_to_bottom_left_to_right': # Заполняем колонку, потом следующую
            primary_iter_is_rows = True
            x_iter = range(cols_in_zone)
            y_iter = range(rows_in_zone)
        # Добавить другие направления по необходимости
        else: # По умолчанию
            x_iter = range(cols_in_zone)
            y_iter = range(rows_in_zone)

        item_idx = 0
        if primary_iter_is_rows: # Итерируемся по колонкам (x), затем по рядам (y)
            for col_idx in x_iter:
                for row_idx in y_iter:
                    if item_idx >= len(items): break
                    item = items[item_idx]
                    # Координаты верхнего левого угла ячейки
                    pos_x = zone_x_start_px + col_idx * self.effective_icon_cell_size['width']
                    pos_y = zone_y_start_px + row_idx * self.effective_icon_cell_size['height']
                    item_copy = item.copy()
                    item_copy['new_coords'] = {'x': pos_x, 'y': pos_y}
                    positions.append(item_copy)
                    item_idx += 1
                if item_idx >= len(items): break
        else: # Итерируемся по рядам (y), затем по колонкам (x)
            for row_idx in y_iter:
                for col_idx in x_iter:
                    if item_idx >= len(items): break
                    item = items[item_idx]
                    pos_x = zone_x_start_px + col_idx * self.effective_icon_cell_size['width']
                    pos_y = zone_y_start_px + row_idx * self.effective_icon_cell_size['height']
                    item_copy = item.copy()
                    item_copy['new_coords'] = {'x': pos_x, 'y': pos_y}
                    positions.append(item_copy)
                    item_idx += 1
                if item_idx >= len(items): break

        if item_idx < len(items):
            logger.warning(f"Не все элементы ({len(items) - item_idx} из {len(items)}) поместились в зону '{zone_name}'.")

        return positions

    def arrange_items(self, desktop_items, screen_resolution, dpi_info):
        self.set_screen_info(screen_resolution, dpi_info) # Устанавливаем актуальную инфо об экране
        prepared_items = self._classify_and_prepare_items(desktop_items)

        sorting_rules = self.settings_manager.get_setting('sorting_rules', {})
        all_arranged_items = []

        # Определяем зоны из настроек (примерная структура)
        # 'position' может быть 'top_left', 'top_right', 'bottom_left', 'bottom_right', 'center', 'left_side', 'right_side'
        # или более сложная система grid_x, grid_y, grid_w, grid_h (в долях от экрана)

        # Пример определения зон (можно вынести в настройки)
        # Это очень упрощенная схема деления экрана.
        # Реальные зоны могут перекрываться или быть более сложными.
        # Коэффициенты для зон (доли от общего разрешения)
        zones_layout = {
            'folders':    {'x_start_ratio': 0.75, 'y_start_ratio': 0.50, 'width_ratio': 0.25, 'height_ratio': 0.50, 'fill_direction': 'right_to_left_bottom_to_top'},
            'games':      {'x_start_ratio': 0.75, 'y_start_ratio': 0.0,  'width_ratio': 0.25, 'height_ratio': 0.50, 'fill_direction': 'right_to_left_top_to_bottom'},
            'programs':   {'x_start_ratio': 0.0,  'y_start_ratio': 0.0,  'width_ratio': 0.25, 'height_ratio': 1.0,  'fill_direction': 'left_to_right_top_to_bottom'}, # Левая колонка
            'text_files': {'x_start_ratio': 0.25, 'y_start_ratio': 0.75, 'width_ratio': 0.50, 'height_ratio': 0.25, 'fill_direction': 'left_to_right_bottom_to_top'}, # Внизу, после программ
            'other':      {'x_start_ratio': 0.25, 'y_start_ratio': 0.25, 'width_ratio': 0.50, 'height_ratio': 0.50, 'fill_direction': 'left_to_right_top_to_bottom'}  # Центр
        }

        processed_categories = set()

        for category_name, rule in sorting_rules.items():
            if not rule.get('enabled', False):
                logger.info(f"Категория '{category_name}' отключена в настройках, пропуск.")
                continue

            items_for_category = [item for item in prepared_items if item['category'] == category_name]
            if not items_for_category:
                logger.debug(f"Нет элементов для категории '{category_name}'.")
                continue

            position_key = rule.get('position', 'center') # 'top_left', 'bottom_right_above_folders' etc.
            # TODO: Преобразовать position_key в конкретные zone_def для _calculate_grid_positions
            # Сейчас используем пример zones_layout, в будущем это должно быть гибче
            zone_definition_key = category_name # Предполагаем, что ключи в zones_layout совпадают с именами категорий
            if zone_definition_key not in zones_layout:
                logger.warning(f"Не найдено определение зоны для ключа '{zone_definition_key}' (категория '{category_name}'). Используется зона 'other'.")
                zone_definition_key = 'other' # Фоллбэк на центральную зону

            zone_def_for_calc = zones_layout[zone_definition_key].copy()
            zone_def_for_calc['sort_order'] = rule.get('sort_order', 'name_asc') # Добавляем правило сортировки из настроек

            logger.info(f"Обработка категории '{category_name}' с позицией '{position_key}' (используется зона '{zone_definition_key}') и сортировкой '{zone_def_for_calc['sort_order']}'.")

            arranged_category_items = self._calculate_grid_positions(items_for_category, zone_def_for_calc, category_name)
            all_arranged_items.extend(arranged_category_items)
            processed_categories.add(category_name)

        # Обработка оставшихся категорий, если для них не было явных правил в sorting_rules,
        # но они были определены классификатором (например, если в sorting_rules нет 'other')
        remaining_items = [item for item in prepared_items if item['category'] not in processed_categories]
        if remaining_items:
            logger.info(f"Обработка оставшихся элементов ({len(remaining_items)}) в зоне 'other'.")
            zone_def_other = zones_layout['other'].copy()
            zone_def_other['sort_order'] = 'date_desc' # Сортировка по умолчанию для "other"
            arranged_remaining = self._calculate_grid_positions(remaining_items, zone_def_other, 'other_remaining')
            all_arranged_items.extend(arranged_remaining)

        logger.info(f'Сформирован план размещения для {len(all_arranged_items)} элементов.')
        return all_arranged_items
