# Veritascope - Your Global News Trend Analyzer

## 📰 Project Description

Veritascope is a comprehensive news aggregation and trend analysis platform that helps users stay informed about global news trends. The application fetches real-time news articles, extracts meaningful keywords,  sentiment from each article, and presents them through an intuitive dashboard interface. Built as a collaborative project by Team 1, Veritascope empowers users to discover, analyze, and track news stories from various sources.

## 🎯 Objective

The main objective of Veritascope is to provide users with:

- Easy access to top headlines and trending news
- Intelligent keyword extraction for quick content understanding
- A clean, user-friendly dashboard for news exploration
- Personalized user experience through registration and login
- Efficient news data management and storage

## ✨ Features

- **News Fetching**: Automatically retrieves top headlines and topic-based news from reliable sources
- **Interactive Dashboard**: Clean and responsive HTML interface for browsing news articles
- **Keyword Extraction**: Advanced text processing to identify and extract key topics from articles
- **User Management**: Secure user registration and login system
- **Database Integration**: MySQL-based storage for news articles and user data
- **Text Preprocessing**: Sophisticated text cleaning and preparation for analysis
- **Environment Configuration**: Secure API key and database credential management

## 🛠️ Tech Stack

- **Backend**: Python, Flask
- **Database**: MySQL
- **Frontend**: HTML, CSS (Templates)
- **APIs**: News API integration
- **Text Processing & NLP**: NLTK, spaCy, scikit-learn, KeyBERT, sentence-transformers, BERTopic, Transformers (HuggingFace), PyTorch
- **Data Processing**: pandas, numpy, scipy
- **Visualization**: matplotlib, wordcloud
- **Forecasting**: Prophet
- **Environment Management**: python-dotenv
  
## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.7 or higher
- MySQL Server
- pip (Python package manager)
- Git

## 🚀 Setup Instructions

### 1. Clone the Repository

git clone https://github.com/S-Devipriya/NewsPulse-Global-News-Trend-Analyzer-Team-1.git

cd NewsPulse-Global-News-Trend-Analyzer-Team-1



### 2. Install Dependencies

Install all required Python packages using the requirements file:

pip install -r requirements.txt


### 3. Configure Environment Variables

Create a `.env` file in the root directory by copying the example file:

cp .example.env .env



Edit the `.env` file and add your credentials:

News API Configuration
NEWS_API_KEY=your_news_api_key_here

MySQL Database Configuration

DB_HOST=localhost

DB_USER=your_mysql_username

DB_PASSWORD=your_mysql_password

DB_NAME=newsdb

Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here



**Note**: You can get a free News API key from [newsapi.org](https://newsapi.org/)

### 4. Set Up the Database

Create the MySQL database:

CREATE DATABASE newsdb;

The application will automatically create the necessary tables on first run.

### 5. Run the Application

Start the Flask backend server:

python backend/veritascope.py

The application should now be running at `http://localhost:5000`

## 💻 Usage

1. **Access the Dashboard**: Open your browser and navigate to `http://localhost:5000`
2. **Register/Login**: Create a new account or log in with existing credentials
3. **Browse News**: View top headlines and trending news on the dashboard
4. **Explore Keywords**: Check extracted keywords to understand article themes quickly
5. **Search Topics**: Use topic-based search to find news on specific subjects
6. **View Analytics**: Access trend analysis, sentiment scores, and forecasts
7. **Admin Dashboard**: Administrators can manage users and view system statistics

## 📁 Project Structure

NewsPulse-Global-News-Trend-Analyzer-Team-1/

NewsPulse-Global-News-Trend-Analyzer-Team-1/

├── backend/

│ ├── analytics_utils.py # Time-series analysis and forecasting utilities

│ ├── fetch_news.py # News fetching module with API integration

│ ├── keyword_extractor.py # Keyword extraction using NLP

│ ├── ner.py # Named Entity Recognition module

│ ├── veritascope.py # Main Flask application (entry point)

│ ├── sentiment.py # Sentiment analysis engine

│ ├── text_preprocessing.py # Text cleaning and preprocessing utilities

│ ├── topic_selection.py # Topic categorization logic

│ ├── trend_detector.py # Trend detection and analysis

│ ├── user_profile.py # User profile management

│ └── users.py # User authentication and authorization

├── templates/

│ ├── admin_dashboard.html # Administrator control panel

│ ├── analytics.html # Analytics and visualization page

│ ├── article_detail.html # Individual article view with details

│ ├── dashboard.html # Main user dashboard

│ ├── home.html # Landing/home page

│ └── login.html # User login interface

├── static/

│ └── images/ # Static images (icons, backgrounds, etc.)

├── .example.env # Example environment configuration

├── .gitignore # Git ignore rules

├── LICENSE # MIT License

├── README.md # Project documentation

└── requirements.txt # Python dependencies


## 🔧 Key Files Explained

- **`backend/veritascope.py`**: Core Flask application handling routing and coordination
- **`backend/fetch_news.py`**: Responsible for fetching and storing news from APIs
- **`backend/keyword_extractor.py`**: Extracts meaningful keywords from news articles
- **`backend/users.py`**: Manages user registration, login, and authentication
- **`templates/dashboard.html`**: Frontend interface for displaying news

## 🤝 Contributors

This project is developed and maintained by **Team 1**:

- **[Sanika2511](https://github.com/Sanika2511)** - Backend Developer
- **[S-Devipriya](https://github.com/S-Devipriya)** - Project Lead & Backend Developer
- **[JahnaviGunti](https://github.com/JahnaviGunti)** - Developer
- **[Repatigirish](https://github.com/Repatigirish)** - Frontend Developer
- **[vaishnavigunda](https://github.com/vaishnavigunda)** - Developer

## 📄 License

This project is the culmination of Team 1's work during the Infosys Springboard Virtual Internship 6.0 program, created for educational purposes to demonstrate full-stack web development, natural language processing, and data analytics skills.

**Happy News Analyzing! 📊📰**

For questions or issues, please open an issue on GitHub or contact any of the team members.
