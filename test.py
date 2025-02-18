import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import os
from selenium.webdriver.edge.options import Options

# Path to msedgedriver.exe
edgedriver_path = "edgedriver_win64/msedgedriver.exe"

# Set up WebDriver
service = Service(edgedriver_path)
edge_options = Options()
edge_options.add_argument('--headless')  # Run browser in background
edge_options.add_argument('--disable-gpu')
edge_options.add_argument('--no-sandbox')
edge_options.add_argument('--disable-dev-shm-usage')
edge_options.add_argument('--disable-extensions')
edge_options.page_load_strategy = 'eager'  # Don't wait for all resources to load
driver = webdriver.Edge(service=service, options=edge_options)

try:
    # Open the login page
    driver.get("https://webprosindia.com/vignanit/Default.aspx")
    wait = WebDriverWait(driver, 5)
    
    # Login process
    username_field = wait.until(EC.presence_of_element_located((By.ID, "txtId2")))
    password_field = wait.until(EC.presence_of_element_located((By.ID, "txtPwd2")))

    # Enter credentials
    username = "24L35A0526"
    password = "13052005"
    username_field.send_keys(username)
    password_field.send_keys(password)

    # Execute required JavaScript for password encryption
    driver.execute_script("encryptJSText(2)")
    driver.execute_script("setValue(2)")

    # Click login button
    login_button = wait.until(EC.element_to_be_clickable((By.ID, "imgBtn2")))
    login_button.click()

    # Wait for login success
    wait.until(EC.presence_of_element_located((By.ID, "divscreens")))
    print("✅ Login successful!")

    # Navigate to academic register page
    academic_url = "https://webprosindia.com/vignanit/Academics/studentacadamicregister.aspx?scrid=2"
    driver.get(academic_url)
    print("✅ Navigated to academic register page")

    try:
        # Find and click export button
        export_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[value='Export']")))
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        initial_files = set(os.listdir(downloads_path))
        export_button.click()
        print("✅ Clicked export button")

        # Wait for download
        timeout = time.time() + 5  # 5 second timeout
        while time.time() < timeout:
            current_files = set(os.listdir(downloads_path))
            new_files = current_files - initial_files
            if any(f.endswith(('.html', '.htm')) for f in new_files):
                newest_file = max((os.path.join(downloads_path, f) for f in new_files), 
                                 key=os.path.getmtime)
                break
            time.sleep(0.1)  # Short sleep to prevent CPU overload
        
        # Get latest downloaded file
        files = [f for f in os.listdir(downloads_path) if f.endswith('.xls') or f.endswith('.xlsx') or f.endswith('.xls') or f.endswith('.xlsx')]
        if files:
            newest_file = max([os.path.join(downloads_path, f) for f in files], 
                             key=os.path.getmtime)
            
            # Read HTML content using BeautifulSoup
            from bs4 import BeautifulSoup, SoupStrainer

            # Only parse the relevant parts of HTML
            parse_only = SoupStrainer(['tr', 'td'])
            with open(newest_file, 'r', encoding='utf-8') as file:
                soup = BeautifulSoup(file.read(), 'lxml', parse_only=parse_only)
                
            # Extract student details
            student_id = soup.select_one('td.reportData2').text.strip().replace(':', '').strip()
            print(f"\nHi {student_id}")

            # Extract headers to get dates
            header_row = soup.select_one('tr.reportHeading2WithBackground')
            dates = [td.text.strip() for td in header_row.select('td')]
            today_index = None
            
            # Get today's date in DD/MM format
            today = time.strftime("%d/%m")
            
            # Find today's column index
            for i, date in enumerate(dates):
                if today in date:
                    today_index = i
                    break
            
            # Extract attendance data
            rows = soup.select('tr[title]')  # Get rows with subject data
            total_present = 0
            total_classes = 0
            todays_attendance = []
            subject_attendance = []
            
            for row in rows:
                cells = row.select('td.cellBorder')
                if len(cells) >= 2:
                    subject = cells[1].text.strip()
                    attendance = cells[-2].text.strip()  # Classes attended/total
                    percentage = cells[-1].text.strip()  # Percentage
                    
                    if attendance != "0/0":
                        present, total = map(int, attendance.split('/'))
                        total_present += present
                        total_classes += total
                        
                        # Check today's attendance if we found today's column
                        if today_index is not None and today_index < len(cells):
                            today_status = cells[today_index].text.strip()
                            if today_status and 'P' in today_status:
                                todays_attendance.append(f"{subject}: P")
                            elif today_status and 'A' in today_status:
                                todays_attendance.append(f"{subject}: A")
                        
                        # Store subject attendance
                        if percentage != ".00":
                            subject_attendance.append(f"{subject:.<8} {attendance:<7} {percentage}%")
            
            # Calculate overall percentage
            overall_percentage = (total_present / total_classes * 100) if total_classes > 0 else 0
            print(f"Total: {total_present}/{total_classes} ({overall_percentage:.2f}%)\n")
            
            # Print today's attendance
            if todays_attendance:
                print("Today's Attendance:")
                print('\n'.join(todays_attendance))
                print()
            
            # Calculate hours that can be skipped
            current_percentage = overall_percentage
            skippable_hours = 0
            temp_present = total_present
            temp_total = total_classes
            
            while current_percentage >= 75 and temp_total < total_classes + 20:
                skippable_hours += 1
                temp_total += 1
                current_percentage = (temp_present / temp_total * 100)
            
            print(f"You can skip {skippable_hours} hours and still maintain above 75%.\n")
            
            # Print subject-wise attendance
            print("Subject-wise Attendance:")
            print('\n'.join(subject_attendance))

            # Delete the downloaded file
            try:
                os.remove(newest_file)
                print("\n✅ Cleaned up downloaded file")
            except Exception as e:
                print(f"\n⚠️ Could not delete file: {str(e)}")

        else:
            print("❌ No HTML files found in Downloads folder")

    except Exception as e:
        print(f"❌ Error processing data: {str(e)}")

except Exception as e:
    print(f"❌ Error occurred: {str(e)}")

finally:
    print("Closing browser...")
    driver.quit()
