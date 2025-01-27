import logging
import os
import pickle
import random
import re
import time

import requests
from bs4 import BeautifulSoup

# Constants
DEFAULT_ZONES = [
    "belgrano-r", "chacarita", "coghlan", "colegiales", "nunez", "palermo", "palermo-chico",
    "palermo-hollywood", "palermo-soho", "paternal", "saavedra", "villa-crespo",
    "villa-ortuzar", "villa-urquiza"
]
DEFAULT_KINDS = ['casas', 'ph']
DEFAULT_TERMS = ['parrilla']
SEEN_FILE = './seen_ids_ML.pkl'
FIRST_RUN_FILE = './first_run_flag.txt'

# Configurable filters
MAX_TOTAL_PRICE = 1400000
MIN_TOTAL_PRICE = 700000
MIN_AMBIENTES = 3
MIN_BAÑOS = 2
MIN_SUPERFICIE_CUBIERTA = 60

# Logging configuration
logging.basicConfig(
    level="INFO",
    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger('MercadoCrawler')


# MercadoCrawler Class
class MercadoCrawler:
    BASE_URL = 'https://inmuebles.mercadolibre.com.ar/{kind}/alquiler/capital-federal/{zone}/{term}_PriceRange_{min_price}-{max_price}_NoIndex_True'

    def __init__(self, zones=None, kinds=None, terms=None):
        """Initialize the MercadoCrawler"""
        self.zones = zones or DEFAULT_ZONES
        self.kinds = kinds or DEFAULT_KINDS
        self.terms = terms or DEFAULT_TERMS
        try:
            self.all_found = self.load_seen_file()
        except FileNotFoundError:
            self.all_found = {}

    def query(self, zone, kind, term):
        url = self.BASE_URL.format(
            zone=zone, kind=kind, term=term, max_price=MAX_TOTAL_PRICE, min_price=MIN_TOTAL_PRICE
        )
        logger.info(f'Query URL: {url}')
        page = requests.get(url)
        soup = BeautifulSoup(page.content, 'html.parser')
        return soup.findAll('div', 'ui-search-result__wrapper')

    @staticmethod
    def get_tracking_id(url):
        return re.findall('(MLA[^#]+)', url)[0]

    def get_details(self, item):
        details = {}
        try:
            # Basic details
            price = item.find('span', class_='andes-money-amount__fraction').get_text()
            details['price'] = int(price.replace('.', ''))
            details['attrs'] = [attr.get_text() for attr in item.find_all('li', class_='poly-attributes-list__item')] or []
            details['url'] = item.find('a', class_='poly-component__title')['href']
            details['id'] = self.get_tracking_id(details['url'])
            details['direccion'] = item.find('span', class_='poly-component__location').get_text()

            # Details from the secondary page
            detail_page = requests.get(details['url'])
            soup_details = BeautifulSoup(detail_page.content, 'html.parser')
            specs_items = soup_details.find_all('tr', {'class': 'andes-table__row'})
            for spec in specs_items:
                header = spec.find('th').get_text(strip=True)
                value = spec.find('td').get_text(strip=True)
                details[header] = value

            # Ambientes handling
            if 'Ambientes' in details:
                details['Ambientes'] = int(re.findall(r'\d+', details['Ambientes'])[0])
            else:
                for attr in details['attrs']:
                    if 'ambs' in attr.lower():
                        details['Ambientes'] = int(re.findall(r'\d+', attr)[0])
                        break
                else:
                    details['Ambientes'] = 0

            # Baños handling
            if 'Baños' in details:
                details['Baños'] = int(re.findall(r'\d+', details['Baños'])[0])
            else:
                for attr in details['attrs']:
                    if 'baño' in attr.lower():
                        details['Baños'] = int(re.findall(r'\d+', attr)[0])
                        break
                else:
                    details['Baños'] = 0

            # Superficie Cubierta handling
            if 'Superficie Cubierta' in details:
                details['Superficie Cubierta'] = int(re.findall(r'\d+', details['Superficie Cubierta'])[0])
            else:
                for attr in details['attrs']:
                    if 'cubiertos' in attr.lower():
                        details['Superficie Cubierta'] = int(re.findall(r'\d+', attr)[0])
                        break
                else:
                    details['Superficie Cubierta'] = 0

            # Expensas and total price
            expensas_raw = details.get('Expensas', '0')
            details['Expensas'] = float(re.findall(r'[\d\.]+', expensas_raw.replace('.', ''))[0]) if expensas_raw else 0.0
            details['total_price'] = details['price'] + details['Expensas']
        except Exception as e:
            details['error'] = f"Error extracting details: {e}"
        return details

    @staticmethod
    def load_seen_file():
        with open(SEEN_FILE, 'rb') as f:
            return pickle.load(f)

    def save_new_items(self, new_items):
        self.all_found.update(new_items)
        with open(SEEN_FILE, 'wb') as f:
            pickle.dump(self.all_found, f)

    def filters_passed(self, details):
        if details['total_price'] > MAX_TOTAL_PRICE or details['total_price'] < MIN_TOTAL_PRICE:
            logger.info('FALSE: Price outside allowed range')
            return False
        if details.get('Ambientes', 0) < MIN_AMBIENTES:
            logger.info(f'FALSE: Insufficient Ambientes ({details.get("Ambientes", 0)})')
            return False
        if details.get('Baños', 0) < MIN_BAÑOS:
            logger.info(f'FALSE: Insufficient Baños ({details.get("Baños", 0)})')
            return False
        if details.get('Superficie Cubierta', 0) < MIN_SUPERFICIE_CUBIERTA:
            logger.info(f'FALSE: Insufficient Superficie Cubierta ({details.get("Superficie Cubierta", 0)})')
            return False
        return True

    def run_search(self):
        found_items = []
        for kind in self.kinds:
            for zone in self.zones:
                for term in self.terms:
                    partial_found_items = self.query(zone, kind, term)
                    found_items.extend(partial_found_items)
                    time.sleep(random.uniform(1, 10))
        new_items = {}
        for item in found_items:
            href = item.find('a', class_='poly-component__title')['href']
            if self.get_tracking_id(href) in self.all_found:
                continue
            details = self.get_details(item)
            if self.filters_passed(details):
                new_items[details['id']] = details
        self.save_new_items(new_items)
        logger.info(f'Total new items: {len(new_items)}')
        return new_items


# Telegram Bot Functions
def telegram_bot_sendtext(bot_message, bot_chatID=None):
    bot_token = os.environ['TELEGRAM_BOT_TOKEN']
    logger.info(bot_message)
    send_text = f'https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={bot_chatID}&parse_mode=Markdown&text={bot_message}'
    response = requests.get(send_text)
    return response.json()

def telegram_test_ping(bot_chatID=None):
    bot_token = os.environ['TELEGRAM_BOT_TOKEN']
    send_text = f'https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={bot_chatID}&parse_mode=Markdown&text=Cron:**Running**'
    requests.get(send_text)


def send_first_run_message():
    """Send a Telegram message on the first run with search parameters."""
    if not os.path.exists(FIRST_RUN_FILE):
        # Formatear mensaje con parámetros de búsqueda
        search_params = (
            f"*🚀 Búsqueda inicial iniciada*\n\n"
            f"- *Zonas:* {', '.join(DEFAULT_ZONES)}\n"
            f"- *Tipos de propiedades:* {', '.join(DEFAULT_KINDS)}\n"
            f"- *Términos de búsqueda:* {', '.join(DEFAULT_TERMS)}\n"
            f"- *Precio mínimo:* {MIN_TOTAL_PRICE}\n"
            f"- *Precio máximo:* {MAX_TOTAL_PRICE}\n"
            f"- *Ambientes mínimos:* {MIN_AMBIENTES}\n"
            f"- *Baños mínimos:* {MIN_BAÑOS}\n"
            f"- *Superficie cubierta mínima:* {MIN_SUPERFICIE_CUBIERTA} m²\n"
        )

        # Enviar mensaje por Telegram
        bot_chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        if bot_chat_id:
            telegram_bot_sendtext(search_params, bot_chatID=bot_chat_id)

        # Crear archivo de marca de primera ejecución
        with open(FIRST_RUN_FILE, 'w') as f:
            f.write('First run completed')


# Main Execution
if __name__ == "__main__":
    send_first_run_message()
    mlc = MercadoCrawler()
    if os.environ.get("SEND_CRON_TEST") == 'True':
        telegram_test_ping(bot_chatID=os.environ['TELEGRAM_CHAT_ID'])

    results = mlc.run_search()
    logger.info("Sending Telegram notifications")

    for ml_id, description in results.items():
        msg = ''
        for k, v in description.items():
            if k == 'id':
                continue
            if k == 'url':
                url_text = f'[inline URL]({v})\n'
            else:
                k = k.replace('_', ' ').title()
                v = str(v).replace('_', ' ')
                msg += f'*{k}:* {v} \n'
        msg += url_text
        telegram_bot_sendtext(msg, bot_chatID=os.environ['TELEGRAM_CHAT_ID'])
