import pandas as pd
import mysql.connector
from prophet import Prophet
from datetime import datetime, timedelta
import os

def connect_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"), 
        password=os.getenv("MYSQL_PASSWORD"), 
        database=os.getenv("MYSQL_DB")
    )

def fetch_daily_counts(table, column, start_days_ago=90):
    conn = connect_db()
    cursor = conn.cursor()
    query = f"""
        SELECT DATE(publishedAt) as day, COUNT(*) as cnt
        FROM {table}
        WHERE publishedAt >= CURDATE() - INTERVAL %s DAY
        AND {column} IS NOT NULL AND {column} != ''
        GROUP BY day
        ORDER BY day ASC;
    """
    cursor.execute(query, (start_days_ago,))
    days, counts = [], []
    for day, cnt in cursor.fetchall():
        days.append(str(day))
        counts.append(cnt)
    cursor.close(); conn.close()
    return days, counts

def get_news_volume_timeseries(days=90):
    days_list, counts = fetch_daily_counts('news', 'id', start_days_ago=days)
    return pd.DataFrame({'ds': days_list, 'y': counts}), days_list, counts

def get_sentiment_timeseries(days=90):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(n.publishedAt), s.overall, COUNT(*) 
        FROM news n 
        JOIN sentiments s ON n.id = s.article_id
        WHERE n.publishedAt >= CURDATE() - INTERVAL %s DAY
        GROUP BY DATE(n.publishedAt), s.overall
        ORDER BY DATE(n.publishedAt) ASC;
    """, (days,))
    days_set = set()
    by_day = {}
    for day, sentiment, cnt in cursor.fetchall():
        day = str(day)
        days_set.add(day)
        if day not in by_day:
            by_day[day] = {'positive':0, 'neutral':0, 'negative':0}
        s = sentiment.lower()
        if s in by_day[day]:
            by_day[day][s] = cnt
    days_list = sorted(list(days_set))
    pos = [by_day[d]['positive'] for d in days_list]
    neu = [by_day[d]['neutral'] for d in days_list]
    neg = [by_day[d]['negative'] for d in days_list]
    cursor.close(); conn.close()
    return days_list, pos, neu, neg

def get_topic_timeseries(topic_id, days=90):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(n.publishedAt), COUNT(*)
        FROM article_topics_mapping atm
        JOIN news n ON atm.article_id = n.id
        WHERE n.publishedAt >= CURDATE() - INTERVAL %s DAY
          AND atm.topic_id = %s
        GROUP BY DATE(n.publishedAt)
        ORDER BY DATE(n.publishedAt) ASC;
    """, (days, topic_id))
    days, counts = [], []
    for day, cnt in cursor.fetchall():
        days.append(str(day))
        counts.append(cnt)
    cursor.close(); conn.close()
    return pd.DataFrame({'ds': days, 'y': counts}), days, counts


def forecast_timeseries(df, periods=7):
    if df.dropna().shape[0] < 2:
        return [], []
    m = Prophet()
    m.fit(df)
    future = m.make_future_dataframe(periods=periods)
    forecast = m.predict(future)
    fcast_dates = forecast['ds'][-periods:].dt.strftime('%Y-%m-%d').tolist()
    fcast_values = forecast['yhat'][-periods:].round(2).tolist()
    return fcast_dates, fcast_values

def get_news_volume_timeseries_and_forecast(days=90, predict_days=7):
    df, history_dates, history_counts = get_news_volume_timeseries(days)
    fcast_dates, fcast_values = forecast_timeseries(df, periods=predict_days)
    return {
        "history_dates": history_dates,
        "history_counts": history_counts,
        "fcast_dates": fcast_dates,
        "fcast_values": fcast_values
    }

def get_sentiment_timeseries_and_forecast(days=90, predict_days=7):
    days_list, pos, neu, neg = get_sentiment_timeseries(days)
    df_pos = pd.DataFrame({'ds': days_list, 'y': pos})
    df_neu = pd.DataFrame({'ds': days_list, 'y': neu})
    df_neg = pd.DataFrame({'ds': days_list, 'y': neg})
    pos_fcast_dates, pos_fcast = forecast_timeseries(df_pos, periods=predict_days)
    neu_fcast_dates, neu_fcast = forecast_timeseries(df_neu, periods=predict_days)
    neg_fcast_dates, neg_fcast = forecast_timeseries(df_neg, periods=predict_days)
    return {
        "days": days_list,
        "pos": pos, "neu": neu, "neg": neg,
        "pos_fcast_dates": pos_fcast_dates, "pos_fcast": pos_fcast,
        "neu_fcast_dates": neu_fcast_dates, "neu_fcast": neu_fcast,
        "neg_fcast_dates": neg_fcast_dates, "neg_fcast": neg_fcast
    }

def get_topic_timeseries_and_forecast(topic_id, days=90, predict_days=7):
    df, history_dates, history_counts = get_topic_timeseries(topic_id, days)
    fcast_dates, fcast_values = forecast_timeseries(df, periods=predict_days)
    return {
        "topic_id": topic_id,
        "history_dates": history_dates,
        "history_counts": history_counts,
        "fcast_dates": fcast_dates,
        "fcast_values": fcast_values
    }


def get_existing_topics(min_articles=20):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.id, t.name
        FROM topics t
        JOIN article_topics_mapping atm ON atm.topic_id = t.id
        GROUP BY t.id, t.name
        HAVING COUNT(atm.article_id) > %s
        ORDER BY t.id ASC;
    """, (min_articles,))
    topics = [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return topics



def get_top_topics_from_db(days=7, limit=5):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT atm.topic_id, t.name, COUNT(*) as count
        FROM article_topics_mapping atm
        JOIN topics t ON atm.topic_id = t.id
        WHERE atm.assigned_at >= CURDATE() - INTERVAL %s DAY
        GROUP BY atm.topic_id, t.name
        ORDER BY count DESC
        LIMIT %s;
    """, (days, limit))
    topics = [{'label': name, 'count': count} for _, name, count in cursor.fetchall()]
    cursor.close()
    conn.close()
    return topics




def get_sentiment_distribution_numerical():
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(positive), SUM(neutral), SUM(negative) FROM sentiments")
    pos, neu, neg = cursor.fetchone()
    total = pos + neu + neg
    if total == 0:
        stats = {'positive': 0, 'neutral': 0, 'negative': 0}
    else:
        stats = {
            'positive': round(pos * 100 / total),
            'neutral': round(neu * 100 / total),
            'negative': round(neg * 100 / total)
        }
    cursor.close()
    conn.close()
    return stats

def get_sentiment_numerical_trend_by_day(days=90):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(n.publishedAt), 
               COUNT(*),
               SUM(s.positive), SUM(s.neutral), SUM(s.negative)
        FROM news n
        JOIN sentiments s ON n.id = s.article_id
        WHERE n.publishedAt >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY DATE(n.publishedAt)
        ORDER BY DATE(n.publishedAt) ASC;
    """, (days,))
    days_list, pos_list, neu_list, neg_list = [], [], [], []
    for day, total, pos, neu, neg in cursor.fetchall():
        days_list.append(str(day))
        pos_pct = int(round((pos / total) if total else 0))
        neu_pct = int(round((neu / total) if total else 0))
        neg_pct = int(round((neg / total) if total else 0))
        pos_list.append(pos_pct)
        neu_list.append(neu_pct)
        neg_list.append(neg_pct)
    cursor.close()
    conn.close()
    return {
        'days': days_list,
        'positive': pos_list,
        'neutral': neu_list,
        'negative': neg_list
    }

# NEW ADDED: Sentiment percentage time-series forecast for dashboard
def get_sentiment_percentage_forecast(days=90, predict_days=7):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(n.publishedAt), COUNT(*),
            SUM(s.positive), SUM(s.neutral), SUM(s.negative)
        FROM news n
        JOIN sentiments s ON n.id = s.article_id
        WHERE n.publishedAt >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY DATE(n.publishedAt)
        ORDER BY DATE(n.publishedAt) ASC;
    """, (days,))
    days_list, pos_list, neu_list, neg_list = [], [], [], []
    for day, total, pos, neu, neg in cursor.fetchall():
        days_list.append(str(day))
        pos_pct = int(round((pos / total) if total else 0))
        neu_pct = int(round((neu / total) if total else 0))
        neg_pct = int(round((neg / total) if total else 0))
        pos_list.append(pos_pct)
        neu_list.append(neu_pct)
        neg_list.append(neg_pct)
    cursor.close()
    conn.close()

    df_pos = pd.DataFrame({'ds': days_list, 'y': pos_list})
    df_neu = pd.DataFrame({'ds': days_list, 'y': neu_list})
    df_neg = pd.DataFrame({'ds': days_list, 'y': neg_list})

    pos_fcast_dates, pos_fcast = forecast_timeseries(df_pos, periods=predict_days)
    neu_fcast_dates, neu_fcast = forecast_timeseries(df_neu, periods=predict_days)
    neg_fcast_dates, neg_fcast = forecast_timeseries(df_neg, periods=predict_days)

    return {
        "days": days_list,
        "pos": pos_list, "neu": neu_list, "neg": neg_list,
        "pos_fcast_dates": pos_fcast_dates, "pos_fcast": pos_fcast,
        "neu_fcast_dates": neu_fcast_dates, "neu_fcast": neu_fcast,
        "neg_fcast_dates": neg_fcast_dates, "neg_fcast": neg_fcast
    }

def get_sentiment_stats_from_db(days=90):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT overall, COUNT(*) FROM sentiments GROUP BY overall;
    ''')
    stats = {'positive': 0, 'neutral': 0, 'negative': 0}
    total = 0
    for label, count in cursor.fetchall():
        l = label.lower()
        if l == 'positive':
            stats['positive'] = count
        elif l == 'neutral':
            stats['neutral'] = count
        elif l == 'negative':
            stats['negative'] = count
        total += count
    cursor.close()
    conn.close()
    # Optionally convert counts to percentages
    if total > 0:
        for k in stats:
            stats[k] = int(round(stats[k] * 100 / total))
    return stats



def get_sentiment_trend_by_day(days=90):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(n.publishedAt) as day, s.overall, COUNT(*) as cnt
        FROM news n
        JOIN sentiments s ON n.id = s.article_id
        WHERE n.publishedAt >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY day, s.overall
        ORDER BY day ASC;
    ''', (days,))
    days_list = []
    data_dict = {}
    for day, sentiment, cnt in cursor.fetchall():
        if day not in days_list:
            days_list.append(day)
        if day not in data_dict:
            data_dict[day] = {'positive': 0, 'neutral': 0, 'negative': 0}
        s = sentiment.lower()
        if s in data_dict[day]:
            data_dict[day][s] = cnt

    # Generate result lists
    positive = [data_dict[d]['positive'] for d in days_list]
    neutral = [data_dict[d]['neutral'] for d in days_list]
    negative = [data_dict[d]['negative'] for d in days_list]
    cursor.close()
    conn.close()
    return {'days': days_list, 'positive': positive, 'neutral': neutral, 'negative': negative}
