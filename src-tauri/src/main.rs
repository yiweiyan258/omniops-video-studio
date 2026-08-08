use serde_json::Value;
use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;
use tauri::{AppHandle, Manager};

fn python_command(script: &Path, arguments: &[String]) -> Command {
    let python = env::var("OMNIOPS_VIDEO_PYTHON").unwrap_or_else(|_| {
        if cfg!(windows) {
            "python".to_string()
        } else {
            "python3".to_string()
        }
    });
    let mut command = Command::new(python);
    command.env("PYTHONDONTWRITEBYTECODE", "1");
    command.arg(script);
    command.args(arguments);
    command
}

fn resolve_cli(app: &AppHandle) -> Result<PathBuf, String> {
    if let Ok(configured) = env::var("OMNIOPS_VIDEO_STUDIO_CLI") {
        let path = PathBuf::from(configured);
        if path.is_file() {
            return Ok(path);
        }
    }

    let executable_name = if cfg!(windows) {
        "omniops-video-studio-cli.exe"
    } else {
        "omniops-video-studio-cli"
    };
    let current_executable = env::current_exe().map_err(|error| error.to_string())?;
    if let Some(parent) = current_executable.parent() {
        let candidate = parent.join(executable_name);
        if candidate.is_file() {
            return Ok(candidate);
        }
    }

    if let Ok(resource_dir) = app.path().resource_dir() {
        for candidate in [
            resource_dir.join(executable_name),
            resource_dir.join("binaries").join(executable_name),
            resource_dir
                .join("scripts")
                .join("omniops-video-studio-cli.py"),
        ] {
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
    }

    let development_cli = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("backend")
        .join("omniops-video-studio-cli.py");
    if development_cli.is_file() {
        return Ok(development_cli);
    }
    Err("OmniOps Video Studio CLI was not found".to_string())
}

#[tauri::command]
fn video_studio_command(app: AppHandle, args: Vec<String>) -> Result<Value, String> {
    let cli = resolve_cli(&app)?;
    let output = if cli.extension().and_then(|value| value.to_str()) == Some("py") {
        python_command(&cli, &args).output()
    } else {
        Command::new(&cli).args(&args).output()
    }
    .map_err(|error| format!("failed to start video CLI: {error}"))?;

    let stdout = String::from_utf8(output.stdout)
        .map_err(|_| "video CLI returned non-UTF-8 output".to_string())?;
    let payload: Value = serde_json::from_str(stdout.trim())
        .map_err(|error| format!("video CLI returned invalid JSON: {error}"))?;
    Ok(payload)
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![video_studio_command])
        .run(tauri::generate_context!())
        .expect("error while running OmniOps Video Studio");
}
