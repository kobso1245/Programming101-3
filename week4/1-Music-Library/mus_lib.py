import random
from datetime import timedelta
from tabulate import tabulate
import os
import json
from time import sleep
from mutagen.mp3 import MP3
from subprocess import Popen, PIPE


class Song:
    def __init__(self, title, artist, album, length, path=""):
        self.__title = title
        self.__artist = artist
        self.__album = album
        self.__length = length
        self.__path = path

    def __str__(self):
        return "{} - {} from {} - {}".format(self.__artist, self.__title,
                                             self.__album, self.__length)

    def title(self):
        return self.__title

    def artist(self):
        return self.__artist

    def album(self):
        return self.__album

    def path(self):
        return self.__path

    def length(self, seconds=False):
        if seconds:
            return self.__length
        return timedelta(seconds=self.__length, microseconds=0, milliseconds=0)

    def __eq__(self, other):
        return (self.__title == other.title() and
                self.__artist == other.artist() and
                self.__album == other.album() and
                self.__length == other.length(seconds=False))

    def __hash__(self):
        return hash(str(self.__title) + str(self.__artist) +
                    str(self.__album) + str(self.__length))


class Playlist:
    def __init__(self, name, repeat=False, shuffle=False):
        self.__name = name
        self.__repeat = repeat
        self.__shuffle = shuffle
        self.__songs = []
        self.__curr_song = 0
        self.__passed = set()
        self.__length = 0
        self.curr_songs = set()

    def add_song(self, other):
        self.__songs.append(other)
        self.__length += 1

    def name(self):
        return self.__name

    def curr_song(self):
        return self.__curr_song

    def get_passed(self):
        return self.__passed

    def remove_song(self, other):
        self.__songs.remove(other)

    def add_songs(self, songs):
        if type(songs) is Playlist:
            lst_songs = songs.show_songs()
            for song in lst_songs:
                self.add_song(song)
        else:
            for song in songs:
                self.add_song(song)

    def show_songs(self):
        return self.__songs

    def get_shuffle(self):
        return self.__shuffle

    def get_repeat(self):
        return self.__repeat

    def total_length(self, nice=False):
        time = sum([song.length(seconds=True) for song in self.__songs])
        if nice:
            return timedelta(seconds=time)
        return time

    def artists(self):
        artsts = set([song.artist() for song in self.__songs])
        return {artist: sum([1 for elem in self.__songs if elem.artist() == artist])
                for artist in artsts}

    def flush(self):
        self.__curr_song = 0

    def next_song(self):
        if self.curr_songs == set():
            self.curr_songs = set(range(len(self.__songs)))

        if self.get_shuffle():
            to_choose_from = list(self.curr_songs.difference(self.__passed))
            if to_choose_from == []:
                curr = random.choice(list(self.curr_songs))
                return self.__songs[curr]
            else:
                curr = random.choice(to_choose_from)
                self.__passed.add(curr)
                return self.__songs[curr]

        if not self.get_repeat():
            if self.__curr_song == self.__length:
                raise Exception
            else:
                self.__curr_song += 1
                return self.__songs[self.__curr_song - 1]

        if self.get_repeat():
            if self.__curr_song == len(self.__songs):
                self.__curr_song = 1
                return self.__songs[0]
            else:
                self.__curr_song += 1
                return self.__songs[self.__curr_song - 1]

        else:
            raise Exception

    def start(self):
        p = play(self.__songs[0].path())
        print("Please write <next> for next song: ")
        npt = input()
        while npt != 'next':
            npt = input("Please write <next> for next song: ")
        stop(p)
        p = play(self.next_song().path())
        sleep(100)

    def pprint_playlist(self):
        i = 1
        out_lst = []
        for elem in self.__songs:
            out_lst.append([i, elem.artist(), elem.title(), elem.length()])
            i = i + 1

        print(tabulate(out_lst, headers=["Number", "Artist", "Song", "Length"],
                       tablefmt="grid"))

    def save(self, path=""):
        artists = {song.artist(): [] for song in self.__songs}
        for song in self.__songs:
            artists[song.artist()].append(",".join((song.title(),
                                                    song.album(),
                                                    song.length(),
                                                    song.path())))
        if path == "":
            fl = open(self.__name.replace(" ", "-")+'.json', "w")
        else:
            fl = open(path+"/"+self.__name.replace(" ", "-") + ".json", "w")
        json.dump(artists, fl, indent=4)
        fl.close()

    @staticmethod
    def load(path):
        dct = []
        with open(path, "r") as f:
            dct = json.load(f)

        if path.count("/"):
            pl_name = " ".join(path.split('/')[-1].split('-')).split('.')[0]
        else:
            pl_name = " ".join(path.split('-')).split('.')[0]

        playlst = Playlist(name=pl_name)
        for artst in dct:
            for sng in dct[artst]:
                names = sng.split(',')
                playlst.add_song(Song(title=names[0], artist=artst,
                                      album=names[1], length=names[2],
                                      path=names[3]))
        return playlst


class MusicCrawler:
    def __init__(self, name, path):
        self.__path = path
        self.__playlst = Playlist(name)

    def gen(self, path):
        try:
            dirs = os.listdir(path)
        except FileNotFoundError as error:
            print(error)

        for curr_dir in dirs:
            pth = path + '/' + curr_dir
            if os.path.isfile(pth):
                full_name = os.path.splitext(pth)
                if full_name[1] == '.mp3':
                        audio = MP3(pth)
                        self.__playlst.add_song(Song(audio['TIT2'],
                                                     audio['TPE1'],
                                                     audio['TALB'],
                                                     audio.info.length,
                                                     pth))
            else:
                self.gen(pth)

    def generate_playlist(self):
        self.gen(self.__path)
        return self.__playlst


class MusicPlayer:
    def __init__(self):
        self.__curr_proc = 0
        self.__playing = 0
        self.__playlists = []
        self.__all_songs = Playlist("All songs")
        self.__curr_playlist = self.__all_songs

        try:
            fl = open("config", "r")
            lst_of_not_done_paths = fl.readlines()
            lst_of_paths = [path[:-1] for path in lst_of_not_done_paths]
            self.first_time(lst_of_paths)
            fl.close()

        except FileNotFoundError:
            inp = input("""Please write all the paths where your music is stored\
with ',' between them: """)
            lst_of_paths = inp.split(',')
            self.first_time(lst_of_paths)
            to_be_saved = [path+'\n' for path in lst_of_paths]
            fl = open("config", "w")
            fl.writelines(to_be_saved)
            fl.close()
        print("Banana Player v42.0. Write <h> for help.")
        inp = 1
        while inp:
            inp = input("Tell me what to do, master..: ")
            if inp == "sh":
                self.__curr_playlist.pprint_playlist()

            if inp == "sh -p":
                print(tabulate([(playlist.name(),
                                 playlist.total_length(nice=True),
                                 playlist.get_shuffle(),
                                 playlist.get_repeat()) for playlist in self.__playlists],
                               headers=["Name", "Length", "Shuffle", "Repeat"],
                               tablefmt="grid"))

            if "ch" in inp:
                plst = int(inp.split(" ")[1]) - 1
                self.__curr_playlist = self.__playlists[plst]
                self.__playing = self.__curr_playlist.next_song()
                self.__curr_proc = 0

            if "pl" in inp and not self.__curr_proc:
                if inp != "pl":
                    sng_n = int(inp.split(" ")[1] - 1)
                    self.__playing = self.__curr_playlist.show_songs()[sng_n]
                self.__curr_proc = play(self.__playing.path())
                print(tabulate([[self.__playing.artist(),
                                 self.__playing.title(),
                                 self.__playing.length(seconds=False)]],
                               headers=["Artist", "Song", "Length"],
                               tablefmt="grid"))

            if inp == "s" and self.__curr_proc:
                stop(self.__curr_proc)
                self.__curr_proc = 0

            if inp == "n":
                try:
                    if self.__curr_proc:
                        stop(self.__curr_proc)
                    self.__playing = self.__curr_playlist.next_song()
                    print(tabulate([[self.__playing.artist(),
                                     self.__playing.title(),
                                     self.__playing.length(seconds=False)]],
                                   headers=["Artist", "Song", "Length"],
                                   tablefmt="grid"))
                    self.__curr_proc = play(self.__playing.path())
                except Exception as data:
                    print(data)
                    print("End of playlist!")
                    stop(self.__curr_proc)
                    self.__playing = self.__curr_playlist.show_songs()[0]
                    self.__curr_playlist.flush()

            if inp == "c":
                print(tabulate([[self.__playing.artist(),
                                 self.__playing.title(),
                                 self.__playing.length(seconds=False)]],
                               headers=["Artist", "Song", "Length"],
                               tablefmt="grid"))

            if inp == "h":
                print(tabulate([["sh [-p]", "Shows all songs in the playlist. [-p] shows all playlists"],
                                ["pl [song number]", "Starts a song."],
                                ["s", "Stops the currently played song"],
                                ["n", "Starts the next song."],
                                ["c", "Current song"],
                                ["ch <playlist number>", "Change the currently played playlist"],
                                ["add", "Adds a new playlist"],
                                ["kill a panda", "No, you can't kill pandas...not today"]],
                               headers=["Option", "What it does"]))

            if inp == "add":
                name = input("Please select name of the playlist: ")
                shuf = input("""Please write <Yes> if you want shuffle\
and <No> if you don't: """)
                rep = input("""Please write <Yes> if you want repeat\
and <No> if you don't: """)

                if shuf.lower() == "yes" and rep.lower == "yes":
                    print("You cant have both shuffle and repeat on")

                if shuf.lower() == "yes":
                    shuf = True
                else:
                    shuf = False

                if "yes" in rep.lower():
                    rep = True
                else:
                    rep = False
                playlist_for_adding = Playlist(name, shuffle=shuf, repeat=rep)
                inp = input("""Please write the numbers of the songs that you \
want to add and put ',' between them: """)

                lst = inp.split(',')
                for elem in lst:
                    playlist_for_adding.add_song(self.__all_songs.show_songs()[int(elem) - 1])
                self.__playlists.append(playlist_for_adding)

                print("All done!")

    def add_playlist(self, playlist):
        self.__playlist.append(playlist)

    def first_time(self, lst_of_paths):
            for path in lst_of_paths:
                crw = MusicCrawler("All songs", path)
                self.__curr_playlist.add_songs(crw.generate_playlist())
            self.__all_songs = self.__curr_playlist
            self.__playlists.append(self.__all_songs)
            self.__playing = self.__playlists[0].next_song()


def play(mp3Path):
    p = Popen(["mpg123", mp3Path], stdout=PIPE, stderr=PIPE)
    return p


def stop(process):
    process.kill()


if __name__ == "__main__":
    music_pl = MusicPlayer()
