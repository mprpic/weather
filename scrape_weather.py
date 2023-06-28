# Download geckodriver from:
# https://github.com/mozilla/geckodriver/releases
#
# Add to PATH:
# export PATH=$PATH:/path/to/geckodriver/directory
#
# https://bugzilla.mozilla.org/show_bug.cgi?id=1372998

import os
import sys
import shutil
from urllib.request import urlopen

import yaml
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

FILE_DIR = './weather'


class Element_has_css_class:
    def __init__(self, locator, css_class):
        self.locator = locator
        self.css_class = css_class

    def __call__(self, driver):
        element = driver.find_element(*self.locator)
        return self.css_class in element.get_attribute('class')


def scrape_meteoblue(browser, url):
    """ Scrape meteoblue model """

    browser.get(url)

    # Accept cookies if loading this site for the first time; otherwise the
    # model image won't load until cookies are accepted.
    try:
        element = browser.find_element_by_id('accept_all_cookies')
    except NoSuchElementException:
        pass
    else:
        element.click()

    # Wait for the model image to be loaded asynchronously. It is finished
    # loading whenever the <img> tag has a class "loaded" added to it.
    # At that point, it will also have a valid src attribute which we can
    # use to download the raw image rather than screenshotting it with
    # Selenium since that doesn't seem to work all the time because the
    # image fades in with JS (plus some other trickery).
    wait = WebDriverWait(browser, 10)
    wait.until(Element_has_css_class((By.CLASS_NAME, 'image_lazyload'), 'loaded'))

    image = browser.find_element_by_class_name('image_lazyload')
    image_url = image.get_attribute(name='src')

    with urlopen(image_url) as response:
        return response.read()


def scrape_yr(browser, url):
    """ Scrape yr.no model """

    browser.get(url)

    return browser.find_element_by_class_name('detailed-graph__main').screenshot_as_png


def scrape_shmu(browser, url):
    """ Scrape SHMU models"""

    browser.get(url)

    return browser.find_element_by_id('imageArea').screenshot_as_png


def scrape_and_save(browser, location, urls):
    """ Scrape and save weather model images for a specific location """

    # Create a directory to hold all scraped images for one location
    dest_dir = os.path.join(FILE_DIR, location)
    os.makedirs(dest_dir)

    # Scrape all images for one location
    scraped_images = []
    for url in urls:
        if 'meteoblue.com' in url:
            image = scrape_meteoblue(browser, url)
            file_name = 'meteoblue'

        elif 'yr.no' in url:
            image = scrape_yr(browser, url)
            file_name = 'yr'

        elif 'shmu.sk' in url:
            image = scrape_shmu(browser, url)
            file_name = 'shmu_ecmwf' if 'mgram10' in url else 'shmu_aladin'

        else:
            sys.stderr.write('Unknown website: {}\n'.format(url))
            continue

        file_name = os.path.join(dest_dir, file_name + '.png')

        with open(file_name, 'wb') as image_file:
            image_file.write(image)

        scraped_images.append(file_name)

    # Join images into one
    images = [Image.open(img) for img in scraped_images]
    max_width = max(image.width for image in images)
    total_height = sum(image.height for image in images)

    # Create a new image file that combines all scraped images vertically.
    # Images are spaced for easier readability.
    image_spacing = 100
    combined_image = Image.new('RGBA', (max_width, total_height + image_spacing * len(images)), 'white')

    vertical_offset = 0
    for image in images:
        horizontal_offset = (max_width - image.width) // 2  # Align image to center
        combined_image.paste(image, (horizontal_offset, vertical_offset))
        vertical_offset += image.height + image_spacing

    combined_image.save(os.path.join(dest_dir, 'all.png'))


if __name__ == '__main__':

    locations = yaml.safe_load(open('weather_config.yml'))

    # Remove previous scraped data; create new empty directory for new data
    if os.path.exists(FILE_DIR):
        shutil.rmtree(FILE_DIR)
    os.makedirs(FILE_DIR)

    # Initialize headless browser
    options = Options()
    options.set_headless(headless=True)
    browser = webdriver.Firefox(firefox_options=options, log_path='/tmp/geckodriver.log')

    for location in locations:
        scrape_and_save(browser, location['name'], location['urls'])

    # Exit headless browser
    browser.quit()
