# -*- coding: utf-8 -*-
import logging
import time
import os
import re

# Попытка импортировать requests и BeautifulSoup, если они понадобятся для реального гугления
try:
    import requests
    from bs4 import BeautifulSoup
    WEB_TOOLS_AVAILABLE = True
except ImportError:
    logger = logging.getLogger('SmartDesktopOrganizer') # Need logger for the warning
    logger.warning("requests and/or BeautifulSoup4 not found. Real web searching will be unavailable.")
    WEB_TOOLS_AVAILABLE = False

from .cache_manager import CacheManager

logger = logging.getLogger('SmartDesktopOrganizer')

class WebClassifier:
    # Define default keywords as class attributes for easier reference/reset if needed
    game_keywords_default = ['game', 'игра', 'gaming', 'play', 'gamer', 'steam', 'epic games', 'origin', 'uplay', 'gog', 'геймплей', 'gameplay', 'обзор игры', 'review game']
    program_keywords_default = ['software', 'программа', 'tool', 'utility', 'app', 'application', 'редактор', 'viewer', 'player', 'development', 'ide', 'office', 'скачать программу', 'download software', 'official site', 'официальный сайт']

    def __init__(self, settings_manager=None, cache_file_path=None): # Added cache_file_path
        self.settings_manager = settings_manager
        # Pass cache_file_path to CacheManager, if provided
        self.cache_manager = CacheManager(
            settings_manager=self.settings_manager,
            cache_file=cache_file_path # Pass it here (will be None if not provided, then CacheManager uses its default)
        )
        self.enable_googling = True
        if self.settings_manager:
            self.enable_googling = self.settings_manager.get_setting('enable_googling', True)

        # Ключевые слова для определения категории (instance attributes)
        self.game_keywords = list(self.game_keywords_default)
        self.program_keywords = list(self.program_keywords_default)


    def _clean_name(self, name):
        name_lower = name.lower()
        name_lower = re.sub(r'\s*-\s*(shortcut|ярлык)$', '', name_lower)
        name_lower = re.sub(r'\.(exe|lnk)$', '', name_lower)
        name_lower = re.sub(r'\s*v\d+(\.\d+)*', '', name_lower)
        name_lower = re.sub(r'\s*\(\s*(x86|x64|32-bit|64-bit)\s*\)', '', name_lower)
        name_lower = name_lower.rstrip('_') # Remove trailing underscores
        return name_lower.strip()

    def _mock_search_google(self, query):
        logger.info(f'Имитация Google поиска для запроса: {query}')
        time.sleep(0.05)
        query_lower = query.lower()
        if any(kw in query_lower for kw in ['steam', 'doom', 'minecraft', 'witcher', 'cyberpunk', 'gta', 'csgo']):
            return 'Это популярная игра. Обзоры, геймплей, скачать игру.'
        if any(kw in query_lower for kw in ['photoshop', 'office', 'excel', 'word', 'vscode', 'pycharm', 'blender', 'autocad']):
            return 'Это известная программа для работы. Официальный сайт, скачать программу.'
        if 'game' in query_lower or 'игра' in query_lower:
            if not ('software' in query_lower or 'программа' in query_lower or 'engine' in query_lower):
                 return 'Результаты поиска указывают, что это может быть игра.'
        if 'software' in query_lower or 'программа' in query_lower or 'utility' in query_lower or 'tool' in query_lower:
            return 'Результаты поиска указывают, что это может быть программа или утилита.'
        if re.search(r'\b(simulator|wars|craft|battle|age of|empire|fantasy|legends|saga|chronicles)\b', query_lower):
            return 'Похоже на название игры, судя по ключевым словам.'
        return 'Не удалось найти точную информацию по запросу. Попробуйте другой запрос.'

    def _parse_search_results(self, text_content):
        text_lower = text_content.lower()
        # Use regex word boundaries for more precise keyword matching
        game_score = sum(1 for kw in self.game_keywords if re.search(r'\b' + re.escape(kw) + r'\b', text_lower))
        program_score = sum(1 for kw in self.program_keywords if re.search(r'\b' + re.escape(kw) + r'\b', text_lower))

        logger.debug(f'Анализ результатов: game_score={game_score}, program_score={program_score} для текста: "{text_lower[:100]}..."')

        if game_score > program_score and game_score > 0:
            return 'game'
        if program_score > game_score and program_score > 0:
            return 'program'
        if 'игровой движок' in text_lower or 'game engine' in text_lower or 'unreal engine' in text_lower or 'unity' in text_lower:
            return 'program'
        return 'unknown'

    def classify_item(self, item_name, item_path=None):
        if not self.enable_googling:
            logger.info('Гугление отключено в настройках. Классификация не будет выполнена.')
            return 'disabled'

        cleaned_name = self._clean_name(item_name)
        if not cleaned_name:
            logger.warning(f'Не удалось получить чистое имя для {item_name}, классификация невозможна.')
            return 'unknown'

        cached_category = self.cache_manager.get(cleaned_name)
        if cached_category:
            logger.info(f'Категория для "{cleaned_name}" найдена в кэше: {cached_category}')
            return cached_category

        query1 = f'"{cleaned_name}" what is it game software program application utility tool official website download category type'
        search_results_text1 = self._mock_search_google(query1)
        category1 = self._parse_search_results(search_results_text1)

        if category1 != 'unknown':
            self.cache_manager.set(cleaned_name, category1)
            logger.info(f'"{cleaned_name}" классифицирован как "{category1}" по имени файла.')
            return category1

        if item_path:
            parent_folder_name = os.path.basename(os.path.dirname(item_path))
            if parent_folder_name and parent_folder_name.lower() not in ['desktop', 'common desktop', 'public desktop', 'c', 'd', 'windows', 'program files', 'program files (x86)'] and len(parent_folder_name) > 2 :
                cleaned_parent_name = self._clean_name(parent_folder_name)
                if cleaned_parent_name:
                    cache_key_parent = cleaned_parent_name + '_folder_hint'
                    cached_parent_category = self.cache_manager.get(cache_key_parent)
                    if cached_parent_category:
                        logger.info(f'Категория для "{cleaned_name}" найдена в кэше по родительской папке "{cleaned_parent_name}": {cached_parent_category}')
                        self.cache_manager.set(cleaned_name, cached_parent_category)
                        return cached_parent_category

                    query2 = f'"{cleaned_parent_name}" folder content category game software program application utility tool'
                    search_results_text2 = self._mock_search_google(query2)
                    category2 = self._parse_search_results(search_results_text2)

                    if category2 != 'unknown':
                        self.cache_manager.set(cache_key_parent, category2)
                        self.cache_manager.set(cleaned_name, category2)
                        logger.info(f'"{cleaned_name}" классифицирован как "{category2}" по родительской папке "{cleaned_parent_name}".')
                        return category2

        logger.info(f'Не удалось классифицировать "{cleaned_name}". Помечен как "unknown".')
        self.cache_manager.set(cleaned_name, 'unknown')
        return 'unknown'
