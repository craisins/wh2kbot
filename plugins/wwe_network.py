# WWE Network Schedule plugin by craisins in 2014

import time
import calendar
import json
import urllib2
from util import hook, http, web

schedule_url = "http://epg.media.net.wwe.com/epg_small.json"

def db_init(db):
    db.execute("drop table if exists wwe_network")
    db.execute("create table if not exists wwe_network(datetime, title, description, alert_start default 0, primary key (datetime))")
    db.commit()


def get_schedule(db=None):
    db_init(db)
    print "wwe_network: get_schedule"
    page = urllib2.urlopen(schedule_url).read()
    schedule = json.loads(page)
    schedule = schedule["events"]
    right_now = time.gmtime()
    right_now_timestamp = calendar.timegm(right_now)
    
    for show in schedule:
        title = show["title"]
        desc = show["big_blurb"]
        time_gmt = show["dates_and_times"]["start_time_gmt"]

        timestamp = calendar.timegm(time.strptime(time_gmt, "%Y-%m-%dT%H:%M:%S+0000"))

        results = db.execute("select * from wwe_network where datetime = ?", (timestamp,)).fetchall()
        # don't load anything older than 5 hours because it's not worth it
        if not results and (timestamp > right_now_timestamp - (60*60*5)):
            db.execute("insert into wwe_network(datetime, title, description) values(?, ?, ?)", (timestamp, title, desc))
            db.commit()
            # debug message
            print "wwe_network: Added {} at {}".format(title, timestamp) 
        # anything older than right now should be marked as alerted because we don't want to again
        db.execute("update wwe_network set alert_start = 1 where datetime < ?", (right_now_timestamp,))
        db.commit()  


@hook.command
def search(inp, nick='', db=None, say=None):
    timestamp_gmt = calendar.timegm(time.gmtime())
    original_input = inp
    inp = inp.lower()
    results = db.execute("select * from wwe_network where datetime > ? and (title like ? or description like ?) order by datetime asc", (timestamp_gmt, '%'+inp+'%', '%'+inp+'%')).fetchall()
    if results:
        counter = 0
        for result in results:
            if counter > 2:
                break
            datetime, title, desc, alert_start = result
            datetime = time.strftime("%Y-%m-%d %I:%M%p %Z", time.localtime(datetime))
            say("{}: \x02{}\x02: {}".format(datetime, title, desc))
            counter += 1
    else:
        say(u"No results found for \"{}\"".format(original_input))


@hook.command
def now(inp, nick='', db=None, say=None):
    timestamp_gmt = calendar.timegm(time.gmtime())
    # get the last event that started
    result = db.execute("select * from wwe_network where datetime < ? order by datetime desc limit 1", (timestamp_gmt,)).fetchone()
    if result:
        datetime, title, desc, alert_start = result
        say(u"\x02{}\x02: {}".format(title, desc))
        return


@hook.command("schedule")
def schedule(inp, nick='', db=None, say=None):
    time_gmt = time.gmtime()
    timestamp_gmt = calendar.timegm(time_gmt)
    # get the last event that started
    result = db.execute("select * from wwe_network where datetime < ? order by datetime desc limit 1", (timestamp_gmt,)).fetchone()
    output = ""
    if result:
        datetime, title, desc, alert_start = result
        say(u"Now: \x02{}\x02: {}".format(title, desc))
    # get the next two events
    results = db.execute("select * from wwe_network where datetime > ? order by datetime asc limit 2", (timestamp_gmt,)).fetchall()
    if results:
        for result in results:
            datetime, title, desc, alert_start = result
            say(u"At {}: \x02{}\x02: {}".format(time.strftime("%I:%M%p %Z", time.localtime(datetime)), title, desc))
    return


@hook.event("JOIN")
@hook.singlethread
def crond(inp, db=None, say=None):
    # start a new thread
    print "Starting wwenetwork:crond"
    get_schedule(db)
    # keep track of when you're scraping the network site
    last_scraped = calendar.timegm(time.gmtime())
    while True:
        time_gmt = time.gmtime()
        timestamp_gmt = calendar.timegm(time_gmt)

        # if it's been 12 hours since scraping the json file, do it again
        if timestamp_gmt > (last_scraped + (60*60*12)):
            get_schedule("Scraping WWE Network for new shows.")
            last_scraped = timestamp_gmt

        # if you're within one minute of a new event starting, let everyone know
        results = db.execute("select * from wwe_network where datetime <= ? and datetime >= ? and alert_start = 0", (timestamp_gmt + 60, timestamp_gmt - 60)).fetchall()
        if results:
            for result in results:
                datetime, title, desc, alert_start = result
                db.execute("update wwe_network set alert_start = 1 where datetime = ?", (datetime,))
                db.commit()
                say(u"Starting Now: \x02{}\x02: {}".format(title, desc))

        time.sleep(60)
