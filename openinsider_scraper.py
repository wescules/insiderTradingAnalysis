import requests
from bs4 import BeautifulSoup
import pandas as pd
import yaml
import logging
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from retry import retry
from pathlib import Path
import json
from typing import Dict, List, Set, Union, Optional
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

@dataclass
class ScraperConfig:
    output_dir: str
    output_file: str
    output_format: str
    start_year: int
    start_month: int
    max_workers: int
    retry_attempts: int
    timeout: int
    min_transaction_value: float
    transaction_types: List[str]
    exclude_companies: List[str]
    include_companies: List[str]
    min_shares_traded: int
    log_level: str
    log_file: str
    rotate_logs: bool
    max_log_size: int
    cache_enabled: bool
    cache_dir: str
    cache_max_age: int

class OpenInsiderScraper:
    def __init__(self, config_path: str = 'config.yaml'):
        self.config = self._load_config(config_path)
        self._setup_logging()
        self._setup_directories()
        self.logger = logging.getLogger('openinsider')
        
    def _load_config(self, config_path: str) -> ScraperConfig:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return ScraperConfig(
            output_dir=config['output']['directory'],
            output_file=config['output']['filename'],
            output_format=config['output']['format'],
            start_year=config['scraping']['start_year'],
            start_month=config['scraping']['start_month'],
            max_workers=config['scraping']['max_workers'],
            retry_attempts=config['scraping']['retry_attempts'],
            timeout=config['scraping']['timeout'],
            min_transaction_value=config['filters']['min_transaction_value'],
            transaction_types=config['filters']['transaction_types'],
            exclude_companies=config['filters']['exclude_companies'],
            include_companies=config['filters']['include_companies'],
            min_shares_traded=config['filters']['min_shares_traded'],
            log_level=config['logging']['level'],
            log_file=config['logging']['file'],
            rotate_logs=config['logging']['rotate_logs'],
            max_log_size=config['logging']['max_log_size'],
            cache_enabled=config['cache']['enabled'],
            cache_dir=config['cache']['directory'],
            cache_max_age=config['cache']['max_age']
        )
    
    def _setup_logging(self) -> None:
        log_level = getattr(logging, self.config.log_level.upper())
        if self.config.rotate_logs:
            handler = RotatingFileHandler(
                self.config.log_file,
                maxBytes=self.config.max_log_size * 1024 * 1024,
                backupCount=5
            )
        else:
            handler = logging.FileHandler(self.config.log_file)
            
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        logger = logging.getLogger('openinsider')
        logger.setLevel(log_level)
        logger.addHandler(handler)
        
        # Add console output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    def _setup_directories(self) -> None:
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        if self.config.cache_enabled:
            Path(self.config.cache_dir).mkdir(parents=True, exist_ok=True)
    
    @retry(tries=3, delay=2, backoff=2)
    def _fetch_data(self, url: str) -> requests.Response:
        return requests.get(url, timeout=self.config.timeout)
    
    def _get_cache_path(self, year: int, month: int) -> Path:
        return Path(self.config.cache_dir) / f"data_{year}_{month}.json"
    
    def _is_cache_valid(self, cache_path: Path) -> bool:
        if not cache_path.exists():
            return False
        cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
        return cache_age < self.config.cache_max_age * 3600
    
    def _get_data_for_month(self, year: int, month: int) -> Set[tuple]:
        cache_path = self._get_cache_path(year, month)
        
        if self.config.cache_enabled and self._is_cache_valid(cache_path):
            with open(cache_path, 'r') as f:
                return set(tuple(x) for x in json.load(f))
        
        start_date = datetime(year, month, 1).strftime('%m/%d/%Y')
        end_date = (datetime(year, month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        end_date = end_date.strftime('%m/%d/%Y')
        
        url = f'http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=-1&fdr={start_date}+-+{end_date}&td=0&tdr=&fdlyl=&fdlyh=&daysago=&xp=1&xs=1&vl={self.config.min_transaction_value}&vh=&ocl=&och=&sic1=-1&sicl=100&sich=9999&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=5000&page=1'

        try:
            response = self._fetch_data(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table', {'class': 'tinytable'})
            if not table:
                self.logger.error(f"No table found for {month}-{year}")
                return set()
                
            rows = table.find('tbody').findAll('tr')
            data = set()
            
            for row in rows:
                cols = row.findAll('td')
                if not cols:
                    continue
                    
                insider_data = {key: cols[index].find('a').text.strip() if cols[index].find('a') else cols[index].text.strip()
                                for index, key in enumerate(['X', 'filing_date', 'trade_date', 'ticker', 'company_name',
                                                             'owner_name', 'Title', 'transaction_type', 'purchase_price', 'Qty',
                                                             'shares_held', '% change', 'Value'])}

                # Apply filters
                if self._apply_filters(insider_data):
                    data.add(tuple(insider_data.values()))
            
            # Save cache
            if self.config.cache_enabled:
                with open(cache_path, 'w') as f:
                    json.dump([list(x) for x in data], f)
            
            return data
            
        except Exception as e:
            self.logger.error(f"Error fetching data for {month}-{year}: {str(e)}")
            return set()
    
    def _clean_numeric(self, value: str) -> float:
        """Clean numeric values from strings, handling currency, percentages, and text."""
        if not value or value.lower() in ['n/a', 'new']:
            return 0.0
        # Remove currency symbols and commas
        clean = value.replace('$', '').replace(',', '')
        # Handle percentages by removing % and converting to decimal
        if '%' in clean:
            clean = clean.replace('+', '').replace('%', '')
            return 0.0  # We don't need the actual percentage value
        try:
            return float(clean)
        except ValueError:
            return 0.0  # Return 0 for any non-numeric values

    def _apply_filters(self, data: Dict[str, str]) -> bool:
        try:
            # Check transaction type filter
            if self.config.transaction_types and data['transaction_type'] not in self.config.transaction_types:
                return False
                
            # Check excluded companies
            if data['ticker'] in self.config.exclude_companies:
                return False

            # Check included companies
            if self.config.include_companies and data['ticker'] not in self.config.include_companies:
                return False
            ``
            return True
        except (ValueError, KeyError) as e:
            self.logger.warning(f"Error filtering data: {str(e)}")
            return False
    
    def scrape(self) -> None:
        self.logger.info("Starting scraping process...")
        
        all_data = []
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = []
            total_months = sum(
                12 if year != current_year else current_month
                for year in range(self.config.start_year, current_year + 1)
            )
            
            for year in range(self.config.start_year, current_year + 1):
                start_month = 1 if year != self.config.start_year else self.config.start_month
                end_month = current_month if year == current_year else 12
                
                for month in range(start_month, end_month + 1):
                    futures.append(executor.submit(self._get_data_for_month, year, month))
            
            with tqdm(total=len(futures), desc="Processing months") as pbar:
                for future in as_completed(futures):
                    try:
                        data = future.result()
                        all_data.extend(data)
                        pbar.update(1)
                    except Exception as e:
                        self.logger.error(f"Error processing month: {str(e)}")
        
        self.logger.info(f"Scraping completed. Found {len(all_data)} transactions.")
        self._save_data(all_data)
    
    def _save_data(self, data: List[tuple]) -> None:
        field_names = ['X', 'filing_date', 'trade_date', 'ticker', 'company_name',
                       'owner_name', 'Title', 'transaction_type', 'purchase_price', 'Qty',
                       'shares_held', '% change', 'Value']
        
        df = pd.DataFrame(data, columns=field_names)
        output_path = Path(self.config.output_dir) / self.config.output_file
        
        if self.config.output_format.lower() == 'csv':
            df.to_csv(output_path, index=False)
        elif self.config.output_format.lower() == 'parquet':
            df.to_parquet(output_path, index=False)
        
        self.logger.info(f"Data saved to {output_path}")

if __name__ == '__main__':
    try:
        scraper = OpenInsiderScraper()
        scraper.scrape()
    except Exception as e:
        logging.error(f"Kritischer Fehler: {str(e)}")
        raise
