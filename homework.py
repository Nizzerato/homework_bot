import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (ErrorInResponse, WrongResponseCode, MissingKey,
                        SendMessageError)

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

SEND_MESSAGE_SUCCESSFUL = 'Сообщение {message} отправлено успешно'
SEND_MESSAGE_ERROR = ('Ошибка {error} при отправке сообщения '
                      '{message} в Telegram')
RESPONSE_ERROR = ('Запрос к сайту вернул ошибку {error}.'
                  'API: {url}, токен авторизации: {headers}, '
                  'запрос с момента времени: {params}')
RESPONSE_CODE_ERROR = ('Значение кода возрата "{response}" '
                       'не соответствует требуемому - "200". API: {url}, '
                       'токен авторизации: {headers}, '
                       'запрос с момента времени: {params}')
NOT_LIST_TYPE = 'Домашка в виде "{type}" а не "list"'
NOT_IN_LIST = 'Ключа "homeworks" нет в списке "{response}"'
STATUS_UNEXPECTED = 'Неожиданное значение ключа "status": {status}'
STATUS_SUMMARY = ('Изменился статус проверки работы "{name}". '
                  '\n\n{verdict}')
TOKEN_ERROR = 'Отстутствует переменная окружения {name}'
RUNTIME_TOKEN_ERROR = 'Не хватает переменной окружения!'
RUNTIME_ERROR = 'Сбой в работе программы: {error}'
API_RESPONSE_ERROR = ('Сайт вернул ответ {response} '
                      'с ошибкой {error}. '
                      'API: {url}, токен авторизации: {headers}, '
                      'запрос с момента времени: {params}')


def send_message(bot, message):
    """Отправка сообщения о статусе работы в телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(SEND_MESSAGE_SUCCESSFUL.format(message=message))
        return True
    except Exception as error:
        logging.error(SendMessageError(
            SEND_MESSAGE_ERROR.format(error=error, message=message)))
        return False


def get_api_answer(timestamp):
    """Делает запрос к сайту и, если ответ корректен, возвращает его."""
    request_params = dict(url=ENDPOINT,
                          headers=HEADERS,
                          params={'from_date': timestamp})
    try:
        response = requests.get(**request_params)
    except requests.RequestException as error:
        raise ConnectionError(
            RESPONSE_ERROR.format(error=error, **request_params))
    if response.status_code != 200:
        raise WrongResponseCode(
            RESPONSE_CODE_ERROR.format(response=response.status_code,
                                       **request_params))
    response = response.json()
    error = ('error', 'code')
    if error in response:
        raise ErrorInResponse(
            API_RESPONSE_ERROR.format(response=response,
                                      **request_params))
    return response


def check_response(response):
    """Проверяет ответ сайта на корректность.
    если ответ корректен - возвращает список домашних работ.
    """
    if isinstance(response, dict):
        if 'homeworks' not in response:
            raise MissingKey(NOT_IN_LIST.format(response=response))
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            NOT_LIST_TYPE.format(type=type(response['homeworks'])))
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус конкретной домашки из информации о ней."""
    name = homework['homework_name']
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(STATUS_UNEXPECTED.format(status=status))
    return STATUS_SUMMARY.format(name=name,
                                 verdict=VERDICTS[status])


def check_tokens():
    """Проверяет доступность необходимых переменных окружения."""
    for name in TOKENS:
        if globals()[name] is not None:
            return True
        logging.critical(TOKEN_ERROR.format(name=name))
    return False


def main():
    """Основная логика работы бота."""
    current_error = set()
    if not check_tokens():
        logging.critical(RUNTIME_TOKEN_ERROR)
        raise KeyError(RUNTIME_TOKEN_ERROR)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            if [message, homework['id']] not in current_error:
                if send_message(bot, message):
                    timestamp = response.get(
                        'current_date',
                        timestamp
                    )
                    current_error.update([message, homework['id']])
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = RUNTIME_ERROR.format(error=error)
            if message in current_error:
                logging.error(message, exc_info=True)
            else:
                if send_message(bot, message) is True:
                    current_error.add(message)
            time.sleep(120)


if __name__ == '__main__':
    LOG_FILE = __file__ + '.log'
    logging.basicConfig(
        handlers=[logging.FileHandler(LOG_FILE),
                  logging.StreamHandler(sys.stdout)],
        level=logging.DEBUG,
        format=('%(asctime)s - %(funcName)s - %(lineno)d - '
                '%(levelname)s - %(message)s'))
    main()
