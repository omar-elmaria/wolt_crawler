# Import the packages
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
import time
import json
import pandas as pd
import re
from google.cloud import bigquery
from datetime import datetime
import logging
logging.basicConfig(
    filename="wolt_scraping_logs.log",
    level="INFO",
    format="%(asctime)s  - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8"
)
from Screenshot import Screenshot
ss = Screenshot.Screenshot()

# Set the Chrome options
chrome_options = Options()
chrome_options.add_argument("start-maximized") # Required for a maximized Viewport
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation', 'disable-popup-blocking']) # Disable pop-ups to speed up browsing
chrome_options.add_experimental_option("detach", True) # Keeps the Chrome window open after all the Selenium commands/operations are performed 
chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en,en_US'}) # Operate Chrome using English as the main language
chrome_options.add_argument('--blink-settings=imagesEnabled=false') # Disable images
chrome_options.add_argument('--disable-extensions') # Disable extensions
chrome_options.add_argument("--headless=new") # Operate Selenium in headless mode
chrome_options.add_argument('--no-sandbox') # Disables the sandbox for all process types that are normally sandboxed. Meant to be used as a browser-level switch for testing purposes only
chrome_options.add_argument('--disable-gpu') # An additional Selenium setting for headless to work properly, although for newer Selenium versions, it's not needed anymore
chrome_options.add_argument("--window-size=1920x1080") # Set the Chrome window size to 1920 x 1080

# Global inputs
total_scroll_count = 2
scraping_country = "Finland"
scraping_location = "Meritullinkatu 10"
base_url = "https://wolt.com/en/discovery/restaurants"
t_start = datetime.now()

# Helper functions
def handle_no_such_element_errors(driver, selector):
    try:
        return driver.find_element(by=By.XPATH, value=selector).text
    except NoSuchElementException:
        return None

# Instantiate a webdriver
driver = webdriver.Chrome(options=chrome_options)

# Navigate to the target URL
logging.info("Navigate to the target URL...")
driver.get(base_url)

# Maximize the window
logging.info("Maximize the window...")
driver.maximize_window()

# Click on the "Accept Cookies" button
logging.info("Click on the 'Accept Cookies' button")
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//button[@data-localization-key='gdpr-consents.banner.accept-button']")))
driver.find_element(by=By.XPATH, value="//button[@data-localization-key='gdpr-consents.banner.accept-button']").click()

# Click on the "Delivery to" button
logging.info("Click on the 'Delivery to' button")
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@data-projection-id='2']/button")))
driver.find_element(by=By.XPATH, value="//div[@data-projection-id='2']/button").click()
# driver.execute_script("document.getElementsByClassName('sc-4ed1b0a0-5 gUqbJK')[0].click();") # Possible alternative to the previous command

# Take a screenshot
image = ss.full_Screenshot(driver, save_path=r'.' , image_name='name.png')

# Change the delivery address to a Finnish address
logging.info("Change the delivery address to a Finnish address")
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//select[@data-test-id='CountriesSelect']")))
select1 = Select(driver.find_element(by=By.XPATH, value="//select[@data-test-id='CountriesSelect']"))
select1.select_by_visible_text(scraping_country)
time.sleep(1)

# Type the address, wait for 3 seconds until the completion of the text appears, then press enter
logging.info("Type the address, wait for 3 seconds until the completion of the text appears, then press enter")
driver.find_element(by=By.XPATH, value="//input[@data-test-id='AddressQueryInput']").send_keys(scraping_location)
time.sleep(3)
driver.find_element(by=By.XPATH, value="//input[@data-test-id='AddressQueryInput']").send_keys(Keys.RETURN)

# Wait for 3 seconds until the "Continue" button appears
time.sleep(3)

# Click "Continue"
logging.info("Click 'Continue' to load the results")
driver.find_element(by=By.XPATH, value="//button[@data-test-id='AddressPicker.ContinueButton']").click()

# Wait until the products appear to start scrolling
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@data-test-id, 'venueCard')]")))

# Scroll to the bottom of the page until all the content is loaded. Only scroll 20 times
scrolling_counter = 1
last_height = driver.execute_script("return document.body.scrollHeight")
while True and scrolling_counter <= total_scroll_count:
    logging.info(f"\nScrolling {scrolling_counter} out of {total_scroll_count}...")
    # Scroll down to bottom
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

    # Wait to load page
    time.sleep(1)

    # Calculate new scroll height and compare with last scroll height
    new_height = driver.execute_script("return document.body.scrollHeight")
    if new_height == last_height:
        break
    last_height = new_height

    scrolling_counter += 1

# Wait again until the 20th product from the bottom appears to start pulling the data
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@data-test-id, 'venueCard')][last()-20]")))


# Pull the restaurant title
restaurants_web_elements = driver.find_elements(by=By.XPATH, value="//a[contains(@data-test-id, 'venueCard')]")
output_list = []
for idx, res in enumerate(restaurants_web_elements):
    logging.info(f"\nGetting the data of restaurant element number {idx + 1}")
    restaurant_name = handle_no_such_element_errors(driver=res, selector=".//h3")
    restaurant_subtitle = handle_no_such_element_errors(driver=res, selector=".//h3/following-sibling::p")
    delivery_time = handle_no_such_element_errors(driver=res, selector=".//h3/../following-sibling::div/div/div[1]")
    delivery_fee = handle_no_such_element_errors(driver=res, selector=".//span[@class='sc-3533de9d-32 sc-3533de9d-33 gdkIjN jTrqRs'] | .//span[@class='sc-3533de9d-32 sc-3533de9d-33 gdkIjN hsIkPU']")

    output_dict = {
        "restaurant_name": restaurant_name,
        "restaurant_subtitle": restaurant_subtitle,
        "delivery_time": delivery_time,
        "delivery_fee": delivery_fee,
        "scraping_timestamp": str(t_start),
        "scraping_location": scraping_location,
        "scraping_country": scraping_country
    }

    output_list.append(output_dict)

# Save the output to a JSON file
logging.info("Dumping the output to a JSON file")
with open("output_wolt_finland.json", mode="w", encoding="utf-8") as f:
    json.dump(obj=output_list, fp=f, ensure_ascii=False, indent=0)
    f.close()

# Close the driver
logging.info("Closing the driver")
driver.quit()

# Open the JSON file containing the data
with open("output_wolt_finland.json", mode="r", encoding="utf-8") as f:
    data = json.load(f)
    df_data = pd.DataFrame(data)
    f.close()

# Add new columns
df_data["delivery_time_min"] = df_data["delivery_time"].apply(lambda x: int(x.split("-")[0]))
df_data["delivery_time_max"] = df_data["delivery_time"].apply(lambda x: int(x.split("-")[1]))
df_data["delivery_fee_numeric"] = df_data["delivery_fee"].apply(lambda x: float('.'.join(re.findall(pattern="\d+", string=x))))
df_data["scraping_timestamp"] = df_data["scraping_timestamp"].apply(lambda x: pd.to_datetime(x))

# Upload the data to bigquery
client = bigquery.Client(project="dh-logistics-product-ops")

job_config = bigquery.LoadJobConfig(
    schema = [
        bigquery.SchemaField("restaurant_name", "STRING"),
        bigquery.SchemaField("restaurant_subtitle", "STRING"),
        bigquery.SchemaField("delivery_time", "STRING"),
        bigquery.SchemaField("delivery_fee", "STRING"),
        bigquery.SchemaField("scraping_timestamp", "TIMESTAMP"),
        bigquery.SchemaField("scraping_location", "STRING"),
        bigquery.SchemaField("scraping_country", "STRING"),
        bigquery.SchemaField("delivery_time_min", "INT64"),
        bigquery.SchemaField("delivery_time_max", "INT64"),
        bigquery.SchemaField("delivery_fee_numeric", "FLOAT64"),
    ]
)
job_config.write_disposition = bigquery.WriteDisposition.WRITE_APPEND

client.load_table_from_dataframe(
    dataframe=df_data,
    destination="dh-logistics-product-ops.pricing.wolt_finland_crawler",
    job_config=job_config
)