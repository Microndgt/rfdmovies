import time
from bs4 import BeautifulSoup as bs

from rfdmovie.cache.download import DownloadCache
from rfdmovie.config import get_config
from rfdmovie.logger import logger
from . import BaseAPI, HtmlDownloader, HtmlParser, Search, USER_AGENTS


class MovieHeavenAPI(BaseAPI):
    @classmethod
    def read(cls, key_word, num=5):
        """
        从电影天堂读取电影下载信息，并且更新数据库缓存
        :param key_word:
        :param num:
        :return: list(dict)
        """
        return cls.read_all(key_word)[:num]

    @classmethod
    def read_all(cls, key_word):
        """

        :param key_word:
        :return: list(dict)
        """
        search = MovieHeavenSearch()
        res = search.search(key_word)
        DownloadCache.write_all(res)
        return res


class MovieHeavenDownloader(HtmlDownloader):
    pass


class MovieHeavenParser(HtmlParser):

    base_url = get_config("movie_heaven.base")

    def parse_pages(self, html):
        soup = bs(html, "html.parser")
        # FIXME 这里解析不同page 有问题
        raw_results = soup.find('div', class_="co_content8").find('table', cellpadding="0")
        if raw_results:
            data = []
            results = raw_results.find_all('a')
            for result in results:
                try:
                    page = int(result.get_text()[1:-1])
                    url = self.base_url + result['href']
                    data.append((page, url))
                except Exception as e:
                    logger.exception(e)
                    break
            return data
        else:
            return

    def parse_page_results(self, html):
        soup = bs(html, "html.parser")
        results = soup.find_all('div', class_="co_content8")[0].find_all('div', id="Zoom")[0].find_all('table')
        result_url = []
        for result in results:
            result_url.append(result.find('a')['href'])
        return result_url

    def parse_search_results(self, html):
        soup = bs(html, "html.parser")
        results = soup.find_all('div', class_="co_content8")[0].find_all('table', width="100%")
        data = []
        for ele in results:
            item = ele.find('a')
            url = self.base_url + item['href']
            name = item.get_text()
            data.append((name, url))
        return data


class MovieHeavenSearch(Search):

    def __init__(self):
        self.search_url = get_config("movie_heaven.search")
        self.downloader = MovieHeavenDownloader()
        self.parser = MovieHeavenParser()
        self.decoding = "gbk"

    def _encode(self, name):
        return "%" + '%'.join([x.upper() for x in str(name.encode("GB2312")).split(r'\x')[1:]])[:-1]

    def search(self, name):
        search_url = self.search_url + self._encode(name)
        results = self.downloader.get(search_url, decoding=self.decoding)
        if not results:
            logger.error("Getting url: {} page failed".format(search_url))
            return []
        page_urls = self.parser.parse_pages(results)
        data = []
        page_data = self.parser.parse_search_results(results)
        data.extend(page_data)
        if page_urls:
            for page, url in page_urls:
                time.sleep(1)
                logger.info("Getting page: {}, url: {} data".format(page, url))
                try:
                    results = self.downloader.get(url, decoding=self.decoding)
                    if not results:
                        logger.error("Getting url page failed")
                        continue
                    page_data = self.parser.parse_search_results(results)
                    data.extend(page_data)
                except:
                    logger.error("Parse page content failed")
        res = []
        for item in data:
            name, url = item
            time.sleep(1)
            logger.info("Getting item: {}, url: {} data".format(name, url))
            try:
                results = self.downloader.get(url, decoding=self.decoding)
                if not results:
                    logger.error("Getting url page failed")
                    continue
                result_urls = self.parser.parse_page_results(results)
                res.append({
                    "name": name,
                    "page_link": url,
                    "download_urls": result_urls
                })
            except:
                logger.error("Parse page content failed")
        return res
