# coding=utf-8
"""
Seamless-branching movie list loader.

Bundled list ships in resources/seamless_branching.json. Optional user-supplied
additions are read from <profile>/seamless_branching_user.json with the same schema.

Schema (per entry):
    {"title": "...", "imdb_id": "tt...", "tmdb_id": 12345}

tmdb_id is optional; the enrichment script populates it for the bundled file.
"""
import os

from . import util

BUNDLED = "seamless_branching.json"
USER = "seamless_branching_user.json"


class SBList(object):
    def __init__(self):
        self.by_imdb = {}
        self.by_tmdb = {}
        self._load(os.path.join(util.ADDON_PATH, "resources", BUNDLED), "bundled")
        self._load(os.path.join(util.PROFILE_PATH, USER), "user")

    def _load(self, path, label):
        data = util.read_json(path)
        if not data:
            return
        added_imdb = 0
        added_tmdb = 0
        for entry in data.get("movies", []):
            imdb_id = entry.get("imdb_id")
            tmdb_id = entry.get("tmdb_id")
            if imdb_id and imdb_id not in self.by_imdb:
                self.by_imdb[imdb_id] = entry
                added_imdb += 1
            if tmdb_id:
                key = str(tmdb_id)
                if key not in self.by_tmdb:
                    self.by_tmdb[key] = entry
                    added_tmdb += 1
        util.log("Loaded {} list: {} imdb, {} tmdb".format(label, added_imdb, added_tmdb))

    def match(self, imdb_id=None, tmdb_id=None):
        if imdb_id and imdb_id in self.by_imdb:
            return self.by_imdb[imdb_id]
        if tmdb_id and str(tmdb_id) in self.by_tmdb:
            return self.by_tmdb[str(tmdb_id)]
        return None

    def __len__(self):
        return len(self.by_imdb)
