from precollapse import base, exceptions as exc
from precollapse.exceptions import CommandMissing
from precollapse.utils import which
from precollapse.base import CommandBackend, UrlWeight, Arguments
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
        print("git buffer", entry, buffer_, stderr)
        print(buffer_.getvalue())
        if not stderr:
            return


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

        def check_submodule(out_path):
            if os.path.exists(os.path.join(out_path, ".gitmodules")):
                return [Arguments("git", "submodule", "init", cwd=out_path),
                        Arguments("git", "submodule", "update", cwd=out_path)]
            return False

        @asyncio.coroutine
        def submodules(**kwargs):
            rv = yield from self.daemon.loop.run_in_executor(None, check_submodule, out_path)
            return rv

        print("out_path", out_path, exists)
        if exists:
            args = [Arguments("git", "--git-dir=%s" %os.path.join(out_path, '.git'), "fetch", "--all"),
                    Arguments("git", "--git-dir=%s" %os.path.join(out_path, '.git'), "merge", "FETCH_HEAD"),
                    submodules]
        else:
            args = [Arguments("git", "clone", entry.url, out_path),
                    submodules]
        return args

    @asyncio.coroutine
    def failure(self, entry, msg, **kwargs):
        if kwargs.get("returncode", None) == 128:
            dm = yield from self.manager.get_download_manager(entry.collection)
            self.log.info("found old non git download. move to craft")
            yield from dm.move_to_craft(entry)

class GitPlugin(base.Plugin):
    name = "git"
    backends = [GitBackend]

    def check(self):
        if not which("git"):
            raise CommandMissing("git missing")
        return True

    def print_name(self):
        print("git plugin")
