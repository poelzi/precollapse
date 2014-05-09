from precollapse import base, exceptions as exc
from precollapse.exceptions import CommandMissing
from precollapse.utils import which
import subprocess
import asyncio
import os
import logging

class GitAnnexDownloadManager(base.DownloadManager):
    """
    Download manager that stores all files in a git-annex tree
    """

    log = logging.getLogger(__name__)
    name = "git-annex"
    quality = 50

    def _git_start(self):
        self.log.debug("initialize git-annex repo: %s" %self.download_path)
        os.makedirs(self.download_path, exist_ok=True)
        #subprocess.call(args, *, stdin=None, stdout=None, stderr=None, shell=False, timeout=None)
        if not os.path.exists(os.path.join(self.download_path, ".git")):

            proc = subprocess.Popen(["git", "init"],
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    cwd=self.download_path)
            try:
                outs, errs = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                outs, errs = proc.communicate()
            if proc.returncode != 0:
                raise exc.DownloadManagerException("can't initialize git repository for %s: %s" %(self.download_path, errs))
        if not os.path.exists(os.path.join(self.download_path, ".git", "annex")):
            name = self.collection and self.collection.name or ""
            proc = subprocess.Popen(["git-annex", "init", name],
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    cwd=self.download_path)
            try:
                outs, errs = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                outs, errs = proc.communicate()
            if proc.returncode != 0:
                raise exc.DownloadManagerException("can't initialize git-annex repository for %s: %s" %(self.download_path, errs))

    @asyncio.coroutine
    def start(self):
        #yield from asyncio.wait_for(self._git_start(), None)
        yield from self.manager.loop.run_in_executor(None, self._git_start)

    @asyncio.coroutine
    def prepare_entry(self, entry, relpath=None):
        """
        Prepare everything for the file to be added to the collection.
        relpath is determined by the backend

        returns absolute path
        """
        print(entry.system_path)
        rv = os.path.join(self.download_path, entry.system_path)
        yield from self.manager.loop.run_in_executor(None, self._prepare_entry, entry, rv)

        return rv

    def _prepare_entry(self, entry, path):
        os.makedirs(path, exist_ok=True)
        proc = subprocess.Popen(["git-annex", "unlock", path],
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL,
                          cwd=self.download_path)
        stdout, stderr = proc.communicate()
        print(stdout, stderr)

    def _rm_recrusive(self, path):
        for (dirpath, dirnames, filenames) in os.walk(path, topdown=False, onerror=None, followlinks=False):
            for fn in filenames:
                os.unlink(os.path.join(dirpath, fn))
            for dn in dirnames:
                os.rmdir(os.path.join(dirpath, dn))
            #print(dirpath, dirnames, filenames)

    def clear_entry(self, entry):
        """
        Removes all files downloaded into the entry
        """
        path = os.path.join(self.download_path, entry.full_path)
        if self.manager.loop:
            yield from asyncio.wait_for(self._rm_recrusive(path), None)
        else:
            self._rm_recrusive(path)

    @asyncio.coroutine
    def entry_done(self, entry):
        """
        Mark file to be successfull downloaded
        """
        path = entry.full_path #os.path.join(self.download_path, entry.full_path[1:])
        proc = yield from asyncio.create_subprocess_exec(
            "git-annex", "add", path,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=self.download_path)
        try:
            stdout, _ = yield from proc.communicate()
        except:
            proc.kill()
            yield from proc.wait()
            raise
        exitcode = yield from proc.wait()
        proc = yield from asyncio.create_subprocess_exec(
            "git", "status", "-s", "--ignore-submodules=dirty", path,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=self.download_path)

        stdout, _ = yield from proc.communicate()
        if len(stdout):
            if exitcode != 0:
                self.log.error("can't add files to git-annex tree: %s", stdout)
                return
            proc = yield from asyncio.create_subprocess_exec(
                "git", "commit", path, "-m", "entry: %s" %entry.full_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.download_path)
            try:
                stdout, _ = yield from proc.communicate()
            except:
                proc.kill()
                yield from proc.wait()
                raise
            exitcode = yield from proc.wait()
            if exitcode != 0:
                self.log.error("can't commit to git-annex tree: %s", stdout)
                return

        return



class GitAnnexPlugin(base.Plugin):
    name = "git-annex"
    download_manager = GitAnnexDownloadManager

    def check(self):
        if not which("git"):
            raise CommandMissing("git missing")
        if not which("git-annex"):
            raise CommandMissing("git-annex missing")
        return True
