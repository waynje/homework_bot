import logging
import os
import time

import requests

import telegram

from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='bot.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(
    logging.StreamHandler()
)


class HomeworkStatusError(Exception):
    """Исключение, если статуса домашки нет в базе статусов."""


class ResponseStatusNot200(Exception):
    """Исключение, когда API не выдает код 200."""


class ResponseNoHomeworksKey(Exception):
    """Исключение, если в ответе API нет ключа 'homeworks'."""


class ApiAnswerError(Exception):
    """Исключение ответа от API."""


def check_tokens():
    """Проверка токенов."""
    TOKEN_MESSAGE = 'Программа остановлена. Для работы программы требуется:'
    BOT_WORKING = True
    if PRACTICUM_TOKEN is None:
        BOT_WORKING = False
        logger.critical(f'{TOKEN_MESSAGE} PRACTICUM_TOKEN')
    if TELEGRAM_CHAT_ID is None:
        BOT_WORKING = False
        logger.critical(f'{TOKEN_MESSAGE} TELEGRAM_CHAT_ID')
    if TELEGRAM_TOKEN is None:
        BOT_WORKING = False
        logger.critical(f'{TOKEN_MESSAGE} TELEGRAM_TOKEN')
    return BOT_WORKING


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение отправлено: {message}.')
    except telegram.TelegramError as telegram_error:
        logger.error(f'Сообщение не отправлено: {telegram_error}.')


def get_api_answer(timestamp):
    """Получаем ответ от API Практикум."""
    timestamp = int(time.time())
    headers = HEADERS
    payload = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=headers,
            params=payload)
    except Exception as error:
        logger.error(f'Нет ответа от эндпоинта: {error}.')
        raise ApiAnswerError
    if homework_statuses.status_code != 200:
        logger.error(f'Эндпоинт {ENDPOINT} недоступен.'
                     f' Код ответа: {homework_statuses.status_code}.')
        raise ResponseStatusNot200
    try:
        return homework_statuses.json()
    except Exception as error:
        message = f'Ошибка преобразования к формату json: {error}'
        logger.error(message)
        raise ApiAnswerError(message)


def parse_status(homework):
    """Анализируем статус."""
    for i in ['homework_name', 'status']:
        if i not in homework:
            message = f'Ключ {i} недоступен.'
            logger.error(message)
            raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error('Статус домашки не найден в базе статусов.')
        raise HomeworkStatusError


def check_response(response):
    """Проверяем данные."""
    if type(response) != dict:
        message = f'Некорректный тип данных. Тип данных: {type(response)}.'
        logger.error(message)
        raise TypeError
    if 'homeworks' not in response:
        message = 'Ключа homeworks нет в ответе API.'
        logger.error('Ключа homeworks нет в ответе API.')
        raise ResponseNoHomeworksKey
    homework_list = response['homeworks']
    if type(homework_list) != list:
        message = (f'Некорректный тип данных. '
                   f'Тип данных: {type(homework_list)}.')
        logger.error(message)
        raise TypeError
    return homework_list


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    new_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if len(homework) == 0:
                logger.info('Статус не обновлен.')
            if new_status != homework[0]['status']:
                message = parse_status(homework[0])
                send_message(bot, message)
                new_status = homework[0]['status']
            else:
                logger.info('Изменений нет.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
