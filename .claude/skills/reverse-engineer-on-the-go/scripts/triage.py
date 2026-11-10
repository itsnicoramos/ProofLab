#!/usr/bin/env python3
"""Stdlib-only triage for reverse-engineering targets in a chat sandbox.

Subcommands:
  triage  PATH                 identify the target and summarize its structure (JSON)
  strings PATH [--min N] [--grep REGEX] [--limit N] [--utf16]
  extract PATH OUTDIR [--only GLOB]   unpack ZIP-family archives or Electron ASARs
"""
import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import struct
import sys
import zipfile

READ_CAP = 64 * 1024 * 1024  # bytes read for strings/entropy/js scans

ELF_MACHINES = {2: "sparc", 3: "x86", 8: "mips", 20: "ppc", 21: "ppc64", 40: "arm", 43: "sparcv9",
                62: "x86_64", 94: "xtensa", 183: "aarch64", 243: "riscv", 258: "loongarch"}
ELF_TYPES = {1: "relocatable", 2: "executable", 3: "shared-object/pie", 4: "core"}
MACHO_CPU = {7: "x86", 0x01000007: "x86_64", 12: "arm", 0x0100000C: "arm64",
             0x0200000C: "arm64_32", 18: "ppc"}
MACHO_FILETYPES = {1: "object", 2: "executable", 6: "dylib", 7: "dylinker", 8: "bundle",
                   11: "dsym", 12: "kext"}
PE_MACHINES = {0x14C: "x86", 0x8664: "x86_64", 0x1C0: "arm", 0xAA64: "arm64", 0x1C4: "armnt"}
PE_SUBSYSTEMS = {1: "native", 2: "windows-gui", 3: "windows-console", 9: "windows-ce",
                 10: "efi-application", 11: "efi-boot-driver", 12: "efi-runtime-driver"}

URL_RE = re.compile(rb"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{4,300}")
SOURCEMAP_RE = re.compile(rb"[#@]\s*sourceMappingURL=([^\s'\"*]+)")
JS_EXTS = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")
BUNDLER_MARKERS = {
    "webpack": [b"__webpack_require__", b"webpackChunk"],
    "vite/rollup": [b"import.meta.url", b"__vite__", b"/assets/index-"],
    "esbuild": [b"__esm(", b"__commonJS(", b"__toESM("],
    "react": [b"react-dom", b"__REACT_DEVTOOLS", b"createElement("],
    "vue": [b"__VUE__", b"createVNode"],
    "electron": [b"ipcRenderer", b"ipcMain", b"contextBridge", b"BrowserWindow"],
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entropy(data):
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return round(-sum(c / n * math.log2(c / n) for c in counts if c), 3)


def read_head(path, n=READ_CAP):
    with open(path, "rb") as f:
        return f.read(n)


def cstr(buf, off):
    end = buf.find(b"\0", off)
    return buf[off:end if end != -1 else len(buf)].decode("utf-8", "replace")


# ---------------------------------------------------------------- ELF
def parse_elf(buf):
    is64 = buf[4] == 2
    end = "<" if buf[5] == 1 else ">"
    e_type, e_machine = struct.unpack_from(end + "HH", buf, 16)
    info = {"format": "elf", "bits": 64 if is64 else 32,
            "endian": "little" if end == "<" else "big",
            "type": ELF_TYPES.get(e_type, e_type), "machine": ELF_MACHINES.get(e_machine, e_machine)}
    try:
        if is64:
            shoff = struct.unpack_from(end + "Q", buf, 0x28)[0]
            shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", buf, 0x3A)
        else:
            shoff = struct.unpack_from(end + "I", buf, 0x20)[0]
            shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", buf, 0x2E)
        sections = []
        if shoff and shnum and shoff + shnum * shentsize <= len(buf):
            def sh(i):
                base = shoff + i * shentsize
                if is64:
                    name, _t, _f, _a, off, size = struct.unpack_from(end + "IIQQQQ", buf, base)
                else:
                    name, _t, _f, _a, off, size = struct.unpack_from(end + "IIIIII", buf, base)
                return name, off, size
            _, str_off, _ = sh(shstrndx)
            for i in range(shnum):
                name, off, size = sh(i)
                sections.append({"name": cstr(buf, str_off + name), "size": size})
        info["sections"] = [s for s in sections if s["name"]]
        names = {s["name"] for s in sections}
        hints = []
        if names & {".gopclntab", ".go.buildinfo", ".note.go.buildid"}:
            hints.append("go")
        if b"rustc" in buf or b"/rustc/" in buf:
            hints.append("rust (rustc strings present)")
        if ".symtab" not in names:
            hints.append("stripped (no .symtab)")
        if ".gnu_debugdata" in names:
            hints.append("minidebuginfo present")
        info["hints"] = hints
    except struct.error:
        info["warning"] = "section table truncated or beyond read window"
    return info


# ---------------------------------------------------------------- Mach-O
LC_SEGMENT, LC_SEGMENT_64 = 0x1, 0x19
LC_LOAD_DYLIB, LC_ID_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB = 0xC, 0xD, 0x80000018, 0x8000001F
LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64 = 0x21, 0x2C
LC_CODE_SIGNATURE, LC_BUILD_VERSION, LC_MAIN = 0x1D, 0x32, 0x80000028


def parse_macho_slice(buf, base=0):
    magic = struct.unpack_from("<I", buf, base)[0]
    if magic in (0xFEEDFACE, 0xFEEDFACF):
        end = "<"
    else:
        end = ">"
        magic = struct.unpack_from(">I", buf, base)[0]
    is64 = magic == 0xFEEDFACF
    cputype, _sub, filetype, ncmds, _size, flags = struct.unpack_from(end + "iiIIII", buf, base + 4)
    info = {"cpu": MACHO_CPU.get(cputype & 0xFFFFFFFF, cputype), "filetype": MACHO_FILETYPES.get(filetype, filetype),
            "load_commands": ncmds, "pie": bool(flags & 0x200000)}
    off = base + (32 if is64 else 28)
    segments, dylibs = [], []
    for _ in range(ncmds):
        if off + 8 > len(buf):
            info["warning"] = "load commands extend beyond read window"
            break
        cmd, cmdsize = struct.unpack_from(end + "II", buf, off)
        if cmdsize < 8:
            break
        if cmd in (LC_SEGMENT, LC_SEGMENT_64):
            segments.append(buf[off + 8:off + 24].split(b"\0")[0].decode("ascii", "replace"))
        elif cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB, LC_REEXPORT_DYLIB, LC_ID_DYLIB):
            name_off = struct.unpack_from(end + "I", buf, off + 8)[0]
            name = cstr(buf, off + name_off)
            if cmd == LC_ID_DYLIB:
                info["install_name"] = name
            else:
                dylibs.append(name)
        elif cmd in (LC_ENCRYPTION_INFO, LC_ENCRYPTION_INFO_64):
            info["encrypted"] = struct.unpack_from(end + "I", buf, off + 16)[0] != 0
        elif cmd == LC_CODE_SIGNATURE:
            info["code_signature"] = True
        elif cmd == LC_MAIN:
            info["has_main"] = True
        off += cmdsize
    info["segments"] = segments
    info["linked_libraries"] = dylibs
    frameworks = sorted({d.split("/")[-1] for d in dylibs if ".framework/" in d})
    if any("libswiftCore" in d for d in dylibs):
        info.setdefault("hints", []).append("swift")
    if frameworks:
        info["frameworks"] = frameworks
    return info


def parse_macho(buf):
    magic_be = struct.unpack_from(">I", buf, 0)[0]
    if magic_be in (0xCAFEBABE, 0xCAFEBABF):
        nfat = struct.unpack_from(">I", buf, 4)[0]
        wide = magic_be == 0xCAFEBABF
        slices = []
        for i in range(nfat):
            if wide:
                cputype, _s, off, _size, _a, _r = struct.unpack_from(">iiQQII", buf, 8 + i * 32)
            else:
                cputype, _s, off, _size, _a = struct.unpack_from(">iiIII", buf, 8 + i * 20)
            entry = {"cpu": MACHO_CPU.get(cputype & 0xFFFFFFFF, cputype), "offset": off}
            if off + 32 <= len(buf):
                try:
                    entry.update(parse_macho_slice(buf, off))
                except struct.error:
                    entry["warning"] = "slice header unreadable"
            slices.append(entry)
        return {"format": "mach-o-universal", "slices": slices}
    info = parse_macho_slice(buf)
    info["format"] = "mach-o"
    return info


# ---------------------------------------------------------------- PE
def parse_pe(buf):
    pe_off = struct.unpack_from("<I", buf, 0x3C)[0]
    if buf[pe_off:pe_off + 4] != b"PE\0\0":
        return {"format": "mz-dos", "note": "MZ header without PE signature"}
    machine, nsec, timestamp, _p, _n, optsize, chars = struct.unpack_from("<HHIIIHH", buf, pe_off + 4)
    opt = pe_off + 24
    magic = struct.unpack_from("<H", buf, opt)[0]
    pe32plus = magic == 0x20B
    subsystem = struct.unpack_from("<H", buf, opt + 68)[0]
    dd = opt + (112 if pe32plus else 96)
    clr_rva = struct.unpack_from("<I", buf, dd + 14 * 8)[0] if dd + 15 * 8 <= len(buf) else 0
    sec_base = opt + optsize
    sections = []
    for i in range(nsec):
        s = sec_base + i * 40
        if s + 40 > len(buf):
            break
        name = buf[s:s + 8].split(b"\0")[0].decode("ascii", "replace")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", buf, s + 8)
        sections.append({"name": name, "virtual_size": vsize, "raw_size": rawsize,
                         "entropy": entropy(buf[rawptr:rawptr + rawsize]) if rawptr + rawsize <= len(buf) else None})
    info = {"format": "pe", "bits": 64 if pe32plus else 32, "machine": PE_MACHINES.get(machine, hex(machine)),
            "subsystem": PE_SUBSYSTEMS.get(subsystem, subsystem), "dll": bool(chars & 0x2000),
            "timestamp": timestamp, "dotnet": clr_rva != 0, "sections": sections}
    names = {s["name"] for s in sections}
    hints = []
    if clr_rva:
        hints.append(".NET assembly: use dnfile for metadata; IL decompilation needs ILSpy (computer)")
    if names & {"UPX0", "UPX1"}:
        hints.append("UPX packed")
    if any((s["entropy"] or 0) > 7.2 for s in sections):
        hints.append("high-entropy section (packed/compressed/encrypted data)")
    info["hints"] = hints
    return info


# ---------------------------------------------------------------- ASAR
def read_asar_header(path):
    with open(path, "rb") as f:
        head = f.read(16)
        if len(head) < 16 or struct.unpack_from("<I", head, 0)[0] != 4:
            return None
        header_size = struct.unpack_from("<I", head, 4)[0]
        json_len = struct.unpack_from("<I", head, 12)[0]
        if json_len > 512 * 1024 * 1024:
            return None
        f.seek(16)
        raw = f.read(json_len)
    try:
        return json.loads(raw.decode("utf-8")), 8 + header_size
    except (ValueError, UnicodeDecodeError):
        return None


def walk_asar(node, prefix=""):
    for name, entry in node.get("files", {}).items():
        p = f"{prefix}/{name}" if prefix else name
        if "files" in entry:
            yield from walk_asar(entry, p)
        elif "link" in entry:
            continue
        else:
            yield p, entry


def summarize_members(names_sizes):
    names = [n for n, _ in names_sizes]
    exts = {}
    for n, s in names_sizes:
        ext = os.path.splitext(n)[1].lower() or "(none)"
        e = exts.setdefault(ext, [0, 0])
        e[0] += 1
        e[1] += s
    top_ext = sorted(exts.items(), key=lambda kv: -kv[1][1])[:15]
    largest = sorted(names_sizes, key=lambda x: -x[1])[:15]
    notable_patterns = ["*package.json", "*AndroidManifest.xml", "classes*.dex", "*Info.plist",
                        "*.so", "*.dylib", "*.dll", "*.node", "*.wasm", "*.map", "*app.asar",
                        "*preload*.js", "*main.js", "*.mobileprovision", "*resources.arsc",
                        "META-INF/MANIFEST.MF", "*AppxManifest.xml", "*.framework/*"]
    # App-owned files first, then shallow paths; vendored node_modules last.
    notable = sorted({n for n in names for p in notable_patterns if fnmatch.fnmatch(n, p)},
                     key=lambda n: ("node_modules/" in n, n.count("/"), n))
    return {"member_count": len(names),
            "by_extension": [{"ext": k, "count": v[0], "bytes": v[1]} for k, v in top_ext],
            "largest": [{"name": n, "bytes": s} for n, s in largest],
            "notable": notable[:200], "notable_truncated": len(notable) > 200}


def zip_flavor(names):
    s = set(names)
    if "AndroidManifest.xml" in s and any(fnmatch.fnmatch(n, "classes*.dex") for n in s):
        return "apk"
    if any(n.startswith("Payload/") and ".app/" in n for n in s):
        return "ipa"
    if "AppxManifest.xml" in s:
        return "msix/appx"
    if "META-INF/MANIFEST.MF" in s:
        return "jar"
    if "[Content_Types].xml" in s:
        return "office-open-xml"
    return "zip"


# ---------------------------------------------------------------- JS / text
def scan_js(data):
    out = {}
    maps = [m.decode("utf-8", "replace") for m in SOURCEMAP_RE.findall(data)]
    if maps:
        out["source_maps"] = maps[:20]
    markers = [k for k, pats in BUNDLER_MARKERS.items() if any(p in data for p in pats)]
    if markers:
        out["markers"] = markers
    urls = sorted({u.decode("utf-8", "replace").rstrip(".,;)'\"") for u in URL_RE.findall(data)})
    if urls:
        out["urls"] = urls[:100]
        out["url_count"] = len(urls)
    api_paths = sorted({m.decode() for m in re.findall(rb"[\"'`](/(?:api|v\d+|graphql|rpc|rest)\b[A-Za-z0-9_./{}:?=&%$-]*)[\"'`]", data)})
    if api_paths:
        out["api_like_paths"] = api_paths[:100]
    return out


def looks_text(data):
    sample = data[:8192]
    if not sample:
        return False
    if b"\0" in sample:
        return False
    printable = sum(1 for b in sample if 32 <= b < 127 or b in (9, 10, 13)) / len(sample)
    return printable > 0.85


# ---------------------------------------------------------------- directory
def triage_dir(path):
    entries = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in (".git",)]
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                entries.append((os.path.relpath(fp, path), os.path.getsize(fp)))
            except OSError:
                pass
    info = {"format": "directory"}
    info.update(summarize_members(entries))
    pkg = os.path.join(path, "package.json")
    if os.path.isfile(pkg):
        try:
            with open(pkg, encoding="utf-8") as f:
                p = json.load(f)
            info["package_json"] = {k: p.get(k) for k in ("name", "productName", "version", "main", "type") if p.get(k)}
            deps = sorted((p.get("dependencies") or {}).keys())
            if deps:
                info["package_json"]["dependencies"] = deps[:80]
        except (ValueError, OSError):
            info["package_json"] = "unreadable"
    return info


# ---------------------------------------------------------------- triage
def triage(path):
    if os.path.isdir(path):
        return triage_dir(path)
    size = os.path.getsize(path)
    head = read_head(path, min(size, READ_CAP))
    result = {"path": path, "bytes": size, "sha256": sha256_file(path),
              "entropy_first_64MiB": entropy(head[:READ_CAP])}
    if size > READ_CAP:
        result["note"] = f"only the first {READ_CAP // (1024 * 1024)} MiB were scanned for structure/strings"
    try:
        if head[:4] == b"\x7fELF":
            result.update(parse_elf(head))
        elif head[:4] in (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xfe\xed\xfa\xce"):
            result.update(parse_macho(head))
        elif head[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf") and struct.unpack_from(">I", head, 4)[0] < 40:
            result.update(parse_macho(head))
        elif head[:4] == b"\xca\xfe\xba\xbe":
            major = struct.unpack_from(">H", head, 6)[0]
            result.update({"format": "java-class", "class_major_version": major})
        elif head[:2] == b"MZ":
            result.update(parse_pe(head))
        elif head[:4] == b"dex\n":
            result.update({"format": "dex", "version": head[4:7].decode("ascii", "replace"),
                           "hint": "pip install androguard for classes/methods"})
        elif head[:4] == b"\0asm":
            result.update({"format": "wasm", "version": struct.unpack_from("<I", head, 4)[0]})
        elif zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                infos = [(i.filename, i.file_size) for i in z.infolist() if not i.is_dir()]
            result["format"] = zip_flavor([n for n, _ in infos])
            result.update(summarize_members(infos))
        elif read_asar_header(path):
            header, _base = read_asar_header(path)
            members = [(p, int(e.get("size", 0))) for p, e in walk_asar(header)]
            result["format"] = "asar"
            result.update(summarize_members(members))
            result["unpacked_members"] = sum(1 for _p, e in walk_asar(header) if e.get("unpacked"))
        elif head[:2] == b"\x1f\x8b":
            result["format"] = "gzip (try tarfile.open(path) for .tgz/.tar.gz)"
        elif head[:8] == b"bplist00":
            result["format"] = "binary-plist (use plistlib.load)"
        elif looks_text(head):
            result["format"] = "javascript" if path.lower().endswith(JS_EXTS) else "text"
            result.update(scan_js(head))
            result["lines"] = head.count(b"\n") + 1
            if result["lines"] < 50 and size > 200_000:
                result["hint"] = "minified: beautify with `pip install jsbeautifier` before reading"
        else:
            result["format"] = "unknown"
            if result["entropy_first_64MiB"] > 7.5:
                result["hint"] = "near-random bytes: compressed or encrypted container"
    except (struct.error, IndexError, zipfile.BadZipFile) as exc:
        result["parse_error"] = f"{type(exc).__name__}: {exc}"
    if result.get("format") not in ("text", "javascript", "directory"):
        js = scan_js(head)
        if js.get("urls"):
            result["embedded_urls"] = js["urls"][:40]
    return result


# ---------------------------------------------------------------- strings
def iter_strings(data, min_len, utf16):
    for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, data):
        yield m.start(), m.group().decode("ascii")
    if utf16:
        for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % min_len, data):
            yield m.start(), m.group().decode("utf-16-le")


def cmd_strings(args):
    data = read_head(args.path)
    pat = re.compile(args.grep, re.I) if args.grep else None
    count = 0
    for off, s in iter_strings(data, args.min, args.utf16):
        if pat and not pat.search(s):
            continue
        print(f"0x{off:08x}  {s[:400]}")
        count += 1
        if count >= args.limit:
            print(f"... stopped at --limit {args.limit}", file=sys.stderr)
            break


# ---------------------------------------------------------------- extract
def safe_dest(outdir, member):
    dest = os.path.realpath(os.path.join(outdir, member))
    root = os.path.realpath(outdir)
    if dest != root and not dest.startswith(root + os.sep):
        raise ValueError(f"refusing path outside output dir: {member}")
    return dest


def cmd_extract(args):
    os.makedirs(args.outdir, exist_ok=True)
    written = 0
    if zipfile.is_zipfile(args.path):
        with zipfile.ZipFile(args.path) as z:
            for info in z.infolist():
                if info.is_dir() or (args.only and not fnmatch.fnmatch(info.filename, args.only)):
                    continue
                dest = safe_dest(args.outdir, info.filename)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                with z.open(info) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                written += 1
    else:
        parsed = read_asar_header(args.path)
        if not parsed:
            sys.exit("not a ZIP-family archive or ASAR")
        header, base = parsed
        with open(args.path, "rb") as f:
            for member, entry in walk_asar(header):
                if args.only and not fnmatch.fnmatch(member, args.only):
                    continue
                if entry.get("unpacked"):
                    print(f"skipped (lives in app.asar.unpacked): {member}", file=sys.stderr)
                    continue
                dest = safe_dest(args.outdir, member)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                f.seek(base + int(entry.get("offset", 0)))
                with open(dest, "wb") as dst:
                    dst.write(f.read(int(entry.get("size", 0))))
                written += 1
    print(json.dumps({"extracted": written, "outdir": os.path.abspath(args.outdir)}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("triage")
    t.add_argument("path")
    s = sub.add_parser("strings")
    s.add_argument("path")
    s.add_argument("--min", type=int, default=6)
    s.add_argument("--grep")
    s.add_argument("--limit", type=int, default=300)
    s.add_argument("--utf16", action="store_true")
    e = sub.add_parser("extract")
    e.add_argument("path")
    e.add_argument("outdir")
    e.add_argument("--only", help="glob filter on member paths, e.g. '*.js'")
    args = ap.parse_args()
    if args.cmd == "triage":
        print(json.dumps(triage(args.path), indent=2))
    elif args.cmd == "strings":
        cmd_strings(args)
    else:
        cmd_extract(args)


if __name__ == "__main__":
    main()
