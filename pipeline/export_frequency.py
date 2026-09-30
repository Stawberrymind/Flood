# pipeline/export_frequency.py
"""Season-max OR across years -> flood-frequency raster (counts of seasons flooded)."""

import ee

from flood_watch import config
from flood_watch.decade import run_manifest
from flood_watch.ee_graphs import punjab_districts, flood_mask_for_window

EE_PROJECT = "ee-YOURUSER"


def main():
    ee.Initialize(project=EE_PROJECT)
    aoi = punjab_districts().union(1).geometry()
    season_layers = []
    for year in config.YEARS:
        rows = [r for r in run_manifest([year])]
        season = ee.ImageCollection(
            [flood_mask_for_window(aoi, r["window"], r["pre"]).unmask(0) for r in rows]
        ).max()
        season_layers.append(season)
    freq = ee.ImageCollection(season_layers).sum().rename("flood_frequency")
    ee.batch.Export.image.toDrive(
        image=freq.byte(),
        description="flood_watch_flood_frequency_2015_2025",
        folder="flood_watch",
        region=aoi,
        scale=30,
        maxPixels=1e10,
    ).start()
    print("frequency export queued")


if __name__ == "__main__":
    main()
