# OmniOps Video Studio

Public repository: `https://github.com/yiweiyan258/omniops-video-studio`

This repository contains the desktop application only. The private OmniOps
control plane, knowledge graph, merchant assets, credentials and runtime
reports are maintained separately.

OmniOps Video Studio is the Windows desktop entry for the existing OmniOps
professional video Worker runtime. The desktop application and WeChat CODEX
share one application CLI and SQLite task store. The application CLI delegates
formal production to one canonical `omniops-video-workbench` component.

## V1 Boundary

V1 supports platform-independent material intake, a 15-60 second final-video
target, professional Worker state, sequential generation with explicit
one-time authorization, local QA, preview, and export. A complete script is
compiled into contiguous model generation units of no more than 15 seconds,
then assembled and checked as one final video. The protocol reports
`writesExternalSystems: false`.

The 0.4 workflow follows four user-facing actions: upload material, confirm
structured material insight, configure the creative plan, and select a
pre-spend creative direction. Product or character features, core selling
points, target audiences, usage scenarios, optional reference video, audio
mode, and final duration are preserved as a structured creation brief. The
Director, Screenwriter, Storyboard, Audio, Editing, and QA Workers remain
responsible for rewriting and validating the final production contract.

V1 does not include external platform writes, social engagement, account
control, automatic paid retry, credentials, merchant identity assets, voice
assets, authorization evidence, historical tasks, or output media.

## Development

Requirements:

- Node.js and npm
- Rust stable toolchain
- Python 3
- The canonical video workbench runtime
- FFmpeg and ffprobe

```powershell
npm install
npm run tauri:dev
```

The desktop shell locates the shared application CLI through
`OMNIOPS_VIDEO_STUDIO_CLI` during development. The application CLI locates the
canonical production component through `OMNIOPS_VIDEO_WORKBENCH`.

## Windows Build

The Windows build must run on Windows x64. It requires an independently
validated portable canonical workbench executable and licensed FFmpeg
binaries. The build refuses to substitute a second video workflow.

```powershell
.\packaging\build-windows.ps1 `
  -WorkbenchExecutable C:\build\omniops-video-workbench.exe `
  -FfmpegExecutable C:\build\ffmpeg.exe `
  -FfprobeExecutable C:\build\ffprobe.exe
```

Expected installer:

```text
dist\OmniOpsVideoStudio-Setup-x64.exe
```

Verification writes:

```text
dist\OmniOpsVideoStudio-Setup-x64.exe.sha256
dist\video-studio-package-verification.json
```

## Shared CLI

```powershell
omniops-video-studio-cli.exe manifest
omniops-video-studio-cli.exe doctor
omniops-video-studio-cli.exe analyze --merchant-id xiaoyuanli --media C:\material\store.jpg
omniops-video-studio-cli.exe compile-brief --brief-json <creation-brief-json>
omniops-video-studio-cli.exe submit --merchant-id xiaoyuanli --goal "人物剧情短视频" --duration-seconds 52 --source desktop
omniops-video-studio-cli.exe list
omniops-video-studio-cli.exe status --job-id <job-id> --refresh
```

One paid shot additionally requires a new `--paid-authorization-id`. The
application records and consumes that ID before invoking the canonical
workbench.
