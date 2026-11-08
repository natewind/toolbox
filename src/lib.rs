pub mod log
{
	use owo_colors::OwoColorize;

	pub fn warning(text: &str) { eprintln!("{} {text}", "Warning:".yellow().bold()) }
	pub fn error(text: &str) { eprintln!("{} {text}", "Error:".red().bold()) }
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
