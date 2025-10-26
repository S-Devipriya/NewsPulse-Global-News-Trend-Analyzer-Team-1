import spacy
import mysql.connector as mysql
import os

# Load spaCy NER model once
nlp = spacy.load("en_core_web_sm")

def extract_entities(text):
    """
    Extract named entities from text.
    Returns:
        dict: {
            'entities': [ {'text': ..., 'label': ...}, ... ],
            'organizations': [str, ...],
            'people': [str, ...],
            'locations': [str, ...]
        }
    """
    doc = nlp(text)
    entities = [{'text': ent.text, 'label': ent.label_} for ent in doc.ents]
    organizations = [ent.text for ent in doc.ents if ent.label_ == 'ORG']
    people = [ent.text for ent in doc.ents if ent.label_ == 'PERSON']
    locations = [ent.text for ent in doc.ents if ent.label_ in ['GPE', 'LOC']]

    return {
        'entities': entities,
        'organizations': organizations,
        'people': people,
        'locations': locations
    }

def save_entities(article_id, entities_list):
    """
    Store entity results for a news article in the database.

    entities_list: [{'text': ..., 'label': ..., 'confidence': ...}, ...]
    If confidence not present, defaults to 1.0.
    """
    connection = mysql.connect(
        host = os.getenv("MYSQL_HOST"),
        user = os.getenv("MYSQL_USER"),
        password = os.getenv("MYSQL_PASSWORD"),
        database = os.getenv("MYSQL_DB")
    )
    cursor = connection.cursor()
    query = '''CREATE TABLE IF NOT EXISTS entities (
               id INT AUTO_INCREMENT PRIMARY KEY,
               article_id INT,
               name VARCHAR(255),
               type VARCHAR(100),
               confidence FLOAT,
               FOREIGN KEY (article_id) REFERENCES news(id)
           );'''
    cursor.execute(query)
    connection.commit()
    query = '''INSERT INTO entities (article_id, name, type, confidence)
               VALUES (%s, %s, %s, %s)'''
    for ent in entities_list:
        cursor.execute(query, (
            article_id,
            ent['text'],
            ent['label'],
            float(ent.get('confidence', 1.0))
        ))
    connection.commit()
    connection.close()
