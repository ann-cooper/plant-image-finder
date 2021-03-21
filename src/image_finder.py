import pandas as pd
import numpy as np
import requests
import urllib
from lxml.html import fromstring
import threading
import concurrent.futures
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)


## PREP
# Read in seed spreadsheet
jelitto = pd.read_excel('jelitto_pricelist.xls')

# Subset of rows to test
jelitto = jelitto.iloc[0:25, :]

# Add row for image url
image_url = jelitto['Item No.'].apply(lambda row: 'https://www.jelitto.com/out/pictures/master/product/1/' + row.lower() + '.jpg')

## DEFINE RESP CODE ERROR HANDLING
def response_code_error(url):
    """Confirm that Jelitto has an image of the plant."""
    try:
        return urllib.request.urlopen(url).getcode()
    except urllib.error.URLError:
        return np.nan

## SETUP FIRST PASS CHECKING URLS
# Save checked urls to a dictionary.
confident_urls = defaultdict(str)

## DO FIRST PASS CHECKING
# Threaded Jelitto image url checking.
with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
    check_url = {executor.submit(response_code_error, url): url for url in image_url}
    print(f"check_url: {check_url}")
    for future in concurrent.futures.as_completed(check_url):
        url = check_url[future]
        try:
            data = future.result()
            if data == 200:
                confident_urls[re.search(r'\/1\/(.*)\.', url).group(1)] = url
            else:
                confident_urls[re.search(r'\/1\/(.*)\.', url).group(1)] = np.nan 
        except Exception as exc:
            print('%r generated an exception: %s' % (url, exc))

## PREP BASE OUTPUT DF
# Cast confident_urls to a dataframe sorted by index (the Item No.)
df = pd.DataFrame.from_dict(confident_urls, orient='index', columns=['url'])
df.sort_index(inplace=True)

# Set the index of the jelitto df to Item No & sort
jelitto.set_index('Item No.', inplace=True)
jelitto.sort_index(inplace=True)

# Add image_url column to jelitto
jelitto['image_url'] = df['url'].values


## PREP SECOND PASS CHECKING
# Create list of wikimedia_urls for rows where jelitto had no image 
# and create alternate lookups for the common name to check if the scientific name has no results
wikimedia_urls = []
alternate_lookups = {}
_url = 'https://commons.wikimedia.org/w/index.php?search='
updates = jelitto[jelitto['image_url'].isnull()]
wikimedia_urls = [(ix, _url + x) for ix, x in updates[['Genus', 'Species ']].apply(lambda x: ' '.join(x).lower(), axis=1).iteritems()]
alternate_lookups = {i: _url+'+'.join(x.split(',')[0].split()) for i,x in updates['Common Names'].iteritems() if not isinstance(x, float)}
alternate_urls = []


def alt_url(url, scientific=False):
    """Test tuple of _id and url to find an image on wikimedia commons."""
    _id = url[0]
    url = url[1]
    page = requests.get(url)
    text = fromstring(page.content)
    new_url = text.xpath("//li[@class='mw-search-result']//a/@href|//ul[contains(@class, 'gallery')]//img/@src")[0]
    if new_url.lower().endswith(('.png', '.jpg', '.jpeg')):
        if (_id, "https://commons.wikimedia.org"+new_url) not in alternate_urls:
            alternate_urls.append((_id, "https://commons.wikimedia.org"+new_url))
        if scientific:
            del alternate_lookups[_id]
    else:
        if scientific:
            pass # try common name
        else:
            alternate_urls.append((_id, np.nan)) 

## DO SECOND PASS CHECKING
# Checking wikimedia urls with scientific name lookup
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    # Start the load operations and mark each future with its URL
    check_url = {executor.submit(alt_url, url, scientific=True): url for url in wikimedia_urls}  
    for future in concurrent.futures.as_completed(check_url):
        url = check_url[future]


# Checking wikimedia common name lookup
if alternate_lookups:
    lookups = [(k,v) for k,v in alternate_lookups.items()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        check_url = {executor.submit(alt_url, url): url for url in lookups}
        for future in concurrent.futures.as_completed(check_url):
            url = check_url[future]

## COMBINE NEW IMAGE URLS WITH BASE DF FOR OUTPUT
# Cast alternate_urls to df with index aligned to jelitto
altdf = pd.DataFrame(alternate_urls)
altdf.rename({0: '_id', 1: 'image_url'}, axis=1, inplace=True)
altdf.set_index('_id', inplace=True)

# Replace null values in image_url with urls from alternate_urls
jelitto = jelitto.combine_first(altdf)


# Check results
print(jelitto[['Genus', 'Species ', 'image_url']])

# Output to csv
jelitto.to_csv('output_data.csv')


