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
               people TEXT,
               organizations TEXT,
               locations TEXT,
               FOREIGN KEY (article_id) REFERENCES news(id),
               UNIQUE KEY (article_id)
           );'''
    cursor.execute(create_table_query)
    conn.commit()
    return conn

def extract_entities(text):
    """
    Extract named entities from text.
    Returns:
        dict: {
            'organizations': [str, ...],
            'people': [str, ...],
            'locations': [str, ...]
        }
    """
    doc = nlp(text)
    organizations = list(set([ent.text for ent in doc.ents if ent.label_ == 'ORG']))
    people = list(set([ent.text for ent in doc.ents if ent.label_ == 'PERSON']))
    locations = list(set([ent.text for ent in doc.ents if ent.label_ in ['GPE', 'LOC']]))

    return {
        'organizations': organizations,
        'people': people,
        'locations': locations
    }

def save_entities(article_id, entities_dict):
    """
    Store entity results for a news article in the database.

    entities_list: [{'text': ..., 'label': ..., 'confidence': ...}, ...]
    If confidence not present, defaults to 1.0.
    """
    conn = connect_db()
    cursor = conn.cursor()
    
    people_str = ",".join(entities_dict['people'])
    orgs_str = ",".join(entities_dict['organizations'])
    locs_str = ",".join(entities_dict['locations'])

    query = '''INSERT INTO entities (article_id, people, organizations, locations)
               VALUES (%s, %s, %s, %s)'''
    try:
        cursor.execute(query, (
            article_id,
            people_str,
            orgs_str,
            locs_str
        ))
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
        SELECT n.id, n.title, n.description
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
        
        entities_dict = extract_entities(text)
        
        save_entities(article_id, entities_dict)
        
    conn.close()
    print("NER batch processing complete.")

if __name__ == "__main__":
    analyze_and_save_entities()
