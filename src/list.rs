use std::{
	cmp,
	fmt,
	fs,
	io,
	path::{
		Path,
		PathBuf,
	},
	process::ExitCode,
};

use clap::Parser;
use itertools::{
	Itertools,
	Position,
};
use owo_colors::OwoColorize;
use toolbox::{
	log,
	when,
};

/// List directory contents
#[derive(Parser)]
#[command(version, long_about = None)]
struct Cli
{
	/// Show hidden files
	#[arg(short, long)]
	all: bool,

	/// Target directory
	#[arg(default_value = ".")]
	target: PathBuf,
}

#[derive(PartialEq, Eq)]
struct ListEntry
{
	name: String,
	is_dir: bool,
}

impl Ord for ListEntry
{
	fn cmp(&self, other: &Self) -> cmp::Ordering
	{
		other
			.is_dir
			.cmp(&self.is_dir)
			.then_with(|| self.name.cmp(&other.name))
	}
}

impl PartialOrd for ListEntry
{
	fn partial_cmp(&self, other: &Self) -> Option<cmp::Ordering> { Some(self.cmp(other)) }
}

impl TryFrom<fs::DirEntry> for ListEntry
{
	type Error = io::Error;

	fn try_from(entry: fs::DirEntry) -> Result<Self, Self::Error>
	{
		Ok(Self {
			name: entry.file_name().to_string_lossy().into_owned(),
			is_dir: entry.file_type()?.is_dir(),
		})
	}
}

impl fmt::Display for ListEntry
{
	fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result
	{
		when! {
			self.is_dir => write!(f, "{}", self.name.blue().bold()),
			else => write!(f, "{}", self.name)
		}
	}
}

impl ListEntry
{
	fn display_branch(&self, position: Position) -> String
	{
		let branch = when! {
			position.is_last() => "╰──",
			else => "├──"
		};

		format!("{branch} {self}")
	}
}

fn main() -> ExitCode
{
	let cli = Cli::parse();

	match list_dir(cli.target, cli.all) {
		Ok(()) => ExitCode::SUCCESS,

		Err(err) => {
			log::error(err);
			ExitCode::FAILURE
		},
	}
}

fn list_dir(target: PathBuf, all: bool) -> io::Result<()>
{
	let target = target.canonicalize()?;

	let name = target
		.file_name()
		.unwrap_or(target.as_os_str())
		.to_string_lossy();

	println!("{}", name.blue().bold());
	list_contents(&target, all)
}

fn list_contents(path: &Path, all: bool) -> io::Result<()>
{
	let mut entries: Vec<_> = fs::read_dir(path)?
		.map(|entry| entry.and_then(ListEntry::try_from))
		.collect::<io::Result<_>>()?;

	if !all {
		entries.retain(|it| !it.name.starts_with('.'));
	}

	entries.sort();

	entries
		.into_iter()
		.with_position()
		.map(|(position, entry)| entry.display_branch(position))
		.for_each(|line| println!("{line}"));

	Ok(())
}
