#!/bin/sh

PROG=`basename $0`

lang_model_name=${SW_INSTALL_SPC_MODEL_NAME:-"en-core-web-lg"}

if [ -f ".env" ]
then
echo $PROG "Install: .env found"
else
    echo $PROG "Copying: .env.dist -> .env"
    cp .env.dist .env
fi

if [ -f "db.sqlite3" ]
then
echo $PROG "Install: db.sqlite3 found"
else
    echo $PROG "Copying: db.sqlite3.dist -> db.sqlite3"
    cp db.sqlite3.dist db.sqlite3
fi

python swirl/banner.py
echo ""

echo $PROG "Installing dependencies:"
pip install -r requirements.txt

echo $PROG "Checking for ${lang_model_name}"
found_model=`pip list 2>/dev/null | grep ${lang_model_name} | awk '{print $1}'`
if [[ "x$found_model" == "x$lang_model_name" ]]
then
   echo $PROG "Found $lang_model_name , skipping download"
else
   echo $PROG "Downloading spacy en_core_web_lg..."
   python -m spacy download en_core_web_lg
fi

echo $PROG "Downloading NLTK modules..."
python -m nltk.downloader stopwords
python -m nltk.downloader punkt

echo $PROG "If no errors occured, run python swirl.py setup"
