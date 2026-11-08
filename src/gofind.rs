use std::{
	env,
	fs::{
		self,
		DirEntry,
	},
	path::PathBuf,
	process::ExitCode,
};

use clap::Parser;
use toolbox::{
	log,
	when,
};

/// Fuzzy-find a directory by name
#[derive(Parser)]
#[command(version, long_about = None)]
struct Cli
{
	/// Root directory to search
	#[arg(long, default_value = "/")]
	root: PathBuf,

	/// Directory names to exclude (repeatable)
	#[arg(long, value_name = "NAME")]
	exclude: Vec<String>,

	/// Path or directory name to find
	query: String,
}

enum SearchResult
{
	Found(PathBuf),
	NotFound,
	EmptyQuery,
}

enum SearchStep
{
	Found(PathBuf),
	Continue(Vec<PathBuf>),
	Stop,
}

struct DirCandidate
{
	name: String,
	path: PathBuf,
}

#[derive(PartialEq, Eq, PartialOrd, Ord)]
struct DirMatch
{
	rank: MatchRank,
	path: PathBuf,
}

#[derive(PartialEq, Eq, PartialOrd, Ord)]
enum MatchRank
{
	Exact,
	Prefix,
	Contains,
}

fn main() -> ExitCode
{
	use SearchResult::*;

	let cli = Cli::parse();

	match find_directory(cli.root, cli.exclude, cli.query) {
		Found(path) => {
			println!("{}", path.display());
			ExitCode::SUCCESS
		},

		NotFound => {
			log::error("No matching directory found!");
			ExitCode::FAILURE
		},

		EmptyQuery => {
			log::error("Search query is empty!");
			ExitCode::FAILURE
		},
	}
}

fn find_directory(root: PathBuf, exclude: Vec<String>, query: String) -> SearchResult
{
	use SearchResult::*;

	if query.is_empty() {
		return EmptyQuery;
	}

	if query.contains('/') {
		return Some(PathBuf::from(query))
			.filter(|it| it.is_dir())
			.map_or(NotFound, Found);
	}

	env::current_dir()
		.inspect_err(|_| log::warning("Could not access the current directory!"))
		.ok()
		.and_then(|current_dir| bfs_find(&query, current_dir, &exclude, false))
		.or_else(|| bfs_find(&query, root, &exclude, true))
		.map_or(NotFound, Found)
}

fn bfs_find(query: &str, root: PathBuf, exclude: &[String], recursive: bool) -> Option<PathBuf>
{
	use SearchStep::*;

	let mut level = vec![root];

	loop {
		match inspect_level(level, query, exclude, recursive) {
			Found(path) => return Some(path),
			Continue(next_level) => level = next_level,
			Stop => return None,
		}
	}
}

fn inspect_level(
	level: Vec<PathBuf>,
	query: &str,
	exclude: &[String],
	recursive: bool,
) -> SearchStep
{
	use SearchStep::*;

	let mut next_level = Vec::new();

	let best = flatten_subdirs(level)
		.filter_map(|entry| pick_candidate(entry, exclude))
		.inspect(|it| {
			if recursive {
				next_level.push(it.path.clone());
			}
		})
		.filter_map(|DirCandidate { name, path }| {
			match_rank(&name, query).map(|rank| DirMatch { rank, path })
		})
		.min();

	match best {
		Some(matched) => Found(matched.path),
		None if next_level.is_empty() => Stop,
		None => Continue(next_level),
	}
}

fn flatten_subdirs(level: Vec<PathBuf>) -> impl Iterator<Item = DirEntry>
{
	level
		.into_iter()
		.filter_map(|dir| fs::read_dir(dir).ok())
		.flatten()
		.filter_map(Result::ok)
		.filter(|entry| entry.file_type().is_ok_and(|ty| ty.is_dir()))
}

fn pick_candidate(entry: DirEntry, exclude: &[String]) -> Option<DirCandidate>
{
	let name = entry.file_name().to_string_lossy().into_owned();

	Some(name)
		.filter(|name| !name.starts_with('.'))
		.filter(|name| !exclude.iter().any(|it| name == it))
		.map(|name| DirCandidate {
			name,
			path: entry.path(),
		})
}

fn match_rank(name: &str, query: &str) -> Option<MatchRank>
{
	use MatchRank::*;

	let name = name.to_lowercase();
	let query = query.to_lowercase();

	when! {
		name == query => Some(Exact),
		name.starts_with(&query) => Some(Prefix),
		name.contains(&query) => Some(Contains),
		else => None,
	}
}
