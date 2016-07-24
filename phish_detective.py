"""
This scipt takes a sitedata json file as an input, extracts keywords, and does
a google query on those. A simple decision tree -based workflow categorizes website in to
    - unresolved
    - definitely not phishing
    - probably not phishing
    - probably phishing
    - definitely phishing

"""

import bs4
import collections
import json
import keywords 
import ocr
import os
import re
import requests
import simple_logger
import sys
import time
import urllib
import utils
import website_fetcher
import goslate

# import ngrams

logger = simple_logger.SimpleLogger()
logger.activate()


#############
# ARGUMENTS #
#############

# header data for google search
HEADERS = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0',}

# regular expression for extracting urls
GOOGLERX = re.compile("""http[s]?://[^\s'"]*""")

# max number of keywords extracted from a website
MAXCOUNT = 5

# stopmlds: mlds that almost always appear in Google's response 
STOPMLDS = ['google', 'youtube', 'blogger', 'googleusercontent', 'schema']


####################
# hidden functions #
####################


def _load_json(jspath):
    try:
        with open(jspath) as f:
            js = json.load(f)
    except FileNotFoundError:
        js = {}
    return js


def _get_screenshot_path(jspath):
    js = _load_json(jspath)
    base = os.path.dirname(os.path.dirname(jspath))
    path = os.path.join(base, 'websites', js['siteid'] + '.png')
    return path


def _asks_password(js, value=None):
    """
    Does the site contain a password field?
    """
    sources = [source for source in js.get('external_source', {}).values()]
    sources.append(js['source'])
    for source in sources:
        source = utils._replace_ampersands(source)
        source = utils._replace_ad(source)
        soup = bs4.BeautifulSoup(source, 'lxml')
        for inputfield in soup.find_all('input'):
            type = inputfield.get('type', None) 
            if type == 'password':
                # logger.print('found a password field')
                return True
    # logger.print("no password fields")
    return False


def _ocr_on_json(jspath):
    js = _load_json(jspath)
    if 'ocr' in js:
        logger.print("this site has been ocr'd before")
        return js
    sspath = _get_screenshot_path(jspath)
    stopwords = set(line.strip() for line in open('data/stopwords_en.txt'))
    stopwords |= set(line.strip() for line in open('data/stopwords_www.txt'))
    logger.print("doing ocr")
    ocrtext = ocr.do_ocr(sspath, 'eng')
    ocrtokens = [word for word in ocrtext.lower().split() if word not in stopwords]
    js['ocr'] = ' '.join(ocrtokens)
    with open(jspath, 'w') as f:
        json.dump(js, f, indent=0, sort_keys=True)
    return js


####################
# public functions #
####################


def fetch_urls(query):
    """
    Do a Google search with a given query. Extract all URLs from the response for later processing.

    Arguments
    ---------
    query: str
        string containing keywords separated by whitespace

    Returns
    -------
    urls: set
        the set of URLs returned by Google
    """
    # quote whitespace so that the query can be placeed in a URL.
    query = urllib.parse.quote(query)
    url = 'http://www.google.com/search?q={}'.format(query)
    r = requests.get(url, headers=HEADERS)
    html = r.text
    urls = set()
    for url in GOOGLERX.findall(html):
        if '<' in url or '\\' in url:  # Google highlights search results
            continue
        mld, ps = keywords.split_mld_ps(url)
        domain = mld + '.' + ps
        if domain == 'google.fi' or domain == 'googleusercontent.com':
            continue
        urls.add(url)
    return urls


def extract_domains(url_set, logging=False):
    """
    Extract mail level domains and public suffixes from a set of urls.

    Returns
    -------
    domains : set
        tuples of form (mld, ps)
    """
    domains = set()
    for url in url_set:
        mld, ps = keywords.split_mld_ps(url)
        domains.add((mld, ps))
    logger.print(" domains returned by google:", logging=logging)
    for mld, ps in domains:
        if mld not in STOPMLDS:
            logger.print("{}.{}".format(mld, ps), nots=True, logging=logging)
    return domains


def prominent_domains(js, keyw, domains=set(), extend_search=True):
    """
    Given keywords of a site and domains returned by a google search, check
    which domains are found from the site. Split the result on primary and
    secondary targets.

    Primary target is a domain that is found from the keywords or in the
    domains guesses from the domain.  Secondary target is a domain that is not
    found from the keywords, but appears elsewhere in the site.

    Parameters
    ----------
    js : json object
        contains site data
    keyw : list
        contains site keywords
    domains : set
        set of tuples (mld, ps)
    extend_search : boolean
        whether to look for prominent domains from text and links as well

    Returns
    -------
    prominent : set
        set of string "mld.ps" that either appear in keywords or can be guessed from the keywords
    """

    prominent = set() 
    mld_guesses = keywords.guess_mld(js)
    
    url_tokens = re.split('\W+', (js['starturl'] + ' ' + js['landurl']).lower())
    title_tokens = re.split('\W+', js['title'].lower())

    # logger.print("checking for prominent domains:")
    for mld, ps in domains:
        mld = mld.lower()
        ps = ps.lower()
        # segments = ngrams.segment(mld)
        if mld in keyw:
            logger.print("mld found from keywords: {}.{}".format(mld, ps), nots=True)
            prominent.add('.'.join([mld, ps]))
            # prominent.add((mld, ps))
        elif mld in mld_guesses:
            logger.print("mld found from mld-guessing: {}.{}".format(mld, ps), nots=True)
            prominent.add('.'.join([mld, ps]))
            # prominent.add((mld, ps))
        # elif extend_search and ' '.join(segments) in ' '.join(js['text'].lower().split()) and mld not in STOPMLDS:
        #     logger.print("found by segmentation from text: {}.{}".format(mld, ps), nots=True)
        #     prominent.add('.'.join([mld, ps]))
        # elif all(item in title_tokens for item in segments):
        #     logger.print("found by segmentation from title: {}.{}".format(mld, ps), nots=True)
        #     prominent.add('.'.join([mld, ps]))
        #     # prominent.add((mld, ps))
        elif mld in url_tokens:
            logger.print("mld in url: {}.{}".format(mld, ps), nots=True)
            prominent.add('.'.join([mld, ps]))
            # prominent.add((mld, ps))

    if extend_search:
        link_domains = set(keywords.split_mld_ps(link) for link in utils.extract_urls(js['source']))
        link_domains |= set(keywords.split_mld_ps(link) for link in js['loglinks'])
        # remove mlds that often occur: google, blogger, ... These are STOPMLDS
        link_domains = set((mld, ps) for (mld, ps) in link_domains if mld not in STOPMLDS)

        for dom in domains:
            if dom in link_domains and dom not in prominent:
                logger.print("mld found from links: {}.{}".format(*dom), nots=True)
                prominent.add('.'.join(dom))
                # prominent.add(dom)

    return prominent



def build_query_domains(js):

    google_domains = set() 

    # google search with mld_guesses
    mld_guesses = keywords.guess_mld(js)
    if mld_guesses:
        mld_guess_str = ' '.join(['"{}"'.format(x) for x in  mld_guesses])
        logger.print("mld guesses: {}".format(mld_guess_str))
        urls = fetch_urls(mld_guess_str)
        google_domains |= extract_domains(urls)
    else:
        logger.print("no mld guesses")

    langid = 'en'
    # langid = goslate.Goslate().detect(js['text'])
    logger.print("langid: {}".format(langid))
    # google search with keywords
    keyw = keywords.keywords(js, max_count=MAXCOUNT, boost=True, langid=langid) 
    # keyw = keywords.keywords(js, max_count=MAXCOUNT, augment=False) 
    keywstring = ' '.join(keyw)
    if keywstring:
        logger.print("keywords: {}".format(keywstring))
        urls = fetch_urls(keywstring)
        google_domains |= extract_domains(urls)
    else:
        logger.print("no keywords")

    # google search with augmented keywords
    augkeyw = keywords.keywords(js, max_count=MAXCOUNT, augment=True, langid=langid) 
    augkeywstring = ' '.join(augkeyw)
    if augkeywstring != keywstring:
        logger.print("augmented keywords: {}".format(augkeywstring))
        urls = fetch_urls(augkeywstring)
        google_domains |= extract_domains(urls)
        
    return google_domains, keyw, augkeyw



def is_phish(js={}, jspath='', url=''):
    """
    Decide whether a website is phishing using its keywords and a Google search
    based on those.

    Parameters
    ----------
    js: dict, optional
        contains site data
    jspath: str, optional
        path to a json file with the site data
    url: str, optional
        url of a website

    Returns
    -------
    rank: int
        * -1 = unresolved, fetching a website failed
        *  0 = not phish
        *  1 = suspicious
        *  2 = phish
    description: str
        above description for the numerical values
    targets: set
        potential targets in case of 1 or 2, empty when rank is -1, 0
    """

    # load json
    if url:
        fetcher = website_fetcher.WebsiteFetcher(logging=True, confirm=True) 
        # sitedata, screenshot = fetcher.fetch_sitedata_and_screenshot(url)
        # js = sitedata
        jspath, sspath = fetcher.fetch_and_save_data(url)
        js = _load_json(jspath)
    elif jspath:
        js = _load_json(jspath)
        sspath = _get_screenshot_path(jspath)
    if not js:
        logger.print("json file is empty; cannot continue")
        return -1, 'unresolved', set()

    logger.print("siteid: {}".format(js['siteid']))
    landurl = js['landurl']
    # logger.print("landing url: {}".format(landurl[:80]))
    logger.print("loglinks:")
    for link in js['loglinks']:
        logger.print(link, nots=True)


    mld, ps = keywords.split_mld_ps(landurl)
    # logger.print("main level domain: {}".format(mld))

    # 1. TESTS
    # password?
    pw = _asks_password(js)
    if pw:
        logger.print("asks for a password")
    else:
        logger.print("does not ask for a password")

    google_domains, keyw, augkeyw =  build_query_domains(js)
    logger.print("query-domains:")
    for dom in google_domains:
        logger.print('.'.join(dom), nots=True)

    if pw:
        # logger.print("asks for a password") 
        prominent_domains_found = prominent_domains(js, keyw + augkeyw, google_domains, extend_search=False)
        mld_in_gmld = (mld, ps) in google_domains
        if mld_in_gmld:
            logger.print("a query-mld matches with site-mld -> not phish")
            return 0, 'not phish', set()
        else:
            logger.print("no query-mld matches with site-mld")
            if prominent_domains_found:
                logger.print("prominent domains found -> phish")
                return 2, 'phish', prominent_domains_found 
            else:
                logger.print("did not find prominent mlds")
                logger.print("doing ocr")
                js = _ocr_on_json(jspath)
                ocrkeyw = keywords.keywords(js, max_count=MAXCOUNT, augment=True, use_ocr=True) 
                keywstring = ' '.join(ocrkeyw)
                logger.print("ocr keywords: {}".format(keywstring))
                urls = fetch_urls(keywstring)
                google_domains = extract_domains(urls)
                prominent_domains_found = prominent_domains(js, ocrkeyw, google_domains, extend_search=True)
                mld_in_gmld = (mld, ps) in google_domains
                if mld_in_gmld:
                    logger.print("a query-mld matches with site-mld -> not phish")
                    return 0, 'not phish', set()
                else:
                    logger.print("no query-mld matches with site-mld")
                    if prominent_domains_found:
                        logger.print("prominent domains found -> phish")
                        return 2, 'phish', prominent_domains_found 
                    else:
                        logger.print("prominent domains not found -> possibly phish")
                        return 1, 'suspicious', set()
    else:
        # logger.print("password not found")
        prominent_domains_found = prominent_domains(js, keyw, google_domains, extend_search=False)
        mld_in_gmld = (mld, ps) in google_domains
        if mld_in_gmld:
            logger.print("a query-mld matches with site-mld -> not phish")
            return 0, 'not phish', set()
        else:
            logger.print("no query-mld matches with site-mld")
            if prominent_domains_found:
                logger.print("prominent domains found -> suspicious")
                return 1, 'suspicious', prominent_domains_found 
            else:
                logger.print("prominent domains not found -> not phish")
                return 0, 'not phish', set()


                # logger.print("did not find prominent mlds")
                # logger.print("doing ocr")
                # js = _ocr_on_json(jspath)
                # ocrkeyw = keywords.keywords(js, max_count=MAXCOUNT, augment=True, use_ocr=True) 
                # keywstring = ' '.join(ocrkeyw)
                # logger.print("ocr keywords: {}".format(keywstring))
                # urls = fetch_urls(keywstring)
                # google_domains = extract_domains(urls)
                # prominent_domains_found = prominent_domains(js, ocrkeyw, google_domains, extend_search=True)
                # mld_in_gmld = (mld, ps) in google_domains
                # if mld_in_gmld:
                #     logger.print("a query-mld matches with site-mld -> not phish")
                #     return 0, 'not phish', set()
                # else:
                #     logger.print("no query-mld matches with site-mld")
                #     if prominent_domains_found:
                #         logger.print("prominent domains found -> suspicious")
                #         return 1, 'suspicious', prominent_domains_found 
                #     else:
                #         logger.print("prominent domains not found -> not phish")
                #         return 0, 'not phish', set()





def is_phish2(ws=None):
    """
    Decide whether a website is phishing using its keywords and a Google search
    based on those.

    Parameters
    ----------
    ws: website object or None
        contains all downloaded information about the site 

    Returns
    -------
    rank: int
        * -1 = unresolved, fetching a website failed
        *  0 = not phish
        *  1 = suspicious
        *  2 = phish
    description: str
        above description for the numerical values
    targets: set
        potential targets in case of 1 or 2, empty when rank is -1, 0
    """

    if ws is None:
        # logger.print("website object is None is empty; cannot continue")
        return -1, 'unresolved', set()

    # logger.print("siteid: {}".format(ws.siteid))
    # logger.print("landing url: {}".format(ws.landurl[:80]))
    mld, ps = keywords.split_mld_ps(ws.landurl)

    # 1. TESTS
    # password?
    pw = ws.has_password
    # if pw:
    #     logger.print("asks for a password")
    # else:
    #     logger.print("does not ask for a password")

    google_domains, keyw, augkeyw =  extract_domains(ws.js['urls_keywords'] + ws.js['urls_augmented']), ws.keywords(), ws.augmented_keywords() 
    # logger.print("query-domains:")
    # for dom in google_domains:
    #     logger.print('.'.join(dom), nots=True)

    if pw:
        # logger.print("password found") 
        prominent_domains_found = prominent_domains(ws.js, keyw + augkeyw, google_domains, extend_search=False)
        mld_in_gmld = (mld, ps) in google_domains
        if mld_in_gmld:
            # logger.print("a query-mld matches with site-mld -> not phish")
            # return 0
            return 0, 'not phish', set()
        else:
            # logger.print("no query-mld matches with site-mld")
            if prominent_domains_found:
                # logger.print("prominent domains found -> phish")
                # return 2 
                return 2, 'phish', prominent_domains_found 
            else:
                # logger.print("did not find prominent mlds")
                # logger.print("doing ocr")
                ocrkeyw = keywords.keywords(ws.js, max_count=MAXCOUNT, augment=True, use_ocr=True) 
                keywstring = ' '.join(ocrkeyw)
                # logger.print("ocr keywords: {}".format(keywstring))
                urls = ws.js['urls_ocr']
                google_domains = extract_domains(urls)
                prominent_domains_found = prominent_domains(ws.js, ocrkeyw, google_domains, extend_search=True)
                mld_in_gmld = (mld, ps) in google_domains
                if mld_in_gmld:
                    # logger.print("a query-mld matches with site-mld -> not phish")
                    # return 0
                    return 0, 'not phish', set()
                else:
                    # logger.print("no query-mld matches with site-mld")
                    if prominent_domains_found:
                        # logger.print("prominent domains found -> phish")
                        # return 2 
                        return 2, 'phish', prominent_domains_found 
                    else:
                        # logger.print("prominent domains not found -> possibly phish")
                        # return 1
                        return 1, 'suspicious', set()
    else:
        # logger.print("password not found")
        prominent_domains_found = prominent_domains(ws.js, keyw, google_domains, extend_search=False)
        mld_in_gmld = (mld, ps) in google_domains
        if mld_in_gmld:
            # logger.print("a query-mld matches with site-mld -> not phish")
            # return 0
            return 0, 'not phish', set()
        else:
            # logger.print("no query-mld matches with site-mld")
            if prominent_domains_found:
                # logger.print("prominent domains found -> suspicious")
                # return 1 
                return 1, 'suspicious', prominent_domains_found 
            else:
                # logger.print("prominent domains not found -> not phish")
                # return 0
                return 0, 'not phish', set()


                # logger.print("did not find prominent mlds")
                # logger.print("doing ocr")
                # js = _ocr_on_json(jspath)
                # ocrkeyw = keywords.keywords(js, max_count=MAXCOUNT, augment=True, use_ocr=True) 
                # keywstring = ' '.join(ocrkeyw)
                # logger.print("ocr keywords: {}".format(keywstring))
                # urls = fetch_urls(keywstring)
                # google_domains = extract_domains(urls)
                # prominent_domains_found = prominent_domains(js, ocrkeyw, google_domains, extend_search=True)
                # mld_in_gmld = (mld, ps) in google_domains
                # if mld_in_gmld:
                #     logger.print("a query-mld matches with site-mld -> not phish")
                #     return 0, 'not phish', set()
                # else:
                #     logger.print("no query-mld matches with site-mld")
                #     if prominent_domains_found:
                #         logger.print("prominent domains found -> suspicious")
                #         return 1, 'suspicious', prominent_domains_found 
                #     else:
                #         logger.print("prominent domains not found -> not phish")
                #         return 0, 'not phish', set()



########
# main #
########

if __name__ == '__main__':
    usage = 'usage:\n\tpython {0} --url <url>\n\tpython {0} --json <jspath>'.format(__file__)
    if not sys.argv[1:]:
        print(usage)
    else:
        logger.activate()
        if sys.argv[1] == '--url':
            url = sys.argv[2]
            print(is_phish(url=url))
        elif sys.argv[1] == '--json':
            jspath = sys.argv[2]
            print(is_phish(jspath=jspath))
        else:
            print(sys.argv[1])
            print(usage)
        print()
