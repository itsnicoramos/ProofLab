---
name: reverse-engineer-on-the-go
description: Reverse engineer apps, binaries, APKs, Electron ASARs and JS bundles from uploaded files or public URLs in Claude chat, REA-style. Evidence first, unknowns kept separate.
---

# Reverse Engineer On The Go

A chat-sized version of REA (Reverse Engineer Anything, github.com/morluto/rea).
Use it to explain how a feature in a shipped app or website works when the
user is on their phone or in Claude chat, where REA's MCP tools are not
connected. Skip it for ordinary source-code questions: read the source.

## 1. Check which mode you are in

- REA tools present (`open_binary`, `analyze_javascript_application`,
  `binary_session`, ...): you are in full REA on the user's computer. Use those
  tools and the `reverse-engineer-anything` skill instead of this one.
- No REA tools: you are in chat mode. You have the code-execution sandbox,
  files the user uploaded, and web fetch. You do not have Hopper, Ghidra, IDA,
  a debugger, or access to the user's devices or running apps.

If the sandbox or code execution is unavailable, say so and work from what the
user pastes (text, screenshots, snippets).

## 2. Get the smallest useful artifact

Ask for the one file that answers the question, not the whole installer:

| User wants to know about | Ask them to upload |
| --- | --- |
| Electron desktop app (Slack, Discord, VS Code...) | `Contents/Resources/app.asar` (macOS) or `resources/app.asar` (Windows) |
| Android app | the `.apk` |
| iOS app | the `.ipa` (App Store binaries are usually encrypted; resources still help) |
| Website feature | the URL, or the specific `.js` bundle + `.map` if they have it |
| Native tool / library | the executable, `.dylib`, `.so` or `.dll` |
| Windows .NET app | the main `.dll` / `.exe` |

Uploaded files usually land in `/mnt/user-data/uploads/`. If not, run
`find / -name '<filename>' -not -path '/proc/*' 2>/dev/null | head`.
Write large outputs (extracted trees, long dumps) to `/mnt/user-data/outputs/`
and give the user the file instead of pasting them.

## 3. Triage before reading anything

The helper script is stdlib-only Python, so it needs no installs:

```bash
S=$(find / -path '*reverse-engineer-on-the-go/scripts/triage.py' 2>/dev/null | head -1)
python3 "$S" triage /mnt/user-data/uploads/<file>     # format, hashes, structure, hints
python3 "$S" strings <file> --grep 'api|token|search' --limit 200
python3 "$S" extract <archive-or-asar> /tmp/out --only '*.js'
```

`triage` identifies ELF, Mach-O (including universal), PE (flags .NET), DEX,
WASM, Java class, ZIP family (APK/IPA/JAR/MSIX), Electron ASAR, JS bundles
(source maps, bundler markers, URLs, API paths) and directories (with
`package.json`). Record the `sha256` it prints: that is the target identity
for every claim.

## 4. Route by target

- **Electron ASAR**: extract, read root `package.json` `main`, then follow the
  main process and preload scripts. Search for `ipcMain.handle`, `contextBridge`,
  `BrowserWindow` `webPreferences`, and the UI text of the feature. Native
  `.node` addons and files in `app.asar.unpacked` need the native route.
- **JS bundle or website**: look for source maps first. A `.map` with
  `sourcesContent` gives near-original source. Otherwise find the feature by
  its UI strings, then trace to handlers, API calls, and state. Beautify
  minified code with `pip install jsbeautifier` when network allows.
- **APK**: inventory, then `pip install androguard` for manifest, permissions,
  activities, and classes. Without network, unzip and read `AndroidManifest.xml`
  (binary XML), `resources.arsc`, assets, and bundled JS (React Native
  `index.android.bundle`, Flutter `libapp.so`).
- **IPA**: read `Payload/*.app/Info.plist` with `plistlib`; triage the main
  executable. If `encrypted: true`, say the code is FairPlay-encrypted and only
  resources, plists, and linked frameworks can be analyzed here.
- **Native (ELF / Mach-O / PE)**: headers, sections, linked libraries, strings
  in context. For specific functions, `pip install lief capstone` and
  disassemble the bytes at a symbol or address. Name what static analysis in
  chat cannot do: full decompilation, cross-references at scale, runtime values.
- **.NET**: `pip install dnfile` for types, methods, and user strings. IL
  decompilation (ILSpy) belongs on the computer.
- **Go binaries**: `.go.buildinfo` and strings give module paths, versions, and
  package names, which usually reveal the architecture quickly.

Use format-aware parsing. Do not infer behavior from filenames or a single
string alone.

## 5. Evidence rules (from REA)

- Label every finding as **Observed** (seen in the artifact, cite member path +
  line/offset), **Inferred** (reasoned from observations, say from which), or
  **Unknown** (not established, say what would establish it).
- Static analysis never observed execution. Do not say "it sends X" when you
  only found code that could send X.
- Bounded searches stay bounded: "no match for `searchIndex` in the 14 JS files
  under `dist/`" is not "the app has no search index".
- Keep the target hash, file names, and versions in the report so a later
  session can reproduce or continue it.

## 6. Report for a phone screen

1. The answer in 3 to 5 short lines.
2. A small evidence table: finding, label, where (member:line or offset).
3. Unknowns and the single best next step.

If the user wants to build a similar feature, separate what the app does
(observed) from your design choices for their version.

## 7. Hand off to full REA when chat is not enough

Hand off for decompilation, runtime tracing, a large binary that won't upload,
encrypted iOS code, or a live app on their machine. REA is installed in Claude
Code on the user's computer. Give them a ready-to-paste prompt, for example:

> Use REA to analyze `/Applications/<App>.app`. Explain how <feature> works,
> show the evidence, and note the unknowns. Prior chat findings: <summary>.

## Scope

Analyze only software the user owns or is authorized to inspect. Explaining
how a feature works is fine. Do not help bypass DRM, licensing, or
authentication, extract other people's credentials or data, or attack services.
