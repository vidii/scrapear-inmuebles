import logging
import os
import pickle
import random
import re
import time

import requests
from bs4 import BeautifulSoup

DEFAULT_ZONES = [
    "barrio-norte",
    "belgrano",
    "caballito",
    "recoleta",
    "belgrano-c",
    "belgrano-chico",
    "botanico",
    "agronomia",
    "chacarita",
    "coghlan",
    "colegiales",
    "nunez",
    "palermo",
    "paternal",
    "parque-chas",
    "parque-chacabuco",
    "parque-centenario",
    "saavedra",
    "santa-rita",
    "villa-crespo",
    "villa-del-parque",
    "villa-devoto",
    "villa-gral-mitre",
    "villa-ortuzar",
    "villa-urquiza"
]

DEFAULT_KINDS = ['ph', 'departamentos']

DEFAULT_TERMS = ['patio', 'terraza']

seen_file = './seen_ids_ML.pkl'

logging.basicConfig(level="INFO",
                    format='%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    )
logger = logging.getLogger('MercadoCrawler')


class MercadoCrawler:
    BASE_URL = 'https://inmuebles.mercadolibre.com.ar/{kind}/alquiler/capital-federal/{zone}/{term}_PriceRange_{min_price}-{max_price}_NoIndex_True'

    def __init__(self, zones=None, kinds=None, terms=None, min_total_price=50000,max_total_price=150000, min_ambientes=3):
        """Search mercado libre house listings"""
        if terms is None:
            terms = DEFAULT_TERMS
        if kinds is None:
            kinds = DEFAULT_KINDS
        if zones is None:
            zones = DEFAULT_ZONES
        self.zones = zones
        self.kinds = kinds
        self.terms = terms
        self.max_total_price = max_total_price
        self.min_total_price = min_total_price
        self.min_ambientes = min_ambientes
        try:
            self.all_found = self.load_seen_file()
        except FileNotFoundError:
            self.all_found = {}

    def query(self, zone, kind, term):
        url = self.BASE_URL.format(zone=zone, kind=kind, term=term, max_price=self.max_total_price, min_price=self.min_total_price)
        logger.info('Query url: ' + url)
        page = requests.get(url)
        soup = BeautifulSoup(page.content, 'html.parser')
        found_items = soup.findAll('a', 'ui-search-result__content')
        return found_items

    @staticmethod
    def get_tracking_id(url):
        return re.findall('(MLA[^#]+)', url)[0]

    def get_details(self, item):
        details = {}
        price = item.find('span', {"class": "price-tag-fraction"}).get_text()
        details['price'] = int(price.replace('.', ''))
        details['attrs'] = item.find('div', {'class': 'ui-search-item__group--attributes'}).get_text().strip()
        details['url'] = item.get('href')
        details['id'] = self.get_tracking_id(details['url']) # TODO: fix quick hack because ids are no longer present
        details['direccion'] = item.find('div', {'class': 'ui-search-item__group--location'}).get_text().strip()
        detail_page = requests.get(details['url'])
        soup_details = BeautifulSoup(detail_page.content, 'html.parser')
        specs_items = soup_details.find_all('tr', {'class': 'andes-table__row'})
        for spec in specs_items:
            header = spec.find('th').get_text()
            value = spec.find('td').get_text()
            details[header] = value
        try:
            details['Expensas'] = float(re.findall('[\d\.]+', details['Expensas'])[0])
            details['total_price'] = details['price'] + details['Expensas']
        except KeyError as e:
            details['total_price'] = details['price']
        return details

    @staticmethod
    def load_seen_file():
        with open(seen_file, 'rb') as f:
            all_found = pickle.load(f)
        return all_found

    def save_new_items(self, new_items):
        self.all_found.update(new_items)
        with open(seen_file, 'wb') as f:
            pickle.dump(self.all_found, f)

    def filters_passed(self, details):
        if details['total_price'] > self.max_total_price:
            logger.info('FALSE: Supera precio total al incluir expensas')
            return False
        if 'Ambientes' in details and int(details['Ambientes']) < self.min_ambientes:
            logger.info('FALSE: Cantidad de ambientes insuficientes')
            return False
        return True

    def make_summary(self, details):
        return details

    def run_search(self):
        found_items = []
        for kind in self.kinds:
            logger.info(f'Searching {kind}')
            for zone in self.zones:
                logger.info(f'\t Searching {zone}')
                for term in self.terms:
                    logger.info(f'\t \t Searching {term}')
                    partial_found_items = self.query(zone, kind, term)
                    logger.info(f'\t \t Found a total of {len(partial_found_items)}')
                    found_items += partial_found_items
                    random_time = random.random() * 10
                    logger.info(f'Sleeping for {random_time}')
                    time.sleep(random_time)
        logger.info(f'     ==== Total found items: {len(found_items)}  ====')
        new_items = {}
        for item in found_items:
            if self.get_tracking_id(item.get('href')) in self.all_found.keys():
                continue
            details = self.get_details(item)
            if self.filters_passed(details):
                new_items[details['id']] = details
        self.save_new_items(new_items)
        logger.info(f'     ==== Total new items: {len(new_items)}  ====')
        return new_items


def telegram_bot_sendtext(bot_message, bot_chatID=None):
    bot_token = os.environ['TELEGRAM_BOT_TOKEN']
    logger.info(bot_message)
    send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message

    response = requests.get(send_text)

    return response.json()


def telegram_test_ping(bot_chatID=None):
    bot_token = os.environ['TELEGRAM_BOT_TOKEN']
    logger.info("Sending cron ping to telegram")
    send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=Cron:**Running**'
    response = requests.get(send_text)



mlc = MercadoCrawler()
if "SEND_CRON_TEST" in os.environ:
    if (os.environ['SEND_CRON_TEST'] == 'True'):
        telegram_test_ping(bot_chatID=os.environ['TELEGRAM_CHAT_ID'])

results = mlc.run_search()
logger.info("Sending telegrams")



for ml_id, description in results.items():
    msg = ''
    for k, v in description.items():
        if 'id' in k:
            continue
        if 'url' in k:
            url_text = f'[inline URL]({v})\n'
        else:
            k = k.replace('_', ' ').replace('*', ' ').title()
            v = str(v).replace('_', ' ').replace('*', ' ')
            text = f'*{k}:* {v} \n'
            msg += text
    msg += url_text
    test = telegram_bot_sendtext(msg, bot_chatID=os.environ['TELEGRAM_CHAT_ID'])
