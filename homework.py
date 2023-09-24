from http import HTTPStatus
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

RETRY_PERIOD = 60 * 10
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
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(
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
    return all([PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN])


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        LOGGER.debug(f'Сообщение отправлено: {message}.')
    except telegram.TelegramError as telegram_error:
        LOGGER.error(f'Сообщение не отправлено: {telegram_error}.')


def get_api_answer(timestamp):
    """Получаем ответ от API Практикум."""
    timestamp = int(time.time())
    payload = {'from_date': timestamp}
    req_params = dict(url=ENDPOINT, headers=HEADERS, params=payload)
    try:
        homework_statuses = requests.get(**req_params)
    except Exception as error:
        LOGGER.error(f'Нет ответа от эндпоинта: {error}.')
        raise ApiAnswerError
    if homework_statuses.status_code != HTTPStatus.OK:
        LOGGER.error(f'Эндпоинт {ENDPOINT} недоступен.'
                     f' Код ответа: {homework_statuses.status_code}.')
        raise ResponseStatusNot200
    try:
        return homework_statuses.json()
    except Exception as error:
        message = f'Ошибка преобразования к формату json: {error}.'
        LOGGER.error(message)
        raise ApiAnswerError(message)


def parse_status(homework):
    """Анализируем статус."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_name or not homework_status:
        LOGGER.error('Ключ недоступен.')
        raise KeyError
    if homework_status not in HOMEWORK_VERDICTS:
        LOGGER.error('Статус домашки не найден в базе статусов.')
        raise HomeworkStatusError
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_response(response):
    """Проверяем данные."""
    if type(response) != dict:
        message = f'Некорректный тип данных. Тип данных: {type(response)}.'
        LOGGER.error(message)
        raise TypeError
    if 'homeworks' not in response:
        message = 'Ключа homeworks нет в ответе API.'
        LOGGER.error('Ключа homeworks нет в ответе API.')
        raise ResponseNoHomeworksKey
    homework_list = response['homeworks']
    if type(homework_list) != list:
        message = (f'Некорректный тип данных. '
                   f'Тип данных: {type(homework_list)}.')
        LOGGER.error(message)
        raise TypeError
    return homework_list


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        LOGGER.critical(
            'Отсутствуют необходимые переменные окружения. '
            'Работа программы завершена.'
        )
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    new_status = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if len(homework) != 0:
                if new_status != homework[0]['status']:
                    message = parse_status(homework[0])
                    send_message(bot, message)
                    new_status = homework[0]['status']
                else:
                    LOGGER.info('Изменений нет.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            LOGGER.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
