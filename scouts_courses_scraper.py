"""
Scouts Training Courses Scraper for getting courses from Scouting Ireland my.scouts.ie

Flow: Login → Manage Group → Events → Filter by "Training" → Select Year (2025/2026) → Navigate through all pages → Extract all training courses
"""

import json
import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

def load_credentials():
    """Load credentials from config.json"""
    with open('config.json', 'r') as f:
        config = json.load(f)
    return config['credentials']

def setup_driver(headless=False):  # Set to False so we can see what's happening
    """Setup Chrome WebDriver"""
    options = Options()
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def find_element_by_text(driver, text, tag='a', timeout=10):
    """Find element containing specific text - looks for links, buttons, tabs, etc."""
    try:
        # Wait for any overlays to disappear with longer timeout
        try:
            WebDriverWait(driver, 10).until_not(
                EC.presence_of_element_located((By.CLASS_NAME, "mud-overlay-scrim"))
            )
        except TimeoutException:
            # Try to click away overlay if it doesn't disappear
            try:
                driver.execute_script("document.querySelector('.mud-overlay-scrim')?.click()")
                time.sleep(1)
            except:
                pass  # No overlay found or clickable, continue

        # Search multiple element types that could contain tabs
        search_tags = ['a', 'button', 'div', 'span', 'li', 'td', 'th']

        # XPath strategies for each tag type
        for tag_type in search_tags:
            xpaths = [
                f"//{tag_type}[contains(text(), '{text}')]",
                f"//{tag_type}[contains(., '{text}')]",
                f"//{tag_type}[normalize-space() = '{text}']",
                f"//{tag_type}[contains(normalize-space(), '{text}')]",
                f"//{tag_type}[text() = '{text}']",
                f"//{tag_type}[text() = '{text.upper()}']"
            ]

            for xpath in xpaths:
                try:
                    element = WebDriverWait(driver, timeout // len(search_tags)).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    print(f"Found '{text}' as {tag_type}: {element.text}")
                    return element
                except TimeoutException:
                    continue

        # Fallback: search all clickable elements
        clickable_elements = driver.find_elements(By.TAG_NAME, "a") + \
                           driver.find_elements(By.TAG_NAME, "button") + \
                           driver.find_elements(By.XPATH, "//*[contains(@onclick, '')]") + \
                           driver.find_elements(By.CSS_SELECTOR, "[role='tab']")

        for element in clickable_elements:
            if element.is_displayed():
                element_text = element.text.strip()
                if text.upper() in element_text.upper():
                    print(f"Found '{text}' via text search: '{element_text}'")
                    return element

    except Exception as e:
        print(f"Could not find element with text '{text}': {e}")

    return None

def parse_course_info(raw_text):
    """Parse raw course text into structured data
    We're making an assumption that the structure of the raw_text for courses is consistent"""

    # Initialize result dictionary
    course_data = {
        'title': '',
        'description': '',
        'status': '',
        'location': '',
        'date': '',
        'bookable': ''
    }

    # Skip very short texts or those that look like just course codes
    if len(raw_text) < 50:
        return course_data

    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]

    course_data['title'] = lines[0]
    course_data['description'] = lines[1]
    course_data['status'] = lines[2].split(':')[1].strip()
    course_data['location'] = lines[3].split('-')[0].strip()
    course_data['date'] = lines[3].split('-')[1].strip()
    if len(lines) > 5:
        course_data['bookable'] = lines[5]

    # Only return course data if we have a title or description
    if not course_data['title'] and not course_data['description']:
        return {'title': '', 'description': '', 'status': '', 'location': '', 'date': '', 'bookable': ''}

    return course_data


def extract_courses_from_page(driver):
    """Extract and parse course information from current page"""
    courses = []

    # Look for course data in various structures
    course_selectors = [
        'table tr',
        '.course-row',
        '.event-row',
        'ul li',
        '[class*="course"]',
        '[class*="event"]',
        '[class*="training"]',
        '[class*="card"]',
        '[class*="item"]',
        'div[class*="list"]',
        'div[class*="grid"]'
    ]

    # First try structured selectors
    for selector in course_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                text = element.text.strip()
                # Look for text that seems like a course (has training keywords and reasonable length)
                if len(text) > 100 and any(keyword.lower() in text.lower() for keyword in [
                    'safeguarding', 'training', 'course', 'workshop', 'first aid', 'adult', 'leader',
                    'scouter', 'woodbadge', 'youth programme', 'scouting together'
                ]):
                    parsed_course = parse_course_info(text)
                    if parsed_course['title']:  # Only add if we got a title
                        courses.append(parsed_course)
        except Exception as e:
            continue

    # If no courses found, try broader search for training-related content
    if not courses:
        print("Trying broader search for training content...")
        try:
            # Look for any elements containing training keywords
            all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Training')] | //*[@class[contains(.,'training')]] | //*[@id[contains(.,'training')]]")

            for element in all_elements:
                if element.is_displayed():
                    text = element.text.strip()
                    # Get parent or related elements for full course information
                    parent = element.find_element(By.XPATH, "./ancestor::*[1]")
                    if parent:
                        parent_text = parent.text.strip()
                        if len(parent_text) > 100 and 'Status:' in parent_text and 'From' in parent_text:
                            parsed_course = parse_course_info(parent_text)
                            if parsed_course['title']:
                                courses.append(parsed_course)

        except Exception as e:
            print(f"Broader search failed: {e}")

    # Also try to find elements with specific course patterns
    if not courses:
        print("Looking for course patterns...")
        try:
            # Look for patterns like "NE-" course codes
            pattern_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'NE-')]")
            for element in pattern_elements:
                if element.is_displayed():
                    # Get the containing element with full course info
                    parent = element.find_element(By.XPATH, "./ancestor::*[contains(text(), 'Status:')]")
                    if parent:
                        parent_text = parent.text.strip()
                        parsed_course = parse_course_info(parent_text)
                        if parsed_course['title']:
                            courses.append(parsed_course)

        except Exception as e:
            print(f"Pattern search failed: {e}")

    print(f"Extracted {len(courses)} courses from page")
    return courses

def navigate_all_pages(driver, years=[2026, 2027]):
    """Navigate through all pages for the specified years"""
    all_courses = []

    for year in years:
        print(f"\n=== Processing Year {year} ===")

        try:
            # Look for 'Event Year' input field
            year_input = None
            time.sleep(2)  # Wait for any JavaScript to load

            # Try to find Event Year input field
            year_input_selectors = [
                'input[placeholder*="Event Year" i]',
                'input[aria-label*="Event Year" i]',
                'input[name*="year" i]',
                'input[title*="Event Year" i]',
                'input[id*="event" i][id*="year" i]',
                '.event-year input',
                '#event-year',
                '.year-filter input'
            ]

            for selector in year_input_selectors:
                try:
                    year_input = driver.find_element(By.CSS_SELECTOR, selector)
                    if year_input.is_displayed():
                        print(f"Found Event Year input: {selector}")
                        break
                except:
                    continue

            if not year_input:
                # Try broader search for any input with "Year" in attributes
                all_inputs = driver.find_elements(By.TAG_NAME, "input")
                print(f"DEBUG: Found {len(all_inputs)} input fields on page")

                for i, input_elem in enumerate(all_inputs):
                    if input_elem.is_displayed():
                        attributes = []
                        try:
                            placeholder = input_elem.get_attribute('placeholder')
                            if placeholder:
                                attributes.append(f"placeholder={placeholder}")
                        except:
                            pass
                        try:
                            aria_label = input_elem.get_attribute('aria-label')
                            if aria_label:
                                attributes.append(f"aria-label={aria_label}")
                        except:
                            pass
                        try:
                            title = input_elem.get_attribute('title')
                            if title:
                                attributes.append(f"title={title}")
                        except:
                            pass
                        try:
                            elem_id = input_elem.get_attribute('id')
                            if elem_id:
                                attributes.append(f"id={elem_id}")
                        except:
                            pass
                        try:
                            elem_name = input_elem.get_attribute('name')
                            if elem_name:
                                attributes.append(f"name={elem_name}")
                        except:
                            pass

                        # Print first 5 inputs for debugging
                        if i < 5:
                            print(f"DEBUG: Input {i+1}: type={input_elem.get_attribute('type')}, value={input_elem.get_attribute('value')}, {attributes}")

                        attr_text = ' '.join(attributes).lower()
                        elem_value = input_elem.get_attribute('value') or ''
                        elem_type = input_elem.get_attribute('type') or ''

                        # Look for year input by multiple criteria
                        if ('year' in attr_text or
                            'year' in elem_value.lower() or
                            elem_type == 'number' or
                            (elem_value and elem_value.isdigit() and len(elem_value) == 4 and int(elem_value) >= 2020 and int(elem_value) <= 2030)):
                            year_input = input_elem
                            print(f"Found potential year input: value={elem_value}, type={elem_type}, {attributes}")
                            break

            if year_input:
                # Check current value first
                from selenium.webdriver.common.keys import Keys
                current_value = year_input.get_attribute('value') or ''
                print(f"Current value in year input: '{current_value}'")

                # If the input already has the correct year, just press Enter
                if current_value == str(year):
                    print(f"[SUCCESS] Year input already has {year}, just triggering filter")
                    year_input.send_keys(Keys.ENTER)
                elif current_value and current_value.isdigit():
                    # If it has a year value, use arrow keys to get to target year
                    current_int = int(current_value)
                    target_int = int(year)

                    if current_int == target_int:
                        print(f"[SUCCESS] Year input already set to {year}, triggering filter")
                        year_input.send_keys(Keys.ENTER)
                    else:
                        print(f"Navigating from {current_int} to {target_int} using arrows...")
                        arrow_count = abs(target_int - current_int)

                        if target_int > current_int:
                            # Need to go up
                            for _ in range(arrow_count):
                                year_input.send_keys(Keys.ARROW_UP)
                                time.sleep(0.1)
                        else:
                            # Need to go down
                            for _ in range(arrow_count):
                                year_input.send_keys(Keys.ARROW_DOWN)
                                time.sleep(0.1)

                        year_input.send_keys(Keys.ENTER)
                        print(f"[SUCCESS] Used arrow keys to select year {year}")
                else:
                    # Clear and enter the year
                    year_input.clear()
                    year_input.send_keys(str(year))
                    print(f"[SUCCESS] Entered year {year} into Event Year field")
                    year_input.send_keys(Keys.ENTER)

                time.sleep(5)  # Wait longer for page to reload with new year filter
                print("[SUCCESS] Applied year filter")

                # Wait for page to fully load after year change
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_elements(By.XPATH, "//button[@aria-label='Next page']")
                    )
                    print("[SUCCESS] Page fully loaded after year change")
                except TimeoutException:
                    print("[WARNING] Page may not have fully loaded, continuing anyway")
            else:
                print(f"[WARNING] Could not find Event Year input field - proceeding with current view")
                # Save screenshot to help debug
                driver.save_screenshot(f'no_year_input_{year}.png')
                print(f"Screenshot saved to no_year_input_{year}.png")

        except Exception as e:
            print(f"[ERROR] Error setting year {year}: {e}")
            continue

        # Navigate through all pages for this year
        page_num = 1
        while True:
            print(f"Extracting courses from page {page_num}...")

            # Save screenshot for debugging course extraction
            driver.save_screenshot(f'courses_page_{year}_{page_num}.png')

            # Extract courses from current page
            courses = extract_courses_from_page(driver)
            if courses:
                print(f"Found {len(courses)} courses on page {page_num}")
                all_courses.extend(courses)
                # Print first course for debugging
                if page_num == 1 and courses:
                    sample_course = courses[0] if isinstance(courses[0], dict) else {'title': str(courses[0])}
                    print(f"Sample course: {sample_course.get('title', sample_course)[:100]}...")
            else:
                print(f"No courses found on page {page_num}")

            # Look for next page button
            next_button = None

            # Try to find next page button - handle icon-based pagination
            try:
                # Strategy 1: Look for buttons with aria-label="Next page"
                next_aria_buttons = driver.find_elements(By.XPATH, "//button[@aria-label='Next page']")
                for button in next_aria_buttons:
                    if button.is_displayed() and button.is_enabled():
                        next_button = button
                        print(f"Found next button via aria-label: 'Next page'")
                        break
                    elif button.is_displayed() and not button.is_enabled():
                        print("Found next button but it's disabled - reached last page")
                        next_button = None  # Explicitly set to None to break the loop
                        break  # Break out of the for loop, will hit the "if not next_button" condition

                # Strategy 2: Look for icon buttons with SVG chevron right icons
                if not next_button:
                    chevron_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'mud-icon-button')]//svg[contains(@d, 'M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z')]")
                    for button in chevron_buttons:
                        if button.is_displayed():
                            # Get the parent button element
                            parent_button = button.find_element(By.XPATH, "./ancestor::button")
                            next_button = parent_button
                            print(f"Found next button via chevron icon")
                            break

                # Strategy 3: Look for any icon button with right-arrow SVG path
                if not next_button:
                    arrow_buttons = driver.find_elements(By.XPATH, "//button[contains(@class, 'mud-icon-button')]//svg[contains(@d, 'M10 6L8.59') or contains(@d, 'l6-6')]")
                    for button in arrow_buttons:
                        if button.is_displayed():
                            # Get the parent button element
                            parent_button = button.find_element(By.XPATH, "./ancestor::button")
                            # Check if it's the right arrow (not left arrow)
                            svg_path = button.get_attribute('d') or ''
                            if 'l6-6' in svg_path or 'M10 6L8.59 7.41' in svg_path:
                                next_button = parent_button
                                print(f"Found next button via right arrow SVG")
                                break

                # Strategy 4: Look for any mud-icon-button that might be next
                if not next_button:
                    icon_buttons = driver.find_elements(By.CSS_SELECTOR, "button.mud-icon-button")
                    for button in icon_buttons:
                        if button.is_displayed():
                            # Check if it contains a right-pointing arrow
                            try:
                                svg = button.find_element(By.TAG_NAME, "svg")
                                path = svg.find_element(By.TAG_NAME, "path")
                                path_d = path.get_attribute('d') or ''
                                if 'M10 6L8.59' in path_d or 'l6-6' in path_d:
                                    next_button = button
                                    print(f"Found next button via icon button inspection")
                                    break
                            except:
                                continue

                # Strategy 5: Fallback to text-based buttons
                if not next_button:
                    elements = driver.find_elements(By.TAG_NAME, "button") + driver.find_elements(By.TAG_NAME, "a")
                    for element in elements:
                        if element.is_displayed():
                            text = element.text.lower().strip()
                            if text in ['next', 'next page', '>', '»', '→'] or 'next' in text:
                                next_button = element
                                print(f"Found next button via text: '{element.text}'")
                                break

            except Exception as e:
                print(f"Error finding next button: {e}")
                pass

            if not next_button:
                print("No more pages found")
                break

            # Click next page
            try:
                print("Clicking next page...")
                # Scroll the button into view to avoid click interception
                driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                time.sleep(1)  # Wait for scroll to complete
                next_button.click()
                time.sleep(3)  # Wait for page to load
                page_num += 1
            except Exception as e:
                print(f"Error clicking next page: {e}")
                # Try JavaScript click as fallback
                try:
                    print("Trying JavaScript click...")
                    driver.execute_script("arguments[0].click();", next_button)
                    time.sleep(3)
                    page_num += 1
                except Exception as js_e:
                    print(f"JavaScript click also failed: {js_e}")
                    break

                # Safety check: prevent infinite loops
                if page_num > 100:  # Reasonable upper limit
                    print("Reached maximum page limit (100), stopping to prevent infinite loop")
                    break

    return all_courses

def main():
    """Main execution"""
    driver = None

    try:
        # Load credentials
        credentials = load_credentials()
        print("[SUCCESS] Credentials loaded")

        # Setup driver
        driver = setup_driver(headless=False)  # Set to False to see browser
        print("[SUCCESS] WebDriver setup complete")

        # Step 1: Login
        print("\n=== Step 1: Logging in ===")
        driver.get("https://my.scouts.ie/login")
        time.sleep(5)  # Wait for Blazor to load

        # Fill login form
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"]'))
        )
        username_field.send_keys(credentials['username'])

        password_field = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        password_field.send_keys(credentials['password'])

        submit_button = driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]')
        submit_button.click()
        print("[SUCCESS] Login submitted")

        time.sleep(5)  # Wait for login to complete

        # Step 2: Click "Manage Group"
        print("\n=== Step 2: Finding Manage Group ===")
        manage_group = find_element_by_text(driver, "Manage Group", timeout=15)
        if manage_group:
            manage_group.click()
            print("[SUCCESS] Clicked Manage Group")
            time.sleep(3)
        else:
            print("[ERROR] Could not find Manage Group")
            return

        # Step 3: Click "Events"
        print("\n=== Step 3: Finding Events ===")

        # Give more time after Manage Group click
        time.sleep(3)

        events = find_element_by_text(driver, "Events", timeout=15)
        if events:
            events.click()
            print("[SUCCESS] Clicked Events")
            time.sleep(3)
        else:
            print("[ERROR] Could not find Events - showing all links for debugging:")
            all_links = driver.find_elements(By.TAG_NAME, "a")
            for i, link in enumerate(all_links[:15]):  # Show first 15 links
                try:
                    text = link.text.strip()
                    href = link.get_attribute('href', '')
                    if text:
                        print(f"  {i+1}. '{text}' -> {href}")
                except:
                    pass

            # Save screenshot for debugging
            driver.save_screenshot('no_events_found.png')
            print("Screenshot saved to no_events_found.png")
            return

        # Step 4: Filter by "Training" - it's a radio button in a number input like Event Year
        print("\n=== Step 4: Setting Training Filter ===")
        time.sleep(3)  # Wait for JavaScript to load controls

        training_filter_found = False

        # Look for number input that might be the "Filter by event type" (similar to Event Year)
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"DEBUG: Found {len(all_inputs)} input fields for filter search")

        for i, input_elem in enumerate(all_inputs):
            if not input_elem.is_displayed():
                continue

            elem_type = input_elem.get_attribute('type') or ''
            elem_id = input_elem.get_attribute('id') or ''
            elem_name = input_elem.get_attribute('name') or ''
            elem_value = input_elem.get_attribute('value') or ''

            # Look for number inputs (like Event Year)
            if elem_type == 'number':
                print(f"DEBUG: Number input {i+1}: value={elem_value}, id={elem_id}, name={elem_name}")

                # This could be the "Filter by event type" input
                # The radio buttons for event types are likely nearby
                try:
                    # Check nearby elements for radio buttons or Training options
                    parent = input_elem.find_element(By.XPATH, "./..")
                    nearby_elements = parent.find_elements(By.XPATH, ".//*")

                    for element in nearby_elements:
                        if element.tag_name == 'input' and element.get_attribute('type') == 'radio':
                            label_or_text = element.get_attribute('value') or ''
                            parent_text = element.text.strip()

                            # Look for radio button related to Training
                            if 'training' in label_or_text.lower() or 'training' in parent_text.lower():
                                print(f"[SUCCESS] Found Training radio button: {label_or_text}")
                                element.click()
                                print("[SUCCESS] Clicked Training radio button")
                                time.sleep(3)
                                training_filter_found = True
                                break

                    # Also check for labels associated with this input
                    labels = parent.find_elements(By.TAG_NAME, "label")
                    for label in labels:
                        label_text = label.text.strip()
                        if 'training' in label_text.lower():
                            print(f"[SUCCESS] Found Training label: {label_text}")
                            label.click()
                            print("[SUCCESS] Clicked Training label")
                            time.sleep(3)
                            training_filter_found = True
                            break

                    if training_filter_found:
                        break

                except Exception as e:
                    print(f"Error checking number input {i+1}: {e}")
                    continue

            # If this is the Event Year input, look nearby for the event type filter
            if elem_value == '2025' and elem_type == 'number':
                print(f"DEBUG: Found Event Year input, looking nearby for event type filter...")
                try:
                    # Search siblings and nearby elements for Training radio
                    parent = input_elem.find_element(By.XPATH, "./..")
                    siblings = parent.find_elements(By.XPATH, ".//input")
                    for sibling in siblings:
                        if sibling.get_attribute('type') == 'radio':
                            radio_value = sibling.get_attribute('value') or ''
                            if 'training' in radio_value.lower():
                                print(f"[SUCCESS] Found Training radio near Event Year: {radio_value}")
                                sibling.click()
                                print("[SUCCESS] Clicked Training radio")
                                time.sleep(3)
                                training_filter_found = True
                                break
                except Exception as e:
                    print(f"Error searching near Event Year: {e}")

        # Strategy 2: Use JavaScript to find radio buttons with Training values
        if not training_filter_found:
            print("Using JavaScript to find Training radio buttons...")
            try:
                js_result = driver.execute_script("""
                    var inputs = document.querySelectorAll('input[type="radio"]');
                    var trainingRadios = [];

                    for (var i = 0; i < inputs.length; i++) {
                        var radio = inputs[i];
                        if (radio.offsetParent !== null) {  // Visible check
                            var value = radio.value || '';
                            var id = radio.id || '';
                            var name = radio.name || '';
                            var text = radio.textContent || radio.innerText || '';

                            if (value.toLowerCase().indexOf('training') >= 0 ||
                                id.toLowerCase().indexOf('training') >= 0 ||
                                name.toLowerCase().indexOf('training') >= 0) {
                                trainingRadios.push({
                                    index: i,
                                    value: value,
                                    id: id,
                                    name: name,
                                    text: text
                                });
                            }
                        }
                    }

                    return trainingRadios;
                """)

                print(f"JavaScript found {len(js_result)} Training radio buttons:")
                for radio_info in js_result:
                    print(f"  Radio: value={radio_info['value']}, id={radio_info['id']}")

                if js_result:
                    # Click the first Training radio found
                    all_radios = driver.find_elements(By.XPATH, "//input[@type='radio']")
                    training_radio = None
                    for radio in all_radios:
                        radio_value = radio.get_attribute('value') or ''
                        if 'training' in radio_value.lower():
                            training_radio = radio
                            break

                    if training_radio:
                        training_radio.click()
                        print("[SUCCESS] Clicked Training radio via JavaScript")
                        time.sleep(3)
                        training_filter_found = True

            except Exception as e:
                print(f"JavaScript radio search failed: {e}")

        # Strategy 3: Look for ANY radio button and check its value, or click the middle one
        if not training_filter_found:
            print("Checking ALL radio buttons for Training...")
            all_radios = driver.find_elements(By.XPATH, "//input[@type='radio']")
            print(f"Found {len(all_radios)} radio buttons")

            # First, try to find Training by value/label
            for i, radio in enumerate(all_radios):
                if not radio.is_displayed():
                    continue

                radio_value = radio.get_attribute('value') or ''
                radio_id = radio.get_attribute('id') or ''

                if 'training' in radio_value.lower() or 'training' in radio_id.lower():
                    print(f"[SUCCESS] Found Training radio {i+1}: {radio_value}")
                    radio.click()
                    print("[SUCCESS] Clicked Training radio")
                    time.sleep(3)
                    training_filter_found = True
                    break

            # If no specific Training found, click the middle radio button
            if not training_filter_found and len(all_radios) >= 3:
                print("No specific Training radio found, clicking middle radio button...")
                middle_index = len(all_radios) // 2  # Get middle index
                middle_radio = all_radios[middle_index]

                print(f"[SUCCESS] Clicking middle radio button (index {middle_index + 1})")
                middle_radio.click()
                time.sleep(3)
                training_filter_found = True

        # Strategy 4: Look for specific "National Activities Training Camps" radio button
        if not training_filter_found:
            print("Looking for 'National Activities Training Camps' Training radio button...")

            # First, look for "National Activities Training Camps" text to locate the right section
            try:
                training_camps_text = driver.find_element(By.XPATH, "//*[contains(text(), 'National Activities Training Camps')]")
                if training_camps_text:
                    print("Found 'National Activities Training Camps' section")

                    # Look for the parent container that contains all radio buttons
                    parent = training_camps_text.find_element(By.XPATH, "./ancestor::*[.//input[@type='radio']]")

                    # Find all radio buttons in this container
                    radio_buttons = parent.find_elements(By.XPATH, ".//input[@type='radio']")
                    labels = parent.find_elements(By.TAG_NAME, "label")

                    print(f"Found {len(radio_buttons)} radio buttons in Training Camps section")

                    for i, radio in enumerate(radio_buttons):
                        radio_value = radio.get_attribute('value') or ''
                        print(f"Radio {i+1}: value='{radio_value}'")

                        # Look for "Training" radio button specifically
                        if 'training' in radio_value.lower():
                            print(f"[SUCCESS] Found Training radio: {radio_value}")
                            radio.click()
                            print("[SUCCESS] Clicked Training radio in National Activities Training Camps")
                            time.sleep(3)
                            training_filter_found = True
                            break

                    # Also check labels associated with radio buttons
                    if not training_filter_found:
                        for label in labels:
                            label_text = label.text.strip()
                            if 'training' in label_text.lower():
                                print(f"[SUCCESS] Found Training label: {label_text}")
                                label.click()
                                print("[SUCCESS] Clicked Training label in National Activities Training Camps")
                                time.sleep(3)
                                training_filter_found = True
                                break

            except Exception as e:
                print(f"Could not find 'National Activities Training Camps' section: {e}")

        # Strategy 5: If still not found, try a broader search but skip "My Training"
        if not training_filter_found:
            print("Looking for Training radio buttons (excluding 'My Training')...")

            all_radios = driver.find_elements(By.XPATH, "//input[@type='radio']")
            print(f"Found {len(all_radios)} total radio buttons")

            for i, radio in enumerate(all_radios):
                if not radio.is_displayed():
                    continue

                try:
                    # Get the associated label text
                    associated_label = None
                    try:
                        # Try multiple ways to find the label
                        label_id = radio.get_attribute('id')
                        if label_id:
                            associated_label = driver.find_element(By.XPATH, f"//label[@for='{label_id}']")
                        else:
                            # Look for preceding or following label
                            associated_label = radio.find_element(By.XPATH, "./preceding::label[1] | ./following::label[1]")
                    except:
                        pass

                    label_text = associated_label.text.strip() if associated_label else ''
                    radio_value = radio.get_attribute('value') or ''

                    print(f"Radio {i+1}: value='{radio_value}', label='{label_text}'")

                    # Look for Training that's NOT "My Training"
                    if ('training' in radio_value.lower() or 'training' in label_text.lower()) and 'my training' not in label_text.lower():
                        print(f"[SUCCESS] Found Training radio (not My Training): {label_text}")
                        radio.click()
                        print("[SUCCESS] Clicked Training radio button")
                        time.sleep(3)
                        training_filter_found = True
                        break

                except Exception as e:
                    continue

        if not training_filter_found:
            print("[WARNING] Could not find Training filter - proceeding without filter")
            # Save screenshot to help debug
            driver.save_screenshot('no_training_filter.png')
            print("Screenshot saved to no_training_filter.png")
        else:
            print("[SUCCESS] Training filter applied successfully")

        # Step 5 & 6: Select years and navigate all pages
        print("\n=== Step 5 & 6: Extracting all training courses for 2026 & 2027 ===")
        courses = navigate_all_pages(driver, years=[2026, 2027])

        # Step 7: Save results
        if courses:
            # Remove duplicates based on title and description
            unique_courses = []
            seen = set()
            for course in courses:
                # Create a unique identifier
                identifier = f"{course['title']}-{course['date']}-{course['location']}"
                if identifier not in seen:
                    seen.add(identifier)
                    unique_courses.append(course)

            # Save to structured CSV
            with open('training_courses_2025_2026.csv', 'w', encoding='utf-8', newline='', errors='ignore') as f:
                writer = csv.writer(f)
                writer.writerow(['Title', 'Description', 'Status', 'Location', 'Date', 'Bookable'])

                for course in unique_courses:
                    # Clean each field
                    title = course['title'].encode('ascii', 'ignore').decode('ascii').strip()
                    description = course['description'].encode('ascii', 'ignore').decode('ascii').strip()
                    status = course['status'].encode('ascii', 'ignore').decode('ascii').strip()
                    location = course['location'].encode('ascii', 'ignore').decode('ascii').strip()
                    date = course['date'].encode('ascii', 'ignore').decode('ascii').strip()
                    bookable = course['bookable'].encode('ascii', 'ignore').decode('ascii').strip()

                    writer.writerow([title, description, status, location, date, bookable])

            print(f"\n[SUCCESS] Found {len(unique_courses)} unique training courses")
            print(f"[SUCCESS] Saved to: training_courses_2025_2026.csv")
            print(f"[SUCCESS] CSV format: Title | Description | Status | Location | Date")

        else:
            print("[ERROR] No courses found")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        if driver:
            driver.save_screenshot('error.png')
    finally:
        if driver:
            print("Closing browser...")
            driver.quit()

if __name__ == "__main__":
    main()