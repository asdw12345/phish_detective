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
