import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("linkedin_automation")

# Load environment variables
load_dotenv()

LINKEDIN_USERNAME = os.getenv("LINKEDIN_USERNAME")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")


class LinkedInAutomation:
    def __init__(self, headless=False):
        """Initialize the LinkedIn automation with optional headless mode"""
        self.driver = None
        self.headless = headless
        self.is_logged_in = False

    def _initialize_driver(self):
        """Initialize the Selenium WebDriver"""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--start-maximized")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)

    def login(self):
        """Login to LinkedIn with credentials from environment variables"""
        if not LINKEDIN_USERNAME or not LINKEDIN_PASSWORD:
            raise ValueError("LinkedIn credentials not set in environment variables")
        
        if self.driver is None:
            self._initialize_driver()
        
        try:
            logger.info("Logging in to LinkedIn...")
            self.driver.get("https://www.linkedin.com/login")
            
            # Wait for the login page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            
            # Enter username and password
            self.driver.find_element(By.ID, "username").send_keys(LINKEDIN_USERNAME)
            self.driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # Wait for login to complete
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav"))
            )
            
            logger.info("Successfully logged in to LinkedIn")
            self.is_logged_in = True
            return True
            
        except TimeoutException:
            logger.error("Timeout while logging in to LinkedIn")
            return False
        except Exception as e:
            logger.error(f"Error logging in to LinkedIn: {str(e)}")
            return False

    def send_message(self, profile_url, message):
        """
        Send a message to a LinkedIn user by profile URL
        
        Args:
            profile_url: The LinkedIn profile URL of the recipient
            message: The message to send
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self.is_logged_in:
            if not self.login():
                return False
        
        try:
            logger.info(f"Navigating to profile: {profile_url}")
            self.driver.get(profile_url)
            
            # Wait for profile page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".pv-top-card"))
            )
            
            # Find and click the message button (there are different possible selectors)
            selectors = [
                "button.pv-s-profile-actions--message",  # Modern layout
                "button.message-anywhere-button",  # Alternate layout
                "button.pvs-profile-actions__action",  # Another variation
                "button[aria-label='Message']"  # General aria-label
            ]
            
            message_button = None
            for selector in selectors:
                try:
                    message_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not message_button:
                logger.error("Could not find message button on profile")
                return False
            
            message_button.click()
            
            # Wait for message dialog to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.msg-form__contenteditable"))
            )
            
            # Type the message
            message_input = self.driver.find_element(By.CSS_SELECTOR, "div.msg-form__contenteditable")
            message_input.click()
            message_input.send_keys(message)
            
            # Send the message
            send_button = self.driver.find_element(By.CSS_SELECTOR, "button.msg-form__send-button")
            send_button.click()
            
            # Wait for message to be sent
            time.sleep(2)
            
            logger.info(f"Successfully sent message to {profile_url}")
            return True
            
        except TimeoutException:
            logger.error(f"Timeout while sending message to {profile_url}")
            return False
        except Exception as e:
            logger.error(f"Error sending message to {profile_url}: {str(e)}")
            return False
    
    def close(self):
        """Close the browser session"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.is_logged_in = False


# Singleton pattern for reusing the browser session
_linkedin_instance = None

def get_linkedin_automation(headless=False):
    """Get or create a LinkedIn automation instance"""
    global _linkedin_instance
    if _linkedin_instance is None:
        _linkedin_instance = LinkedInAutomation(headless=headless)
    return _linkedin_instance

def send_linkedin_message(profile_url, message_content):
    """
    Send a LinkedIn message using Selenium
    
    Args:
        profile_url: LinkedIn profile URL
        message_content: Message to send
        
    Returns:
        dict: Result of operation with success status and message
    """
    try:
        linkedin = get_linkedin_automation(headless=False)  # Set to True for production
        success = linkedin.send_message(profile_url, message_content)
        
        if success:
            return {
                "status": "success",
                "message": "LinkedIn message sent successfully"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to send LinkedIn message"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error: {str(e)}"
        }


if __name__ == "__main__":
    # Test the LinkedIn automation
    profile_url = "https://www.linkedin.com/in/example-profile"
    message = "Hello! This is a test message from the LinkedIn automation."
    
    result = send_linkedin_message(profile_url, message)
    print(result)
