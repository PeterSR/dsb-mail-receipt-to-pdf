import pathlib
import argparse
import imaplib
import getpass
import pdfkit
import email, email.policy
import mailparser

from ttp import ttp
from dataclasses import dataclass
from price_parser import Price


@dataclass
class TravelInfo:
    purchase_type: str
    date: str
    source: str
    destination: str
    price: float


def generate_pdf_name(travel_info: TravelInfo) -> str:
    date = travel_info.date
    src = travel_info.source
    dst = travel_info.destination
    if travel_info.price < 50:
        type_ = "pladsbillet"
    elif travel_info.price > 3000:
        type_ = "pendlerkort"
    else:
        type_ = "billet"
    return f"DSB-{date}-{src}-{dst}-{type_}.pdf"


def find_by_key(seq, key):
    predicate = lambda x: isinstance(x, dict) and key in x
    d = next((x for x in seq if predicate(x)), None)
    if d is not None:
        return d.get(key)
    else:
        return None


def short_location(loc):
    if loc:
        if "københavn" in loc.lower():
            loc = "KBH"
        elif "odense" in loc.lower():
            loc = "ODN"
        elif "lyngby" in loc.lower():
            loc = "LBY"

    return loc


def month_to_number(month):
    map = {
        "januar": 1,
        "februar": 2,
        "marts": 3,
        "april": 4,
        "maj": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "december": 12,
    }

    return map.get(month.lower(), None)


def extract_travel_info(text: str) -> TravelInfo:
    date = None
    source = None
    destination = None
    price = None

    template_path = pathlib.Path(__file__).parent / "mail-template.txt"
    template = template_path.read_text()

    parser = ttp(data=text, template=template)
    parser.parse()
    res = parser.result()

    x = res[0][0]

    if "travel" in x:
        travel = x["travel"]

        source = travel["source"]
        destination = travel["destination"]

        day = travel["day"]
        month = travel["month"]
        year = travel["year"]

        purchase_type = "travel"

    elif "commuter_card" in x:
        card = x["commuter_card"]

        source = card["source"]
        destination = card["destination"]

        day = card["from_day"]
        month = card["from_month"]
        year = card["from_year"]

        purchase_type = "commuter-card"

    else:
        raise ValueError("Purchase is neither ticket nor commuter card.")

    price = x.get("price")
    if price:
        amount = price["amount"]
        curr = price["currency"]
        price = Price.fromstring(f"{amount} {curr}")
        price = price.amount_float

    if not all([source, destination, price, day, month, year, purchase_type]):
        raise ValueError("Could not determine all values")

    source = short_location(source)
    destination = short_location(destination)

    year = int(year)
    month = int(month_to_number(month))
    day = int(day)
    date = f"{year}-{month:02}-{day:02}"

    return TravelInfo(purchase_type, date, source, destination, price)


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument("-H", "--host")
    argparser.add_argument("-u", "--username")
    argparser.add_argument("-p", "--password")

    pdf_options = {
        'encoding': "UTF-8",
    }

    args = argparser.parse_args()

    imap_host = args.host if args.host else input("Host: ")
    imap_user = args.username if args.username else input("Username: ")
    imap_pass = args.password if args.password else getpass.getpass()

    with imaplib.IMAP4_SSL(imap_host) as imap:
        imap.login(imap_user, imap_pass)
        imap.enable("UTF8=ACCEPT")
        imap.select('INBOX')

        _, data = imap.search(None, "FROM netbutikken@dsb.dk")
        for num in data[0].split():
            _, data = imap.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(data[0][1], policy=email.policy.default)
            msg = mailparser.MailParser(msg)

            text = msg.text_html[0]
            text = text.replace("<head></head>", """<head><meta charset="utf-8"></head>""")
            travel_info = extract_travel_info(text)
            filename = generate_pdf_name(travel_info)
            pdfkit.from_string(text, filename, options=pdf_options)


if __name__ == "__main__":
    main()