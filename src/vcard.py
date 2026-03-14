from __future__ import annotations

import base64
import re

from datetime import date, datetime
from fnmatch import fnmatch
from functools import cached_property
from pathlib import Path
from typing import ClassVar, Literal, override

import click

from pydantic import (
	BaseModel,
	EmailStr,
	Field,
	RootModel,
	computed_field,
	field_validator,
)
from pydantic_extra_types.country import CountryAlpha2
from pydantic_extra_types.phone_numbers import PhoneNumber

CONTACTS = "contacts.json"
PHOTOS = "photos/{id}.png"

Platform = Literal["instagram", "telegram", "vk"]
Category = Literal["Crushes", "Family", "Friends"]
PhoneNumbers = dict[CountryAlpha2, PhoneNumber]


def kebab_case(s: str) -> str:
	return s.strip().lower().replace(" ", "-")


def format_e164(number: PhoneNumber) -> PhoneNumber:
	without_prefix = number.removeprefix("tel:")
	return PhoneNumber(re.sub(r"[()\- ]", "", without_prefix))


class Profile(BaseModel):
	id: int
	handle: str

	BASE_URL: ClassVar[dict[Platform, str]] = {
		"instagram": "instagram.com",
		"telegram": "t.me",
		"vk": "vk.com",
	}

	def link(self, platform: Platform) -> str:
		return f"{Profile.BASE_URL[platform]}/{self.handle}"


class Card(BaseModel):
	first_name: str
	last_name: str | None = None
	birthday: date
	email: EmailStr | None = None
	profiles: dict[Platform, Profile] = {}
	phone_numbers: PhoneNumbers = {}
	categories: set[Category] = Field(min_length=1)

	@override
	def __eq__(self, other: object) -> bool:
		return isinstance(other, Card) and self.id == other.id

	@override
	def __hash__(self):
		return hash(self.id)

	@field_validator("birthday", mode="before")
	def validate_birthday(cls, value: str | date) -> date:
		return (
			datetime.strptime(value, "%d %b %Y").date()
			if isinstance(value, str)
			else value
		)

	@computed_field
	@cached_property
	def id(self) -> str:
		last_name = f" {self.last_name}" if self.last_name is not None else ""
		return kebab_case(self.first_name + last_name)

	@computed_field
	@cached_property
	def photo(self) -> bytes:
		path = Path(PHOTOS.format(id=self.id))
		return path.read_bytes()

	def into_vcf(self) -> str:
		lines: list[str] = [
			"BEGIN:VCARD",
			"VERSION:4.0",
			f"N:{self.last_name or ''};{self.first_name};;;",
			f"BDAY:{self.birthday.strftime('%Y%m%d')}",
		]

		if self.email is not None:
			lines.append(f"EMAIL:{self.email}")

		profiles = [
			f"URL:{profile.link(platform)}"
			for platform, profile in self.profiles.items()
		]

		lines.extend(profiles)

		phone_numbers = [
			f"TEL;TYPE={country}:{format_e164(number)}"
			for country, number in sorted(self.phone_numbers.items())
		]

		lines.extend(phone_numbers)

		categories = ",".join(self.categories)
		lines.append(f"CATEGORIES:{categories}")

		photo = base64.b64encode(self.photo).decode("ascii")
		lines.append(f"PHOTO:data:image/png;base64,{photo}")

		lines.append("END:VCARD\n")
		return "\n".join(lines)


class Contacts(RootModel[list[Card]]):
	@property
	def id(self) -> str:
		return "contacts"

	@override
	def __eq__(self, other: object) -> bool:
		return isinstance(other, Contacts) and self.id == other.id

	@override
	def __hash__(self):
		return hash(self.id)

	def into_vcf(self) -> str:
		return "\n".join(card.into_vcf() for card in self.root)

	def match_or_all(self, patterns: list[str]) -> set[Card | Contacts]:
		return {
			it
			for it in self.root
			for pattern in map(kebab_case, patterns)
			if fnmatch(it.id, pattern)
		} or {self}


@click.command(
	help=(
		"Convert contacts from JSON and PNG to a vCard. "
		"Uses contacts.json and photos/*.png in the current directory. "
		"Accepts zero or more patterns to match contact names. Includes all by default."
	)
)
@click.option(
	"-o",
	"--output",
	type=click.Path(exists=True, path_type=Path),
	default="/media/Data/Downloads",
	show_default=True,
	help="Output directory.",
)
@click.argument("patterns", nargs=-1)
def main(patterns: list[str], output: Path):
	contacts = Contacts.model_validate_json(Path(CONTACTS).read_text())

	for card in contacts.match_or_all(patterns):
		output_file = output / f"{card.id}.vcf"
		_ = output_file.write_text(card.into_vcf(), encoding="utf-8")
