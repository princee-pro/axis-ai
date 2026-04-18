"""
API Integration Module.
Handles external API calls for weather, news, stock data, etc.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta

class APIIntegration:
    """
    Manages external API integrations and response caching.
    """
    def __init__(self, logger=None):
        self.logger = logger
        self.cache = {}  # Simple cache: {url: (timestamp, response)}
        self.cache_ttl = 300  # Cache TTL in seconds (5 minutes)
        
        # API keys (should be in config, using placeholder for now)
        self.api_keys = {
            'weather': 'demo',  # Use 'demo' for testing
            'news': 'demo',
            'stocks': 'demo'
        }
    
    def _log(self, message, level="INFO", goal_id=None):
        """Log message if logger is available."""
        if self.logger:
            self.logger.log(message, level, goal_id)
        else:
            print(f"[API] {message}")
    
    def _get_cached(self, cache_key):
        """Get cached response if still valid."""
        if cache_key in self.cache:
            timestamp, response = self.cache[cache_key]
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.cache_ttl:
                return response
        return None
    
    def _set_cache(self, cache_key, response):
        """Store response in cache."""
        self.cache[cache_key] = (datetime.now(), response)
    
    def make_request(self, url, goal_id=None):
        """
        Make a generic HTTP GET request.
        
        Args:
            url (str): URL to request
            goal_id (int): Optional goal ID for logging
        
        Returns:
            dict: Response data or error
        """
        # Check cache first
        cached = self._get_cached(url)
        if cached:
            self._log(f"Using cached response for {url}", goal_id=goal_id)
            return cached
        
        try:
            self._log(f"Making API request to {url}", goal_id=goal_id)
            req = urllib.request.Request(url, headers={'User-Agent': 'Jarvis/1.0'})
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                # Cache successful response
                self._set_cache(url, data)
                return data
                
        except urllib.error.HTTPError as e:
            error_msg = f"HTTP error {e.code}: {e.reason}"
            self._log(error_msg, "ERROR", goal_id)
            return {"error": error_msg}
        except urllib.error.URLError as e:
            error_msg = f"URL error: {e.reason}"
            self._log(error_msg, "ERROR", goal_id)
            return {"error": error_msg}
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response: {e}"
            self._log(error_msg, "ERROR", goal_id)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Request failed: {e}"
            self._log(error_msg, "ERROR", goal_id)
            return {"error": error_msg}
    
    def get_weather(self, city, goal_id=None):
        """
        Get weather data for a city.
        
        Args:
            city (str): City name
            goal_id (int): Optional goal ID for logging
        
        Returns:
            dict: Weather data or error
        """
        # Using OpenWeatherMap API (demo mode returns mock data)
        api_key = self.api_keys.get('weather', 'demo')
        
        if api_key == 'demo':
            # Mock response for testing
            self._log(f"Using mock weather data for {city}", goal_id=goal_id)
            return {
                "city": city,
                "temperature": 25,
                "condition": "Partly Cloudy",
                "humidity": 65,
                "mock": True
            }
        
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        response = self.make_request(url, goal_id)
        
        if "error" not in response:
            # Parse OpenWeatherMap response
            return {
                "city": response.get("name", city),
                "temperature": response.get("main", {}).get("temp"),
                "condition": response.get("weather", [{}])[0].get("description"),
                "humidity": response.get("main", {}).get("humidity")
            }
        
        return response
    
    def get_news(self, category="technology", goal_id=None):
        """
        Get news headlines.
        
        Args:
            category (str): News category
            goal_id (int): Optional goal ID for logging
        
        Returns:
            dict: News data or error
        """
        api_key = self.api_keys.get('news', 'demo')
        
        if api_key == 'demo':
            # Mock response for testing
            self._log(f"Using mock news data for category: {category}", goal_id=goal_id)
            return {
                "category": category,
                "articles": [
                    {"title": "AI Advances in 2026", "source": "Tech News"},
                    {"title": "New Python Framework Released", "source": "Dev Today"},
                    {"title": "Quantum Computing Breakthrough", "source": "Science Daily"}
                ],
                "mock": True
            }
        
        url = f"https://newsapi.org/v2/top-headlines?category={category}&apiKey={api_key}"
        response = self.make_request(url, goal_id)
        
        if "error" not in response:
            articles = response.get("articles", [])[:5]  # Top 5
            return {
                "category": category,
                "articles": [{"title": a.get("title"), "source": a.get("source", {}).get("name")} for a in articles]
            }
        
        return response
    
    def get_stock_price(self, symbol, goal_id=None):
        """
        Get stock price data.
        
        Args:
            symbol (str): Stock symbol (e.g., 'AAPL')
            goal_id (int): Optional goal ID for logging
        
        Returns:
            dict: Stock data or error
        """
        api_key = self.api_keys.get('stocks', 'demo')
        
        if api_key == 'demo':
            # Mock response for testing
            self._log(f"Using mock stock data for {symbol}", goal_id=goal_id)
            return {
                "symbol": symbol.upper(),
                "price": 150.25,
                "change": "+2.5%",
                "mock": True
            }
        
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
        response = self.make_request(url, goal_id)
        
        if "error" not in response:
            quote = response.get("Global Quote", {})
            return {
                "symbol": symbol.upper(),
                "price": quote.get("05. price"),
                "change": quote.get("10. change percent")
            }
        
        return response
