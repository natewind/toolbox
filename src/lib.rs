pub mod log
{
	use std::fmt::Display;

	use owo_colors::OwoColorize;

	pub fn warning(text: impl Display) { eprintln!("{} {text}", "Warning:".yellow().bold()) }
	pub fn error(text: impl Display) { eprintln!("{} {text}", "Error:".red().bold()) }
}

#[macro_export]
macro_rules! when {
	(
		$( $condition:expr => $result:expr, )*
		else => $default:expr $(,)?
	) => {{
		$( if $condition { $result } else )*
		{ $default }
	}};
}
