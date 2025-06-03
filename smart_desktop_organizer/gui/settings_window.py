# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QGroupBox, QLabel, QCheckBox,
                             QPushButton, QSpinBox, QComboBox, QHBoxLayout, QScrollArea, QWidget,
                             QLineEdit, QListWidget, QAbstractItemView, QMessageBox) # Added QMessageBox
from PyQt5.QtCore import Qt
import logging

logger = logging.getLogger('SmartDesktopOrganizer')

class SettingsWindow(QDialog):
    def __init__(self, settings_manager, parent=None, web_classifier=None):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.web_classifier = web_classifier # Нужен для очистки кэша
        self.setWindowTitle('Настройки Smart Desktop Organizer')
        self.setMinimumWidth(550) # Increased width
        self.setMinimumHeight(500) # Added minimum height

        # Основной макет
        main_layout = QVBoxLayout(self)

        # Область с прокруткой для содержимого настроек
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        settings_content_widget = QWidget()
        scroll_area.setWidget(settings_content_widget)
        content_layout = QVBoxLayout(settings_content_widget)

        # --- Группа настроек "Общие" ---
        general_group = QGroupBox('Общие настройки')
        general_layout = QFormLayout()

        self.cb_delete_to_recycle_bin = QCheckBox('Удалять файлы в корзину (если возможно)')
        general_layout.addRow(self.cb_delete_to_recycle_bin)

        self.cb_confirm_delete = QCheckBox('Запрашивать подтверждение перед удалением')
        general_layout.addRow(self.cb_confirm_delete)

        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
        general_layout.addRow('Уровень логирования:', self.combo_log_level)

        general_group.setLayout(general_layout)
        content_layout.addWidget(general_group)

        # --- Группа настроек "Классификатор" ---
        classifier_group = QGroupBox('Настройки классификатора (интернет-поиск)')
        classifier_layout = QFormLayout()

        self.cb_enable_googling = QCheckBox('Включить классификацию через интернет')
        classifier_layout.addRow(self.cb_enable_googling)

        self.spin_cache_ttl = QSpinBox()
        self.spin_cache_ttl.setRange(1, 365)
        self.spin_cache_ttl.setSuffix(' дней')
        classifier_layout.addRow('Время жизни кэша классификатора:', self.spin_cache_ttl)

        self.btn_clear_cache = QPushButton('Очистить кэш классификатора')
        self.btn_clear_cache.clicked.connect(self.clear_classifier_cache)
        classifier_layout.addRow(self.btn_clear_cache)

        classifier_group.setLayout(classifier_layout)
        content_layout.addWidget(classifier_group)

        # --- Группа настроек "Сортировка" ---
        sorting_group = QGroupBox('Настройки макета рабочего стола')
        sorting_layout = QFormLayout()

        self.spin_icon_spacing_h = QSpinBox()
        self.spin_icon_spacing_h.setRange(32, 256)
        self.spin_icon_spacing_h.setSuffix(' px')
        sorting_layout.addRow('Горизонтальный размер ячейки иконки:', self.spin_icon_spacing_h)

        self.spin_icon_spacing_v = QSpinBox()
        self.spin_icon_spacing_v.setRange(32, 256)
        self.spin_icon_spacing_v.setSuffix(' px')
        sorting_layout.addRow('Вертикальный размер ячейки иконки:', self.spin_icon_spacing_v)
        # TODO: Добавить сюда настройки для grid_size (если 0, то авто)
        # TODO: Добавить сюда настройки для sorting_rules (сложный GUI)

        sorting_group.setLayout(sorting_layout)
        content_layout.addWidget(sorting_group)

        # --- Группа настроек "Исключения" ---
        exclusions_group = QGroupBox('Исключения из сканирования и сортировки')
        exclusions_main_layout = QVBoxLayout()

        excluded_files_group_layout = QHBoxLayout()
        self.list_excluded_files = QListWidget()
        self.list_excluded_files.setSelectionMode(QAbstractItemView.ExtendedSelection)
        excluded_files_group_layout.addWidget(self.list_excluded_files)

        excluded_files_buttons_layout = QVBoxLayout()
        excluded_files_buttons_layout.addWidget(QLabel('Исключенные файлы:'))
        self.edit_excluded_file = QLineEdit()
        self.edit_excluded_file.setPlaceholderText('имя файла, например, my_doc.txt')
        excluded_files_buttons_layout.addWidget(self.edit_excluded_file)
        self.btn_add_excluded_file = QPushButton('Добавить файл')
        self.btn_add_excluded_file.clicked.connect(lambda: self.add_to_list(self.list_excluded_files, self.edit_excluded_file, True))
        excluded_files_buttons_layout.addWidget(self.btn_add_excluded_file)
        self.btn_remove_excluded_file = QPushButton('Удалить выбранные')
        self.btn_remove_excluded_file.clicked.connect(lambda: self.remove_from_list(self.list_excluded_files))
        excluded_files_buttons_layout.addWidget(self.btn_remove_excluded_file)
        excluded_files_buttons_layout.addStretch()
        excluded_files_group_layout.addLayout(excluded_files_buttons_layout)
        exclusions_main_layout.addLayout(excluded_files_group_layout)

        excluded_folders_group_layout = QHBoxLayout()
        self.list_excluded_folders = QListWidget()
        self.list_excluded_folders.setSelectionMode(QAbstractItemView.ExtendedSelection)
        excluded_folders_group_layout.addWidget(self.list_excluded_folders)

        excluded_folders_buttons_layout = QVBoxLayout()
        excluded_folders_buttons_layout.addWidget(QLabel('Исключенные папки:'))
        self.edit_excluded_folder = QLineEdit()
        self.edit_excluded_folder.setPlaceholderText('имя папки, например, Work Stuff')
        excluded_folders_buttons_layout.addWidget(self.edit_excluded_folder)
        self.btn_add_excluded_folder = QPushButton('Добавить папку')
        self.btn_add_excluded_folder.clicked.connect(lambda: self.add_to_list(self.list_excluded_folders, self.edit_excluded_folder, False))
        excluded_folders_buttons_layout.addWidget(self.btn_add_excluded_folder)
        self.btn_remove_excluded_folder = QPushButton('Удалить выбранные')
        self.btn_remove_excluded_folder.clicked.connect(lambda: self.remove_from_list(self.list_excluded_folders))
        excluded_folders_buttons_layout.addWidget(self.btn_remove_excluded_folder)
        excluded_folders_buttons_layout.addStretch()
        excluded_folders_group_layout.addLayout(excluded_folders_buttons_layout)
        exclusions_main_layout.addLayout(excluded_folders_group_layout)

        exclusions_group.setLayout(exclusions_main_layout)
        content_layout.addWidget(exclusions_group)

        # Кнопки управления
        button_box_layout = QHBoxLayout()
        self.btn_save = QPushButton('Сохранить и закрыть')
        self.btn_save.clicked.connect(self.save_settings_action)
        button_box_layout.addWidget(self.btn_save)

        self.btn_reset = QPushButton('Сбросить по умолчанию')
        self.btn_reset.clicked.connect(self.reset_settings_action)
        button_box_layout.addWidget(self.btn_reset)

        self.btn_cancel = QPushButton('Отмена')
        self.btn_cancel.clicked.connect(self.reject)
        button_box_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(button_box_layout)

        self.load_settings()
        logger.debug('Окно настроек инициализировано.')

    def load_settings(self):
        self.cb_delete_to_recycle_bin.setChecked(self.settings_manager.get_setting('delete_to_recycle_bin', True))
        self.cb_confirm_delete.setChecked(self.settings_manager.get_setting('default_delete_confirmation', True))
        self.combo_log_level.setCurrentText(self.settings_manager.get_setting('log_level', 'INFO').upper())
        self.cb_enable_googling.setChecked(self.settings_manager.get_setting('enable_googling', True))
        self.spin_cache_ttl.setValue(self.settings_manager.get_setting('googling_cache_ttl_days', 7))
        icon_spacing = self.settings_manager.get_setting('icon_spacing', {'horizontal': 75, 'vertical': 75})
        self.spin_icon_spacing_h.setValue(icon_spacing.get('horizontal', 75))
        self.spin_icon_spacing_v.setValue(icon_spacing.get('vertical', 75))
        self.populate_list_widget(self.list_excluded_files, self.settings_manager.get_setting('excluded_files', []))
        self.populate_list_widget(self.list_excluded_folders, self.settings_manager.get_setting('excluded_folders', []))
        logger.info('Настройки загружены в окно настроек.')

    def apply_settings_action(self):
        self.settings_manager.set_setting('delete_to_recycle_bin', self.cb_delete_to_recycle_bin.isChecked())
        self.settings_manager.set_setting('default_delete_confirmation', self.cb_confirm_delete.isChecked())
        new_log_level = self.combo_log_level.currentText()
        self.settings_manager.set_setting('log_level', new_log_level)
        self.settings_manager.set_setting('enable_googling', self.cb_enable_googling.isChecked())
        self.settings_manager.set_setting('googling_cache_ttl_days', self.spin_cache_ttl.value())
        icon_spacing = {
            'horizontal': self.spin_icon_spacing_h.value(),
            'vertical': self.spin_icon_spacing_v.value()
        }
        self.settings_manager.set_setting('icon_spacing', icon_spacing)
        self.settings_manager.set_setting('excluded_files', self.get_list_widget_items(self.list_excluded_files))
        self.settings_manager.set_setting('excluded_folders', self.get_list_widget_items(self.list_excluded_folders))

        if self.web_classifier and hasattr(self.web_classifier, 'cache_manager'):
             self.web_classifier.cache_manager.cache_ttl_days = self.spin_cache_ttl.value()
             self.web_classifier.enable_googling = self.cb_enable_googling.isChecked()

        # Обновляем уровень логгера немедленно
        current_logger = logging.getLogger('SmartDesktopOrganizer')
        current_logger.setLevel(new_log_level)
        for handler in current_logger.handlers: # Обновляем и у обработчиков, если нужно
            handler.setLevel(new_log_level)
        logger.info(f'Уровень логирования изменен на {new_log_level}')

        logger.info('Настройки применены и сохранены.')
        QMessageBox.information(self, "Настройки", "Настройки применены и сохранены.")


    def save_settings_action(self):
        self.apply_settings_action()
        self.accept()

    def reset_settings_action(self):
        # Импортируем значения по умолчанию динамически, чтобы избежать проблем с порядком импорта
        from smart_desktop_organizer.config_manager.settings import DEFAULT_SETTINGS

        reply = QMessageBox.question(self, 'Сброс настроек',
                                     'Вы уверены, что хотите сбросить все настройки к значениям по умолчанию?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.cb_delete_to_recycle_bin.setChecked(DEFAULT_SETTINGS['delete_to_recycle_bin'])
            self.cb_confirm_delete.setChecked(DEFAULT_SETTINGS['default_delete_confirmation'])
            self.combo_log_level.setCurrentText(DEFAULT_SETTINGS['log_level'].upper())
            self.cb_enable_googling.setChecked(DEFAULT_SETTINGS['enable_googling'])
            self.spin_cache_ttl.setValue(DEFAULT_SETTINGS['googling_cache_ttl_days'])
            self.spin_icon_spacing_h.setValue(DEFAULT_SETTINGS['icon_spacing']['horizontal'])
            self.spin_icon_spacing_v.setValue(DEFAULT_SETTINGS['icon_spacing']['vertical'])
            self.populate_list_widget(self.list_excluded_files, DEFAULT_SETTINGS['excluded_files'])
            self.populate_list_widget(self.list_excluded_folders, DEFAULT_SETTINGS['excluded_folders'])
            logger.info('Значения в форме сброшены на настройки по умолчанию. Нажмите "Сохранить" для применения.')
            QMessageBox.information(self, "Сброс настроек", "Настройки в форме сброшены. Нажмите 'Сохранить и закрыть', чтобы применить их.")


    def clear_classifier_cache(self):
        if self.web_classifier and hasattr(self.web_classifier, 'cache_manager'):
            reply = QMessageBox.question(self, 'Очистка кэша',
                                         'Вы уверены, что хотите очистить кэш классификатора? Это действие необратимо.',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.web_classifier.cache_manager.clear_cache()
                logger.info('Кэш классификатора очищен из окна настроек.')
                QMessageBox.information(self, "Кэш очищен", "Кэш классификатора был успешно очищен.")
        else:
            logger.warning('Экземпляр WebClassifier не передан в окно настроек, не могу очистить кэш.')
            QMessageBox.warning(self, "Ошибка", "Не удалось получить доступ к менеджеру кэша.")

    def add_to_list(self, list_widget, line_edit_widget, is_file): # Added line_edit_widget
        text = line_edit_widget.text().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка ввода", "Имя не может быть пустым.")
            return
        # Проверка на недопустимые символы для имен файлов/папок (упрощенная)
        if any(char in text for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
            QMessageBox.warning(self, "Ошибка ввода", f"Имя {'файла' if is_file else 'папки'} содержит недопустимые символы.")
            return
        if is_file and '.' not in text: # Простая проверка на расширение для файла
             QMessageBox.warning(self, "Ошибка ввода", "Имя файла должно содержать расширение (например, 'имя.txt').")
             return

        if not list_widget.findItems(text, Qt.MatchExactly):
            list_widget.addItem(text)
            line_edit_widget.clear()
        else:
            QMessageBox.information(self, "Информация", "Такой элемент уже есть в списке.")


    def remove_from_list(self, list_widget):
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "Информация", "Не выбраны элементы для удаления.")
            return
        for item in selected_items:
            list_widget.takeItem(list_widget.row(item))

    def populate_list_widget(self, list_widget, items):
        list_widget.clear()
        if items:
            list_widget.addItems(items)

    def get_list_widget_items(self, list_widget):
        return [list_widget.item(i).text() for i in range(list_widget.count())]
