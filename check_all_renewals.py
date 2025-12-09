"""
Scouting Ireland Renewal Checker

This script analyzes member training and vetting sheets downloadable from my.scouts.ie
to identify scouters who need renewals within the next 3 months and those with expired requirements.

Usage:
    python check_all_renewals.py

Requirements:
    - Member-Trainings-Report-{timestamp}.xlsx
    - Member-Vetting-Report-{timestamp}.xlsx

Output:
    - Console output showing upcoming and expired renewals
"""

import pandas as pd
from datetime import datetime, timedelta
import re
import os

def extract_safeguarding_date(text):
    """Extract safeguarding date from training course text."""
    if pd.isna(text):
        return None

    text = str(text)

    # Check if this is a safeguarding-related course
    safeguarding_keywords = ['safeguarding', 'safe guarding']
    is_safeguarding = any(keyword.lower() in text.lower() for keyword in safeguarding_keywords)

    # Also check "This is Scouting - Being A Scouter" which is the initial safeguarding course
    is_being_scouter = 'Being A Scouter' in text

    if not (is_safeguarding or is_being_scouter):
        return None

    # Extract dates using regex - look for dates after "from"
    date_pattern = r'from\s+(\d{1,2})/(\d{1,2})/(\d{4})\s+to'
    match = re.search(date_pattern, text, re.IGNORECASE)

    if match:
        day, month, year = match.groups()
        return datetime(int(year), int(month), int(day))

    # If no "from ... to" pattern, try to find any date in the text
    date_pattern_alt = r'(\d{1,2})/(\d{1,2})/(\d{4})'
    matches = re.findall(date_pattern_alt, text)

    if matches:
        # Take the last match (latest date mentioned in the text)
        day, month, year = matches[-1]
        return datetime(int(year), int(month), int(day))

    return None

def parse_vetting_date(date_str):
    """Parse vetting date from dd/mm/yyyy format."""
    if pd.isna(date_str):
        return None

    date_str = str(date_str).strip()

    # Parse dd/mm/yyyy format using regex
    match = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
    if match:
        day, month, year = match.groups()
        return datetime(int(year), int(month), int(day))

    return None

# Read the training file
print("Loading training data...")
training_files = [f for f in os.listdir('.') if f.startswith('Member-Trainings-Report') and f.endswith('.xlsx')]
if not training_files:
    print("Error: No Member Training Report file found!")
    exit(1)

df_training = pd.read_excel(training_files[0])
print(f"Loaded vetting report: {training_files[0]}")

# Find and read the vetting report
vetting_files = [f for f in os.listdir('.') if f.startswith('Member-Vetting-Report') and f.endswith('.xlsx')]
if not vetting_files:
    print("Error: No Member Vetting Report file found!")
    exit(1)

df_vetting = pd.read_excel(vetting_files[0])
print(f"Loaded vetting report: {vetting_files[0]}")

# Get current date
today = datetime.now()
three_months_from_now = today + timedelta(days=90)

print(f"\nCurrent date: {today.strftime('%d/%m/%Y')}")
print(f"Checking for renewals needed by: {three_months_from_now.strftime('%d/%m/%Y')}")
print("=" * 70)
print("SCOUTERS NEEDING RENEWAL WITHIN NEXT 3 MONTHS:")
print("=" * 70)

# Create a dictionary to store all renewal information
all_renewals = {}

# Process safeguarding training
print("\n1. Checking Safeguarding Training...")
for index, row in df_training.iterrows():
    name = f"{row['First Name']} {row['Surname']}"
    email = row['Email Address']

    all_safeguarding_dates = []

    # Check all training course columns
    for col_idx in range(5, 26):
        course_text = row.iloc[col_idx]
        date = extract_safeguarding_date(course_text)
        if date:
            all_safeguarding_dates.append(date)

    if all_safeguarding_dates:
        latest_date = max(all_safeguarding_dates)
        expiry_date = latest_date + timedelta(days=365 * 3)

        if today <= expiry_date <= three_months_from_now:
            if name not in all_renewals:
                all_renewals[name] = {
                    'Email': email,
                    'Safeguarding': {
                        'Last Completed': latest_date.strftime('%d/%m/%Y'),
                        'Expiry Date': expiry_date.strftime('%d/%m/%Y'),
                        'Days Until': (expiry_date - today).days
                    }
                }
            else:
                all_renewals[name]['Safeguarding'] = {
                    'Last Completed': latest_date.strftime('%d/%m/%Y'),
                    'Expiry Date': expiry_date.strftime('%d/%m/%Y'),
                    'Days Until': (expiry_date - today).days
                }

# Process vetting
print("2. Checking Vetting...")
for index, row in df_vetting.iterrows():
    name = f"{row['First Name']} {row['Surname']}"
    email = row['Email Address']
    vetting_date = parse_vetting_date(row['Latest Vetting Completion Date'])

    if vetting_date:
        expiry_date = vetting_date + timedelta(days=365 * 3)

        if today <= expiry_date <= three_months_from_now:
            if name not in all_renewals:
                all_renewals[name] = {
                    'Email': email,
                    'Vetting': {
                        'Last Completed': vetting_date.strftime('%d/%m/%Y'),
                        'Expiry Date': expiry_date.strftime('%d/%m/%Y'),
                        'Days Until': (expiry_date - today).days
                    }
                }
            else:
                all_renewals[name]['Vetting'] = {
                    'Last Completed': vetting_date.strftime('%d/%m/%Y'),
                    'Expiry Date': expiry_date.strftime('%d/%m/%Y'),
                    'Days Until': (expiry_date - today).days
                }

# Display results
if all_renewals:
    print(f"\nFound {len(all_renewals)} scouter(s) needing renewal:\n")

    for name, info in sorted(all_renewals.items(), key=lambda x: min(
        x[1].get('Safeguarding', {}).get('Days Until', 999),
        x[1].get('Vetting', {}).get('Days Until', 999)
    )):
        print(f"Name: {name}")
        print(f"Email: {info['Email']}")

        if 'Safeguarding' in info:
            s = info['Safeguarding']
            print(f"  - Safeguarding: Expires {s['Expiry Date']} (in {s['Days Until']} days)")

        if 'Vetting' in info:
            v = info['Vetting']
            print(f"  - Vetting: Expires {v['Expiry Date']} (in {v['Days Until']} days)")

        print("-" * 50)
else:
    print("\nNo scouters need safeguarding or vetting renewal within the next 3 months.")

# Also check for expired items
print("\n" + "=" * 70)
print("SCOUTERS WITH EXPIRED REQUIREMENTS (OVER 3 YEARS OLD) SHOULD BE ON 'STAY AWAY':")
print("=" * 70)

expired_items = []

# Check expired safeguarding
for index, row in df_training.iterrows():
    name = f"{row['First Name']} {row['Surname']}"
    email = row['Email Address']

    all_safeguarding_dates = []
    for col_idx in range(5, 26):
        course_text = row.iloc[col_idx]
        date = extract_safeguarding_date(course_text)
        if date:
            all_safeguarding_dates.append(date)

    if all_safeguarding_dates:
        latest_date = max(all_safeguarding_dates)
        expiry_date = latest_date + timedelta(days=365 * 3)

        if expiry_date < today:
            expired_items.append({
                'Name': name,
                'Email': email,
                'Type': 'Safeguarding',
                'Last Completed': latest_date.strftime('%d/%m/%Y'),
                'Expiry Date': expiry_date.strftime('%d/%m/%Y'),
                'Days Expired': (today - expiry_date).days
            })

# Check expired vetting
for index, row in df_vetting.iterrows():
    name = f"{row['First Name']} {row['Surname']}"
    email = row['Email Address']
    vetting_date = parse_vetting_date(row['Latest Vetting Completion Date'])

    if vetting_date:
        expiry_date = vetting_date + timedelta(days=365 * 3)

        if expiry_date < today:
            expired_items.append({
                'Name': name,
                'Email': email,
                'Type': 'Vetting',
                'Last Completed': vetting_date.strftime('%d/%m/%Y'),
                'Expiry Date': expiry_date.strftime('%d/%m/%Y'),
                'Days Expired': (today - expiry_date).days
            })

if expired_items:
    expired_items.sort(key=lambda x: x['Days Expired'])
    print(f"\nFound {len(expired_items)} expired requirements:\n")

    for item in expired_items:
        print(f"{item['Name']} - {item['Type']}")
        print(f"  Email: {item['Email']}")
        print(f"  Expired {item['Days Expired']} days ago (was due {item['Expiry Date']})")
        print("-" * 40)
else:
    print("\nNo expired safeguarding or vetting requirements found.")