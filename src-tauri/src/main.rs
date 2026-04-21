// Project Beta — Tauri 2.x Main Entry
// Spawns the Python sidecar, waits for /health, passes port to frontend.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            sidecar::spawn(app.handle().clone())?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}
