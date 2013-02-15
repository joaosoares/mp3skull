from bs4 import BeautifulSoup
from urlparse import urlsplit, urlparse
from threading import Thread
from Queue import Queue
from progressbar import *
import argparse, os, requests


# Download functions by kender @ stackoverflow
def url2name(url):
    return os.path.basename(urlsplit(url)[2])

def download(url, localFileName = None):
    localName = url2name(url)
    r = requests.get(url)
    total_size = int(r.headers["Content-Length"].strip())
    downloaded = 0

    if r.url != url:
        # if we were redirected
        localName = url2name(r.url)
    if localFileName:
        # we can force to save file as custom name
        localName = localFileName

    widgets = [localName, ": ", Bar(marker="|", left="[", right=" "),
            Percentage(), " ", FileTransferSpeed(), "] ", str(downloaded),
            " of {0}MB".format(round(total_size / 1024 / 1024 , 2))]
    pbar = ProgressBar(widgets=widgets, maxval=total_size)
    pbar.start()
    
    with open(localName, 'wb') as fp:
        for chunk in r.iter_content(1024):
            if chunk:
                fp.write(chunk)
                downloaded += len(chunk)
                pbar.update(downloaded)
    pbar.finish()
    
class Query:
    '''
    Class to store search results, modify and display them.
    '''
    def __init__(self, query):
        self.query=query
        self.results = []
        self.filter(self.query)

    def display_results(self, nresults=30, start_res=1):
        end_res = start_res + nresults - 1
        print("Showing results %s-%s:" % (start_res, end_res))
        for i, result in enumerate(self.results[start_res-1:end_res-1], start=start_res):
            print "%s) %s [%s, %s, %s]" % (i, result[0], result[2], result[3], result[4])
        if len(self.results) > end_res:
            chosen_index = raw_input("Pick a number to download (%s-%s), 'm' for more. " % (start_res, end_res))
            if chosen_index == 'm':
                print("")
                query_song(song, start_res=end_res+1)
        else:
            chosen_index = raw_input("Pick a number to download (%s-%s). " % (start_res, min(end_res, len(self.results))))
        try:
            chosen = self.results[int(chosen_index)-1]
            download(chosen[1], chosen[0].strip()+".mp3")
            print("Download completed.")
        except ValueError:
            again = raw_input("Invalid option. Try again? (y/n) ")
            if again in ('y', 'ye', 'yes'):
                self.display_results(nresults)
            else:
                sys.exit(1)
        return None

    def get_raw_results(self, query):
        r = requests.get('http://mp3skull.com/mp3/%s.html' % query)
        soup = BeautifulSoup(r.text)
        results = soup.find_all(id="song_html")
        values = []
        for item in results:
            info = item.contents[3]
            # Get download url
            url = info.find_all('div')[2].div.div.a['href']
            # Get title
            title = info.div.b.get_text()
            # Get bitrate, duration and file size
            song_info = item.find(class_='left')
            # Bitrate
            try:
                bitrate = song_info.contents[2].strip()
            except:
                bitrate = None
            # Duration
            try:
                duration = song_info.contents[4].strip()
            except:
                duration = None
            # File size
            try:
                file_size = song_info.contents[6].strip()
            except:
                file_size = None
            
            values.append([title, url, bitrate, duration, file_size])
        return values
    
    def check_response(self, q):
        while True:
            entry=q.get()
            try:
                print "#",
                r = requests.head(entry[1])
                if r.status_code == requests.codes.ok:
                    self.results.append(entry)
            except requests.exceptions.RequestException:
                pass
            print "*",
            q.task_done()

    def filter(self,query):
        concurrent = 200
        q = Queue(concurrent*2)
        for i in range(concurrent):
            t=Thread(target=self.check_response, args=(q,))
            t.daemon=True
            t.start()
        try:
            values = self.get_raw_results(query)
            for entry in values:
                q.put(entry)
            q.join()
        except KeyboardInterrupt:
            sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Search and download mp3s from mp3skull.')
    parser.add_argument('query', type=str, nargs='+')
    args = parser.parse_args()
    result = Query('_'.join(args.query))
    result.display_results()
