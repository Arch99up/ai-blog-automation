#!/bin/bash
python -m nltk.downloader punkt stopwords averaged_perceptron_tagger
gunicorn -b 0.0.0.0:10000 app:app
