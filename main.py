import argparse
import imaplib
import getpass
import calendar
import pdfkit
import email, email.policy
import mailparser

from ttp import ttp
from dataclasses import dataclass


@dataclass
class TravelInfo:
    date: str
    source: str
    destination: str
    price: float


def generate_pdf_name(travel_info: TravelInfo) -> str:
    date = travel_info.date
    src = travel_info.source
    dst = travel_info.destination
    type_ = "pladsbillet" if travel_info.price < 50 else "billet"
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

    with open("./mail-template.txt") as f:
        template = f.read()

    parser = ttp(data=text, template=template)
    parser.parse()
    res = parser.result()

    x = res[0][0]

    source = short_location(find_by_key(x, "source"))
    destination = short_location(find_by_key(x, "destination"))

    price = find_by_key(x, "price")
    price = float(price.replace(",", ".")) if price else None

    day = find_by_key(x, "day")
    month = month_to_number(find_by_key(x, "month"))
    year = find_by_key(x, "year")

    if not all([source, price, day, month, year]):
        raise ValueError("Could not determine all values")

    year = int(year)
    month = int(month)
    day = int(day)
    date = f"{year}-{month:02}-{day:02}"

    return TravelInfo(date, source, destination, price)


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