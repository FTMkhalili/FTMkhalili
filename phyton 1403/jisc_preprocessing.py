#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import argparse
import csv
import datetime
import json
from os import path
import re
import sys
from urllib.error import HTTPError, URLError

ARG_HELP_STRINGS = {
    "source_file": "The jisc csv file",
    "exchange_rates_cache_file": "An optional cache file for ECB exchange rates",
    "no_decorations": "Do not use ANSI coded colors in console output",
    "jisc_file_format": "The format type of the Jisc input file"
}

FIELDNAMES = {
    "2014_16": {
        "article": [
            "APC paid (actual currency) including VAT if charged",
            "APC paid (£) including VAT (calculated)",
            "APC paid (£) including VAT if charged",
            "Currency of APC",
            "DOI",
            "Date of APC payment",
            "Date of initial application by author",
            "ISSN0",
            "Institution",
            "Journal",
            "Licence",
            "PubMed Central (PMC) ID",
            "PubMed ID",
            "Publisher",
            "TCO year",
            "Type of publication",
            "Drop?",
            "Year of publication",
            "period",
            "is_hybrid",
            "euro"
        ],
        "book": [
            "Line number",
            "APC paid (actual currency) including VAT if charged",
            "APC paid (£) including VAT (calculated)",
            "APC paid (£) including VAT if charged",
            "Article title",
            "Currency of APC",
            "DOI",
            "Date of APC payment",
            "Date of initial application by author",
            "Institution",
            "Journal",
            "Licence",
            "Publisher",
            "TCO year",
            "Type of publication",
            "Year of publication",
            "period",
            "euro",
            "ISBN"
        ]
    },
    "2017": {
        "article": [
            "APC paid (£) including VAT if charged",
            "DOI",
            "Date of APC payment",
            "ISSN0",
            "Institution",
            "Journal",
            "Licence",
            "PubMed ID",
            "Publisher",
            "TCO year",
            "Type of publication",
            "Drop?",
            "Period of APC payment",
            "period",
            "is_hybrid",
            "euro"
        ],
        "book": [
            "Line number",
            "APC paid (£) including VAT if charged",
            "Article title",
            "DOI",
            "Date of APC payment",
            "Institution",
            "Journal",
            "Licence",
            "Publisher",
            "TCO year",
            "Type of publication",
            "Period of APC payment",
            "period",
            "euro",
            "ISBN"
        ]
    },
    "2018": {
        "article": [
            "Institution",
            "Date of acceptance",
            "PubMed ID",
            "DOI",
            "Publisher",
            "Journal",
            "Type of publication",
            "Date of publication",
            "Date of APC payment",
            "APC paid (£) including VAT if charged",
            "period",
            "is_hybrid",
            "euro"
        ],
        "book": [
            "Line number",
            "Institution",
            "Date of acceptance",
            "DOI",
            "Publisher",
            "Journal",
            "Type of publication",
            "Article title",
            "Date of publication",
            "Date of APC payment",
            "APC paid (£) including VAT if charged",
            "period",
            "euro",
            "ISBN"
        ]
    }
}

PUBLICATION_TYPES_BL = [
    "Book chapter",
    "Book edited",
    "Conference Paper/Proceeding/Abstract",
    "Letter"
]

PUBLICATION_TYPES_BOOKS = [
    "Book",
    "Monograph"
]

DATE_DAY_RE = {
    "2014_16": re.compile("(?P<year>[0-9]{4})-?(?P<month>[0-9]{2})?-?(?P<day>[0-9]{2})?"),
    "2017": re.compile("(?P<year>[0-9]{4})-?(?P<month>[0-9]{2})?-?(?P<day>[0-9]{2})?"),
    "2018": re.compile("(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/(?P<year>[0-9]{4})")
}

DATE_STRPTIME = {
    "2014_16": "%Y-%m-%d",
    "2017": "%Y-%m-%d",
    "2018": "%m/%d/%Y"
}

PERIOD_FIELD_SOURCE = {
    "2014_16": [
        "Date of APC payment",
        "Year of publication",
        "Date of initial application by author",
        "TCO year"
    ],
    "2017": [
        "Date of APC payment",
        "Period of APC payment",
        "TCO year"
    ],
    "2018": [
        "Date of APC payment",
        "Date of publication",
        "Date of acceptance"
    ]
}

EXCHANGE_RATES_CACHE = {}
EXCHANGE_RATES_CACHE_FILE = None

DELETE_REASONS = {}

CURRENT_YEAR = 2017
#CURRENT_YEAR = datetime.datetime.now().year

NO_DECORATIONS = False

def delete_line(line_dict, reason):
    _print("r", "   - " + reason + ", line deleted")
    if reason not in DELETE_REASONS:
        DELETE_REASONS[reason] = 1
    else:
        DELETE_REASONS[reason] += 1
    for key in line_dict:
        line_dict[key] = ""

def line_as_list(line_dict, pub_type):
    return [line_dict[field] for field in FIELDNAMES[FORMAT][pub_type]]

def is_money_value(string):
    try:
        number = float(string)
        return number > 0
    except ValueError:
        return False

def is_valid_date(date_match_obj):
    gd = date_match_obj.groupdict()
    if gd["year"] is None or gd["month"] is None or gd["day"] is None:
        return False
    try:
        date = datetime.datetime(int(gd["year"]), int(gd["month"]), int(gd["day"]))
        if date > datetime.datetime.now():
            return False
        return True
    except ValueError:
        return False

def shutdown():
    _print("r", "Updating exchange rates cache...")
    with open(EXCHANGE_RATES_CACHE_FILE, "w") as f:
        f.write(json.dumps(EXCHANGE_RATES_CACHE, sort_keys=True, indent=4, separators=(',', ': ')))
        f.flush()
    _print("r", "Done.")
    sys.exit()
    
def _print(color, s):
    if color in ["r", "y", "g", "b"] and not NO_DECORATIONS:
        getattr(oat, "print_" + color)(s)
    else:
        print(s)
        

def get_exchange_rate(currency, frequency, date, jisc_format):
    if currency not in EXCHANGE_RATES_CACHE:
        EXCHANGE_RATES_CACHE[currency] = {}
    if frequency not in EXCHANGE_RATES_CACHE[currency]:
        EXCHANGE_RATES_CACHE[currency][frequency] = {}
    if not len(EXCHANGE_RATES_CACHE[currency][frequency]):
        try:
            rates = oat.get_euro_exchange_rates(currency, frequency)
            EXCHANGE_RATES_CACHE[currency][frequency] = rates
        except HTTPError as httpe:
            _print("r", "HTTPError while querying the ECB data warehouse: " + httpe.reason)
            shutdown()
        except URLError as urle:
            _print("r", "URLError while querying the ECB data warehouse: " + urle.reason)
            shutdown()
        except ValueError as ve:
            _print("r", "ValueError while querying the ECB data warehouse: " + ve.reason)
            shutdown()
    if frequency == "D":
        # The ECB does not report exchange rate for all dates due to weekends/holidays. We have
        # consider some days in advance to find the next possible data in some cases.
        day = datetime.datetime.strptime(date, DATE_STRPTIME[jisc_format])
        for i in range(6):
            future_day = day + datetime.timedelta(days=i)
            search_day = future_day.strftime("%Y-%m-%d")
            if search_day in EXCHANGE_RATES_CACHE[currency][frequency]:
                _print("y", "     [Exchange rates: Cached value used]")
                if i > 0:
                    msg = "     [Exchange rates: No rate found for date {}, used value for {} instead]"
                    _print("y", msg.format(date, search_day))
                return EXCHANGE_RATES_CACHE[currency][frequency][search_day]
        _print("r", "Error during Exchange rates lookup: No rate for " + date + " or any following day!")
        shutdown()
    else:
        return EXCHANGE_RATES_CACHE[currency][frequency][date]
        
def calculate_euro_value(line, jisc_format):
    payment_date = line["Date of APC payment"]
    date_match = DATE_DAY_RE[jisc_format].match(payment_date)
    if jisc_format in ["2017", "2018"]:
        apc_pound = line["APC paid (£) including VAT if charged"]
        field_used_for_pound_value = "APC paid (£) including VAT if charged"
    elif jisc_format == "2014_16":
        apc_orig = line["APC paid (actual currency) including VAT if charged"]
        apc_pound = ""
        field_used_for_pound_value = ""
        for field in ["APC paid (£) including VAT (calculated)", "APC paid (£) including VAT if charged"]:
            if is_money_value(line[field]):
                apc_pound = line[field]
                field_used_for_pound_value = field
                break
        if is_money_value(apc_orig):
            currency = line["Currency of APC"].strip()
            if currency == "EUR":
                line["euro"] = apc_orig
                msg = "   - Created euro field ('{}') by using the value in 'APC paid (actual currency) including VAT if charged' directly since the currency is EUR"
                _print("g", msg.format(apc_orig))
            elif len(currency) == 3:
                if date_match and is_valid_date(date_match):
                    rate = get_exchange_rate(currency, "D", payment_date, jisc_format)
                    euro_value = round(float(apc_orig) / float(rate), 2)
                    line["euro"] = str(euro_value)
                    msg = "   - Created euro field ('{}') by dividing the value in 'APC paid (actual currency) including VAT if charged' ({}) by {} (EUR -> {} conversion rate on {}) [ECB]"
                    msg = msg.format(euro_value, apc_orig, rate, currency, payment_date)
                    _print("g", msg)
                else:
                    year = line["period"]
                    if int(year) >= CURRENT_YEAR:
                        del_msg = "period ({}) too recent to determine average yearly conversion rate".format(year)
                        delete_line(line, del_msg)
                        return
                    try:
                        rate = get_exchange_rate(currency, "A", year, jisc_format)
                    except KeyError:
                        _print("r", "KeyError: An average yearly conversion rate is missing (" + currency + ", " + year + ")")
                        shutdown()
                    euro_value = round(float(apc_orig) / float(rate), 2)
                    line["euro"] = str(euro_value)
                    msg = "   - Created euro field ('{}') by dividing the value in 'APC paid (actual currency) including VAT if charged' ({}) by {} (avg EUR -> {} conversion rate in {}) [ECB]"
                    msg = msg.format(euro_value, apc_orig, rate, currency, year)
                    _print("g", msg)
    if line["euro"] == "" and is_money_value(apc_pound):
        if date_match and is_valid_date(date_match):
            rate = get_exchange_rate("GBP", "D", payment_date, jisc_format)
            euro_value = round(float(apc_pound) / float(rate), 2)
            line["euro"] = str(euro_value)
            msg = "   - Created euro field ('{}') by dividing the value in '{}' ({}) by {} (EUR -> GBP conversion rate on {}) [ECB]"
            msg = msg.format(euro_value, field_used_for_pound_value, apc_pound, rate, payment_date)
            _print("g", msg)
        else:
            year = line["period"]
            if int(year) > CURRENT_YEAR:
                del_msg = "period ({}) too recent to determine average yearly conversion rate".format(year)
                delete_line(line, del_msg)
                return
            try:
                rate = get_exchange_rate("GBP", "A", year, jisc_format)
            except KeyError:
                _print("r", "KeyError: An average yearly conversion rate is missing (GBP, " + year + ")")
                shutdown()
            euro_value = round(float(apc_pound) / float(rate), 2)
            line["euro"] = str(euro_value)
            msg = "   - Created euro field ('{}') by dividing the value in '{}' ({}) by {} (avg EUR -> GBP conversion rate in {}) [ECB]"
            msg = msg.format(euro_value, field_used_for_pound_value, apc_pound, rate, year)
            _print("g", msg)
    if line["euro"] == "":
        delete_line(line, "Unable to properly calculate a converted euro value")
       
def main():
    global EXCHANGE_RATES_CACHE, EXCHANGE_RATES_CACHE_FILE, NO_DECORATIONS, FORMAT
    parser = argparse.ArgumentParser()
    parser.add_argument("source_file", help=ARG_HELP_STRINGS["source_file"])
    parser.add_argument("jisc_file_format", choices=list(FIELDNAMES), help=ARG_HELP_STRINGS["jisc_file_format"])
    parser.add_argument("-c", "--exchange_rates_cache_file", help=ARG_HELP_STRINGS["exchange_rates_cache_file"], default="_exchange_rates_cache.json")
    parser.add_argument("-n", "--no-decorations", help=ARG_HELP_STRINGS["no_decorations"], action="store_true")

    args = parser.parse_args()

    NO_DECORATIONS = args.no_decorations
    EXCHANGE_RATES_CACHE_FILE = args.exchange_rates_cache_file
    FORMAT = args.jisc_file_format

    if path.isfile(args.exchange_rates_cache_file):
        with open(EXCHANGE_RATES_CACHE_FILE, "r") as f:
            try:
                EXCHANGE_RATES_CACHE = json.loads(f.read())
            except ValueError:
                _print("r", "Could not decode a cache structure from " + EXCHANGE_RATES_CACHE_FILE + ", starting with an empty cache.")
        
    f = open(args.source_file, "r", encoding="utf-8")
    reader = csv.DictReader(f)

    article_content = [list(FIELDNAMES[FORMAT]["article"])]
    book_content = [list(FIELDNAMES[FORMAT]["book"])]
    empty_article_line = ["" for i in range(len(FIELDNAMES[FORMAT]["article"]))]
    empty_book_line = ["" for i in range(len(FIELDNAMES[FORMAT]["book"]))]
    for line in reader:
        line["period"] = ""
        line["euro"] = ""
        line["Journal"] = line["Journal"].replace("\n", " ")
        _print("b", "--- Analysing line " + str(reader.line_num) + " ---")
        is_book = False
        pub_type = line["Type of publication"]
        if pub_type in PUBLICATION_TYPES_BOOKS:
            line["Line number"] = str(reader.line_num)
            line["ISBN"] = ""
            is_book = True
        else:
            line["is_hybrid"] = ""
        # Publication blacklist checking
        if pub_type in PUBLICATION_TYPES_BL and not is_book:
            delete_line(line, "Blacklisted pub type ('" + pub_type + "')")
            article_content.append(list(empty_article_line))
            continue
        # DOI checking
        if len(line["DOI"].strip()) == 0 and not is_book:
            delete_line(line, "Empty DOI")
            article_content.append(list(empty_article_line))
            continue
        # Drop checking
        if "Drop?" in FIELDNAMES[FORMAT]["article"] and line["Drop?"] == "1":
            delete_line(line, "Drop mark found")
            article_content.append(list(empty_article_line))
            continue
        # period field generation
        for source_field in PERIOD_FIELD_SOURCE[FORMAT]:
            content = line[source_field].strip()
            match = DATE_DAY_RE[FORMAT].match(content)
            if match:
                year = match.groupdict()["year"]
                if int(year) > CURRENT_YEAR:
                    continue
                line["period"] = year
                msg = "   - Created period field ('{}') by parsing value '{}' in column '{}'".format(year, content, source_field)
                _print("g", msg)
                break
        else:
            delete_line(line, "Unable to determine payment date for period column")
            article_content.append(list(empty_article_line))
            continue
        # euro field generation
        calculate_euro_value(line, FORMAT)
        if is_book:
            if line["Line number"] != "":
                book_content.append(line_as_list(line, "book"))
                delete_line(line, "Book content (extracted to separate file)")
            article_content.append(list(empty_article_line))
        else:
            article_content.append(line_as_list(line, "article"))
    with open('out.csv', 'w') as out:
        writer = oat.OpenAPCUnicodeWriter(out, None, False, True)
        writer.write_rows(article_content)
    with open('out_books.csv', 'w') as out:
        writer = oat.OpenAPCUnicodeWriter(out, None, False, True)
        writer.write_rows(book_content)

    print("\n\nPreprocessing finished, deleted articles overview:")

    sorted_reasons = sorted(DELETE_REASONS.items(), key=lambda x: x[1])
    sorted_reasons.reverse()
    for item in sorted_reasons:
        _print("r", item[0].ljust(72) + str(item[1]))
    _print("r,", "-------------------------------------------------")
    _print("r", "Total".ljust(72) + str(sum(DELETE_REASONS.values())))

    shutdown()

if __name__ == '__main__' and __package__ is None:
    sys.path.append(path.dirname(path.dirname(path.dirname(path.dirname(path.abspath(__file__))))))
    import openapc_toolkit as oat
    main()
