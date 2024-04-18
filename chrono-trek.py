#!/usr/bin/env python3

import csv
import json
from typing import List, Optional
import click

from lib.jellyfin_client import JellyfinClient
from lib.jellyfin_data import Library, Series, Video, build_libraries, build_library, build_playlist, create_jf_playlist, get_items_for_library, get_items_for_playlist

series_map = {
    "TOS": "The Original Series",
    "TAS": "The Animated Series",
    "TNG": "The Next Generation",
    "DS9": "Deep Space Nine",
    "VOY": "Voyager",
    "ENT": "Enterprise",
    "SHO": "Short Treks",
    "PIC": "Picard",
    "DIS": "Discovery",
    "LDS": "Lower Decks",
    "PRO": "Prodigy",
    "SNW": "Strange New Worlds",
}

class VideoEntry:
    def __init__(self, name: str, parent: str, season: Optional[int], episode: Optional[int]):
        self.name = name
        self.parent = parent
        self.is_movie : bool = parent.upper() == "MOV"
        self.season = season
        self.episode = episode
        self._series = None

        self.name = self.name.replace("’", "'").replace("…", "...")
        if self.name == "Prophesy":
            self.name = "Prophecy"
        if self.name == "Inter Arma Silent Leges":
            self.name = "Inter Arma Enim Silent Leges"
        if self.name == "Vis a Vis":
            self.name = "Vis À Vis"
        if self.name == "Menage a Troi":
            self.name = "Ménage à Troi"
        if self.name == "When The Bow Breaks":
            self.name = "When the Bough Breaks"
        if self.name == "Is There No Truth in Beauty?":
            self.name = "Is There in Truth No Beauty?"
        if self.name == "Momento Mori":
            self.name = "Memento Mori"
        if self.name == "The Butchers Knife Cares Not for the Lambs Cry":
            self.name = "The Butcher's Knife Cares Not for the Lamb's Cry"
        if self.name == "Battle of the Binary Stars":
            self.name = "Battle at the Binary Stars"
        if self.name == "E-Squared":
            self.name = "E²"

        if self.name == "The Cage" and self.season == 0:
            self.season = 1
            self.episode = 0

    def series_name(self):
        if self.is_movie:
            return None
        if not self._series:
            series = self.parent.upper()
            if series in series_map:
                self._series = series_map[series]
            else:
                print("Unknown series: {}".format(series))
                exit(1)
        return self._series


class ChronoList:
    def __init__(self):
        self.videos: List[VideoEntry] = []

    def load_from_file(self, file_path: str):
        with open(file_path, "r") as file:
            reader = csv.reader(file, delimiter='|')
            header = None
            for row in reader:
                if not header:
                    header = row
                else:
                    name = row[3]
                    parent = row[0]
                    season = int(row[1]) if row[1] else None
                    episode = int(row[2]) if row[2] else None
                    self.videos.append(VideoEntry(name, parent, season, episode))


def matches_series(series: Series, entry: VideoEntry):
    series_name = entry.series_name()
    if series.Name.endswith(series_name):
        return True
    if series_name == "The Original Series" and series.Name == "Star Trek" and len(series.seasons) == 3:
        return True
    if series_name == "The Animated Series" and series.Name == "Star Trek" and len(series.seasons) == 2:
        return True


def matches_episode(video: Video, entry: VideoEntry):
    if entry.name == "Vox" and video.Name == "Võx" or \
       entry.name == "I, Excretes" and video.Name == "I, Excretus":
        return True

    entry_name = entry.name.lower()
    video_name = video.Name.lower()
    if entry_name == video_name or entry_name.startswith(video_name) or video_name.startswith(entry_name):
        return True
    
    entry_name = entry_name.replace(",", "").replace("part ii", "part 2").replace("part i", "part 1")
    video_name = video_name.replace(",", "").replace("part ii", "part 2").replace("part i", "part 1")
    if entry_name == video_name:
        return True
    
    entry_name = entry_name.replace("the", "").replace("  ", " ").replace("(", "").replace(")", "").replace("--", "").replace(":", "").replace("  ", " ").strip()
    video_name = video_name.replace("the", "").replace("  ", " ").replace("(", "").replace(")", "").replace("--", "").replace(":", "").replace("  ", " ").strip()
    if entry_name == video_name:
        return True

    entry_name = entry_name.replace("-", " ").replace("...", "")
    video_name = video_name.replace("-", " ").replace("...", "")
    if entry_name == video_name:
        return True

    if video_name.endswith(entry_name.replace(" part 1", "").replace(" part 2", "")):
        return True

    return False


def ids_for_playlist(chrono_list_file: str, movies: Library, shows: Library):
    ids = []
    chrono_list = ChronoList()
    chrono_list.load_from_file(chrono_list_file)
    prev_entry = None
    for entry in chrono_list.videos:
        if entry.is_movie:
            for id, movie in movies.jf_items.items():
                if movie.Name == entry.name or (movie.Name == "Star Trek" and entry.name == "Star Trek (2009)"):
                    break
            else:
                print("{}: UNKNOWN".format(entry.name))
        else:
            series_id = "UNKNOWN"
            season_id = "UNKNOWN"
            video_id = "UNKNOWN"

            for id, series in shows.jf_items.items():
                if matches_series(series, entry):
                    series_id = id
                    for sid, season in series.seasons.items():
                        if season.season_number == entry.season:
                            season_id = sid
                            for video in season.videos:
                                if matches_episode(video, entry):
                                    video_id = video.Id
                                    ids.append(video_id)
                                    break

            if series_id == "UNKNOWN" or season_id == "UNKNOWN" or video_id == "UNKNOWN":
                if prev_entry and series_id != "UNKNOWN" and season_id != "UNKNOWN" and entry.name.endswith("Part 2") and prev_entry.name.endswith("Part 1"):
                    print("Assuming {} is combined in the file that has {}".format(entry.name, prev_entry.name))
                else:
                    print("{} S{}E{} {}: {} {} {}".format(entry.series_name(), entry.season, entry.episode, entry.name, series_id, season_id, video_id))
            prev_entry = entry
    return ids


class CliContext:
    def __init__(self, client: JellyfinClient, user_id: str, debug: bool):
        self.client = client
        self.user_id = user_id
        self.debug = debug


@click.group()
@click.pass_context
@click.option('--debug', flag_value=True, help="Enable debug-level of logging")
@click.option('--url', help='')
@click.option('--user-id', help='')
@click.option('--token', help='')
@click.option('--device-id', help='')
def cli(ctx, debug: bool, url: str, user_id: str, token: str, device_id: str):
    """chrono-trek - create playlist of chronological star trek
    """

    if not url or not user_id or not token or not device_id:
        login_file = "login.json"
        # print("Loading login creds from {}".format(login_file))
        with open(login_file, "r") as f:
            data = json.loads(f.read())
            if "url" in data:
                url = data["url"]
            if "user_id" in data:
                user_id = data["user_id"]
            if "token" in data:
                token = data["token"]
            if "device_id" in data:
                device_id = data["device_id"]

    client = JellyfinClient(base_url=url, token=token, device_id=device_id)
    ctx.obj = CliContext(client, user_id, debug)


@cli.command()
@click.argument("chrono-list-file")
@click.pass_obj
def validate(context: CliContext, chrono_list_file: str):
    libraries = build_libraries(context.client, context.user_id)
    movies : Library = None
    shows : Library = None
    for library in libraries:
        if library.Name == "Movies":
            movies = library
        if library.Name == "TV Shows":
            shows = library

    if not movies:
        print("Cannot find 'Movies' library")
        exit(1)
    if not shows:
        print("Cannot find 'TV Shows' library")
        exit(1)
    if not build_library(context.client, context.user_id, movies):
        print("Cannot get all items from 'Movies'")
        exit(2)
    if not build_library(context.client, context.user_id, shows):
        print("Cannot get all items from 'TV Shows'")
        exit(2)

    ids_for_playlist(chrono_list_file, movies, shows)


@cli.command("create-playlist")
@click.argument("chrono-list-file")
@click.argument("name")
@click.pass_obj
def create_playlist(context: CliContext, chrono_list_file: str, name: str):
    libraries = build_libraries(context.client, context.user_id)
    movies : Library = None
    shows : Library = None
    for library in libraries:
        if library.Name == "Movies":
            movies = library
        if library.Name == "TV Shows":
            shows = library

    if not movies:
        print("Cannot find 'Movies' library")
        exit(1)
    if not shows:
        print("Cannot find 'TV Shows' library")
        exit(1)
    if not build_library(context.client, context.user_id, movies):
        print("Cannot get all items from 'Movies'")
        exit(2)
    if not build_library(context.client, context.user_id, shows):
        print("Cannot get all items from 'TV Shows'")
        exit(2)

    ids = ids_for_playlist(chrono_list_file, movies, shows)
    create_jf_playlist(context.client, context.user_id, name, ids)


@cli.command()
@click.pass_obj
def show(context: CliContext):
    # libraries = build_libraries(context.client, context.user_id)
    # playlists : Library = None
    # for library in libraries:
    #     print("{}: {}".format(library.Name, library.Id))
    #     if library.Name == "Playlists":
    #         playlists = library

    # if playlists:
    #     raw_playlists = get_items_for_library(context.client, context.user_id, playlists.Id)
    #     print(get_items_for_playlist(context.client, context.user_id, raw_playlists[-1]["Id"]))
    playlist = build_playlist(context.client, context.user_id, "Chill")
    print(playlist.__dict__)


if __name__ == "__main__":
    cli()
