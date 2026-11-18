//! Tiny per-folder bootstrap. The shared versioned runtime owns the Qt UI.
#![cfg_attr(target_os = "windows", windows_subsystem = "windows")]
use std::{env, fs, path::Path, process::Command};

fn launch() -> Result<(), String> {
    let exe = env::current_exe().map_err(|e| e.to_string())?;
    let folder = exe.parent().ok_or("Cannot locate the game folder")?;
    let descriptor = fs::read_to_string(folder.join("launcher-runtime.txt"))
        .map_err(|_| "Cannot find launcher-runtime.txt. Keep the launcher in its game folder.".to_string())?;
    let lines: Vec<&str> = descriptor.lines().collect();
    if lines.len() < 3 || lines[0] != "ORRE-LAUNCHER-1" {
        return Err("Invalid launcher runtime descriptor.".into());
    }
    let runtime = Path::new(lines[1]);
    let working = Path::new(lines[2]);
    if !runtime.is_absolute() || !runtime.is_file() || !working.is_absolute() || !working.is_dir() {
        return Err("The shared Orre runtime could not be found. Open this game folder from Pokémon Orre Randomizer to repair its launcher.".into());
    }
    let mut command = Command::new(runtime);
    command.args(&lines[3..]).arg("--play-folder").arg(folder.join("game.json"));
    command.current_dir(working);
    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }
    command.spawn().map_err(|e| format!("Cannot start the launcher: {e}"))?;
    Ok(())
}

#[cfg(target_os = "windows")]
fn show_error(message: &str) {
    #[link(name = "user32")]
    unsafe extern "system" {
        fn MessageBoxW(window: *mut std::ffi::c_void, text: *const u16, title: *const u16, flags: u32) -> i32;
    }
    let text: Vec<u16> = message.encode_utf16().chain(Some(0)).collect();
    let title: Vec<u16> = "Pokémon Orre Randomizer".encode_utf16().chain(Some(0)).collect();
    unsafe { MessageBoxW(std::ptr::null_mut(), text.as_ptr(), title.as_ptr(), 0x10); }
}

#[cfg(not(target_os = "windows"))]
fn show_error(message: &str) { eprintln!("{message}"); }

fn main() {
    if let Err(error) = launch() {
        show_error(&error);
        std::process::exit(1);
    }
}
