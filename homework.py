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
errors = []


def send_errors_but_not_spam(bot, message):
    if message not in errors:
        # Now each error should be sent only once.
        errors.append(message)
        bot.send_message(TELEGRAM_CHAT_ID, message)


def send_message(bot, message):
    """Send message to bot."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'sent message:\n{message}')
    except telegram.error.TelegramError as error:
        logger.error(f'error when sending message:\n{error}')
        raise Exception('send message error')


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
        raise Exception('homework not in response')
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
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception('status is different')
    verdict = HOMEWORK_VERDICTS.get(homework_status)

    if homework_name not in cache:
        logger.info('adding new homework to cache')

    if cache.get(homework_name) != homework_status:
        cache[homework_name] = homework_status
        logger.info(f'new status for {homework_name} = {homework_status}')
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'

    return


def check_tokens():
    """Check that tokens exists. If not - stop programm."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        logger.critical('TOKEN NOT FOUND. ALARM.')
        # Wanted to just raise error and stop programm there.
        # But pytest think differently.
        return False

    return True


def main():
    """Основная логика работы бота."""
    loop = check_tokens() # Should i just put it in loop conditions?
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while loop is True:
        try:
            logger.debug(f'new iteration on {current_timestamp}')
            response_from_api = get_api_answer(current_timestamp)
            current_timestamp = response_from_api.get('current_date')
            response = check_response(response_from_api)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'error in main():\n{current_timestamp}\n{error}')
            send_errors_but_not_spam(bot, message)
        else:
            for homework in response:
                message = parse_status(homework)
                if message is not None:
                    send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
