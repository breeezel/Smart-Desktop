# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import QMessageBox
import logging

logger = logging.getLogger('SmartDesktopOrganizer')

def show_info_dialog(parent, title, message):
    # Показывает простое информационное сообщение
    logger.debug(f'Показ информационного диалога: Title="{title}", Message="{message}"')
    QMessageBox.information(parent, title, message, QMessageBox.Ok)

def show_confirmation_dialog(parent, title, message):
    # Показывает диалог подтверждения с кнопками Да/Нет
    logger.debug(f'Показ диалога подтверждения: Title="{title}", Message="{message}"')
    reply = QMessageBox.question(parent, title, message,
                                 QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return reply == QMessageBox.Yes
