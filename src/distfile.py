import hashlib
import os
import random
import subprocess
import urllib

from . import config
from . import util


class Distfile:

    def __init__(self, distdir, name, checksum, master_sites,
                 patches=frozenset()):
        for patch in patches:
            if not os.path.isfile(patch):
                raise Exception('Patch %s does not exist' % patch)

        self._distdir = distdir
        self._name = name
        self._checksum = checksum
        self._master_sites = master_sites | config.FALLBACK_MIRRORS
        self._patches = patches
        self._pathname = os.path.join(distdir, self._name)

    def _fetch(self):
        for i in range(10):
            print('CHECKSUM', self._pathname)
            # Validate the existing file on disk.
            try:
                checksum = hashlib.sha256()
                with open(self._pathname, 'rb') as f:
                    while True:
                        data = f.read(16384)
                        if not data:
                            break
                        checksum.update(data)
                if checksum.hexdigest() == self._checksum:
                    return
            except FileNotFoundError as e:
                print(e)

            url = (random.sample(self._master_sites, 1)[0] +
                   os.path.basename(self._name))
            print('FETCH', url)
            try:
                with util.unsafe_fetch(url) as fin:
                    util.make_parent_dir(self._pathname)
                    with open(self._pathname, 'wb') as fout:
                        while True:
                            data = fin.read(16384)
                            if not data:
                                break
                            fout.write(data)
            except urllib.error.URLError as e:
                print(e)
        raise Exception('Failed to fetch %s' % self._name)

    def extract(self, target):
        # Fetch and extract tarball.
        self._fetch()
        subprocess.check_call(['tar', '-xC', target, '-f', self._pathname])

        # Remove leading directory names.
        while True:
            entries = os.listdir(target)
            if len(entries) != 1:
                break
            subdir = os.path.join(target, entries[0])
            if not os.path.isdir(subdir):
                break
            target = subdir

        # Apply patches.
        for patch in self._patches:
            with open(patch) as f:
                subprocess.check_call(
                    ['patch', '-d', target, '-tsp0'], stdin=f)

        # Delete .orig files that patch leaves behind.
        for path in util.walk_files(target):
            if path.endswith('.orig'):
                os.unlink(path)
        return target
