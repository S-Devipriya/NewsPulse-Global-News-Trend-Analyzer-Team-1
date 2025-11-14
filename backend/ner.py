import spacy
import mysql.connector as mysql
import os
from dotenv import load_dotenv

load_dotenv()

# Load spaCy NER model once
print("Loading spaCy model...")
nlp = spacy.load("en_core_web_sm")
print("spaCy model loaded.")

def connect_db():
    conn = mysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB")
    )
    cursor = conn.cursor()
    create_table_query = '''CREATE TABLE IF NOT EXISTS entities (
               id INT AUTO_INCREMENT PRIMARY KEY,
               article_id INT,
               name VARCHAR(255),
               type VARCHAR(100),
               confidence FLOAT,
               FOREIGN KEY (article_id) REFERENCES news(id),
               INDEX(article_id)
           );'''
    cursor.execute(create_table_query)
    conn.commit()
    return conn

def extract_entities(text):
    """Extract named entities from text."""
    doc = nlp(text)
    allowed_labels = {'PERSON', 'ORG', 'GPE', 'LOC'}
    unique_ents = list(set([(ent.text, ent.label_) for ent in doc.ents if ent.label_ in allowed_labels]))
    return [{'text': text, 'label': label} for text, label in unique_ents]

def save_entities(article_id, entities_list):
    """
    Store entity results for a news article in the database.
    entities_list: [{'text': ..., 'label': ..., 'confidence': ...}, ...]
    If confidence not present, defaults to 1.0.
    """
    conn = connect_db()
    cursor = conn.cursor()

    query = '''INSERT INTO entities (article_id, name, type, confidence) VALUES (%s, %s, %s, %s)'''
    
    rows_to_insert = []
    for ent in entities_list:
        rows_to_insert.append((
            article_id,
            ent['text'],
            ent['label'],
            float(ent.get('confidence', 1.0))
        ))

    try:
        if rows_to_insert:
            cursor.executemany(query, rows_to_insert)
            conn.commit()
    except Exception as e:
        print(f"Error saving entities for article {article_id}: {e}")
    finally:
        conn.close()

def analyze_and_save_entities():
    """
    Batch function to find articles without entities, analyze them,
    and save the results to the 'entities' table.
    """
    conn = connect_db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute('''
        SELECT n.id, n.title, n.description, n.content
        FROM news n
        LEFT JOIN entities e ON n.id = e.article_id
        WHERE e.article_id IS NULL;
    ''')

    articles_to_process = cursor.fetchall()
    
    if not articles_to_process:
        print("No new articles for NER.")
        conn.close()
        return

    print(f"Found {len(articles_to_process)} new articles for NER...")

    for article in articles_to_process:
        article_id = article['id']
        title = article['title'] or ""
        description = article['description'] or ""
        text = title + " " + description

        if not text.strip():
            continue
            
        print(f"Extracting entities for article {article_id}...")
        
        entities_list = extract_entities(text)
        save_entities(article_id, entities_list)
        
    conn.close()
    print("NER batch processing complete.")

if __name__ == "__main__":
    analyze_and_save_entities()