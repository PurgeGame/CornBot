from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json

# Create a new instance of the Firefox driver
driver = webdriver.Firefox()

# Get the absolute path of the HTML file
html_file_path = os.path.abspath('test.html')

# Go to the webpage that you want to scrape
driver.get('https://magicpool.space/')

# Wait for the dynamically loaded elements to show up
WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.XPATH, "/html/body/div/section/div/div/div/div[2]/table/tbody/tr[1]"))
)
time.sleep(5)

page_source = driver.page_source

# Write the page source to a file
# Write the page source to a file
with open('output.html', 'w', encoding='utf-8') as f:
    f.write(page_source)

# Get the absolute path to the HTML file
html_file_path = os.path.abspath('output.html')

# Load the HTML file in the Selenium driver
driver.get('file:///' + html_file_path)

# Find the rows in the table
rows = driver.find_elements(By.XPATH, "/html/body/div/section/div/div/div/div[2]/table/tbody/tr")

# Initialize an empty list to store the data
data = []

for row in rows:
    try:
        # Find the span elements in the row
        spans = row.find_elements(By.TAG_NAME, "span")
        # Get the rune name and sanitize it
        rune_name = row.find_element(By.XPATH, ".//a").text.replace("\u2022", "").strip()
        # Initialize variables
        snipe_price, floor_price, volume_24h = None, None, None
        # Get the snipe_price, floor_price and 24h_volume
        for span in spans:
            if 'SATS' in span.text:
                if not snipe_price:
                    snipe_price = float(span.text.split(' ')[0].replace(',', ''))
                elif not floor_price:
                    floor_price = float(span.text.split(' ')[0].replace(',', ''))
            elif 'BTC' in span.text and not volume_24h:
                volume_24h = float(span.text.split(' ')[0].replace(',', ''))
            if snipe_price and floor_price and volume_24h:
                break
        # Append the data to the list if it meets the conditions
        if snipe_price != 0 and floor_price is not None and volume_24h >= 0.01:
            data.append({
                "rune_name": rune_name,
                "snipe_price": snipe_price,
                "floor_price": floor_price,
                "24h_volume": volume_24h
            })
    except Exception as e:
        print(f"An error occurred: {e}")

# Close the browser
driver.quit()

# Write the data to a JSON file
with open('scraper.json', 'w') as f:
    json.dump(data, f, indent=4)