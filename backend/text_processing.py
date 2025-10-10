#!/usr/bin/env python
# coding: utf-8

# In[3]:


import re
import string
import nltk
import spacy
from textblob import TextBlob
from nltk.corpus import stopwords

# Load spaCy English model
nlp = spacy.load("en_core_web_sm")
nltk.download('stopwords')
stop_words = set(stopwords.words('english'))

def preprocess_text(text):
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Remove URLs
    text = re.sub(r"http\S+|www\S+|https\S+", '', text, flags=re.MULTILINE)

    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))

    # Remove numbers
    text = re.sub(r'\d+', '', text)

    # Tokenize using spaCy
    doc = nlp(text)

    tokens = []
    for token in doc:
        # Remove stopwords and whitespace tokens
        if token.text in stop_words or token.is_space:
            continue
        # Lemmatize token
        lemma = token.lemma_.strip()
        if lemma and lemma != '-PRON-':  # remove pronouns
            tokens.append(lemma)

    # Join tokens back to string
    cleaned_text = " ".join(tokens)

    # Spell correction with TextBlob (optional)
    corrected_text = str(TextBlob(cleaned_text).correct())

    return corrected_text


# In[ ]:




