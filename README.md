# OpenInsider Data Analysis

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Code Style](https://img.shields.io/badge/code%20style-black-black.svg)](https://github.com/psf/black)

This project scrapes insider trades and price history of stocks to examine what are high conviction insider trades. 
Lets make some bread together!

## 🔧 Usage

1. Run the scraper:
```bash
python openinsider_scraper.py
```
2. Download price history for all ticker symbols:
```bash
python download_price_data.py
```
3. Compute returns of all trades:
```bash
python compute_returns.py
```
4. Analyze data in the Jupyter Notebook:



## ⚙️ Configuration

All settings are managed through `config.yaml`:

### 📁 Output Settings
```yaml
output:
  directory: data       # Output directory for scraped data
  filename: insider     # Base filename for output files
  format: csv          # Output format (csv or parquet)
```

### 🔄 Scraping Settings
```yaml
scraping:
  start_year: 2024           # Start year
  start_month: 3             # Start month
  max_workers: 10            # Number of parallel downloads
  retry_attempts: 3          # Number of retry attempts
  timeout: 30               # Request timeout in seconds
```

### 🔎 Filter Settings
```yaml
filters:
  min_transaction_value: 50000  # Minimum transaction value in USD
  transaction_types:            # Transaction types to include
    - P - Purchase
    - S - Sale
    - F - Tax
  exclude_companies: []         # Companies to exclude (by ticker)
  min_shares_traded: 100        # Minimum number of shares
```

### 📝 Logging Settings
```yaml
logging:
  level: INFO          # Logging level (DEBUG, INFO, WARNING, ERROR)
  file: scraper.log    # Log file name
  rotate_logs: true    # Enable log rotation
  max_log_size: 10     # Max log size in MB
```

### 💾 Cache Settings
```yaml
cache:
  enabled: true        # Enable caching
  directory: .cache    # Cache directory
  max_age: 24         # Cache max age in hours
```
