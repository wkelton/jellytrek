from typing import Any, Dict, List, Optional, Union

from jellyfin_api_client import Client
from jellyfin_api_client.api.items import get_items_by_user_id
from jellyfin_api_client.api.playlists import get_playlist_items, create_playlist, add_to_playlist, move_item
from jellyfin_api_client.models.base_item_dto_query_result import BaseItemDtoQueryResult
from jellyfin_api_client.models.create_playlist_dto import CreatePlaylistDto


class JFItem:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Video(JFItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class Season(JFItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._season_number = -2
        self.videos : List[Video] = []

    @property
    def season_number(self):
        if self._season_number == -2:
            if hasattr(self, "IndexNumber") and "Season {}".format(self.IndexNumber) == self.Name:
                self._season_number = self.IndexNumber
            else:
                self._season_number = -1
        return self._season_number


class Series(JFItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seasons : Dict[str, Season] = {}


class Library(JFItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jf_items : Dict[str, Union[Series, Video]] = {}

    def populate_tree_from_items(self, items: List[Dict[Any, Any]]):
        videos = []
        seasons = []
        series = []
        other_items = []

        for item in items:
            if "IsFolder" in item and item["IsFolder"]:
                if "Type" in item and item["Type"] == "Series":
                    series.append(Series(**item))
                elif "Type" in item and item["Type"] == "Season":
                    seasons.append(Season(**item))
            elif "MediaType" in item and item["MediaType"] == "Video":
                videos.append(Video(**item))
            else:
                other_items.append(JFItem(**item))

        for ser in series:
            self.jf_items[ser.Id] = ser

        parentless_seasons = []

        for season in seasons:
            if season.SeriesId in self.jf_items:
                self.jf_items[season.SeriesId].seasons[season.Id] = season
            else:
                parentless_seasons.append(season)

        for video in videos:
            for _, series in self.jf_items.items():
                if hasattr(video, "SeasonId") and video.SeasonId in series.seasons:
                    series.seasons[video.SeasonId].videos.append(video)
                    break
            else:
                self.jf_items[video.Id] = video


class VideoPlaylist(JFItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.videos : List[Video] = []

    def populate_from_items(self, items: List[Dict[Any, Any]]):
        for item in items:
            self.videos.append(Video(**item))


def parse_get_items(result: Optional[BaseItemDtoQueryResult]):
    if result:
        result_dict = result.to_dict()
        if "Items" in result_dict:
            return result_dict["Items"]
        return None
    else:
        return None


def get_libraries(client: Client, user_id: str):
    result = get_items_by_user_id.sync(client=client, user_id=user_id)
    return parse_get_items(result)


def get_items_for_library(client: Client, user_id: str, library_id: str):
    result = get_items_by_user_id.sync(client=client, user_id=user_id, parent_id=library_id, recursive=True)
    return parse_get_items(result)


def get_playlists_library(client: Client, user_id: str):
    result = get_items_by_user_id.sync(client=client, user_id=user_id)
    for library in parse_get_items(result):
        if library["Name"] == "Playlists":
            return library


def get_items_for_playlist(client: Client, user_id: str, playlist_id: str):
    result = get_playlist_items.sync(client=client, user_id=user_id, playlist_id=playlist_id)
    return parse_get_items(result)


def build_library(client: Client, user_id: str, library: Library):
    raw_items = get_items_for_library(client, user_id, library.Id)
    if raw_items:
        library.populate_tree_from_items(raw_items)
        return True
    return False


def build_libraries(client: Client, user_id: str, populate: bool = False):
    libraries = []
    for raw_library in get_libraries(client, user_id):
        library = Library(**raw_library)
        libraries.append(library)
        if populate:
            library.populate_tree_from_items(client, user_id, library.Id)
    return libraries


def build_playlist(client: Client, user_id: str, name: str):
    playlists = get_playlists_library(client, user_id)
    for raw_playlist in get_items_for_library(client, user_id, playlists["Id"]):
        if raw_playlist["Name"] == name:
            playlist = VideoPlaylist(**raw_playlist)
            playlist.populate_from_items(get_items_for_playlist(client, user_id, playlist.Id))
            return playlist


def create_jf_playlist(client: Client, user_id: str, name: str, ids: List[str]):
    create_playlist.sync(client=client, json_body=CreatePlaylistDto(name=name, user_id=user_id, ids=ids))


def add_to_jf_playlist(client: Client, user_id: str, playlist_id: str, ids: List[str]):
    add_to_playlist.sync_detailed(client=client, user_id=user_id, playlist_id=playlist_id, ids=ids)


def move_item_in_jf_playlist(client: Client, playlist_id: str, id: str, new_index: int):
    move_item.sync_detailed(client=client, playlist_id=playlist_id, item_id=id, new_index=new_index)