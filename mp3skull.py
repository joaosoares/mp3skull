#!/usr/bin/env python

from bs4 import BeautifulSoup
from urlparse import urlsplit, urlparse
from threading import Thread
from Queue import Queue
from subprocess import call
from progressbar import *
import argparse, os, requests, logging, re
import xml.etree.ElementTree as ET
import cmd2 as cmd


class CLI:
    def __init__(self, search_terms):
        self.query = search_terms
        self.search = Query(self.query) # start a new Query class for specified input
        self.show(self.search)

    def show(self, query, nresults=10, start_res=1):
        '''Displays search results on the screen and
           asks the user for a selection among a list,
           with the following commands:
           - 'm' for more results if sensible
           - ',' between numbers for multidownload
        '''
        
        end_res = start_res + nresults - 1
        results = query.get_results(end_res)
        print("Showing results {current_min}-{current_max} of {total}:".format(
            current_min = start_res,
            current_max = end_res,
            total = len(results),
            ))
        for i, result in enumerate(results[start_res-1:end_res], start=start_res):
            print "%s) %s [%s, %s, %s]" % (
                    i,
                    result['title'],
                    result['duration'],
                    result['bitrate'],
                    result['file_size'],
                    )
        
        min_num = start_res
        max_num = min(len(results), end_res)
        more_results = True if (len(results) > nresults+start_res-1) else False
        
        prompt_text = "Pick a number to download({start}-{end}). {more}".format(
                start=min_num,
                end=max_num,
                more = "'m' for more'" if more_results else "",
                )

        user_selection = raw_input(prompt_text)

        # try to understand user input
        if re.match('[Mm]', user_selection):
            if more_results:
                self.show(results, nresults, start_res+nresults)
                return None
            else:
                user_selection = raw_input("No more results available. Try something else. ")
        
        if re.match('(\s?[0-9]\s?,?\s?)+$', user_selection):
            wanted_results = []
            for x in user_selection.split(','):
                wanted_results.append(int(x)) 
            print("Starting download")
            for index, item in enumerate(wanted_results):
                result = results[index-1] # for reajusting first num to 0
                self.download(result)
                print("Download completed.")
        
        else:
            again = raw_input("Invalid option. Try again? (y/n) ")
            if again in ('y', 'ye', 'yes'):
                self.display_results(nresults=nresults, start_res=start_res)
            else:
                sys.exit(1)
                return None

    def download(self, search_result, local_filename = None):
        '''Downloads a search result stored in a Query class'''
        def url2name(url):
            return os.path.basename(urlsplit(url)[2])
        r = requests.get(search_result['url'], stream=True)
        # File naming
        filename = search_result['title']+".mp3"
        if local_filename:
            filename = local_filename
    
        # Getting file size
        total_size = int(r.headers["Content-Length"].strip())
        downloaded = 0
        # Progress bar
        widgets = [filename, ": ", Bar(marker="|", left="[", right=" "),
                Percentage(), " ", FileTransferSpeed(), "] ", str(downloaded),
                " of {0}MB".format(round(total_size / 1024 / 1024 , 2))]
        pbar = ProgressBar(widgets=widgets, maxval=total_size)
        pbar.start()

        with open(filename, 'wb') as fp:
            for chunk in r.iter_content(512):
                if chunk:
                    fp.write(chunk)
                    downloaded += len(chunk)
                    pbar.update(downloaded)
        pbar.finish()
    

class Query:
    '''
    Class to store and modify a single search result as a list.
    '''
    def __init__(self, query, *args, **kwargs):
        self.query=query
        self.raw_results = self.get_raw_results(self.query)
        self.results = []
        self.last_checked = 0

    def get_raw_results(self, query):
        logging.debug("Making a request to mp3skull")
        r = requests.get('http://mp3skull.com/mp3/%s.html' % query)
        logging.debug("Ok. Parsing received page using Beautiful Soup")
        soup = BeautifulSoup(r.text)
        results = soup.find_all(id="song_html")
        result_list = []
        for item in results:
            values = {}
            info = item.contents[3]
            # Get download url
            values['url'] = info.find_all('div')[2].div.div.a['href']
            # Get title
            values['title'] = info.div.b.get_text().strip()
            # Get bitrate, duration and file size
            song_info = item.find(class_='left')
            # Bitrate
            try:
                values['bitrate'] = song_info.contents[2].strip()
            except:
                values['bitrate'] = None
            # Duration
            try:
                values['duration'] = song_info.contents[4].strip()
            except:
                values['duration'] = None
            # File size
            try:
                values['file_size'] = song_info.contents[6].strip()
            except:
                values['file_size'] = None
            
            result_list.append(values)
        logging.debug("Finished parsing page, returning list of results")
        return result_list
    
    def get_from_queue(self, q, entry_list):
        while True:
            entry=q.get()
            if self.check_response(entry) is not None:
                entry_list.append(entry)
            q.task_done()
    
    def check_response(self, entry):
        try:
            r = requests.head(entry['url'])
            if r.status_code == requests.codes.ok:
                return entry
        except requests.exceptions.RequestException:
            return None
        return None

    def batch_responses(self, entry_list, wanted_results=10):
        valid_responses = []
        logging.debug("Checking raw responses for valid connections")
        for entry in entry_list:
            if len(valid_responses) > wanted_results:
                return valid_responses
            if self.check_response(entry) is not None:
                valid_responses.append(entry)
        return valid_responses
    
    def get_results(self, max_results):
        for index, result in enumerate(self.raw_results):
            if len(self.results) >= max_results:
                return self.results[:max_results]
            if index > self.last_checked:
                entry = self.check_response(result)
                if entry:
                    self.results.append(entry)
                self.last_checked += self.last_checked
    def get(self, index):
        return self.results[index]

    def filter(self, raw_results):
        results = []
        concurrent = 200
        q = Queue(concurrent*2)
        for i in range(concurrent):
            t=Thread(target=self.get_from_queue, args=(q,results))
            t.daemon=True
            t.start()
        try:
            for entry in raw_results:
                print "Q",
                q.put(entry)
            q.join()
        except KeyboardInterrupt:
            sys.exit(1)
        return results

class App(cmd.Cmd):
    """Simple example"""
    
    prompt = '>> '
    intro = "Welcome to the Music Downloader! Please type 'search' followed by your query to look for a song, 'queue' to see and download your queue."
    
    def __init__(self, *args, **kwargs):
        cmd.Cmd.__init__(self, *args, **kwargs)
        self.queue = []

    @cmd.options([cmd.make_option('-q', '--queue', action="store_true", help="Queue results and download later")
        ])
    def do_search(self, term, opts=None):
        term = ''.join(term)
        if term:
            print(self.colorize(("searching for %s" % term), 'blue'))
            query = Query(term)
            choice = self.select(self.get_select(query), 'Which one? ') - 1 # adjust for list start at index 0
            action = self.select("play queue download", 'What do you want to do with the file "%s"? ' % choice)
            if action == "download":
                print "Downloading..."
                self.download(query.get(choice))
            elif action == "queue":
                self.queue.append(query.get(choice))
                print "Added to queue"
            elif action == "play":
                call("mplayer \"%s\"" % query.get(choice)['url'])
                print "Finished playing."
        else:
            print "please specify a query"

    def do_artist(self, query):
        print "artist %s" % query 

    def do_song(self, query):
        print "song %s" % query
    
    def do_queue(self, query):
        if len(self.queue) > 0:
            print("Items in queue:")
            for item in self.queue:
                print item['title']
            choice = self.select("Yes No", "Download all items from queue? ")
            if choice == "Yes":
                print "Alright. Downloading all songs..."
                for item in self.queue:
                    self.download(item)
            elif choice == "No":
                print "Okay. I get it."
        else:
            print("queue is empty")
    def get_select(self, query):
        tuples = []
        i = 1
        for item in query.get_results(10):
            tuples.append((i, item['title']))
            i += 1
        return tuples

    def download(self, result, local_filename = None):
        '''Downloads from URL'''
        def url2name(url):
            return os.path.basename(urlsplit(url)[2])
        r = requests.get(result['url'], stream=True)
        # File naming
        filename = result['title']+".mp3"
        if local_filename:
            filename = local_filename
    
        # Getting file size
        total_size = int(r.headers["Content-Length"].strip())
        downloaded = 0
        # Progress bar
        widgets = [filename, ": ", Bar(marker="|", left="[", right=" "),
                Percentage(), " ", FileTransferSpeed(), "] ", str(downloaded),
                " of {0}MB".format(round(total_size / 1024 / 1024 , 2))]
        pbar = ProgressBar(widgets=widgets, maxval=total_size)
        pbar.start()

        with open(filename, 'wb') as fp:
            for chunk in r.iter_content(512):
                if chunk:
                    fp.write(chunk)
                    downloaded += len(chunk)
                    pbar.update(downloaded)
        pbar.finish()
 
if __name__ == '__main__':
    # set up logging
    logging.basicConfig(level=logging.DEBUG)
    
    # Command line options
#    parser = argparse.ArgumentParser(description='Search and download mp3s from mp3skull.')
#    parser.add_argument('query', type=str, nargs='+')
#    args = parser.parse_args()
    
    App().cmdloop()

    # Start command line interface
#    search = CLI(' '.join(args.query))
#    search.display_results(search.results)
