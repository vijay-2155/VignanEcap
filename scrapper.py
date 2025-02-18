import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
import os
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Chrome
from bs4 import BeautifulSoup, SoupStrainer
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_driver():
    """Setup and return configured WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    
    # Check if running on Linux (deployment) or Windows (development)
    if os.name == 'nt':  # Windows
        driver_path = "edgedriver_win64/msedgedriver.exe"
        from selenium.webdriver.edge.service import Service as EdgeService
        from selenium.webdriver.edge.options import Options as EdgeOptions
        from selenium.webdriver import Edge
        
        edge_options = EdgeOptions()
        edge_options.add_argument('--headless')
        service = EdgeService(driver_path)
        return Edge(service=service, options=edge_options)
    else:  # Linux
        return Chrome(options=chrome_options)

def login_to_portal(driver, username, password):
    """Handle login process"""
    wait = WebDriverWait(driver, 10)
    try:
        # Clear cache and cookies
        driver.delete_all_cookies()
        
        # Navigate to login page with retry
        for attempt in range(3):
            try:
                driver.get("https://webprosindia.com/vignanit/Default.aspx")
                break
            except Exception as e:
                if attempt == 2:
                    return False, f"Failed to load login page: {str(e)}"
                time.sleep(2)
        
        # Wait for and interact with elements
        try:
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "txtId2")),
                message="Username field not found"
            )
            password_field = wait.until(
                EC.presence_of_element_located((By.ID, "txtPwd2")),
                message="Password field not found"
            )
            
            # Clear and send keys with verification
            username_field.clear()
            password_field.clear()
            username_field.send_keys(username)
            password_field.send_keys(password)
            
            # Verify input
            if username_field.get_attribute('value') != username:
                return False, "Failed to input username correctly"
            
            # Execute login scripts with verification
            driver.execute_script("encryptJSText(2)")
            driver.execute_script("setValue(2)")
            
            # Click login button
            login_button = wait.until(
                EC.element_to_be_clickable((By.ID, "imgBtn2")),
                message="Login button not clickable"
            )
            login_button.click()
            
            # Wait for login success with shorter timeout
            success_element = wait.until(
                EC.presence_of_element_located((By.ID, "divscreens")),
                message="Login failed - invalid credentials"
            )
            
            # Verify login success
            if not success_element.is_displayed():
                return False, "Login failed - authentication error"
            
            return True, "Login successful"
            
        except TimeoutException as e:
            return False, f"Login timeout: {str(e)}"
            
    except Exception as e:
        return False, f"Login error: {str(e)}"

def get_attendance_data(driver):
    """Extract attendance data from portal"""
    wait = WebDriverWait(driver, 10)
    try:
        # Navigate to attendance page with retry
        academic_url = "https://webprosindia.com/vignanit/Academics/studentacadamicregister.aspx?scrid=2"
        for attempt in range(3):
            try:
                driver.get(academic_url)
                break
            except Exception:
                if attempt == 2:
                    return None, "Failed to load attendance page"
                time.sleep(2)
        
        # Wait for export button with retry
        export_button = None
        for attempt in range(3):
            try:
                export_button = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[value='Export']"))
                )
                break
            except Exception:
                if attempt == 2:
                    return None, "Export button not found"
                time.sleep(2)
        
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(downloads_path):
            os.makedirs(downloads_path)
        
        # Track new files with improved timeout
        initial_files = set(os.listdir(downloads_path))
        export_button.click()
        
        # Wait for download with extended timeout
        newest_file = None
        timeout = time.time() + 15  # Extended timeout
        while time.time() < timeout and not newest_file:
            current_files = set(os.listdir(downloads_path))
            new_files = current_files - initial_files
            excel_files = [f for f in new_files if f.endswith(('.xls', '.xlsx'))]
            if excel_files:
                newest_file = max([os.path.join(downloads_path, f) for f in excel_files], 
                                key=os.path.getmtime)
                # Verify file is complete
                if os.path.getsize(newest_file) > 0:
                    break
            time.sleep(0.5)
            
        if not newest_file:
            return None, "No attendance data file downloaded"
            
        return newest_file, "Data exported successfully"
        
    except Exception as e:
        return None, f"Failed to get attendance data: {str(e)}"

def parse_attendance_data(file_path):
    """Parse attendance HTML and return formatted data"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            soup = BeautifulSoup(file.read(), 'lxml', parse_only=SoupStrainer(['tr', 'td']))
        
        # Get student ID
        student_id = soup.select_one('td.reportData2').text.strip().replace(':', '').strip()
        
        # Get dates and find today's column
        header_row = soup.select_one('tr.reportHeading2WithBackground')
        dates = [td.text.strip() for td in header_row.select('td')]
        today = time.strftime("%d/%m")
        today_index = next((i for i, date in enumerate(dates) if today in date), None)
        
        # Process attendance data
        rows = soup.select('tr[title]')
        total_present = total_classes = 0
        todays_attendance = []
        subject_attendance = []
        
        for row in rows:
            cells = row.select('td.cellBorder')
            if len(cells) >= 2:
                subject = cells[1].text.strip()
                attendance = cells[-2].text.strip()
                percentage = cells[-1].text.strip()
                
                if attendance != "0/0":
                    present, total = map(int, attendance.split('/'))
                    total_present += present
                    total_classes += total
                    
                    # Only add subjects with clear P or A status
                    if today_index and today_index < len(cells):
                        today_status = cells[today_index].text.strip()
                        if 'P' in today_status or 'A' in today_status:
                            todays_attendance.append(f"{subject}: {'P' if 'P' in today_status else 'A'}")
                    
                    if percentage != ".00":
                        subject_attendance.append(f"{subject:.<8} {attendance:<7} {percentage}%")
        
        # Calculate overall percentage and skippable hours
        overall_percentage = (total_present / total_classes * 100) if total_classes > 0 else 0
        skippable_hours = calculate_skippable_hours(total_present, total_classes)
        
        return {
            'student_id': student_id,
            'total_present': total_present,
            'total_classes': total_classes,
            'overall_percentage': overall_percentage,
            'todays_attendance': todays_attendance,
            'subject_attendance': subject_attendance,
            'skippable_hours': skippable_hours
        }
    except Exception as e:
        raise Exception(f"Failed to parse attendance data: {str(e)}")

def calculate_skippable_hours(present, total):
    """Calculate how many hours can be skipped while maintaining 75%"""
    current = (present / total * 100)
    skippable = 0
    while current >= 75 and total < total + 20:
        skippable += 1
        total += 1
        current = (present / total * 100)
    return skippable

def get_attendance_report(username, password):
    """Main function to get attendance report"""
    driver = None
    downloaded_file = None
    
    try:
        logging.info(f"Starting attendance check for user {username}")
        
        # Initialize driver with retry
        retry_count = 3
        for attempt in range(retry_count):
            try:
                driver = setup_driver()
                break
            except WebDriverException as e:
                if attempt == retry_count - 1:
                    raise
                logging.warning(f"Driver setup failed (attempt {attempt + 1}): {str(e)}")
                time.sleep(2)
        
        # Login with retry
        for attempt in range(retry_count):
            success, message = login_to_portal(driver, username, password)
            if success:
                break
            if attempt == retry_count - 1:
                return f"❌ Login failed after {retry_count} attempts: {message}"
            logging.warning(f"Login failed (attempt {attempt + 1}): {message}")
            time.sleep(2)
        
        # Get attendance data
        file_path, message = get_attendance_data(driver)
        logging.info(f"Data extraction: {message}")
        if not file_path:
            return f"❌ {message}"
            
        # Parse and format data
        data = parse_attendance_data(file_path)
        downloaded_file = file_path
        logging.info("Data parsed successfully")
        
        # Format output
        output = []
        output.append(f"Hi {data['student_id']}")
        output.append(f"Total: {data['total_present']}/{data['total_classes']} ({data['overall_percentage']:.2f}%)\n")
        
        if data['todays_attendance']:
            output.append("Today's Attendance:")
            output.extend(data['todays_attendance'])
            output.append("")
        
        output.append(f"You can skip {data['skippable_hours']} hours and still maintain above 75%.\n")
        output.append("Subject-wise Attendance:")
        output.extend(data['subject_attendance'])
        
        report = "\n".join(output)
        logging.info(f"Report generated: {len(report)} characters")
        return report
        
    except WebDriverException as e:
        logging.error(f"WebDriver error: {str(e)}")
        return "❌ Browser automation error. Please try again later."
    except Exception as e:
        logging.error(f"Error in attendance report: {str(e)}")
        return f"❌ Error: {str(e)}"
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except:
                pass

if __name__ == "__main__":
    logging.info("Scraper module loaded successfully")