from base_scraper import BaseScraper
from bs4 import BeautifulSoup

import re
from datetime import datetime, timedelta
import urllib.parse

class InternshalaSScraper(BaseScraper):
    """Scraper for Internshala jobs and internships"""
    
    def __init__(self):
        super().__init__("Internshala")
        self.base_url = "https://internshala.com"
        
    def scrape_jobs(self, keywords=None, max_jobs=50):
        """Scrape jobs from Internshala"""
        jobs = []
        
        if not keywords:
            keywords = ['software', 'python', 'web development', 'data science']
        
        for keyword in keywords:
            if len(jobs) >= max_jobs:
                break
                
            logging.info(f"Scraping Internshala for keyword: {keyword}")
            
            # Search for internships
            internship_jobs = self._scrape_category(keyword, 'internships', max_jobs - len(jobs))
            jobs.extend(internship_jobs)
            
            if len(jobs) >= max_jobs:
                break
                
            # Search for jobs
            job_jobs = self._scrape_category(keyword, 'jobs', max_jobs - len(jobs))
            jobs.extend(job_jobs)
            
            self.random_delay(2, 4)
        
        logging.info(f"Scraped {len(jobs)} jobs from Internshala")
        return jobs[:max_jobs]
    
    def _scrape_category(self, keyword, category, max_jobs):
        """Scrape a specific category (internships or jobs)"""
        jobs = []
        page = 1
        
        while len(jobs) < max_jobs and page <= 3:  # Limit to 3 pages per category
            url = self._build_search_url(keyword, category, page)
            
            response = self.get_page(url)
            if not response:
                break
                
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if category == 'internships':
                job_elements = soup.find_all('div', class_='internship_meta')
            else:
                job_elements = soup.find_all('div', class_='job_meta')
            
            if not job_elements:
                break
                
            for job_element in job_elements:
                if len(jobs) >= max_jobs:
                    break
                    
                job_data = self.parse_job_details(job_element, category)
                if job_data:
                    jobs.append(job_data)
                    
            page += 1
            self.random_delay(1, 3)
            
        return jobs
    
    def _build_search_url(self, keyword, category, page=1):
        """Build search URL for Internshala"""
        encoded_keyword = urllib.parse.quote(keyword)
        
        if category == 'internships':
            base_path = '/internships'
        else:
            base_path = '/jobs'
            
        url = f"{self.base_url}{base_path}/keywords-{encoded_keyword}"
        
        if page > 1:
            url += f"/page-{page}"
            
        return url
    
    def parse_job_details(self, job_element, category):
        """Parse individual job details from Internshala"""
        try:
            # Find the main container
            container = job_element.find_parent('div', class_='individual_internship')
            if not container:
                return None
            
            # Job title and company
            title_element = container.find('h3', class_='heading_4_5')
            if not title_element:
                return None
                
            job_role = self.clean_text(title_element.get_text())
            
            # Company name
            company_element = container.find('p', class_='heading_6')
            company_name = self.clean_text(company_element.get_text()) if company_element else "Unknown"
            
            # Apply link
            apply_link_element = container.find('a', href=True)
            apply_link = ""
            if apply_link_element:
                href = apply_link_element.get('href')
                if href.startswith('/'):
                    apply_link = self.base_url + href
                else:
                    apply_link = href
            
            # Location
            location_element = container.find('span', string=re.compile(r'Location|Work From Home|Remote'))
            location = "Remote"
            if location_element:
                location_text = location_element.find_parent().get_text()
                if "Work From Home" in location_text or "Remote" in location_text:
                    location = "Remote"
                else:
                    location_match = re.search(r'Location[:\s]*([^•\n]+)', location_text)
                    if location_match:
                        location = self.clean_text(location_match.group(1))
            
            # Stipend
            stipend_element = container.find('span', string=re.compile(r'Stipend|Salary'))
            stipend = ""
            if stipend_element:
                stipend_text = stipend_element.find_parent().get_text()
                stipend_match = re.search(r'₹[\d,]+(?:-₹[\d,]+)?(?:/month|/year)?|Unpaid|Performance based', stipend_text)
                if stipend_match:
                    stipend = self.clean_text(stipend_match.group(0))
            
            # Duration
            duration_element = container.find('span', string=re.compile(r'Duration'))
            duration = ""
            if duration_element:
                duration_text = duration_element.find_parent().get_text()
                duration_match = re.search(r'Duration[:\s]*([^•\n]+)', duration_text)
                if duration_match:
                    duration = self.clean_text(duration_match.group(1))
            
            # Skills
            skills_container = container.find('div', class_='round_tabs_container')
            skills = []
            if skills_container:
                skill_elements = skills_container.find_all('span', class_='round_tabs')
                skills = [self.clean_text(skill.get_text()) for skill in skill_elements]
            
            # Experience level
            experience_level = "Entry Level"
            if category == 'jobs':
                exp_element = container.find('span', string=re.compile(r'Experience'))
                if exp_element:
                    exp_text = exp_element.find_parent().get_text()
                    if any(keyword in exp_text.lower() for keyword in ['senior', '3+', '5+', 'experienced']):
                        experience_level = "Mid Level"
                    elif any(keyword in exp_text.lower() for keyword in ['lead', 'manager', '7+', '10+']):
                        experience_level = "Senior Level"
            
            # Application deadline
            deadline_element = container.find('div', class_='status')
            application_deadline = None
            if deadline_element:
                deadline_text = deadline_element.get_text()
                # Try to extract deadline information
                if 'days left' in deadline_text.lower():
                    days_match = re.search(r'(\d+)\s*days?\s*left', deadline_text)
                    if days_match:
                        days = int(days_match.group(1))
                        application_deadline = (datetime.now() + timedelta(days=days)).isoformat()
            
            job_data = {
                'jobId': self.generate_job_id(company_name, job_role, self.site_name),
                'jobRole': job_role,
                'companyName': company_name,
                'description': f"{job_role} position at {company_name}",
                'stipend': stipend,
                'duration': duration,
                'location': location,
                'applyLink': apply_link,
                'skills': skills,
                'site': self.site_name,
                'jobType': 'Internship' if category == 'internships' else 'Full-time',
                'category': self._categorize_job(job_role, skills),
                'experienceLevel': experience_level,
                'applicationDeadline': application_deadline
            }
            
            return job_data
            
        except Exception as e:
            logging.error(f"Error parsing Internshala job: {e}")
            return None
    
    def _categorize_job(self, job_role, skills):
        """Categorize job based on role and skills"""
        job_role_lower = job_role.lower()
        skills_text = ' '.join(skills).lower()
        
        if any(keyword in job_role_lower or keyword in skills_text 
               for keyword in ['software', 'developer', 'programming', 'coding']):
            return 'Software Development'
        elif any(keyword in job_role_lower or keyword in skills_text 
                 for keyword in ['data', 'analyst', 'machine learning', 'ai']):
            return 'Data Science'
        elif any(keyword in job_role_lower or keyword in skills_text 
                 for keyword in ['design', 'ui', 'ux', 'graphic']):
            return 'Design'
    
        else:
            return 'Other'
