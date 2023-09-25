import concurrent.futures
import re
import threading
import urllib
from collections import defaultdict

import numpy as np
import pandas as pd
import requests
from lxml.html import fromstring


def response_code_error(url: str) -> int:
    """Confirm that the catalog has an image of the plant.

    Parameters
    ----------
    url: str
        URL to check

    Returns
    -------
        int|np.nan
    """
    print(f"Checking url: {url}")
    try:
        code = urllib.request.urlopen(url).getcode()
    except urllib.error.URLError as err:
        print(f"No catalog image {err}")
        code = np.nan
    return code


class ImageFinder:
    """Find plant images for seed catalog data.

    Attributes
    ----------
    catalog_df: pd.DataFrame
    scientific_names: list
    common_names: list
    alt_urls: list

    Methods
    -------
    find_wikimedia_image(url_tup)
        Use tuple of _id and url to find an image on wikimedia commons.
    check_image_urls
        Return df of confident image urls based on the url pattern for plant images.
    format_dfs
        Add confident image urls to the catalog df.
    get_alt_urls
        Generate alternative possible image urls.
    check_alt_urls
        check_alt_urls
    combine_output_data
        Combine catalog df with additional image urls.
    run
        Run ImageFinder.
    """

    def __init__(self, catalog_df):
        self.catalog_df = catalog_df

        self.confident_urls = None
        self.scientific_names = None
        self.common_names = None
        self.alt_urls = None

    @staticmethod
    def find_wikimedia_image(url_tup: tuple) -> tuple:
        """Use tuple of _id and url to find an image on wikimedia commons.

        Parameters
        ----------
        url_tup: tuple
            A tuple of _id and a url

        Returns
        -------
        alt_url: tuple
            (_id, new_url)
        """
        _id = url_tup[0]
        url = url_tup[1]
        page = requests.get(url)
        text = fromstring(page.content)
        new_url = text.xpath(
            "//li[contains(@class,'mw-search-result')]//a/@href|//ul[contains(@class, 'gallery')]//img/@src"
        )[0]
        if new_url.lower().endswith((".png", ".jpg", ".jpeg", ".pdf")):
            alt_url = (_id, f"https://commons.wikimedia.org{new_url}")
        else:
            alt_url = (_id, None)
        return alt_url

    def check_image_urls(self) -> pd.DataFrame:
        """Return df of confident image urls based on the url pattern for plant images.

        Args:
            df (pd.DataFrame): Df of seed spreadsheet data

        Returns:
            pd.DataFrame: Confident urls for plant images.
        """
        image_urls = self.catalog_df["Item No."].apply(
            lambda row: f"https://www.jelitto.com/out/pictures/master/product/1/{row.lower()}.jpg"
        )
        self.confident_urls = defaultdict(str)

        # Check image_urls
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            check_url = {
                executor.submit(response_code_error, url): url for url in image_urls
            }
            for future in concurrent.futures.as_completed(check_url):
                url = check_url[future]
                try:
                    data = future.result()
                    if data == 200:
                        self.confident_urls[
                            re.search(r"\/1\/(.*)\.", url).group(1)
                        ] = url
                    else:
                        self.confident_urls[
                            re.search(r"\/1\/(.*)\.", url).group(1)
                        ] = np.nan
                except Exception as exc:
                    print(f"{url} generated an exception: {exc}")
        return self.confident_urls

    def format_dfs(self) -> pd.DataFrame:
        """Add confident image urls to the catalog df.

        Args:
            df (pd.DataFrame): The seed catalog df
            confident_urls_df (pd.DataFrame): df of confident image urls
        """

        confident_urls_df = pd.DataFrame.from_dict(
            self.confident_urls, orient="index", columns=["url"]
        )
        confident_urls_df.sort_index(inplace=True)

        self.catalog_df.set_index("Item No.", inplace=True)
        self.catalog_df.sort_index(inplace=True)
        self.catalog_df["image_url"] = confident_urls_df["url"].values

        return self.catalog_df

    def get_alt_urls(self):
        """Generate alternative possible image urls.

        Args:
            df (pd.DataFrame): Catalog df

        Returns:
            tuple: scientific name lookup list, common name lookup list
        """
        _url = "https://commons.wikimedia.org/w/index.php?search="
        updates = self.catalog_df[self.catalog_df["image_url"].isnull()]
        self.scientific_names = [
            (ix, _url + x)
            for ix, x in updates[["Genus", "Species "]]
            .apply(lambda x: " ".join(x).lower(), axis=1)
            .items()
        ]
        self.common_names = [
            (i, _url + "+".join(x.split(",")[0].split()))
            for i, x in updates["Common Names"].items()
            if not isinstance(x, float)
        ]

        return self

    def check_alt_urls(self) -> list:
        """Check alternative image urls and return list.

        Args:
            common_names (dict): common name lookups
            scientific_names (list): scientific name lookups

        Returns:
            list: [(id, image url)]
        """
        self.alt_urls = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            check_url = {
                executor.submit(self.find_wikimedia_image, url): url
                for url in self.scientific_names
            }
            for future in concurrent.futures.as_completed(check_url):
                url_tup = future.result()
                if url_tup[1]:
                    self.alt_urls.append(url_tup)

        if self.common_names:
            with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                check_url = {
                    executor.submit(self.find_wikimedia_image, url): url
                    for url in self.common_names
                }
                for future in concurrent.futures.as_completed(check_url):
                    url_tup = future.result()
                    self.alt_urls.append(url_tup)
        return self.alt_urls

    def combine_output_data(self):
        """Combine catalog df with additional image urls."""
        altdf = pd.DataFrame(self.alt_urls)
        altdf.rename({0: "_id", 1: "image_url"}, axis=1, inplace=True)
        altdf.set_index("_id", inplace=True)

        self.catalog_df = self.catalog_df.combine_first(altdf)
        self.catalog_df.to_csv("image_urls.csv")

    def run(self):
        for step in [
            self.check_image_urls,
            self.format_dfs,
            self.get_alt_urls,
            self.check_alt_urls,
            self.combine_output_data,
        ]:
            try:
                step()
            except Exception as err:
                print(f"Error: {err}")


if __name__ == "__main__":
    catalog_df = pd.read_excel("src/jelitto_pricelist.xls")
    # Subset of rows to test
    catalog_df = catalog_df.iloc[0:25, :]
    image_finder = ImageFinder(catalog_df=catalog_df)
    image_finder.run()
