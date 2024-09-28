import os
import time
import random
import requests
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from cryptography.fernet import Fernet
from tabulate import tabulate
from playwright.sync_api import sync_playwright

# 从环境变量获取用户名、密码和加密的配置URL
USERNAME = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")
ENCRYPTED_CLASH_CONFIG_URL = os.environ.get("ENCRYPTED_CLASH_CONFIG_URL")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY")  # 加密密钥

HOME_URL = "https://linux.do/"

def fetch_clash_config(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

def load_proxies_from_clash_config(config_text):
    config = yaml.safe_load(config_text)
    proxies = config.get('proxies', [])
    proxy_list = []
    for proxy in proxies:
        if proxy.get('type') in ['http', 'socks5', 'socks5-tls']:
            proxy_list.append(f"{proxy['type']}://{proxy['server']}:{proxy['port']}")
        elif proxy.get('type') == 'hysteria2':
            proxy_list.append(f"http://{proxy['server']}:{proxy['port']}")
        elif proxy.get('type') == 'vless':
            proxy_list.append(f"http://{proxy['server']}:{proxy['port']}")
        # Add other proxy types as needed
    return proxy_list

def encrypt_link(link, key):
    fernet = Fernet(key)
    return fernet.encrypt(link.encode()).decode()

def decrypt_link(encrypted_link, key):
    fernet = Fernet(key)
    return fernet.decrypt(encrypted_link.encode()).decode()

class LinuxDoBrowser:
    def __init__(self, proxy=None) -> None:
        self.pw = sync_playwright().start()
        self.browser = self.pw.firefox.launch(headless=True, proxy={"server": proxy} if proxy else None)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(HOME_URL)

    def login(self):
        self.page.click(".login-button .d-button-label")
        time.sleep(2)
        self.page.fill("#login-account-name", USERNAME)
        time.sleep(2)
        self.page.fill("#login-account-password", PASSWORD)
        time.sleep(2)
        self.page.click("#login-button")
        time.sleep(10)
        user_ele = self.page.query_selector("#current-user")
        if not user_ele:
            print("Login failed")
            return False
        else:
            print("Check in success")
            return True

    def click_topic(self, topic_href, proxy):
        browser = self.pw.firefox.launch(headless=True, proxy={"server": proxy} if proxy else None)
        context = browser.new_context()
        page = context.new_page()
        page.goto(HOME_URL + topic_href)
        time.sleep(3)
        if random.random() < 0.02:  # 100 * 0.02 * 30 = 60
            self.click_like(page)
        time.sleep(3)
        page.close()
        context.close()
        browser.close()

    def run(self):
        if not self.login():
            return 
        self.click_topics_multithreaded()
        self.print_connect_info()

    def click_like(self, page):
        page.locator(".discourse-reactions-reaction-button").first.click()
        print("Like success")

    def click_topics_multithreaded(self):
        topics = self.page.query_selector_all("#list-area .title")
        topic_hrefs = [topic.get_attribute("href") for topic in topics]
        
        # 解密配置URL
        decrypted_url = decrypt_link(ENCRYPTED_CLASH_CONFIG_URL, ENCRYPTION_KEY)
        proxies = load_proxies_from_clash_config(fetch_clash_config(decrypted_url))
        
        with ThreadPoolExecutor(max_workers=len(proxies)) as executor:  # 使用代理数量作为线程数
            futures = [executor.submit(self.click_topic, href, proxies[i % len(proxies)]) for i, href in enumerate(topic_hrefs)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Error clicking topic: {e}")

    def print_connect_info(self):
        page = self.context.new_page()
        page.goto("https://connect.linux.do/")
        rows = page.query_selector_all("table tr")

        info = []

        for row in rows:
            cells = row.query_selector_all("td")
            if len(cells) >= 3:
                project = cells[0].text_content().strip()
                current = cells[1].text_content().strip()
                requirement = cells[2].text_content().strip()
                info.append([project, current, requirement])

        print("--------------Connect Info-----------------")
        print(tabulate(info, headers=["项目", "当前", "要求"], tablefmt="pretty"))

        page.close()

if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Please set USERNAME and PASSWORD")
        exit(1)
    if not ENCRYPTED_CLASH_CONFIG_URL:
        print("Please set a valid ENCRYPTED_CLASH_CONFIG_URL")
        exit(1)
    if not ENCRYPTION_KEY:
        print("Please set a valid ENCRYPTION_KEY")
        exit(1)
    
    l = LinuxDoBrowser()
    l.run()
