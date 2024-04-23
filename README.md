# jellytrek

Script for creating playlist in Jellyfin of Star Trek in chronological order.

## Create playlist in Jellyfin of Star Trek in chronological order

### Login

Run `login.py --url "your-url" --user "your-user-name" --password "your-password"`. This creates a `login.json` file that the other script uses to authentication.

### Chronological list

See [The Ultimate Chronological Star Trek Viewing Guide](https://www.startrekviewingguide.com/).

Create a file that is `|` deliminated fields of the Star Trek content you want in your playlist. Check the `data` directory for a script to build this from the above website.

### Check your Jellyfin videos

Run `chrono-trek.py check-videos path/to/list` to see if this script can find all the videos from the list in your Jellyfin instance. This may require tedious changes to your Jellyfin episodes or video file names to get everything to be correct. Ensure your episodes are actually registered correctly in Jellyfin. This script was written against a Jellyfin instance that has all its episodes correctly detected and named by IMDB.

### Create playlist

Run `chrono-trek.py create-playlist path/to/list "Playlist Name"`. Check your Jellyfin instance for the new playlist.

### Check playlist

Run `chrono-trek.py check-playlist path/to/list "Playlist Name"`. This will print any mismatches.

### Update playlist

This doesn't appear to work correctly. It will add new videos. But it will not place them in the correct place.

Reordering or removing is not supported.

Run `chrono-trek.py update-playlist path/to/list "Playlist Name"`.

## Requirements
- Python 3
- [jellyfin-api-client](https://github.com/GeoffreyCoulaud/jellyfin-api-client)
- click
