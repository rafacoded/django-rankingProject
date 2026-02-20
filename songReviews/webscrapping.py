import requests
import bs4

html = requests.get()

soup = bs4.BeautifulSoup(html.content, 'html.parser')