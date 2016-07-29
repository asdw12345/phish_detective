# Phish Detective

A collection of scripts to download meta data from a website, extract keywords from it, and determine whether it is a phishing site. 

This code was written in collaboration with Samuel Marchal for a research project at Aalto University, Finland, under the supervision of Professor N. Asokan. See

[S. Marchal, K. Saari, N. Singh, N. Asokan. Know Your Phish: Novel Techniques for Detecting Phishing Sites and their Targets](http://arxiv.org/abs/1510.06501)


## Usage


Then the simplest way to use these scripts is to run

```
python phish_detective.py --url <url of suspected phishing website>
```

Such sites can be foung, e.g., in http://www.phishtank.com.



## Installation and use

The installation relies on the Anaconda Python distribution and Homebrew.

```
$ brew install tesseract
$ conda create --name phish_detective --file package-list.txt
$ pip install -r requirements.txt
```

Next switch to the newly created environment and run a test:

```
$ source activate phish_detective
$ python phish_detective.py --url http://www.nytimes.com
```

## Dependencies

* `tesseract` for Optical Character Recognition.
* At the time of writing, the Firefox driver in `selenium` does not work in my
  Mac OS X 10.11.4 with the most recent version (47.0) of Firefox.
  However, downgrading Firefox to version 45.0.2 solves the problem.

