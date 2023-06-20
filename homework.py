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
    token_status = True
    for token in TOKEN_NAMES:
        if not globals().get(token):
            token_status = False
            logging.critical(f'{token} недоступен')
    return token_status


def send_message(bot, message):
    """Отправка сообщений в Telegramю."""
    logging.debug('Начало отправки сообщения')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено')
    except telegram.error.TelegramError:
        logger.error('Ошибка при отправке сообщения')


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
    else:
        if hw_answer.status_code != 200:
            error_message = 'Статус страницы {hw_answer.status_code}'
            raise AssertionError(error_message)
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
        logging.error('Отсутствие ожидаемых ключей в ответе API')
        raise KeyError('Отсутствие ожидаемых ключей в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        logging.error('Неожиданный статус домашней работы')
        raise SystemError('Неожиданный статус домашней работы')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if homeworks := response['homeworks']:
                hw_status = parse_status(homeworks[0])
                send_message(bot, hw_status)
                continue
            logging.debug('Статус hw не изменился')
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        stream=sys.stdout,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    logger = logging.getLogger(__name__)
    main()
