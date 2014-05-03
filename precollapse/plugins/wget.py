from precollapse.base import CommandBackend, UrlWeight
from precollapse import base
from precollapse.exceptions import CommandMissing
from precollapse.utils import which
import urllib
import re

RE_LENGTH=re.compile(r'Length: ([0-9]+) \(.*\) \[([^\]]*)\]')


class WgetBackend(CommandBackend):

    name = "wget"
    arguments = (
        ("--recrusive", {"action": "store_true"}),
        )

    def process_update(self, entry, buffer_, stderr=False):
        print(buffer_)
        #Length: 86069 (84K) [text/html]
        #if len(buffer_.getvalue()) > 300:
        #    embed()

        match = RE_LENGTH.search(buffer_.getvalue())
        print("match", match)
        if match:
            length, content_type = match.groups()
            print(length, content_type)


    def weight_entry(self, entry):
        try:
            if not entry.url:
                return UrlWeight.unable
            url = urllib.parse.urlparse(entry.url)
            if url.scheme not in ("http", "https", "ftp"):
                return UrlWeight.unable
            return UrlWeight.good
        except Exception as e:
            self.log.debug("can't handle url: %s" %e)
            return UrlWeight.unable

    def get_command_args(self, entry):
        out_path = self.manager.download_manager.prepare_entry(entry, None)
        args = ["wget", "--progress=dot", "-P", out_path, "-N", entry.url]
        return args

class WgetPlugin(base.Plugin):

    backends = [WgetBackend]

    def check(self):
        if not which("wget"):
            raise CommandMissing("wget missing")
        return True

