from __future__ import annotations

from pathlib import Path

import click
import imagehash
import pillow_jxl  # pyright: ignore[reportUnusedImport]
import rustworkx as rx

from PIL import Image

FILE_EXTENSIONS = {".jxl", ".png", ".jpg", ".jpeg"}


class ClusteredImages:
	def __init__(self) -> None:
		pass


def image_paths(root: Path, recursive: bool) -> list[Path]:
	paths = root.rglob("*") if recursive else root.iterdir()
	filtered = (path for path in paths if path.suffix.lower() in FILE_EXTENSIONS)
	return list(filtered)


def cluster_duplicates(
	files: list[Path],
	hashes: dict[Path, imagehash.ImageHash],
	threshold: int,
) -> list[list[Path]]:
	graph = rx.PyGraph()
	_ = graph.add_nodes_from(files)

	nodes = {file: index for index, file in enumerate(files)}

	for index, left in enumerate(files):
		left_hash = hashes[left]

		_ = graph.add_edges_from(
			(nodes[left], nodes[right], None)
			for right in files[index + 1 :]
			if left_hash - hashes[right] <= threshold
		)

	return [
		[graph[node] for node in cluster]
		for cluster in rx.connected_components(graph)
		if len(cluster) > 1
	]


def serialize_paths(paths: list[Path]) -> str:
	return "\n".join(path.as_posix() for path in paths)


def serialize_groups(groups: list[list[Path]]) -> str:
	return "\n\n".join(serialize_paths(group) for group in groups)


@click.command(
	help=(
		"Find visually similar images in the current directory.\n\n"
		"Supports JPEG XL, PNG and JPEG."
	)
)
@click.option(
	"-r",
	"--recursive",
	is_flag=True,
	default=False,
	help="Scan subdirectories recursively.",
)
@click.option(
	"--threshold",
	type=int,
	default=6,
	show_default=True,
	help="Hamming distance threshold.",
)
def main(recursive: bool, threshold: int):
	root = Path(".")
	files = image_paths(root, recursive)

	hashes = {file: imagehash.phash(Image.open(file)) for file in files}
	groups = cluster_duplicates(files, hashes, threshold)

	print(serialize_groups(groups))


if __name__ == "__main__":
	main()
