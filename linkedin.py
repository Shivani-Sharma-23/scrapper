from base_scraper import BaseScraper
from bs4 import BeautifulSoup
import logging

from datetime import datetime, timedelta
import urllib.parse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time

class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn jobs"""
    
    def __init__(self):
        super().__init__("LinkedIn")
        self.base_url = "https://www.linkedin.com"
        self.driver = None
        self.setup_driver()
        
    def setup_driver(self):
        """Setup Selenium WebDriver for LinkedIn"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        try:
            self.driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception as e:
            logging.error(f"Failed to setup Chrome driver: {e}")
            self.driver = None
    
    def scrape_jobs(self, keywords=None, max_jobs=50):
        """Scrape jobs from LinkedIn"""
        if not self.driver:
            logging.error("WebDriver not available, cannot scrape LinkedIn")
            return []
            
        jobs = []
        
        if not keywords:
            keywords = ['software engineer', 'python developer', 'data analyst', 'web developer']
        
        for keyword in keywords:
            if len(jobs) >= max_jobs:
                break
                
            logging.info(f"Scraping LinkedIn for keyword: {keyword}")
            
            try:
                job_results = self._search_jobs(keyword, max_jobs - len(jobs))
                jobs.extend(job_results)
                self.random_delay(3, 6)
                
            except Exception as e:
                logging.error(f"Error scraping LinkedIn for keyword '{keyword}': {e}")
                continue
        
        logging.info(f"Scraped {len(jobs)} jobs from LinkedIn")
        return jobs[:max_jobs]
    
    def _search_jobs(self, keyword, max_jobs):
        """Search for jobs on LinkedIn"""
        jobs = []
        
        # Build search URL
        search_url = self._build_search_url(keyword)
        
        try:
            self.driver.get(search_url)
            time.sleep(3)
            
            # Wait for job listings to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='job-card']"))
            )
            
            # Scroll to load more jobs
            self._scroll_to_load_jobs()
            
            # Get job cards
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='job-card']")
            
            for i, job_card in enumerate(job_cards[:max_jobs]):
                if len(jobs) >= max_jobs:
                    break
                    
                try:
                    job_data = self.parse_job_details(job_card)
                    if job_data:
                        jobs.append(job_data)
                        
                except Exception as e:
                    logging.error(f"Error parsing LinkedIn job card {i}: {e}")
                    continue
                    
        except TimeoutException:
            logging.error("Timeout waiting for LinkedIn job listings to load")
        except Exception as e:
            logging.error(f"Error searching LinkedIn jobs: {e}")
            
        return jobs
    
    def _build_search_url(self, keyword):
        """Build LinkedIn job search URL"""
        encoded_keyword = urllib.parse.quote(keyword)
        return f"{self.base_url}/jobs/search/?keywords={encoded_keyword}&location=India&geoId=102713980&f_TPR=r86400&f_JT=F%2CI&sortBy=DD"
    
    def _scroll_to_load_jobs(self):
        """Scroll page to load more job listings"""
        try:
            for _ in range(3):  # Scroll 3 times
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
        except Exception as e:
            logging.error(f"Error scrolling LinkedIn page: {e}")
    
    def parse_job_details(self, job_card):
        """Parse individual job details from LinkedIn job card"""
        try:
            # Job title
            title_element = job_card.find_element(By.CSS_SELECTOR, "h3 a")
            job_role = self.clean_text(title_element.text)
            apply_link = title_element.get_attribute('href')
            
            # Company name
            company_element = job_card.find_element(By.CSS_SELECTOR, "h4 a")
            company_name = self.clean_text(company_element.text)
            
            # Location
            location_element = job_card.find_element(By.CSS_SELECTOR, "[data-testid='job-location']")
            location = self.clean_text(location_element.text)
            
            # Job description (limited from card view)
            description = f"{job_role} position at {company_name}"
            try:
                desc_element = job_card.find_element(By.CSS_SELECTOR, ".job-search-card__snippet")
                description = self.clean_text(desc_element.text)
            except NoSuchElementException:
                pass
            
            # Time posted
            time_element = job_card.find_element(By.CSS_SELECTOR, "time")
            posted_time = self.clean_text(time_element.text)
            
            # Extract salary/stipend info if available
            stipend = ""
            try:
                salary_element = job_card.find_element(By.CSS_SELECTOR, ".job-search-card__salary-info")
                stipend = self.clean_text(salary_element.text)
            except NoSuchElementException:
                pass
            
            # Determine job type and experience level
            job_type = "Full-time"
            experience_level = "Entry Level"
            
            # Check if it's an internship
            if any(keyword in job_role.lower() for keyword in ['intern', 'trainee', 'graduate']):
                job_type = "Internship"
            elif any(keyword in job_role.lower() for keyword in ['senior', 'lead', 'principal']):
                experience_level = "Senior Level"
                job_type = "Full-time"
            elif any(keyword in job_role.lower() for keyword in ['mid', 'intermediate', '3+']):
                experience_level = "Mid Level"
                job_type = "Full-time"
            
            # Extract skills (limited in card view)
            skills = self._extract_skills_from_text(f"{job_role} {description}")
            
            # Calculate application deadline (estimate)
            application_deadline = None
            if 'day' in posted_time.lower():
                try:
                    days_match = re.search(r'(\d+)\s*days?\s*ago', posted_time)
                    if days_match:
                        days_ago = int(days_match.group(1))
                        # Estimate 30 days from posting date
                        deadline_date = datetime.now() + timedelta(days=(30 - days_ago))
                        application_deadline = deadline_date.isoformat()
                except:
                    pass
            
            job_data = {
                'jobId': self.generate_job_id(company_name, job_role, self.site_name),
                'jobRole': job_role,
                'companyName': company_name,
                'description': description,
                'stipend': stipend,
                'duration': "Not specified",
                'location': location,
                'applyLink': apply_link,
                'skills': skills,
                'site': self.site_name,
                'jobType': job_type,
                'category': self._categorize_job(job_role, skills),
                'experienceLevel': experience_level,
                'applicationDeadline': application_deadline
            }
            
            return job_data
            
        except Exception as e:
            logging.error(f"Error parsing LinkedIn job details: {e}")
            return None
    
    def _extract_skills_from_text(self, text):
        """Extract common skills from job text"""
        common_skills = [
            'Python', 'Java', 'JavaScript', 'React', 'Node.js', 'Angular', 'Vue.js',
            'HTML', 'CSS', 'SQL', 'MongoDB', 'PostgreSQL', 'MySQL', 'Redis',
            'Django', 'Flask', 'Spring', 'Express', 'FastAPI', 'Laravel',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'Jenkins', 'Git',
            'Machine Learning', 'Deep Learning', 'TensorFlow', 'PyTorch', 'Pandas',
            'NumPy', 'Scikit-learn', 'Data Analysis', 'Statistics', 'R',
            'UI/UX', 'Figma', 'Adobe', 'Photoshop', 'Illustrator',
            'Project Management', 'Agile', 'Scrum', 'JIRA', 'Confluence'
        ]
        
        found_skills = []
        text_lower = text.lower()
        
        for skill in common_skills:
            if skill.lower() in text_lower:
                found_skills.append(skill)
        
        return found_skills[:10]  # Limit to 10 skills
    
    def _categorize_job(self, job_role, skills):
        """Categorize job based on role and skills"""
        job_role_lower = job_role.lower()
        skills_text = ' '.join(skills).lower()
        
        if any(keyword in job_role_lower or keyword in skills_text 
               for keyword in ['software', 'developer', 'engineer', 'programming', 'coding']):
            return 'Software Development'
        elif any(keyword in job_role_lower or keyword in skills_text 
                 for keyword in ['data', 'analyst', 'scientist', 'machine learning', 'ai']):
            return 'Data Science'
        elif any(keyword in job_role_lower or keyword in skills_text 
                 for keyword in ['design', 'ui', 'ux', 'graphic', 'creative']):
            return 'Design'
        elif any(keyword in job_role_lower or keyword in skills_text 
                 for keyword in ['marketing', 'digital', 'content', 'social media']):
            return 'Marketing'
        elif any(keyword in job_role_lower or keyword in skills_text 
                 for keyword in ['manager', 'management', 'lead', 'director']):
            return 'Management'
        else:
            return 'Other'
    
    def close(self):
        """Close the webdriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def __del__(self):
        """Destructor to ensure driver is closed"""
        self.close()