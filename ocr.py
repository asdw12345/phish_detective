
# Author:   Kalle Saari kalle.saari@aalto.fi
# Copyright 2015 Secure Systems Group, Aalto University, https://se-sy.org/
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import os
import re
import subprocess
import sys
import tempfile
import threading
import simple_logger

logger = simple_logger.SimpleLogger()


def fix_langid(langid):
    d = {}
    d['en'] = 'eng'
    d['fi'] = 'fin'
    d['fr'] = 'fra'
    # if langid is already in a known length-3 form, do nothing.
    if langid in d.values():
        return langid
    else:
        return d.get(langid, 'eng')


def helper(sspath, imagepath, textpath, channel, inverted, lang='eng'):
    return_code = subprocess.call(['python', 'ocr_helper.py', sspath, imagepath, str(channel), str(inverted)])
    # logger.print("running command:\n" + 'tesseract ' + imagepath + ' ' + textpath + ' -l ' + lang)
    os.system('tesseract ' + imagepath + ' ' + textpath + ' -l ' + lang)


def do_ocr(sspath, langid):
    """
    
    Arguments
    ---------
    sspath : str
        path to screenshot
    langid : str
        3-letter language code

    Returns
    -------
    ocrtext : str
        ocr text extracted with OCR, lowercased and 1- and 2-letter tokens filtered out
    """
    lang = fix_langid(langid)
    print('using language for OCR: {}'.format(lang))
    worker_threads = set()
    imagepath = 6 * ['']
    textpath = 6 * ['']
    for n in range(6):
        channel, inverted = n // 2, n % 2
        # logger.print('channel = {} and inverted = {}'.format(channel, inverted))
        imagepath[n] = tempfile.NamedTemporaryFile(suffix='figure_{}{}.png'.format(channel, inverted))
        textpath[n] = tempfile.NamedTemporaryFile(suffix='out_{}{}'.format(channel, inverted))
        worker = threading.Thread(target=helper, args=(sspath, imagepath[n].name, textpath[n].name, channel, inverted, lang))
        worker.setDaemon(True)
        worker.start()
        worker_threads.add(worker)
    for t in worker_threads:
        t.join()
    ocrtext = ''
    for n in range(6):
        ocrtext += '\n' + re.sub('\s+', ' ', open(textpath[n].name + ".txt").read())

    tokenstring = ocrtext
    # replace digits with space
    tokenstring = re.sub('\d+', ' ', tokenstring)
    # merge words separated by hyphens, e.g., e-mail
    tokenstring = re.sub('\-+', '', tokenstring)
    # replace non-alphanumeric and  non-underscore symbols with space
    tokenstring = re.sub('\W+', ' ', tokenstring)
    # replace underscore with space
    tokenstring = re.sub('_+', ' ', tokenstring)
    # split on to spaces
    tokens = re.split('\s+', tokenstring)
    # ignore tokens with less than 3 characters
    tokens = [token.lower() for token in tokens if len(token) >= 3]
    # check token against norvig's ngram words
    # tokens = [token for token in tokens if token in norvig]

    return ' '.join(tokens)


if __name__ == '__main__':
    usage = __file__ + " <screenshot.png> <langid-3>"
    if len(sys.argv) == 1:
        print(usage)
    else:
        sspath = sys.argv[1]
        if len(sys.argv) >= 3:
            lang = sys.argv[2]
        else:
            lang = 'eng'
        # logger.print('using language {} for ocr'.format(lang))
        logger.print(do_ocr(sspath, lang))

