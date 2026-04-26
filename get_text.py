from bs4 import BeautifulSoup
import sys
html = sys.stdin.read()
soup = BeautifulSoup(html, 'html.parser')
print(soup.get_text())
