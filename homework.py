import logging
import time

import telegram
import requests

from logging import StreamHandler

from dotenv import load_dotenv

from exceptions import MissingKey

load_dotenv()


PRACTICUM_TOKEN = 'AQAAAAA1QB8LAAYckQF-1QcA_UizqoP9amd1rZ8'
TELEGRAM_TOKEN = '2123906839:AAFVGLk5GZOQbcDW9xKORX-sVt3if5fcZ34'
TELEGRAM_CHAT_ID = 1045342333

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream='sys.stdout')
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправка сообщения о статусе работы в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logging.error('Ошибка при отправке сообщения в Telegram')
        raise Exception('Ошибка при отправке сообщения в Telegram')
    logging.info('Сообщение в Telegram отправлено успешно')


def get_api_answer(current_timestamp):
    """Делает запрос к API и, если ответ корректен, выводит его."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        logging.error('Ошибка при запросе к основному API')
        raise Exception('Ошибка при запросе к основному API')
    response = response.json()
    return response


def check_response(response):
    """Проверяет ответ API на корректность.
    если ответ корректен - выводит список домашних работ.
    """
    if 'error' in response:
        logging.error(f'{response: "error"}')
        raise Exception(f'{response: "error"}')
    if not isinstance(response['homeworks'], list):
        logging.error('homework is not list')
        raise TypeError('Домашка приходит не в виде списка')
    if not response['homeworks']:
        logging.error('No homework in the list')
        raise MissingKey('Домашки нет в списке')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус конкретной домашки из информации о ней."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if not isinstance(homework, dict):
        logging.error('Ответ вернул неверный тип данных')
        raise TypeError('Ответ вернул неверный тип данных')
    if 'homework_name' not in homework:
        logging.error('Отсутствует ключ "homework_name"')
        raise MissingKey('Отсутствует ключ "homework_name"')
    if 'status' not in homework:
        logging.error('Отсутствует ключ "status"')
        raise MissingKey('Отсутствует ключ "status"')
    if homework['status'] not in HOMEWORK_STATUSES.keys():
        logging.error('Неверное значение ключа "status"')
        raise ValueError('Неверное значение ключа "status"')
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{HOMEWORK_STATUSES[homework_status]}')


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    if TELEGRAM_TOKEN is None:
        logging.critical('Отстутствует переменная '
                         'окружения "TELEGRAM_TOKEN"')
        return False
    if TELEGRAM_CHAT_ID is None:
        logging.critical('Отстутствует переменная окружения '
                         '"TELEGRAM_CHAT_ID"')
        return False
    if PRACTICUM_TOKEN is None:
        logging.critical('Отстутствует переменная окружения '
                         '"PRACTICUM_TOKEN"')
        return False
    if HOMEWORK_STATUSES is None:
        logging.critical('Отстутствует переменная окружения '
                         '"HOMEWORK_STATUSES"')
        return False
    return True


def main():
    """Основная логика работы бота."""
    error_set = ['test error']
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            check_response(response)
            message = parse_status(check_response(response)[0])
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'{message}')
            if str(error) != str(error_set[-1]):
                error_set.append(str(error))
                send_message(bot, message)
                time.sleep(RETRY_TIME)
            else:
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
