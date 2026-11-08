# Toolbox

A collection of useful command-line tools.

To install a single utility:

```bash
cargo install --git https://github.com/natewind/toolbox --bin <NAME>
```

To install everything:

```bash
cargo install --git https://github.com/natewind/toolbox --bins
```

## `audiotag`

*Documentation pending the Rust rewrite.*

## `gofind`

Fuzzy-find a directory by name.

### Usage

```bash
gofind [OPTIONS] <QUERY>
```

To replace `cd` for terminal navigation:

```bash
go()
{
	local dir

	dir=$(gofind \
		--root <ROOT> \
		--exclude <NAME> \
		"$*" || return
	)

	cd -- "$dir" && list
}
```

### Arguments

* `<QUERY>` — Path or directory name to find

### Options

* `--root <ROOT>` — Root directory to search (default: `/`)
* `--exclude <NAME>` — A directory name to exclude (repeatable)

### Bevaviour

Directories are checked in the following order:

1. Exact path if the query conatins `/`
2. Immediate subdirectories of the current directory
3. Subdirectories of `<ROOT>`, using breadth-first search

Dot-directories are skipped, except inside an exact path.

Matching is case-insensitive, with the following priority:

1. Exact match
2. Prefixed by the query
3. Containing the query

### Errors

* Search query is empty
* No matching directory found

## `imgdupes`

*Documentation pending the Rust rewrite.*

## `list`

List directory contents.

### Usage

```bash
list [OPTIONS] [TARGET]
```

### Arguments

* `[TARGET]` — Target directory (default: `.`)

### Options

* `-a`, `--all` — Show hidden files

### Behaviour

* Directories are listed first and displayed in bold blue text
* Entries are sorted case-sensitively

Example output:

```
toolbox
├── src
├── target
├── Cargo.lock
├── Cargo.toml
├── LICENSE.md
├── README.md
╰── rustfmt.toml
```

## `vcard`

*Documentation pending the Rust rewrite.*
