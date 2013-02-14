from bs4 import BeautifulSoup
from urlparse import urlsplit
import urllib2
import argparse
import os

parser = argparse.ArgumentParser(description='Search and download mp3s from mp3skull.')
parser.add_argument('query', type=str, nargs='+')
args = parser.parse_args()
search = '_'.join(args.query)

def get_results(query):
    '''
    Parses the page and create a list of tuples with title and url
    '''
    page = urllib2.urlopen('http://mp3skull.com/mp3/%s.html' % query).read()
    soup = BeautifulSoup(page)
    results = soup.find_all(id="song_html")
    values = []
    for item in results:
        info = item.contents[3]
        title = info.div.b.get_text()
        url = info.find_all('div')[2].div.div.a['href']
        values.append([title, url])
    return values

# Download functions by kender @ stackoverflow
def url2name(url):
    return os.path.basename(urlsplit(url)[2])

def download(url, localFileName = None):
    localName = url2name(url)
    req = urllib2.Request(url)
    r = urllib2.urlopen(req)
    if r.url != url:
        # if we were redirected
        localName = url2name(r.url)
    if localFileName:
        # we can force to save file as custom name
        localName = localFileName
    f = open(localName, 'wb')
    f.write(r.read())
    f.close()




print("Searching for %s" % " ".join(args.query))
results = get_results(search)
print("Showing first 30 results:")
for i, song in enumerate(results[:30]):
    print "%s) %s" % (i+1, song[0])
chosen = raw_input("Pick a number to download (1-%s)" % len(results))
download(results[int(chosen)-1][1])
print("Download completed.")

