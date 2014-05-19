# WWE News plugin by craisins in 2014

import time
import calendar
from util import hook, http, web
import urllib2
from bs4 import BeautifulSoup


SCRAPE_EVERY = 15

feeds = (
#    ("http://bleacherreport.com/articles/feed?tag_id=2182", "BR"),
#    ("http://feeds.feedburner.com/impactwrestling/news?format=xml", "TNA"),
    ("http://www.wwe.com/feeds/rss/features", "WWE")
)

def db_init(db):
    """Check that our db has the wwe_news table, create it if not."""
    db.execute("drop table if exists wwe_news")
    db.execute("create table if not exists wwe_news(id INTEGER PRIMARY KEY AUTOINCREMENT, site TEXT, timestamp INTEGER, title TEXT, full_link TEXT, short_link TEXT, is_shown INTEGER DEFAULT 0)")
    db.commit()


def say_news(db=None, say=None, notice=None, message=None):
    val = get_news(db)
    if val != "":
        say(val)

@hook.singlethread
@hook.event("JOIN")
def crond(inp, nick='', db=None, say=None, notice=None, message=None):
    last_updated = {}
    db_init(db)
    while(True):
        if 'scrape' not in last_updated or (last_updated['scrape'] + (60 * SCRAPE_EVERY)) <= time.time():
            for feed in feeds:
                scrape_feed(feed, db)
            if 'scrape' not in last_updated:
                db.execute("update wwe_news set is_shown = ?", (1,))
                db.commit()
            last_updated['scrape'] = time.time()
        if 'say' not in last_updated or (last_updated['say'] + 60) <= time.time():
            say_news(db, say, notice, message)
            last_updated['say'] = time.time()
        time.sleep(60)


@hook.command
def news(inp, db=None, say=None):
    source = inp.strip().lower()
    if source != "wwe" and source != "tna":
        result = db.execute("select id, site, title, short_link from wwe_news order by timestamp desc LIMIT 3").fetchall()
    else:
        result = db.execute("select id, site, title, short_link from wwe_news where site=? order by timestamp desc LIMIT 3", (source.upper(),)).fetchall()
    for news in result:
        val = u"\x02[{}]\x02 {} - {}".format(news[1], news[2], news[3])
        say(val)

def scrape_feed(info, db):
    url, name = info
    page = urllib2.urlopen(url)#.read()
#    page = page.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    soup = BeautifulSoup(page, "xml")
    items = soup.find_all('item')
    for item in items:
        date = item.find('pubDate').find(text=True)[:-6]
        date = time.strptime(date, '%a, %d %b %Y %H:%M:%S')
        date = time.mktime(date)
        title = item.find('title').find(text=True).replace('<![CDATA[', '').replace(']]>', '')
        full_link = item.find('guid')
        if full_link is None:
            full_link = item.find('link')
        full_link = full_link.find(text=True)
        found_result = db.execute("select * from wwe_news where site=? and full_link=?", (name, full_link,)).fetchone()
        if found_result:
            continue
	
	if date >= (time.time() - (60 * SCRAPE_EVERY) - (60 * 5)):
            print "trying to get isgd link"
            short_link = web.isgd(full_link)
        else:
            short_link = full_link

        if short_link == "":
            short_link = full_link

        db.execute("insert into wwe_news(site, timestamp, title, full_link, short_link) values(?, ?, ?, ?, ?)", (name, date, title, full_link, short_link))
        print u"inserting: [{}]: {}".format(name, str(date))
        db.commit()


def get_news(db):
    res = db.execute("select id, site, title, short_link from wwe_news where is_shown = 0 limit 1").fetchone()
    if res:
        db.execute("update wwe_news set is_shown=? where id=?", (1, res[0]))
        db.commit()
        return u"\x02[{}]\x02 {} - {}".format(res[1], res[2], res[3])
    return ""
