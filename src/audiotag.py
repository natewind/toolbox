from __future__ import annotations

import subprocess
import tomllib

from pathlib import Path
from typing import Literal

import click
import tomlkit

from mutagen.flac import FLAC
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError
from pydantic_extra_types.language_code import LanguageName
from tomlkit.items import Table

LIST_SEPARATOR = ", "


LossyCodec = Literal["MP3", "Opus", "Vorbis", "Unknown"]

TuneType = Literal[
	"An dro",
	"Cochinchine",
	"Hanter-dro",
	"Jig",
	"Mazurka",
	"Norwegian",
	"Polka",
	"Reel",
	"Scottiche",
	"Waltz",
]

ExtraLanguage = Literal["Dovahzul", "Khuzdûl", "Old English", "Vocable"]


class SoundtrackIndex(BaseModel):
	volume: int = 0
	track: int = 0


class Lyrics(BaseModel):
	languages: list[LanguageName | ExtraLanguage] = Field(default_factory=list)
	authors: list[str] = Field(default_factory=list)
	text: str = ""

	@field_validator("authors", mode="after")
	@classmethod
	def validate_authors(cls, value: list[str]) -> list[str]:
		return list(filter(bool, value))

	@field_validator("text", mode="after")
	def validate_text(cls, value: str) -> str:
		return value.strip()


class Metadata(BaseModel):
	title: str = ""
	artist: str = ""
	original: LossyCodec | None = None
	tune_type: TuneType | None = None
	soundtrack: SoundtrackIndex | None = None
	lyrics: Lyrics | None = None

	@field_validator("original", "tune_type", mode="before")
	@classmethod
	def validate_literals(
		cls, value: str | LossyCodec | TuneType | None
	) -> str | LossyCodec | TuneType | None:
		return value or None

	@field_validator("soundtrack", mode="after")
	@classmethod
	def validate_soundtrack(
		cls, value: SoundtrackIndex | None
	) -> SoundtrackIndex | None:
		if value is None or value.volume == 0 and value.track == 0:
			return None

		return value

	@field_validator("lyrics", mode="after")
	@classmethod
	def validate_lyrics(cls, value: Lyrics | None) -> Lyrics | None:
		return (
			None
			if (
				value is None
				or len(value.languages) == 0
				and len(value.authors) == 0
				and value.text == ""
			)
			else value
		)

	# Manual validation to avoid a separate model for partial update
	def validate_required(self):
		missing: list[str] = []

		if self.title == "":
			missing.append("title")

		if self.artist == "":
			missing.append("artist")

		if self.soundtrack is not None and self.soundtrack.track == 0:
			missing.append("soundtrack.track")

		if (lyrics := self.lyrics) is not None:
			if len(lyrics.languages) == 0:
				missing.append("lyrics.languages")

			if lyrics.text == "":
				missing.append("lyrics.text")

		if len(missing) != 0:
			raise ValidationError.from_exception_data(
				title=f"Metadata",
				line_errors=[
					{
						"type": PydanticCustomError("missing", "Field required"),
						"loc": (field,),
						"input": self,
					}
					for field in missing
				],
			)

	@classmethod
	def from_toml(cls, file: Path, update: bool = False) -> Metadata:
		toml = tomllib.loads(file.read_text())
		metadata = cls.model_validate(toml)

		if not update:
			metadata.validate_required()

		return metadata

	def write(self, audio_path: str, update: bool = False):
		audio = FLAC(audio_path)

		if not update:
			audio.delete()
			audio.clear_pictures()

		if self.title != "":
			audio["TITLE"] = self.title

		if self.artist != "":
			audio["ARTIST"] = self.artist

		if self.tune_type is not None:
			audio["ALBUM"] = self.tune_type

		if (soundtrack := self.soundtrack) is not None:
			if soundtrack.volume != 0:
				audio["DISCNUMBER"] = str(soundtrack.volume)

			audio["TRACKNUMBER"] = str(soundtrack.track)

		if self.original is not None:
			audio["ORIGINALFORMAT"] = self.original

		if (lyrics := self.lyrics) is not None:
			if len(lyrics.languages) != 0:
				audio["LANGUAGE"] = LIST_SEPARATOR.join(lyrics.languages)

			if len(lyrics.authors) != 0:
				audio["LYRICIST"] = LIST_SEPARATOR.join(lyrics.authors)

			if lyrics.text != "":
				audio["LYRICS"] = lyrics.text

		audio.save()


def ascii_bold_blue(s: str) -> str:
	return f"\033[1;34m{s}\033[0m"


def read_tag(audio: FLAC, tag: str) -> str:
	return audio.get(tag, default=[""])[0]


def read_metadata(audio: FLAC) -> Table:
	metadata = tomlkit.table()

	metadata["title"] = read_tag(audio, "TITLE")
	metadata["artist"] = read_tag(audio, "ARTIST")
	metadata["original"] = read_tag(audio, "ORIGINALFORMAT")
	metadata["tune_type"] = read_tag(audio, "ALBUM")

	metadata.setdefault("soundtrack", {})["volume"] = int(
		read_tag(audio, "DISCNUMBER") or 0
	)

	metadata.setdefault("soundtrack", {})["track"] = int(
		read_tag(audio, "TRACKNUMBER") or 0
	)

	languages = read_tag(audio, "LANGUAGE")

	metadata.setdefault("lyrics", {})["languages"] = (
		[] if languages == "" else languages.split(LIST_SEPARATOR)
	)

	authors = read_tag(audio, "LYRICIST")

	metadata.setdefault("lyrics", {})["authors"] = (
		[] if authors == "" else authors.split(LIST_SEPARATOR)
	)

	text = read_tag(audio, "LYRICS")

	metadata.setdefault("lyrics", {})["text"] = tomlkit.string(
		"\n" if text == "" else f"\n{text}\n", multiline=True
	)

	return metadata


def remove_unused_blocks(audio_path: str):
	_ = subprocess.run(
		[
			"metaflac",
			"--remove",
			"--block-type=SEEKTABLE",
			audio_path,
		],
		check=True,
	)

	_ = subprocess.run(
		[
			"metaflac",
			"--remove",
			"--block-type=PADDING",
			"--dont-use-padding",
			audio_path,
		],
		check=True,
	)


def inspect_metadata(audio_path: str):
	_ = subprocess.run(
		[
			"metaflac",
			"--list",
			audio_path,
		],
		check=True,
	)

	print()


@click.group()
def main():
	"""
	Sync metadata between FLAC and TOML.
	Stores metadata in {name}.toml for every {name}.flac in the current directory.

	Only supports the following tags (TAG = toml_key):

	\b
	TITLE = title
	ARTIST = artist

	\b
	ORIGINALFORMAT = original (optional, for lossy only), possible values:
	    MP3
	    Opus
	    Vorbis
		Unknown

	(Albums are otherwise pointless, but many players display them in the UI,
	which makes them a convenient place to put the tune types for dancing playlists.)

	\b
	ALBUM = tune_type (optional), possible values:
	    An dro
	    Cochinchine
	    Hanter-dro
	    Jig
	    Mazurka
	    Norwegian
	    Polka
	    Reel
	    Scottiche
	    Waltz

	\b
	soundtrack (optional)
	    DISCNUMBER = volume (optional) != 0
	    TRACKNUMBER = track != 0

	\b
	lyrics
	    LANGUAGE = languages: []
	    LYRICIST = authors (optional): []
	    LYRICS = text
	"""


@main.command(help="Read metadata from FLAC and save to TOML.")
@click.argument("pattern", required=False, default="*.flac", nargs=-1)
def read(pattern: tuple[str]):
	target = Path(".")

	for filename in pattern:
		audio_path = target / filename
		audio = FLAC(audio_path)
		metadata = read_metadata(audio)
		toml_data = tomlkit.dumps(metadata)

		meta_file = target / f"{audio_path.stem}.toml"
		_ = meta_file.write_text(toml_data)


def save(update: bool):
	for meta_file in Path(".").glob("*.toml"):
		metadata = Metadata.from_toml(meta_file, update=update)
		audio_path = f"{meta_file.stem}.flac"
		metadata.write(audio_path, update=update)
		remove_unused_blocks(audio_path)

		print(ascii_bold_blue(audio_path))
		inspect_metadata(audio_path)


def info(label: str, message: str | None = None):
	message = "" if message is None else f" {message}"
	print(f"\033[1;34m{label}\033[0m")


@main.command(help="Update FLAC tags that are present in TOML.")
def update():
	save(update=True)


@main.command(help="Overwrite FLAC metadata from TOML.")
def write():
	save(update=False)
