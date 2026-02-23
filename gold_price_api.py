#!/usr/bin/env python3
"""
Gold Price API Integration
Fetches real-time gold price from various sources
"""

import requests
from datetime import datetime

class GoldPriceAPI:
    """Fetch gold price from multiple sources"""
    
    def __init__(self):
        self.sources = {
            'logammulia': self._fetch_logammulia,
            'antam': self._fetch_antam,
            'mock': self._fetch_mock
        }
    
    def get_price(self, source='mock'):
        """Get gold price from specified source"""
        if source in self.sources:
            return self.sources[source]()
        return self._fetch_mock()
    
    def _fetch_logammulia(self):
        """Fetch from LogamMulia API (if available)"""
        try:
            # TODO: Implement real API when available
            # url = "https://api.logammulia.com/v1/prices"
            # response = requests.get(url, timeout=10)
            # data = response.json()
            # return self._parse_logammulia(data)
            return self._fetch_mock()
        except:
            return self._fetch_mock()
    
    def _fetch_antam(self):
        """Fetch from Antam website (scraping if needed)"""
        try:
            # TODO: Implement scraping or API when available
            return self._fetch_mock()
        except:
            return self._fetch_mock()
    
    def _fetch_mock(self):
        """Mock data for testing"""
        import random
        
        # Base price with random variation
        base_price = 1050000
        variation = random.randint(-20000, 30000)
        price = base_price + variation
        
        # Calculate change percentage
        change_pct = (variation / base_price) * 100
        change_str = f"{'+' if change_pct > 0 else ''}{change_pct:.1f}%"
        
        return {
            'price': price,
            'change': change_str,
            'date': datetime.now().strftime('%d %B %Y'),
            'source': 'mock',
            'timestamp': datetime.now().isoformat()
        }

if __name__ == "__main__":
    api = GoldPriceAPI()
    price_data = api.get_price('mock')
    
    print("Gold Price Data:")
    print(f"  Price: Rp {price_data['price']:,}")
    print(f"  Change: {price_data['change']}")
    print(f"  Date: {price_data['date']}")
    print(f"  Source: {price_data['source']}")
