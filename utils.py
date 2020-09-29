import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
from pathlib import Path
import re
import PyPDF2
from datetime import datetime
from pathlib import Path

black_test_list= ['abc', 'def',34,1.3,'super long text to trigger wrapping and get under the 80(?) char recommended line length']

def parse_long_dates(date_string):
    """Extracts three simple strings representing the year, month, and day
    from a date in the  in the long format like 'November 19, 2010'.

    Args:
        date_string (str): The date in 'long' format
    Returns:
        year (str): The year as a four-character string
        month (str): The month as a string representing an integer between 1 and 12
        day (str): The day as a string representing an integer between 1 and 31
    """
    # check for garbage at the end of the string
    while not date_string[-1].isnumeric():
        date_string = date_string[:-1]
    # grab the front of the string, where we expect the three-letter month to be
    month = date_string[:3]
    # this error will come up, so we catch it
    if month == "une":
        month = "Jun"
    # grab the back of the string to get the year
    year = date_string[-4:]
    # try to convert the month to str(int) form, or throw an error
    try:
        month = str(time.strptime(month, "%b").tm_mon)
    except ValueError as err:
        print(f"month: {month}")
        print(f"Encountered ValueError on file: {date_string}")
    day = date_string.split(" ")[1]
    day = "".join(filter(str.isdigit, day))
    # check integrity
    assert (
        year.isnumeric()
    ), f"The year is not numeric. year: {year} input: {date_string}"
    assert (
        month.isnumeric()
    ), f"The month is not numeric. month: {month} input: {date_string}"
    assert day.isnumeric(), f"The day is not numeric. day: {day} input: {date_string}"
    return year, month, day


def store_boe_pdfs(base_url, minutes_url):
    """Finds .pdf files stored at the given url and stores them within the
    repository for later analysis.
    Args:
        base_url (str): The main url for the Comptroller of Baltimore's webiste
        minutes_url (str): The url where the function can find links to pages of
            pdf files organized by year
    Returns:
        None: This is a void function.
    """
    response = requests.get(minutes_url)
    soup = BeautifulSoup(response.text, "html.parser")
    root = Path.cwd()
    pdf_dir = root / "pdf_files"
    total_counter = 0

    if not pdf_dir.is_dir():
        pdf_dir.mkdir(parents=True, exist_ok=False)

    for year in range(2009, 2021):
        # make a directory for the files
        save_path = pdf_dir / str(year)
        save_path.mkdir(parents=True, exist_ok=True)
        # find all links where the associated text contains the year
        link = soup.find("a", href=True, text=str(year))
        annual_url = base_url + link["href"]
        print(f"Saving files from url: {annual_url}")
        # now follow the link to the page with that year's pdfs
        response_annual = requests.get(annual_url)
        soup_annual = BeautifulSoup(response_annual.text, "html.parser")
        pdf_links = soup_annual.find_all(name="a", href=re.compile("files"))
        for idx, link in enumerate(pdf_links):
            pdf_location = link["href"]
            pdf_url = base_url + pdf_location
            pdf_file = requests.get(pdf_url)
            # derive name of the pdf file we're going to create
            # encoding and decoding removes hidden characters
            pdf_html_text = (
                link.get_text().strip().encode("ascii", "ignore").decode("utf-8")
            )
            # handle cases where the date is written out in long form
            if any(char.isdigit() for char in pdf_html_text):
                pdf_year, pdf_month, pdf_day = parse_long_dates(pdf_html_text)
                pdf_filename = "_".join([pdf_year, pdf_month, pdf_day]) + ".pdf"
                try:
                    with open(save_path / pdf_filename, "wb") as f:
                        f.write(pdf_file.content)
                    total_counter += 1
                except TypeError as err:
                    print(f"an error occurred with path {pdf_location}: {err}")
    print(f"Wrote {total_counter} .pdf files to local repo.")
    return


def get_boe_minutes(base_url="https://comptroller.baltimorecity.gov",
                    minutes_url_part="/boe/meetings/minutes",
                    save_folder='BoE Minutes PDFs',
                    start_dir=os.path.dirname(__file__)):
    """
    base_url:
        url for the comptrollers website

    minutes_url:
        the extra bit of the URL that specifies the minutes "landing page"

        https://comptroller.baltimorecity.gov/boe/meetings/minutes

    save_folder:
        the name of the folder used to hold the minutes PDFs,
        shouldn't have any slashes

    start_dir:
        defaults to the directory the calling script is in. used to
        make a full path (relative to the calling script or absolute)
        with save_folder
    """
    # print(start_dir)  # print the directory this script is in
    os.chdir(start_dir)  # set the cwd to avoid any OS/python shenanigans
    pdf_save_dir = f'{start_dir}/{save_folder}/'  # set save directory for pdfs
    os.makedirs(pdf_save_dir, exist_ok=True)  # create directory if it doesn't exist (no error if it does)
    minutes_url = base_url + minutes_url_part

    # because whoever wrote the BoE website didn't make it easy to scrape
    # date_regex = re.compile(r'([(January|February|March|April|May|June|July|August|September|October|November|December)]) (\d{1,2}), (\d{4})', re.IGNORECASE)
    date_regex = re.compile(r'(\w*)\s+(\d{1,2})\D*(\d{4})', re.IGNORECASE)
    """
    This regex captures any long date formats

    The compoents of the regex:
        (\w*) - First capture group, one or more word chars to find month
        \s - Space between month and date, not captured
        (\d{1,2}) - Second capture group, one or two numbers to find date
        \D* - Non decimal chars between date and year, not captured
        (\d{4}) - Third capture group, string of four numbers to find year
    """
    month_dict = {'january': '01',
                  'february': '02',
                  'march': '03',
                  'april': '04',
                  'may': '05',
                  'june': '06',
                  'july': '07',
                  'august': '08',
                  'september': '09',
                  'october': '10',
                  'november': '11',
                  'december': '12'}

    # this creates a dictionary containing all possible single-letter deletions of every month
    # it's used to correct for typos in the text of a link to the minutes
    # ex: Novembe 17, 2010 (one of two real examples as of Aug 9, 2020)
    typo_dict = {k: list() for k in month_dict.keys()}
    for month in typo_dict.keys():
        for i in range(len(month)):
            typo_dict[month].append(month[:i] + month[i+1:])

    start_page = requests.get(minutes_url)  # grab the 'starting page' that provides links to the minutes for a specific year
    start_page.raise_for_status()  # doing the \
    start_soup = BS(start_page.text, 'lxml')  # needful

    # this eliminates the need to specify the years to grab since four-digit years are used consistently
    year_tags = start_soup.find_all('a', href=True, text=re.compile(r'^\d{4}$'))  # find the tags that link to the minutes for specific years
    year_links = [tag.get('href') for tag in year_tags]  # extracting the links

    for link in year_links:
        print(link)
        year_page = requests.get(link)
        year_page.raise_for_status()
        soup = BS(year_page.text, 'lxml')

        minutes_tags = soup.find_all('a', text=date_regex)  # grab tags that link to the pdfs

        for tag in minutes_tags:
            file_name_re = date_regex.search(tag.string)
            # example filename: 'BoE Minutes 2009-04-01.pdf'

            try:  # most links will fit this pattern
                file_name = (
                    'BoE Minutes '
                    + file_name_re.group(3) # year
                    + '-'
                    + month_dict[file_name_re.group(1).lower()] # month
                    + '-'
                    + file_name_re.group(2).zfill(2) # day
                    + '.pdf'
                )
            except KeyError as e:  # this code only triggers if there's a typo in the month string
                month_error = file_name_re.group(1).lower()
                print(f'Error "{e}" for minutes on: "{tag.string}", '
                      f'regex found: {file_name_re.groups()}. '
                      f'Attempting typo matching...')
                for k, v in typo_dict.items():  # this loop searches for matches among single-letter deletions
                    correct_month = False
                    if month_error in v:
                        correct_month = k
                        break

                if correct_month:  # if we found a match
                    file_name = (
                        'BoE Minutes '
                        + file_name_re.group(3) # year
                        + '-'
                        + month_dict[correct_month] # month
                        + '-'
                        + file_name_re.group(2).zfill(2) # day
                        + '.pdf'
                    )
                else:
                    #  sorry, you'll have to update the regex if you hit this code
                    print(f'Error: could not match month string '
                          f'{file_name_re.group(1)} in '
                          f'match {file_name_re.groups()}. ')

            if os.path.exists(pdf_save_dir + file_name):  # skip the download if we've already done it
                print(f'skipping: {file_name}')
            else:
                if tag.get('href').startswith('http'):  # because there is literally ONE link in the entire list that is an absolute path
                    min_url = tag.get('href')
                else:
                    min_url = base_url + tag.get('href')
                minutes_req = requests.get(min_url)
                minutes_req.raise_for_status()
                with open(pdf_save_dir + file_name, 'wb') as p:  # save the file
                    p.write(minutes_req.content)
                print(f'saved: {file_name}')


def store_pdf_text_to_df(path):
    """Finds .pdf files stored at the given url and stores them within the
    repository for later analysis.

    Args:
        base_url (str): The main url for the Comptroller of Baltimore's webiste
        minutes_url (str): The url where the function can find links to pages of
        pdf files organized by year
    Returns:
        None: This is a void function.
    """
    pdf_paths = list(path.rglob("*.pdf"))
    text_df = pd.DataFrame(columns=["date", "page_number", "minutes"])
    for pdf_path in pdf_paths:
        # print(f"Parsing file: {pdf_path.name}")
        minutes = ""
        pdfFileObj = open(pdf_path, "rb")
        try:
            pdfReader = PyPDF2.PdfFileReader(pdfFileObj, strict=False)
        except:
            print(f"An error occurred reading file {pdf_path}")
        for page in pdfReader.pages:
            minutes += page.extractText().strip()

        date_string = pdf_path.stem
        date = datetime.strptime(date_string, "%Y_%m_%d").date()
        page_number = re.findall(r"(^[0-9]+)", minutes)
        if page_number:
            page_number = page_number[0]
        else:
            page_number = ""
        try:
            row = {
                "date": date,
                "page_number": page_number,
                "minutes": minutes.strip()
            }
            text_df = text_df.append(row, ignore_index=True)
        except ValueError:
            print(f"No date found for file {pdf_path}")
    print(f"Wrote {len(text_df)} rows to the table of minutes.")
    return text_df


def is_empty(_dir: Path) -> bool:
    return not bool([_ for _ in _dir.iterdir()])


def replace_chars(val):
    val = " ".join(val.split())
    val = val.replace("™", "'")
    val = val.replace("Œ", "-")
    return val
