import datetime
import re
import sys

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

class SimpleLogger(object):

    tablength = len("2015-08-24 12:57:52     ")

    def __init__(self, active=True, info='', linewidth=100):
        self.active = active
        self.output = None
        self.linewidth = linewidth
        self.info = info

    def split_to_lines(self, text):
        tokens = re.split('\s+', text)
        lines = []
        newline = []
        for token in tokens:
            token = token.strip()
            if not token:
                continue
            if len(' '.join(newline) + ' ' + token) >= self.linewidth:
                if newline:
                    lines.append(' '.join(newline))
                    newline = [token]
                else:
                    lines.append(token)
                    newline = []
            else:
                newline.append(token)
        if newline:
            lines.append(' '.join(newline))
        return lines

    def set_output(self, fname=None):
        if fname:
            self.output = open(fname, 'w')
        else:
            self.output = sys.stdout

    def print(self, message='', argument=None, nots=False, logging=True):
        if not self.active or not logging:
            return None
        if not isinstance(message, str):
            message = str(message)
        now = datetime.datetime.now()
        datestr = now.strftime('%Y-%m-%d %H:%M:%S')
        if self.info:
            datestr += ' ' + self.info + ' '
        if nots:  # no time, print string of whitespaces insted
            datestr = len(datestr) * ' '
        if argument is None:
            text = ''
        elif isinstance(argument, str):
            text = argument
        else:
            text = repr(argument)
        completemsg = ('\n' + self.tablength * ' ').join(self.split_to_lines(message + ' ' + text))
        print("{}\t{}".format(datestr, completemsg), file=self.output)

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False
