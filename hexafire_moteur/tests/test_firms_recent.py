import numpy as np
import pandas as pd

from hexafire import tables
from hexafire.config import Config
from hexafire.firms_recent import preparer_api


def test_preparer_api(tmp_path):
    cfg = Config(tmp_path / "b", tmp_path / "p", tmp_path / "a", tmp_path / "j", 0.25, (0,), 30, ("l",),
                 2003, 2020, 2012, 2020, "2021-01")
    (cfg.agregats).mkdir(parents=True)
    pd.DataFrame({"cle": []}).to_csv(cfg.agregats / "sources_fixes.csv", index=False)
    d = cfg.donnees_brutes / "firms_api" / "VIIRS_NOAA21_NRT"
    d.mkdir(parents=True)
    (d / "2026-09-01_5j.csv").write_text(
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_ti5,frp,daynight\n"
        "9.5,2.3,330,0.4,0.4,2026-09-01,236,N21,VIIRS,n,2.0NRT,290,3.1,N\n"
        "9.5,2.3,330,0.4,0.4,2026-09-01,1305,N21,VIIRS,l,2.0NRT,290,3.1,D\n"
        "9.6,2.4,330,0.4,0.4,2026-09-02,1310,N21,VIIRS,h,2.0NRT,290,9.0,D\n")
    m = cfg.donnees_brutes / "firms_api" / "MODIS_NRT"
    m.mkdir(parents=True)
    (m / "2026-09-01_5j.csv").write_text(
        "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight\n"
        "9.5,2.3,330,1,1,2026-09-01,1030,T,MODIS,80,6.1NRT,290,12,D\n"
        "9.5,2.3,330,1,1,2026-09-01,1330,A,MODIS,20,6.1NRT,290,12,D\n")
    assert preparer_api(cfg) == 2
    v = tables.lire(tables.chemin_table(cfg.donnees_preparees / "NOAA-21" / "2026", "NOAA-21_202609_api"))
    assert len(v) == 2 and set(v["jour_nuit"]) == {"J", "N"} and 236 in set(v["hhmm"])
    t = tables.lire(tables.chemin_table(cfg.donnees_preparees / "Terra" / "2026", "Terra_202609_api"))
    assert len(t) == 1
