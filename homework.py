import logging
import os
import sys
import time


import requests
import telegram
from dotenv import load_dotenv


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKEN_NAMES = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

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
    missing_tokens = []
    for token in TOKEN_NAMES:
        if not globals().get(token):
            missing_tokens = False
            missing_tokens.append(missing_tokens)
            logging.critical(f'{token} недоступен')
        return missing_tokens
    if not check_tokens():
        logging.critical('Отсутствие обязательных переменных окружения')
        sys.exit('Отсутствие обязательных переменных окружения')


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
        raise RequestExceptionError(error_message)
    if hw_answer.status_code != 200:
        raise ValueError(f'Статус страницы {hw_answer.status_code}')
    return hw_answer.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    logging.debug('Проверка ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ответ не является словарем')
    if 'homeworks' not in response:
        raise TypeError('Ответ не содержит ключ homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('homeworks данные приходят не в виде списка')
    logging.debug('Проверка выполнена успешно')


def parse_status(homework):
    """Извлекает статус."""
    logging.debug('Проверка извлечения статуса')
    if 'homework_name' not in homework:
        raise KeyError('Отсутствие ожидаемых ключей в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неожиданный статус домашней работы {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    check_tokens
    timestamp = int(time.time())
    old_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework_date = check_response(response)
            if len(homework_date) == 0:
                logging.debug('Статус не изменился')
            else:
                message = parse_status(homework_date[0])
                send_message(bot, message)
                timestamp = response.get('current_date', timestamp)
            old_message = ''
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if old_message != message:
                send_message(bot, message)
                old_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    main()
