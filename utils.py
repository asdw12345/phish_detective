import json
import re

import requests
import subprocess

from bs4 import BeautifulSoup
from collections import Counter, defaultdict
from glob import glob
from os.path import join, splitext
from urllib.parse import urlparse
import urllib
import goslate

# https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
stopwords = defaultdict(set)
for fname in glob('data/stopwords/stop-words/*.txt'):
    lang = fname[-6:-4]
    # print(lang, end=' ')
    words = [w.strip() for w in open(fname, encoding='utf8').readlines()]
    stopwords[lang].update(set(words))


def _replace_ampersands(html):
    """Replace ampersand symbols in html"""
    html = re.sub('&amp;', '&', html, flags=re.DOTALL)
    html = re.sub('&quot;', '"', html, flags=re.DOTALL)
    # html = re.sub('&amp;', ' ', html, flags=re.DOTALL)
    # html = re.sub('&quot;', ' ', html, flags=re.DOTALL)
    html = re.sub('&lt;', '\<', html)
    html = re.sub('&gt;', '\>', html)
    return html


def _replace_ad(html):
    """Remove symbols 'a0:' and 'a2:'. 'a0:' stands for 'nobreak'"""
    # opening tag
    html = re.sub('\<\s*a\d\:', '<', html)
    # closing tag
    html = re.sub('\</\s*a\d\:', '</', html)
    return html


def _remove_tags(html):
    """Remove tags, ie anything like <...>, from input html string."""
    html = _replace_ampersands(html)
    html = re.sub('\<sup\>|\</sup\>', '', html)
    html = re.sub('\<sub\>|\</sub\>', '', html)
    tagrx = re.compile('\<.+?\>', flags=re.DOTALL)
    html = tagrx.sub(' ', html)
    return html


def get_langid(js, use_bow=False, use_ocr=False, path=None):
    if use_ocr:
        c = bow(js, use_ocr=True, path=path)
        text = ' '.join(c.keys())
    elif use_bow:
        c = bow(js, use_ocr=False, path=path)
        text = ' '.join(c.keys())
    else:
        text = js['title'] + ' ' + get_text(js, show_grouping=False)
    return langid.classify(text)


def translate(js, text=None, skip_title=False):
    """
    Translate text using Google translator.
    """
    gs = goslate.Goslate()
    if not text:
        text = '\n'.join(js_to_lines(js, skip_title=skip_title))
    return gs.translate(text, 'en')


def remove_urls(text):
    urlrx = re.compile("""http[s]?://[^\s'"]*""")
    text = urlrx.sub(' ', text)
    return text


def html_to_lines(html, skip_title=False):
    html = _replace_ampersands(html)
    html = _replace_ad(html)
    soup = BeautifulSoup(html)
    # remove <script> ... </script>
    [x.extract() for x in soup.find_all('script')]
    # remove <noscript> ... </noscript>
    [x.extract() for x in soup.find_all('noscript')]
    # remove <style> ... </style>
    [x.extract() for x in soup.find_all('style')]
    # remove <option> 
    [x.extract() for x in soup.find_all('select')]
    # text = soup.get_text(separator=' ', strip=True)
    if skip_title:
        try:
            [x.extract() for x in soup.find('title')]
        except:
            pass
    text = re.sub('\n+', '\n', soup.get_text())
    lines = text.split('\n')
    # # remove non-alphanumerics
    # lines = [re.sub('\W+', ' ', line) for line in lines]
    # # remove numbers
    # lines = [re.sub('\d+', ' ', line) for line in lines]
    # # remove underscores
    # lines = [re.sub('_+', ' ', line) for line in lines]
    # # remove extra white space
    lines = [re.sub('\s+', ' ', line) for line in lines]
    # img tag
    for img in soup.find_all('img'):
        try:
            alt = img['alt']
        except:
            alt = ''
        lines.append(alt)
        try:
            title = img['title']
        except:
            title = ''
        lines.append(title)
    # a tag
    for a in soup.find_all('a'):
        try:
            title = a['title']
        except:
            title = ''
        lines.append(title)
    # input tag
    for inp in soup.find_all('input'):
        try:
            title = inp['title']
        except:
            title = ''
        lines.append(title)
    lines = [remove_urls(line) for line in lines if line.strip()]
    lines = [line.strip() for line in lines if line.strip()]
    return lines


def js_to_lines(js, skip_title=False):
    html = js['source']
    lines = html_to_lines(html, skip_title)
    for html in js.get('external_source', {}).values():
        for line in html_to_lines(html):
            if line not in lines:
                lines.append(line)
    # remove duplicate lines, which might occur if html source are duplicates
    # lines = sorted(set(lines))
    return lines


def js_to_text(js, skip_title=False):
    return ' '.join(js_to_lines(js, skip_title))


def prune_url(url):
    """
    Remove protocol and file extension from url
    """
    parsed = urlparse(url) 
    netloc = parsed.netloc
    path = splitext(parsed.path)[0]
    return netloc + path


def tokenize(text, use_segmentation=False, lowercase=True, ngrams=[1]):
    from ngrams.ngrams import segment
    if lowercase:
        text = text.lower()
    # split on to spaces
    tokens = re.split('\s+', text, flags=re.UNICODE)
    # split on digits
    # digitrx = re.compile('\d+', flags=re.UNICODE)
    # tokens = [part.strip() for token in tokens for part in digitrx.split(token)]
    # split (and merge) words separated by hyphens
    hyphenrx = re.compile('\-+', flags=re.UNICODE)
    tokens = [part.strip() for token in tokens for part in hyphenrx.split(token) if token !='e-mail']
    # split on non-alphanumeric and underscore
    notalpharx = re.compile('\W+', flags=re.UNICODE)
    tokens = [part.strip() for token in tokens for part in notalpharx.split(token)]
    # split on underscore
    underscorerx = re.compile('_+', flags=re.UNICODE)
    tokens = [part.strip() for token in tokens for part in underscorerx.split(token)]
    # ignore 0- and 1-letter tokens
    tokens = [token for token in tokens if len(token) > 1] 
    if use_segmentation:
        tokens = [part for token in tokens for part in segment(token)]
    all_tokens = []
    for n in ngrams:
        for i in range(len(tokens) - n + 1):
            all_tokens.append(' '.join(tokens[i:i + n]))
    return all_tokens


def find_copyright(js):
    """
    Find copyright information and return set of word extracted from it
    """
    sources = [source for source in js.get('external_source', {}).values()]
    sources.append(js['source'])
    copyrights = set()
    for source in sources:
        source = _replace_ampersands(source)
        source = _replace_ad(source)
        soup = BeautifulSoup(source)
        # remove <script> ... </script>
        [x.extract() for x in soup.find_all('script')]
        # remove <noscript> ... </noscript>
        [x.extract() for x in soup.find_all('noscript')]
        # remove <style> ... </style>
        [x.extract() for x in soup.find_all('style')]
        # remove <option> 
        [x.extract() for x in soup.find_all('select')]
        for copyright in soup.find_all(text=re.compile('©|[Cc]opyright')):
            # print(copyright)
            copyright = _remove_tags(copyright)
            # copyright = re.sub('\W+', '', copyright)
            copyright = re.sub('\d+', '', copyright)
            copyright = tokenize(copyright) 
            copyrights |= set(copyright)
    # stopwords = set(['all', 'rights', 'reserved', 'copyright', 'co', 'inc', 'or', 'its', 'affiliates'])
    # copyrights.difference_update(stopwords)
    return copyrights


def bow(js, type=None, remove_stopwords=True, use_ocr=False, path=None):
    if use_ocr:
        text = tesseract(path)
    else:
        text = ' '.join(js_to_lines(js))
    tokens = tokenize(text)
    if remove_stopwords:
        lang, conf = get_langid(js)
        if conf > 0.2 and lang in stopwords:
            sw = stopwords[lang]
        else:
            sw = set()
        tokens = [token for token in tokens if token not in sw]
    return Counter(tokens)


def get_langid(js, use_bow=False, use_ocr=False, path=None):
    import langid
    if use_ocr:
        c = bow(js, use_ocr=True, path=path)
        text = ' '.join(c.keys())
    elif use_bow:
        c = bow(js, use_ocr=False, path=path)
        text = ' '.join(c.keys())
    else:
        text = ' '.join(js_to_lines(js))
    return langid.classify(text)


def group_headers(js):
    """
    Extract headers from all available sources and return a dictionary build from them.
    """
    sources = [source for source in js.get('external_source', {}).values()]
    sources.append(js['source'])
    html = ' '.join(sources)
    soup = BeautifulSoup(html)
    headers = defaultdict(list)
    for h in soup.find_all('h1'):
        header = h.text.strip()
        if header:
            headers['h1'].append(header)
    for h in soup.find_all('h2'):
        header = h.text.strip()
        if header:
            headers['h2'].append(header)
    for h in soup.find_all('h3'):
        header = h.text.strip()
        if header:
            headers['h3'].append(header)
    for h in soup.find_all('h4'):
        header = h.text.strip()
        if header:
            headers['h4'].append(header)
    for h in soup.find_all('h5'):
        header = h.text.strip()
        if header:
            headers['h5'].append(header)
    for h in soup.find_all('h6'):
        header = h.text.strip()
        if header:
            headers['h6'].append(header)
    return headers


def extract_urls(html):
    """Try to find all embedded links, whether external or internal"""
    # substitute real html symbols
    html = _replace_ampersands(html)

    urls = set()

    hrefrx = re.compile("""href\s*\=\s*['"](.*?)['"]""")
    for url in re.findall(hrefrx, html):
        urls.add(str(url))

    srcrx = re.compile("""src\s*\=\s*['"](.*?)['"]""")
    for url in re.findall(srcrx, html):
        urls.add(str(url))

    html = re.sub('%20', ' ', html, flags=re.DOTALL)
    # extract URLs that are not surrounded by quotes
    urlrx = re.compile("""[^'"](http[s]?://[\.a-zA-Z0-9/]+?)\s""")
    # urlrx = re.compile("""[^'"](http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)\s""", flags=re.DOTALL)
    for url in re.findall(urlrx, html):
        urls.add(str(url))
    
    # extract URLs that are surrounded by quotes
    # remove whitespace
    html = re.sub('\s+', '', html)
    urlrx = re.compile("'(http[s]?://[\.a-zA-Z0-9/]+?)'", flags=re.DOTALL)
    urlrx = re.compile('"(http[s]?://[\.a-zA-Z0-9/]+?)"', flags=re.DOTALL)
    # urlrx = re.compile("""['" ](http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+?)['" ]""", flags=re.DOTALL)
    for url in re.findall(urlrx, html):
        urls.add(url)

    # remove empty string if exists
    try:
        urls.remove('')
    except KeyError:
        pass

    return sorted(urls)



def js_to_urls(js, skip_start=False):
    if skip_start:
        urls = []
    else:
        urls = [js['starturl'], js['landurl']]
    sources = [source for source in js.get('external_source', {}).values()]
    sources.append(js['source'])
    html = ' '.join(sources)
    urls += extract_urls(html)
    urls += js['loglinks']
    return sorted(set(urls))



def registered_domain(url):
    """
    For url of form http://xxx.yyy.zzz.mld.ps/path, return
        (mld, mld.ps)
    """
    with open('data/public_suffix_list.dat', 'r') as f:
        tld = set(line.strip() for line in f)
    # next covers both google.com and http://google.com
    parsed = urlparse(url)
    hostname = parsed.netloc or parsed.path 
    tokens = hostname.split('.')
    for i in range(len(tokens)):
        suffix = '.'.join(tokens[i:])
        if suffix in tld:
            if i == 0:
                return None, hostname
            else:
                return tokens[i - 1], '.'.join(tokens[i - 1:])
    # last resort, try something
    return '.'.join(tokens[:-1]), '.'.join(tokens) 


def do_ocr(path, channel, inverted):
    image_path = join(path, 'figure_{}{}.png'.format(channel, inverted))
    text_path = join(path,'out_{}{}'.format(channel, inverted))
    return_code = subprocess.call(['python', 'process_image.py', path, str(channel), str(inverted)])
    return_code = subprocess.call(['tesseract', image_path, text_path])


def tesseract(path):
    from threading import Thread
    ocr_text_path = join(path, "ocr_text.txt")
    worker_threads = set()
    for n in range(6):
        channel, inverted = n // 2, n % 2
        worker = Thread(target=do_ocr, args=(path, channel, inverted))
        worker.setDaemon(True)
        worker.start()
        worker_threads.add(worker)
    for t in worker_threads:
        t.join()
    ocr_lines = []
    for n in range(6):
        channel, inverted = n // 2, n % 2
        text_path = join(path,'out_{}{}.txt'.format(channel, inverted))
        text = open(text_path).read()
        lines = text.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        ocr_lines += lines
    with open(ocr_text_path, 'w') as f:
        for line in ocr_lines:
            f.write(line + '\n')
    # c = Counter(token for line in ocr_lines for token in re.split('\s+', line))
    # result = []
    # for line in ocr_lines:
    #     cleaned = ''
    #     for token in re.split('\s+', line):
    #         if c[token] > 1:
    #             cleaned += token + ' '
    #     cleaned = cleaned.strip()
    #     if cleaned not in result:
    #         result.append(cleaned)
    # return '\n'.join(result)




def extract_keywords(js, path=None, use_source=False, use_ocr=False, use_log=False):
    """
    Parameters
    ----------
    js : json
        json object containing the site data
    path : str
        path to the site's directory in disk
    usr_ocr : boolean
        Extract text using ocr
    use_log : boolean
        Use urls from the Firefox log. Default is to only use start and landing urls.

    Return
    ------
    tuple in which first entry comes fron url and title; second from url and text;
    third from title and text; fourth from copyright.
    """
    urls = set()
    login_stopwords = set(['com', 'php', 'log', 'in', 'login', 'sign', 'signin'])

    urls.add(js['starturl'])
    urls.add(js['landurl'])
    # extract links
    if use_source:
        html = js['source']
        urls |= set(url for url in extract_urls(html))
        for html in js.get('external_source', {}).values():
            urls |= set(url for url in extract_urls(html))
    if use_log:
        urls |= set(url for url in js['loglinks'])

    urls = set(prune_url(url) for url in urls)
    urltokens = set(token for url in urls for token in tokenize(url, use_segmentation=True))
    urltokens -= login_stopwords 

    # extract title
    title = js['title'] 
    titletokens = set(tokenize(title, use_segmentation=False))
    titletokens -= login_stopwords

    # extract text from remaining sources
    text = ' '.join(js_to_lines(js, skip_title=True))
    if use_ocr:
        text += ' ' + tesseract(path)
    texttokens = set(tokenize(text, use_segmentation=False))
    texttokens -= login_stopwords

    url_and_title = set.intersection(urltokens, titletokens)
    text_and_title = set.intersection(texttokens, titletokens)
    url_and_text = set.intersection(urltokens, texttokens)

    copyrights = find_copyright(js)
    copyrights = set(re.sub('\d+|©', '', cr).strip() for cr in copyrights)
    # print('copyrights:', end=' ')
    # print(copyrights)
    keywords = {}
    keywords['url_title'] = url_and_title
    keywords['text_title'] = text_and_title
    keywords['url_text'] = url_and_text
    keywords['copyrights'] = copyrights 

    # mainlevel domains
    mlds = set()
    for url in js['loglinks']:
        mlds.add(registered_domain(url)[0])
    mlds -= set([registered_domain(js['starturl'])[0]])
    mlds -= set([registered_domain(js['landurl'])[0]])
    mlds -= set(['mozilla'])
    mlds -= set(['jquery'])
    mlds -= set(['digicert'])
    keywords['mlds'] = mlds

    return keywords 



def google(keywords, js):
    """
    keywords is a string of keywords
    """
    # first build html dump
    html_dump = js['source']
    for html in js.get('external_source', {}).values():
        html_dump += html 
    for url in js.get('loglinks', []):
        html_dump += url
    html_dump = html_dump.lower()

    targets = set() 
    headers = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0',}
    # googlerx = re.compile('(http[s]?[^\&]*)')  # /url?q=https://fr.wikipedia.org/wiki/La_Banque_postale&sa=U&ei=Zn...
    googlerx = re.compile('http[s]?://.*?/')
    query = urllib.parse.quote(keywords)
    url = 'http://www.google.com/search?q={}'.format(query)
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.content)

    for a in soup.find_all('a'):
        if 'href' in a.attrs:
            # print(url)
            href = a['href']
            li = googlerx.findall(href)
            # print(li)
            if len(li) == 2:
                url = li[1]
                mld, rd = registered_domain(url)
                if mld in html_dump:
                    targets.add(rd)
    return targets


def google_wiki(keyword, langid='en', js={}):
    """Google query targets, output if English wikipedia entry is found"""
    targets = []
    headers = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0',}
    googlerx = re.compile('(http[s]?[^\&]*)')  # /url?q=https://fr.wikipedia.org/wiki/La_Banque_postale&sa=U&ei=Zn...
    infoboxrx = re.compile('infobox')
    domainrx = re.compile('^[a-zA-Z\-]+\.([a-zA-Z\-]+\.)*[a-zA-Z\-]+$')
    # query = 'http://www.google.com/search?q=wikipedia%20{}%20{}'.format(langid, keyword)
    query = 'http://www.google.com/search?q=wikipedia%20{}'.format(keyword)
    r = requests.get(query, headers=headers)
    soup = BeautifulSoup(r.content)
    keywords = extract_keywords(js)
    # phish_tokens = set([word for li in keywords for word in li])
    # print(phish_tokens)

    for a in soup.find_all('a'):
        search = googlerx.search(a.get('href', ''))
        if not search:
            continue
        url = search.groups()[0]
        mld, rd = registered_domain(url)
        if rd == 'wikipedia.org' and '#' not in url:
        # if '.wikipedia.org' in url and '#' not in url:
        # if url.startswith('https://{}.wikipedia.org'.format(langid)) and '#' not in url:
            wikiurl = url
            r = requests.get(url)
            html = str(r.content)
            wikisoup = BeautifulSoup(r.content)
            title = wikisoup.find(id="firstHeading")
            title = title.text
            if not title or keyword not in title.lower():
                continue
            print(wikiurl)
            infobox = wikisoup.find(class_=infoboxrx)
            if infobox:
                for anchor in infobox.find_all('a'):
                    if 'href' in anchor.attrs:
                        targeturl = anchor['href']
                        # is the link internal
                        if targeturl.startswith('/'):
                            continue
                        reg_domain = registered_domain(targeturl)[1]
                        if reg_domain:
                            t = (title, reg_domain, wikiurl)
                            print(reg_domain)
                            targets.append(t)
            external_links = wikisoup.find_all('a', class_="external text")
            external_domains = set()
            for anchor in external_links.find_all('a'):
                if 'href' in anchor.attrs:
                    targeturl = anchor['href']
                    # is the link internal
                    if targeturl.startswith('/'):
                        continue
                    reg_domain = registered_domain(targeturl)[1]
                    if reg_domain:
                        external_domains.add((title, reg_domain, wiki_url))
    return targets, sorted(external_domains)


if __name__ == '__main__':
    targets = google_wiki('hipercard', 'pt')
    for t in targets:
        print("{}\t{}\t{}".format(*t))
    # for fname in glob('data/new_new_phish/*/sitedata.json'):
    # cnt = 0
    # langs = []
    # for i, path in enumerate(glob('data/phish_combined/*')):
    #     js = json.load(open(join(path, 'sitedata.json')))
    #     _ = extract_keywords(js, path, use_log=False)
    #     print()

        # text = js_to_text(js)
        # lang, conf = langid.classify(text[:100].lower())
        # if conf < 0.5:
            # print(fname)
            # print('\t' + text[:100])
            # print('\t' + lang + ' '+ str(conf))
            # print()
            # cnt += 1
        # else:
            # langs.append(lang)
    # counter = Counter(langs)
    # for lang, freq in counter.most_common(n=None):
    #     print("{} {}".format(lang, freq))
    # print("{} {}".format(i, cnt))
