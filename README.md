# NewsPulse - Global News Trend Analyzer

## 📰 Project Description

NewsPulse is a comprehensive news aggregation and trend analysis platform that helps users stay informed about global news trends. The application fetches real-time news articles, extracts meaningful keywords, and presents them through an intuitive dashboard interface. Built as a collaborative project by Team 1, NewsPulse empowers users to discover, analyze, and track news stories from various sources.

## 🎯 Objective

The main objective of NewsPulse is to provide users with:
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
- **Text Processing**: Natural Language Processing libraries
- **Environment Management**: python-dotenv

## 📋 Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.7 or higher
- MySQL Server
- pip (Python package manager)
- Git

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/S-Devipriya/NewsPulse-Global-News-Trend-Analyzer-Team-1.git
cd NewsPulse-Global-News-Trend-Analyzer-Team-1
```

### 2. Install Dependencies

Install all required Python packages using the requirements file:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create a `.env` file in the root directory by copying the example file:

```bash
cp .example.env .env
```

Edit the `.env` file and add your credentials:

```env
# News API Configuration
NEWS_API_KEY=your_news_api_key_here

# MySQL Database Configuration
DB_HOST=localhost
DB_USER=your_mysql_username
DB_PASSWORD=your_mysql_password
DB_NAME=newspulse_db

# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here
```

**Note**: You can get a free News API key from [newsapi.org](https://newsapi.org/)

### 4. Set Up the Database

Create the MySQL database:

```sql
CREATE DATABASE newspulse_db;
```

The application will automatically create the necessary tables on first run.

### 5. Run the Application

Start the Flask backend server:

```bash
python backend/newspulse.py
```

The application should now be running at `http://localhost:5000`

## 💻 Usage

1. **Access the Dashboard**: Open your browser and navigate to `http://localhost:5000`
2. **Register/Login**: Create a new account or log in with existing credentials
3. **Browse News**: View top headlines and trending news on the dashboard
4. **Explore Keywords**: Check extracted keywords to understand article themes quickly
5. **Search Topics**: Use topic-based search to find news on specific subjects

## 📁 Project Structure

```
NewsPulse-Global-News-Trend-Analyzer-Team-1/
├── backend/
│   ├── newspulse.py              # Main Flask application
│   ├── fetch_news.py             # News fetching module
│   ├── keyword_extractor.py      # Keyword extraction logic
│   ├── text_preprocessing.py     # Text cleaning utilities
│   └── users.py                  # User authentication handler
├── templates/
│   └── dashboard.html            # Main dashboard interface
├── .example.env                  # Example environment configuration
├── .gitignore                    # Git ignore rules
└── requirements.txt              # Python dependencies
```

## 🔧 Key Files Explained

- **`backend/newspulse.py`**: Core Flask application handling routing and coordination
- **`backend/fetch_news.py`**: Responsible for fetching and storing news from APIs
- **`backend/keyword_extractor.py`**: Extracts meaningful keywords from news articles
- **`backend/users.py`**: Manages user registration, login, and authentication
- **`templates/dashboard.html`**: Frontend interface for displaying news

## 🤝 Contributors

This project is developed and maintained by **Team 1**:

- **[S-Devipriya](https://github.com/S-Devipriya)** - Project Lead & Backend Developer
- **[Repatigirish](https://github.com/Repatigirish)** - Frontend Developer
- **[Sanika2511](https://github.com/Sanika2511)** -  Backend Developer


## 📄 License

This project is created for educational purposes as part of Team 1's collaborative work.



**Happy News Analyzing! 📊📰**

For questions or issues, please open an issue on GitHub or contact any of the team members.
