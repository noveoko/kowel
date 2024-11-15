import requests
from bs4 import BeautifulSoup
import os
import time
from urllib.parse import urljoin
import logging

class MazovianLibraryScraper:
    def __init__(self, base_url="https://mbc.cyfrowemazowsze.pl/"):
        self.base_url = base_url
        self.session = requests.Session()
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='scraper.log'
        )
        self.logger = logging.getLogger(__name__)

    def get_edition_links(self, search_page_html):
        """Extract links to individual edition pages"""
        soup = BeautifulSoup(search_page_html, 'html.parser')
        links = []
        for item in soup.find_all('div', class_='objectbox__content'):
            link_elem = item.find('a')
            if link_elem:
                links.append({
                    'url': urljoin(self.base_url, link_elem['href']),
                    'title': link_elem.text.strip()
                })
        return links

    def extract_pdf_url(self, edition_page_url):
        """Get the PDF download URL from an edition page"""
        try:
            response = self.session.get(edition_page_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for content link which typically leads to PDF
            content_link = soup.find('a', {'class': 'dlibra-icon-file'})
            if content_link:
                return urljoin(self.base_url, content_link['href'])
        except Exception as e:
            self.logger.error(f"Error extracting PDF URL from {edition_page_url}: {str(e)}")
        return None

    def download_pdf(self, pdf_url, output_path):
        """Download PDF file"""
        try:
            response = self.session.get(pdf_url, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return True
        except Exception as e:
            self.logger.error(f"Error downloading PDF from {pdf_url}: {str(e)}")
            return False

    def clean_filename(self, title):
        """Create valid filename from title"""
        invalid_chars = '<>:"/\\|?*'
        filename = ''.join(c if c not in invalid_chars else '_' for c in title)
        return filename[:150] + '.pdf'  # Limit filename length

    def scrape_editions(self, search_results_html, output_dir="downloaded_editions"):
        """Main scraping function"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        edition_links = self.get_edition_links(search_results_html)
        self.logger.info(f"Found {len(edition_links)} editions to process")

        for edition in edition_links:
            filename = self.clean_filename(edition['title'])
            output_path = os.path.join(output_dir, filename)
            
            if os.path.exists(output_path):
                self.logger.info(f"Skipping {filename} - already exists")
                continue

            self.logger.info(f"Processing: {edition['title']}")
            pdf_url = self.extract_pdf_url(edition['url'])
            
            if pdf_url:
                if self.download_pdf(pdf_url, output_path):
                    self.logger.info(f"Successfully downloaded: {filename}")
                time.sleep(2)  # Polite delay between downloads
            else:
                self.logger.warning(f"Could not find PDF URL for: {edition['title']}")

        self.logger.info("Scraping completed")

# Example usage
if __name__ == "__main__":
    scraper = MazovianLibraryScraper()
    
    # Read the search results HTML from file
    with open('search_results.html', 'r', encoding='utf-8') as f:
        search_results_html = f.read()
    
    scraper.scrape_editions(search_results_html)
