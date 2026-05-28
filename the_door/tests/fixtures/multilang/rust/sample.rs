/// Greet someone by name.
/// Returns the formatted string.
#[derive(Debug)]
pub struct Greeter;

impl Greeter {
    /// Build the greeting.
    pub fn greet(&self, name: &str, times: i32) -> String {
        format!("hello {}", name)
    }
}
