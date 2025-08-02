from flask import Flask, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import threading
import time
import json
import re
from datetime import datetime
import logging

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # GitHub Pages'den erişim için

# Global veri depolama
current_data = {
    'usd_try': {'buy': 0, 'sell': 0, 'change': 0},
    'eur_try': {'buy': 0, 'sell': 0, 'change': 0},
    'gold_ons': {'buy': 0, 'sell': 0, 'change': 0},
    'silver_kg': {'buy': 0, 'sell': 0, 'change': 0},
    'quarter': {'buy': 0, 'sell': 0, 'change': 0},
    'ata': {'buy': 0, 'sell': 0, 'change': 0},
    'last_update': '',
    'status': 'initializing'
}

def clean_price(price_str):
    """Fiyat string'ini temizle ve float'a çevir"""
    if not price_str:
        return 0.0
    
    # Sadece rakam, nokta ve virgülü bırak
    cleaned = re.sub(r'[^\d.,]', '', str(price_str))
    
    # Türkçe format: 1.234,56 -> 1234.56
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            # 1.234,56 formatı
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            # 1,234.56 formatı
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        # Sadece virgül var - Türkçe decimal
        cleaned = cleaned.replace(',', '.')
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def scrape_iar_platform():
    """IAR Platform'dan verileri çek"""
    global current_data
    
    try:
        logger.info("IAR Platform'dan veri çekiliyor...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # IAR Platform ana sayfası
        response = requests.get('https://www.iarplatform.com', headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Piyasa verileri tablosunu bul
        tables = soup.find_all('table')
        
        if not tables:
            logger.warning("Tablo bulunamadı, alternatif parsing deneniyor...")
            parse_alternative_format(soup)
            return
            
        # Ana piyasa tablosunu bul
        main_table = None
        for table in tables:
            table_text = table.get_text().upper()
            if any(keyword in table_text for keyword in ['USD', 'EUR', 'ALTIN', 'GÜMÜŞ', 'ÇEYREK']):
                main_table = table
                break
        
        if not main_table:
            logger.warning("Piyasa tablosu bulunamadı")
            current_data['status'] = 'no_table_found'
            return
        
        # Tablo satırlarını parse et
        rows = main_table.find_all('tr')
        data_found = False
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue
                
            # İlk hücredeki ürün adını al
            product_name = cells[0].get_text(strip=True).upper()
            
            try:
                # Alış ve satış fiyatlarını al
                buy_price = clean_price(cells[1].get_text(strip=True))
                sell_price = clean_price(cells[2].get_text(strip=True))
                
                # Değişim bilgisi varsa al
                change = 0
                if len(cells) > 3:
                    change_text = cells[3].get_text(strip=True)
                    if change_text and change_text != '-':
                        change = clean_price(change_text)
                
                # Ürün tipine göre kaydet
                if 'USD' in product_name and ('TRY' in product_name or 'TL' in product_name):
                    current_data['usd_try'] = {'buy': buy_price, 'sell': sell_price, 'change': change}
                    logger.info(f"USD/TRY: {buy_price} / {sell_price}")
                    data_found = True
                    
                elif 'EUR' in product_name and ('TRY' in product_name or 'TL' in product_name):
                    current_data['eur_try'] = {'buy': buy_price, 'sell': sell_price, 'change': change}
                    logger.info(f"EUR/TRY: {buy_price} / {sell_price}")
                    data_found = True
                    
                elif 'ALTIN' in product_name and 'ONS' in product_name:
                    current_data['gold_ons'] = {'buy': buy_price, 'sell': sell_price, 'change': change}
                    logger.info(f"Altın ONS: {buy_price} / {sell_price}")
                    data_found = True
                    
                elif 'GÜMÜŞ' in product_name and 'KG' in product_name:
                    current_data['silver_kg'] = {'buy': buy_price, 'sell': sell_price, 'change': change}
                    logger.info(f"Gümüş KG: {buy_price} / {sell_price}")
                    data_found = True
                    
                elif 'ÇEYREK' in product_name and 'ESKİ' in product_name:
                    current_data['quarter'] = {'buy': buy_price, 'sell': sell_price, 'change': change}
                    logger.info(f"Eski Çeyrek: {buy_price} / {sell_price}")
                    data_found = True
                    
                elif 'ATA' in product_name and 'ESKİ' in product_name:
                    current_data['ata'] = {'buy': buy_price, 'sell': sell_price, 'change': change}
                    logger.info(f"Eski Ata: {buy_price} / {sell_price}")
                    data_found = True
                    
            except Exception as e:
                logger.error(f"Satır parse hatası: {e}")
                continue
        
        if data_found:
            current_data['last_update'] = datetime.now().strftime('%H:%M:%S')
            current_data['status'] = 'success'
            logger.info(f"Veri başarıyla güncellendi: {current_data['last_update']}")
        else:
            current_data['status'] = 'no_data_found'
            logger.warning("Hiç veri bulunamadı")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"İstek hatası: {e}")
        current_data['status'] = 'connection_error'
        
    except Exception as e:
        logger.error(f"Genel hata: {e}")
        current_data['status'] = 'error'

def parse_alternative_format(soup):
    """Alternatif format parsing - JavaScript verilerini bulmaya çalış"""
    try:
        scripts = soup.find_all('script')
        
        for script in scripts:
            if script.string and ('usd' in script.string.lower() or 'eur' in script.string.lower()):
                logger.info("JavaScript veri bloğu bulundu")
                # Bu kısım sitenin yapısına göre özelleştirilmeli
                break
        
        # Div'lerden veri çekmeye çalış
        price_divs = soup.find_all('div', class_=re.compile(r'price|currency|gold|silver', re.I))
        
        for div in price_divs:
            text = div.get_text().upper()
            if 'USD' in text and any(char.isdigit() for char in text):
                logger.info(f"Potansiyel USD verisi bulundu: {text}")
                
    except Exception as e:
        logger.error(f"Alternatif parsing hatası: {e}")

def background_scraper():
    """Arka planda sürekli veri çekme"""
    while True:
        scrape_iar_platform()
        time.sleep(30)  # 30 saniyede bir güncelle

@app.route('/')
def index():
    """Ana sayfa - API bilgileri"""
    return jsonify({
        'message': 'IAR Platform API Server',
        'version': '1.0.0',
        'status': current_data['status'],
        'last_update': current_data['last_update'],
        'endpoints': {
            '/api/prices': 'Güncel fiyat verileri',
            '/api/status': 'Sunucu durumu',
            '/api/health': 'Health check'
        }
    })

@app.route('/api/prices')
def get_prices():
    """Güncel fiyat verilerini döndür"""
    return jsonify(current_data)

@app.route('/api/status')
def get_status():
    """Sunucu durumunu döndür"""
    return jsonify({
        'status': current_data['status'],
        'last_update': current_data['last_update'],
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': 'running',
        'data_points': len([k for k, v in current_data.items() if isinstance(v, dict) and v.get('buy', 0) > 0])
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/test')
def test_scraping():
    """Manuel test scraping"""
    scrape_iar_platform()
    return jsonify({
        'message': 'Test scraping completed',
        'data': current_data
    })

if __name__ == '__main__':
    logger.info("🚀 IAR Platform Scraper Server başlatılıyor...")
    
    # İlk veriyi hemen çek
    scrape_iar_platform()
    
    # Arka plan thread'ini başlat
    scraper_thread = threading.Thread(target=background_scraper, daemon=True)
    scraper_thread.start()
    
    # Flask sunucusunu başlat
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
