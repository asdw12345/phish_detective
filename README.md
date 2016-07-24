# phish_detective
A collection of scripts to download meta data from a website, extract keywords from it, and determine whether it is a phishing site.

## Usage

Let `url` be a URL of a website that is suspected to be phishing. Such URLs can be found, e.g., from http://www.phishtank.com

Then the simples way to use these scripts is to run

```
python phish_detective.py --url url
```


## Dependencies

* `tesseract` for Optical Character Recognition.
* At the time of writing, the Firefox driver in `selenium` does not work in my
  Mac OS X 10.11.4 with the most recent version (47.0) of Firefox.
  However, downgrading Firefox to version 45.0.2 solves the problem.


## Todo

* Clean the `requirements.txt` files, which is currently encompassing the full
  Anaconda distribution and them some.

