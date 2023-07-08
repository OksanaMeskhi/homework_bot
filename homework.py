import contextlib
import logging
import os
import sys
import time
from http import HTTPStatus


import requests
import telegram
from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKEN_NAMES = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
NO_TOKEN = 'Отсутствуют переменные окружения: {tokens}'

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности токенов."""
    no_token = [
        name for name in TOKEN_NAMES
        if name not in globals() or not globals()[name]
    ]
    if no_token:
        logging.critical(NO_TOKEN.format(tokens=no_token))
        sys.exit(1)


def send_message(bot, message):
    """Отправка сообщений в Telegramю."""
    logging.debug('Начало отправки сообщения')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug('Сообщение отправлено')


def get_api_answer(timestamp):
    """Запрос к API."""
    logging.debug('Отправка запроса и получение ответа API')
    params = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        hw_answer = requests.get(**params)
    except requests.RequestException as error:
        error_message = f'{ENDPOINT} недоступен: {error}'
        raise ConnectionError(error_message) from error
    if hw_answer.status_code != HTTPStatus:
        raise ValueError(f'Статус ответа {hw_answer.status_code}')
    return hw_answer.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    logging.debug('Проверка ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ответ не является словарем')
    if 'homeworks' not in response:
        raise KeyError('Ответ не содержит ключ homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks данные приходят не в виде списка')
    logging.debug('Проверка выполнена успешно')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус."""
    logging.debug('Проверка извлечения статуса')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API')
    homework_name = homework('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        error_detail = (
            f'Неожиданный статус {homework_status}')
        raise ValueError(error_detail)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    logging.debug('Инициализация бота')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.debug('Бот успешно инициализирован')
    timestamp = int(time.time())
    old_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            hw_date = check_response(response)
            if hw_date is not None:
                message = parse_status(hw_date[0])
                send_message(bot, message)
                timestamp = response.get('current_date', timestamp)

        except Exception as error:
            message = f'Сбой в работе программы {error}'
            logging.error(message)
            if old_message != message:
                with contextlib.suppress(Exception):
                    send_message(bot, old_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    main()
