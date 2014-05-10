from precollapse.base import Backend, UrlWeight
from precollapse import base, utils
from precollapse.exceptions import CommandMissing
from precollapse.db import create_session, model
import urllib
import asyncio
import re
from sqlalchemy.orm import object_session
from sqlalchemy.orm.exc import NoResultFound

try:
    import feedparser
except ImportError:
    feedparser = None

class FeedreaderBackend(Backend):

    name = "feedreader"
    arguments = (
        )

    def weight_entry(self, entry):
        try:
            if not entry.url:
                return UrlWeight.unable
            url = urllib.parse.urlparse(entry.url)
            if url.scheme not in ("http", "https"):
                return UrlWeight.unable
            for suffix in ['.atom', '.rss', '.rdf', 'atom.xml', '.atom-1.0',
                           'rss.xml']:
                if url.path.endswith(suffix):
                    return UrlWeight.very_good
            return UrlWeight.unable
        except Exception as e:
            self.log.debug("can't handle url: %s" %e)
            return UrlWeight.unable

    def parse_feed(self, entry):
        os = object_session(entry)
        os.expunge(entry)

        session = create_session()
        session.add(entry)
        if entry.type != model.EntryType.collection:
            entry.type = model.EntryType.collection
            session.commit()
        feed = feedparser.parse(entry.url)
        if feed['bozo']:
            msg = []
            if feed.get('status', 0) > 400:
                if feed['status'] == 404:
                    msg.append("HTTP Error 404. File not found. Please check url: %s" %entry.url)
                else:
                    msg.append("HTTP error: %s" %feed['status'])
            msg.append(str(feed['bozo_exception']))
            self.failure(entry, "\n".join(msg))
            return
        for fentry in feed.get('entries', ()):

            subentry, created = entry.get_or_create_child(fentry['title'],
                               {'name':          fentry['title'],
                                'parent_id':     entry.id,
                                'collection_id': entry.collection_id,
                                'type':          model.EntryType.collection_directory})
            #embed()
            for link in fentry.get('links', ()):
                if link.get('rel', None) in ['enclosure', 'alternate']:
                    fname = urllib.parse.urlparse(link['href'])
                    bname = utils.basename(fname.path)
                    lnk, created = subentry.get_or_create_child(bname,
                                         {"name":          bname,
                                          "parent_id":     subentry.id,
                                          "collection_id": subentry.collection_id,
                                          "type":          model.EntryType.collection_single})
                    session.add(lnk)
                    lnk.url = link['href']
                    lnk.set_meta("type", link['type'])
            session.commit()


    def handle_entry(self, future, entry):
        process = self.manager.loop.run_in_executor(None, self.parse_feed, entry)

        yield from asyncio.wait_for(process, 60.0)
        #result = yield from process.result()
        #print(result)



class FeedreaderPlugin(base.Plugin):

    backends = [FeedreaderBackend]

    def check(self):
        if not feedparser:
            raise exc.ModuleMissing("feedreader")
        return True

