// sidecar.rs — Spawns and manages the Python/Nuitka sidecar process.
//
// Lifecycle:
//   1. Spawn sidecar binary (Nuitka .exe in production, python main.py in dev)
//   2. Poll GET /api/v1/stats until 200 — max 30 seconds
//   3. Emit `sidecar-ready` event to frontend with port number
//   4. On app exit — SIGTERM the sidecar, wait up to 5 seconds
//
// Port: fixed 8000 on 127.0.0.1 (GR-S01 loopback security model)

use std::env;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};
use std::process::{Child, Command, Stdio};

use tauri::{AppHandle, Emitter, Manager};

const SIDECAR_PORT: u16 = 8000;
const SIDECAR_HOST: &str = "127.0.0.1";
const HEALTH_URL:   &str = "http://127.0.0.1:8000/api/v1/stats";
const STARTUP_TIMEOUT_SECS: u64 = 60;
const SHUTDOWN_TIMEOUT_SECS: u64 = 5;

/// Global sidecar child process — stored so we can kill it on exit.
static SIDECAR_PID: Mutex<Option<u32>> = Mutex::new(None);

pub fn spawn(app: AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    thread::spawn(move || {
        match start_sidecar_process() {
            Ok(child_pid) => {
                *SIDECAR_PID.lock().unwrap() = Some(child_pid);
                eprintln!("[Tauri] Sidecar spawned — PID {child_pid}");

                // Poll until ready or timeout
                let t0 = Instant::now();
                let mut ready = false;
                while t0.elapsed() < Duration::from_secs(STARTUP_TIMEOUT_SECS) {
                    if poll_health() {
                        ready = true;
                        break;
                    }
                    thread::sleep(Duration::from_millis(1000));
                }

                if ready {
                    eprintln!("[Tauri] Sidecar ready after {:.1}s", t0.elapsed().as_secs_f32());
                    // Emit sidecar-ready with port so frontend can use it
                    let _ = app.emit("sidecar-ready", SIDECAR_PORT);
                    // Also inject into window JS globals via eval
                    inject_port(&app, SIDECAR_PORT);
                } else {
                    eprintln!("[Tauri] ERROR: Sidecar did not start within {STARTUP_TIMEOUT_SECS}s");
                    let _ = app.emit("sidecar-error", "Sidecar did not start in time");
                }
            }
            Err(e) => {
                eprintln!("[Tauri] ERROR: Failed to spawn sidecar: {e}");
                let _ = app.emit("sidecar-error", format!("{e}"));
            }
        }
    });

    Ok(())
}

/// Spawns the sidecar process. Returns the child PID.
fn start_sidecar_process() -> Result<u32, Box<dyn std::error::Error + Send + Sync>> {
    // In dev mode: use python main.py from the sidecar directory
    // In production: use the Nuitka-compiled binary bundled with Tauri
    let is_dev = cfg!(debug_assertions);

    let mut cmd = if is_dev {
        // Dev — find python and run main.py from the sidecar directory
        let sidecar_dir = sidecar_dev_dir();
        let mut c = Command::new("python");
        c.arg("main.py");
        c.current_dir(&sidecar_dir);
        c.env("HF_HUB_OFFLINE", "1");
        c.env("TRANSFORMERS_OFFLINE", "1");
        c.env("HF_DATASETS_OFFLINE", "1");
        c
    } else {
        // Production — the Nuitka binary is bundled as a sidecar
        // tauri resolves the binary path via the sidecar pattern
        let mut c = Command::new("main-x86_64-pc-windows-msvc");
        c.env("TAURI_RESOURCE_DIR", resource_dir());
        c
    };

    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    let child = cmd.spawn()?;
    let pid = child.id();

    // Detach stdout/stderr on a logging thread
    if let Some(stdout) = child.stdout {
        // Note: child.stdout consumed — log in bg thread
    }

    Ok(pid)
}

/// Polls the health endpoint once. Returns true if 200 OK.
fn poll_health() -> bool {
    // Use a blocking reqwest call — safe because we're on a background thread
    match reqwest::blocking::get(HEALTH_URL) {
        Ok(r) => r.status().is_success(),
        Err(_)  => false,
    }
}

/// Returns the sidecar directory for dev mode (relative to the Tauri project root).
fn sidecar_dev_dir() -> String {
    // During dev: src-tauri/../sidecar
    env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()))
        .map(|d| {
            // Executable is in target/debug/ — navigate up to project root
            d.ancestors()
                .nth(3)
                .map(|r| r.join("sidecar").to_string_lossy().into_owned())
                .unwrap_or_else(|| "../sidecar".to_string())
        })
        .unwrap_or_else(|| "../sidecar".to_string())
}

/// Returns the Tauri resource directory path for production model loading.
fn resource_dir() -> String {
    // In production this is set by Tauri via TAURI_RESOURCE_DIR env var
    env::var("TAURI_RESOURCE_DIR").unwrap_or_else(|_| ".".to_string())
}

/// Injects window.__SIDECAR_PORT__ into all webview windows via JS eval.
fn inject_port(app: &AppHandle, port: u16) {
    if let Some(window) = app.get_webview_window("main") {
        let script = format!("window.__SIDECAR_PORT__ = {};", port);
        let _ = window.eval(&script);
    }
}

/// Called on app exit. Terminates the sidecar gracefully.
pub fn shutdown() {
    if let Some(pid) = SIDECAR_PID.lock().unwrap().take() {
        eprintln!("[Tauri] Shutting down sidecar PID {pid}...");

        #[cfg(target_os = "windows")]
        {
            // Windows: TerminateProcess via taskkill
            let _ = Command::new("taskkill")
                .args(["/PID", &pid.to_string(), "/F"])
                .status();
        }

        #[cfg(not(target_os = "windows"))]
        {
            use std::os::unix::process::ExitStatusExt;
            let _ = Command::new("kill")
                .args(["-TERM", &pid.to_string()])
                .status();
        }

        // Wait up to SHUTDOWN_TIMEOUT_SECS
        let t0 = Instant::now();
        while t0.elapsed() < Duration::from_secs(SHUTDOWN_TIMEOUT_SECS) {
            thread::sleep(Duration::from_millis(500));
        }
        eprintln!("[Tauri] Sidecar shutdown complete.");
    }
}
