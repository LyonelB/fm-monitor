#!/usr/bin/env python3
"""rds_lookup.py - RDS station lookup for fm-monitor
Usage:
  from rds_lookup import RDSLookup
  lookup = RDSLookup(country="FR")
  station = lookup.get(pi="FA41")
"""
import json, time, threading, urllib.request, urllib.error
from pathlib import Path

DB_BASE_URL      = "https://raw.githubusercontent.com/LyonelB/rds-station-db/main/data"
CACHE_DIR        = Path.home() / ".cache" / "fm-monitor" / "rds-db"
CACHE_TTL        = 24 * 3600
USER_AGENT       = "fm-monitor/0.5 (https://github.com/LyonelB/fm-monitor)"

class RDSLookup:
    def __init__(self, country="FR", auto_refresh=True):
        self.country = country.upper()
        self._lock   = threading.Lock()
        self._by_pi  = {}
        self._by_ps  = {}
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._cache  = CACHE_DIR / f"{self.country}.json"
        self._load()
        if auto_refresh:
            threading.Thread(target=self._bg_refresh, daemon=True).start()

    def get_by_pi(self, pi):  return self._by_pi.get(pi.upper())
    def get_by_ps(self, ps):  return self._by_ps.get(ps.strip().upper())
    def get(self, pi=None, ps=None):
        if pi:
            r = self.get_by_pi(pi)
            if r: return r
        return self.get_by_ps(ps) if ps else None
    def station_count(self):  return len(self._by_pi)
    def force_refresh(self):  self._load(force=True)

    def _load(self, force=False):
        data = None
        if not force and self._cache.exists():
            if time.time() - self._cache.stat().st_mtime < CACHE_TTL:
                try:
                    with open(self._cache) as f: data = json.load(f)
                except: pass
        if data is None:
            data = self._fetch()
            if data:
                try:
                    with open(self._cache, "w") as f: json.dump(data, f, ensure_ascii=False)
                except: pass
        if data: self._index(data)

    def _fetch(self):
        url = f"{DB_BASE_URL}/{self.country}.json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        except:
            if self._cache.exists():
                try:
                    with open(self._cache) as f: return json.load(f)
                except: pass
            return None

    def _index(self, data):
        bp, bs = {}, {}
        for s in data.get("stations", []):
            pi = s.get("pi","").upper()
            ps = s.get("ps","").strip().upper()
            if pi: bp[pi] = s
            if ps: bs[ps] = s
        with self._lock:
            self._by_pi, self._by_ps = bp, bs

    def _bg_refresh(self):
        while True:
            time.sleep(3600)
            if self._cache.exists() and time.time()-self._cache.stat().st_mtime >= CACHE_TTL:
                self._load(force=True)

def get_lookup(country="FR"):
    global _singleton
    if '_singleton' not in globals() or _singleton.country != country.upper():
        _singleton = RDSLookup(country=country)
    return _singleton

if __name__ == "__main__":
    import sys
    cc    = sys.argv[1] if len(sys.argv) > 1 else "FR"
    query = sys.argv[2] if len(sys.argv) > 2 else None
    lu    = RDSLookup(country=cc)
    print(f"Chargé : {lu.station_count()} stations ({cc})")
    if query:
        r = lu.get(pi=query) or lu.get(ps=query)
        print(json.dumps(r, indent=2, ensure_ascii=False) if r else f"Introuvable : {query}")
    else:
        for pi, s in sorted(lu._by_pi.items()):
            logo = "🖼" if s.get("logo_url") else "·"
            print(f"  {pi}  {s.get('ps',''):8s}  {s.get('name','')}  {logo}")
