#!/usr/bin/env python3

import csv
import json
from typing import List, Optional
import click

from lib.jellyfin_client import JellyfinClient
from lib.jellyfin_data import Library, Series, Video, add_to_jf_playlist, build_libraries, build_library, build_playlist, create_jf_playlist, move_item_in_jf_playlist

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
        if self.name == "Vox":
            self.name = "Võx"
        if self.name == "I, Excretes":
            self.name = "I, Excretus"

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
    entry_name = entry.name.lower()
    video_name = video.Name.lower()
    if entry_name == video_name:
        return True
    
    entry_name = entry_name.replace(",", "").replace("part ii", "part 2").replace("part i", "part 1")
    video_name = video_name.replace(",", "").replace("part ii", "part 2").replace("part i", "part 1")
    if entry_name == video_name:
        return True
    
    entry_name = entry_name.replace("the", "").replace("(", "").replace(")", "").replace("--", "").replace(":", "").replace("  ", " ").strip()
    video_name = video_name.replace("the", "").replace("(", "").replace(")", "").replace("--", "").replace(":", "").replace("  ", " ").strip()
    if entry_name == video_name:
        return True

    entry_name = entry_name.replace("-", " ").replace("...", "").replace("?", "").replace("!", "")
    video_name = video_name.replace("-", " ").replace("...", "").replace("?", "").replace("!", "")
    if entry_name == video_name:
        return True

    if entry_name.replace("part 1", "").strip() == video_name.replace("part 1", "").strip():
        return True

    return False


def ids_for_playlist(chrono_list_file: str, movies: Library, shows: Library):
    ids = []
    names = []

    matched_count = 0
    unmatched_count = 0
    merged_count = 0

    chrono_list = ChronoList()
    chrono_list.load_from_file(chrono_list_file)
    prev_entry = None
    prev_video = None
    for entry in chrono_list.videos:
        if entry.is_movie:
            found = False
            for id, movie in movies.jf_items.items():
                if movie.Name == entry.name or (movie.Name == "Star Trek" and entry.name == "Star Trek (2009)"):
                    ids.append(movie.Id)
                    names.append(movie.Name)
                    matched_count += 1
                    found = True
                    break
            if not found:
                unmatched_count += 1
                print(f"{entry.name}: id=None")
        else:
            series_id = None
            season_id = None
            video_id = None

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
                                    names.append(video.Name)
                                    matched_count += 1
                                    prev_video = video
                                    break

            found = series_id and season_id and video_id
            if not found and prev_entry and series_id and season_id:
                if (entry.name.endswith("Part 2") and prev_entry.name.endswith("Part 1")) or \
                    (entry.name.endswith(" II") and prev_entry.name.endswith(" I")):
                    merged_count += 1
                    print(f"Assuming {entry.name} is combined in the file that has {prev_entry.name} ({prev_video.Name})")
                    found = True
            if not found:
                unmatched_count += 1
                print(f"{entry.series_name()} S{entry.season}E{entry.episode} {entry.name}: series_id={series_id} season_id={season_id} episode_id={video_id}")

            prev_entry = entry

    print(f"Videos in list: {len(chrono_list.videos)}\tMatched in Jellyfin: {matched_count}\tUnmatched: {unmatched_count}\tAssumed merged: {merged_count}")

    return ids, names


class CliContext:
    def __init__(self, client: JellyfinClient, user_id: str):
        self.client = client
        self.user_id = user_id


@click.group()
@click.option('--url', help='URL to your Jellyfin instance')
@click.option('--user-id', help='Jellyfin user id (not name)')
@click.option('--token', help='Jellyfin user token (not api token)')
@click.option('--device-id', help='jellytrek device-id')
@click.pass_context
def cli(ctx, url: str, user_id: str, token: str, device_id: str):
    """chrono-trek - create playlist of chronological star trek

       run login.py first, and this will read the login details from login.json
    """

    if not url or not user_id or not token or not device_id:
        login_file = "login.json"
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
    ctx.obj = CliContext(client, user_id)


@cli.command("check-videos")
@click.argument("chrono-list-file")
@click.pass_obj
def check_videos(context: CliContext, chrono_list_file: str):
    """check your Jellyfin instance for the videos in the input file
    """
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


@cli.command("check-playlist")
@click.argument("chrono-list-file")
@click.argument("name")
@click.pass_obj
def check_playlist(context: CliContext, chrono_list_file: str, name: str):
    """check your Jellyfin playlist for the videos in the input file
    """
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

    ids, names = ids_for_playlist(chrono_list_file, movies, shows)
    jf_playlist = build_playlist(context.client, context.user_id, name)

    if len(ids) != len(jf_playlist.videos):
        print(f"Mismatch on number of videos: list={len(ids)}, playlist={len(jf_playlist.videos)}")

    for index, video in enumerate(jf_playlist.videos):
        if video.Id != ids[index]:
            print(f"{index:03d} {video.Name} != {names[index]}")


@cli.command("create-playlist")
@click.argument("chrono-list-file")
@click.argument("name")
@click.pass_obj
def create_playlist(context: CliContext, chrono_list_file: str, name: str):
    """create a Jellyfin playlist of the videos in the input file
    """
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

    ids, _ = ids_for_playlist(chrono_list_file, movies, shows)
    create_jf_playlist(context.client, context.user_id, name, ids)


@cli.command("update-playlist")
@click.argument("chrono-list-file")
@click.argument("name")
@click.pass_obj
def update_playlist(context: CliContext, chrono_list_file: str, name: str):
    """update a Jellyfin playlist of the videos in the input file

       Currently only adding is supported (not reordering or removing)

       Moving new items in the correct place in the playlist doesn't seem to be working
    """
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

    ids, names = ids_for_playlist(chrono_list_file, movies, shows)
    jf_playlist = build_playlist(context.client, context.user_id, name)

    if len(ids) <= len(jf_playlist.videos):
        print(f"List has {len(ids)} videos which is not more than already in the playlist: {len(jf_playlist.videos)}")
        exit(3)

    new_ids = []
    new_indices = []
    new_names = []
    prev_index = 0
    for id_index, id in enumerate(ids):
        found = False
        for index, video in enumerate(jf_playlist.videos):
            if video.Id == id:
                prev_index = index
                found = True
                break
        if not found:
            new_ids.append(id)
            new_indices.append(prev_index + len(new_indices))
            new_names.append(names[id_index])

    if len(new_ids) != len(ids) - len(jf_playlist.videos):
        print(f"Expected {len(ids) - len(jf_playlist.videos)} new videos, but {len(new_ids)} would be new to the playlist")
        exit(4)

    add_to_jf_playlist(context.client, context.user_id, jf_playlist.Id, new_ids)

    for index, id in enumerate(new_ids):
        print(f"Moving {new_names[index]} to {new_indices[index]}")
        move_item_in_jf_playlist(context.client, jf_playlist.Id, id, new_indices[index])
            

if __name__ == "__main__":
    cli()
