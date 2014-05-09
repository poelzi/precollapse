from precollapse import base, exceptions as exc
from precollapse.exceptions import CommandMissing
from precollapse.utils import which
from precollapse.base import CommandBackend, UrlWeight
import subprocess
import asyncio
import os
import logging
import urllib

class GitBackend(CommandBackend):

    name = "git"
    #arguments = (
        #("--recrusive", {"action": "store_true"}),
        #)

    def process_update(self, entry, buffer_, stderr=False):
        #print(buffer_)
        #Length: 86069 (84K) [text/html]
        #if len(buffer_.getvalue()) > 300:
        #    embed()
        if not stderr:
            return

        match = RE_LENGTH.search(buffer_.getvalue())
        #print("match", match)
        if match:
            length, content_type = match.groups()
            print(length, content_type)


    def weight_entry(self, entry):
        try:
            if not entry.url:
                return UrlWeight.unable
            url = urllib.parse.urlparse(entry.url)
            # typical git url
            if url.scheme == "git" or \
               (url.scheme in ("ssh", "https", "http") and url.path[-4:] == ".git"):
                return UrlWeight.very_good
            # a likeliy url
            if url.scheme in ("ssh", "https", "http") and url.path.find(".git") > -1:
                return UrlWeight.likeliy
            return UrlWeight.unable
        except Exception as e:
            self.log.debug("can't handle url: %s" %e)
            return UrlWeight.unable

    @asyncio.coroutine
    def get_command_args(self, entry):
        #embed()
        dm = yield from self.manager.get_download_manager(entry.collection)
        out_path = yield from dm.prepare_entry(entry, None)
        def check_exists(out_path):
            if os.path.exists(os.path.join(out_path, ".git")):
                return True
            return False
        exists = yield from self.daemon.loop.run_in_executor(None, check_exists, out_path)
        print("out_path", out_path, exists)
        if exists:
            args = ["git", "--git-dir=%s" %out_path, "pull"]
        else:
            args = ["git", "clone", entry.url, out_path]
        return args


class GitPlugin(base.Plugin):
    name = "git"
    backends = [GitBackend]

    def check(self):
        if not which("git"):
            raise CommandMissing("git missing")
        return True

    def print_name(self):
        print("git plugin")
