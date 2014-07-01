# WWE News plugin by craisins in 2014

import time
import calendar
from util import hook, http, web
import urllib2
from bs4 import BeautifulSoup


SCRAPE_EVERY = 15

feeds = [
#    ("http://bleacherreport.com/articles/feed?tag_id=2182", "BR"),
#    ("http://feeds.feedburner.com/impactwrestling/news?format=xml", "TNA"),
    ("http://www.wwe.com/feeds/rss/features", "WWE")
]

def db_init(db):
    """Check that our db has the wh2k_news table, create it if not."""
    db.execute("drop table if exists wh2k_news")
    db.execute("create table if not exists wh2k_news(id INTEGER PRIMARY KEY AUTOINCREMENT, site TEXT, timestamp INTEGER, title TEXT, full_link TEXT, short_link TEXT, is_shown INTEGER DEFAULT 0)")
    db.commit()


def say_news(db=None, say=None, notice=None, message=None):
    val = get_news(db)
    for v in val:
        say(v)


@hook.singlethread
@hook.event("JOIN")
def crond(inp, nick='', db=None, say=None, notice=None, message=None):
    last_updated = {}
    db_init(db)
    while True:
        if 'scrape' not in last_updated or (last_updated['scrape'] + (60 * SCRAPE_EVERY)) <= time.time():
            for feed in feeds:
                scrape_feed(feed, db, 1)
            if 'scrape' not in last_updated:
                for feed in feeds:
                    scrape_feed(feed, db, 48)
                db.execute("update wh2k_news set is_shown = ?", (1,))
                db.commit()
            last_updated['scrape'] = time.time()
        if 'say' not in last_updated or (last_updated['say'] + 60) <= time.time():
            say_news(db, say, notice, message)
            last_updated['say'] = time.time()
        if time.strftime("%H %M", time.localtime()) == "12 00":
            scrape_feed(("http://feeds.feedburner.com/impactwrestling/news?format=xml", "TNA"), db, 24)
            tna_feed = [ {"column": "site",
                "comparer": "=",
                "value": "TNA"
            } ]
            print "GOT TNA NEWS!"
            val = get_news(db, tna_feed, 100)
            if len(val) > 0:
                say("\x02I'M AFRAID I'VE GOT SOME BAD NEWS!\x02")
                for i in val:
                    say(i)
                    time.sleep(20)

                say("\x02YOU'RE WELCOME!\x02")

        time.sleep(60)


@hook.command
def news(inp, db=None, say=None):
    result = db.execute("select id, site, title, short_link from wh2k_news where site=? order by timestamp desc LIMIT 3", ('WWE',)).fetchall()
    for news in result:
        val = u"\x02[{}]\x02 {} - {}".format(news[1], news[2], news[3])
        say(val)

def scrape_feed(info, db, past_hours=1):
    url, name = info
    page = urllib2.urlopen(url)#.read()
#    page = page.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
    soup = BeautifulSoup(page, "xml")
    items = soup.find_all('item')
    for item in items:
        date = item.find('pubDate').find(text=True)[:-6]
        date = time.strptime(date, '%a, %d %b %Y %H:%M:%S')
        date = time.mktime(date)
        if date < time.time() - (60 * 60 * past_hours):
            continue
        title = item.find('title').find(text=True).replace('<![CDATA[', '').replace(']]>', '')
        full_link = item.find('guid')
        if full_link is None:
            full_link = item.find('link')
        full_link = full_link.find(text=True)
        found_result = db.execute("select * from wh2k_news where site=? and full_link=?", (name, full_link,)).fetchone()
        if found_result:
            continue

        short_link = full_link

        db.execute("insert into wh2k_news(site, timestamp, title, full_link, short_link) values(?, ?, ?, ?, ?)", (name, date, title, full_link, short_link))
        print u"inserting: [{}]: {}".format(name, str(date))
        db.commit()


def get_news(db, where={}, limit=1):
    sql = "select id, site, title, short_link from wh2k_news where is_shown = ? "
    sql_params = [0]
    for w in where:
        sql = sql + " and (" + w['column'] + " " + w['comparer'] + " ?) "
        sql_params.append(w['value'])
    sql = sql + " limit {}".format(limit)
    res = db.execute(sql, sql_params).fetchall()
    if res:
        ret_val = []
        for r in res:
            
            db.execute("update wh2k_news set is_shown=? where id=?", (1, r[0]))
            db.commit()
            print "updating id: {}".format(r[0])
            ret_val.append(u"\x02[{}]\x02 {} - {}".format(r[1], r[2], r[3]))
        return ret_val
    return []
