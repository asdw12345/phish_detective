
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


import sys
import numpy as np
import matplotlib.pyplot as plt
from os.path import join

screenshotpath = sys.argv[1]
imagepath = sys.argv[2]
channel = int(sys.argv[3])
inverted = int(sys.argv[4])
I = plt.imread(screenshotpath) 
if inverted:
    cmap = plt.cm.binary_r
else:
    cmap = plt.cm.binary
J = I[:, :, channel]
fig = plt.figure()
# Reduce the height of the image size to 800.
# Full screen is about 1000.
# Long webpage can yield an image of height 3000,
# which reduces the quality of OCR.
# Take 400 from top and 300 from bottom of the page.
plt.imshow(np.vstack([I[:300, :, channel], I[-300:, :, channel]]), cmap=cmap)
# plt.imshow(I[:, :, channel], cmap=cmap)
plt.axis('off')
F = plt.gcf()
F.savefig(imagepath, dpi=400, bbox_inches='tight')
