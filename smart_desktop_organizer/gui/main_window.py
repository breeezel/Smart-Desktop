# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit, QHBoxLayout, QLabel
from PyQt5.QtCore import Qt
import logging

from .settings_window import SettingsWindow
from .dialogs import show_info_dialog

logger = logging.getLogger('SmartDesktopOrganizer')

class MainWindow(QMainWindow):
    web_classifier_instance = None # Class attribute to hold the instance

    def __init__(self, settings_manager, web_classifier_instance): # Added web_classifier_instance
        super().__init__()
        self.settings_manager = settings_manager
        self.web_classifier_instance = web_classifier_instance # Store the instance
        self.settings_window_instance = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Smart Desktop Organizer')
        self.setGeometry(300, 300, 600, 400)  # x, y, width, height

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout()

        # Панель с кнопками
        button_layout = QHBoxLayout()
        self.btn_check_desktop = QPushButton('Проверить рабочий стол')
        self.btn_check_desktop.clicked.connect(self.check_desktop_action)
        button_layout.addWidget(self.btn_check_desktop)

        self.btn_sort_desktop = QPushButton('Сортировать рабочий стол')
        self.btn_sort_desktop.clicked.connect(self.sort_desktop_action)
        button_layout.addWidget(self.btn_sort_desktop)

        self.btn_settings = QPushButton('Настройки')
        self.btn_settings.clicked.connect(self.open_settings_window)
        button_layout.addWidget(self.btn_settings)

        main_layout.addLayout(button_layout)

        # Статусное поле/поле логов
        self.status_label = QLabel('Статус:')
        main_layout.addWidget(self.status_label)
        self.status_text_edit = QTextEdit()
        self.status_text_edit.setReadOnly(True)
        self.status_text_edit.setText('Добро пожаловать в Smart Desktop Organizer!')
        main_layout.addWidget(self.status_text_edit)

        central_widget.setLayout(main_layout)
        logger.info('Главное окно инициализировано.')

    def update_status(self, message):
        self.status_text_edit.append(message)
        logger.info(f'Статус GUI обновлен: {message}')

    def check_desktop_action(self):
        message = 'Функция "Проверить рабочий стол" находится в разработке.'
        self.update_status(message)
        show_info_dialog(self, 'Информация', message)
        logger.info('Нажата кнопка "Проверить рабочий стол".')

    def sort_desktop_action(self):
        message = 'Функция "Сортировать рабочий стол" находится в разработке.'
        self.update_status(message)
        show_info_dialog(self, 'Информация', message)
        logger.info('Нажата кнопка "Сортировать рабочий стол".')

    def open_settings_window(self):
        if self.settings_window_instance is None or not self.settings_window_instance.isVisible():
            # Pass web_classifier_instance to SettingsWindow constructor
            self.settings_window_instance = SettingsWindow(
                self.settings_manager,
                self,
                web_classifier=self.web_classifier_instance
            )
            self.settings_window_instance.show()
        else:
            self.settings_window_instance.activateWindow()
        logger.info('Открыто окно настроек.')

    def closeEvent(self, event):
        logger.info('Главное окно закрывается.')
        if QApplication.instance(): # Check if QApplication instance exists
            QApplication.instance().quit()
        event.accept()
