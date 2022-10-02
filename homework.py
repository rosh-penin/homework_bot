import logging
import os
import time

from dotenv import load_dotenv
import requests
import telegram

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YA_P_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ERROR_COUNT_LIMIT = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(
    logging.Formatter('%(asctime)s %(levelname)s %(message)s')
)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

cache = {}
errors = {}


def cache_errors(message):
    """
    Put errors in dict with counter.
    Returns True if error occurs first time or error counter overfilled.
    """
    if message not in errors:
        errors[message] = 1
        logger.info('error was added to cache and sent to telegram')
        return True

    errors[message] += 1
    if errors[message] >= ERROR_COUNT_LIMIT:
        del errors[message]


def send_message(bot, message):
    """Send message to bot."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'sent message:\n{message}')
    except telegram.error.TelegramError as error:
        logger.error(f'error when sending message:\n{error}')
        # Why raising error if there is no except catching?
    except Exception as error:
        logger.error(f'something else go wrong in send_message: {error}')


def get_api_answer(current_timestamp):
    """Get JSON from API and return it as a python dict."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, params, headers=HEADERS)
    except Exception as error:
        logger.error(f'error getting ENDPOINT:\n{error}')
        raise Exception('get_api func broke')

    if response.status_code != 200:
        raise Exception(
            f'response status code not 200 but {response.status_code}'
        )

    return response.json()


def check_response(response):
    """If JSON correct returns list of homeworks."""
    if not isinstance(response, dict):
        logger.error('response is not dict')
        raise TypeError('response is not dict')
    if 'homeworks' not in response:
        logger.error('homework not in response')
        raise KeyError('homework not in response')
    if not isinstance(response['homeworks'], list):
        logger.error('homework is not list')
        raise TypeError('homework is not list')

    return response.get('homeworks')


def parse_status(homework):
    """
    Compare current homework status with cache.
    If there is a difference - return message.
    """
    for key in ('homework_name', 'status'):
        if key not in homework:
            raise KeyError('There is no correct keys in homework')

    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception('status is different')

    verdict = HOMEWORK_VERDICTS.get(homework_status)
    if homework_name not in cache:
        logger.info('adding new homework to cache')

    if cache.get(homework_name) != homework_status:
        cache[homework_name] = homework_status
        logger.info(f'new status for {homework_name} = {homework_status}')

        return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Check that tokens exists. If not - stop programm."""
    if all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):

        return True
    logger.critical('TOKEN NOT FOUND. ALARM.')


def main():
    """Основная логика работы бота."""
    loop = check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while loop:
        try:
            logger.debug(f'new iteration on {current_timestamp}')
            response_from_api = get_api_answer(current_timestamp)
            current_timestamp = response_from_api.get('current_date')
            response = check_response(response_from_api)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'error in main():\n{current_timestamp}\n{error}')
            if cache_errors(message):
                send_message(bot, message)
        else:
            for homework in response:
                try:
                    message = parse_status(homework)
                except Exception as error:
                    logger.error(f'Error while parsing message:{error}')
                else:
                    if message:
                        send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
