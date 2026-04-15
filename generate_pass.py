#!/usr/bin/env python3
"""
Generate an Apple Wallet business card pass (.pkpass).

Requirements:
  - Python 3.6+
  - OpenSSL (for signing)
  - Apple Developer certificates (see README.md)

Usage:
  python generate_pass.py [--config config.json] [--output businesscard.pkpass]
"""

import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path


# ---------------------------------------------------------------------------
# Tiny PNG generator (no external dependencies)
# ---------------------------------------------------------------------------

def _png_chunk(name: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(name + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)


def create_png(width: int, height: int, color: tuple = (60, 65, 76)) -> bytes:
    """Return the raw bytes of a solid-colour PNG image."""
    ihdr = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw_rows = b"".join(b"\x00" + bytes(color) * width for _ in range(height))
    idat = _png_chunk(b"IDAT", zlib.compress(raw_rows, 9))
    iend = _png_chunk(b"IEND", b"")
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


# ---------------------------------------------------------------------------
# pass.json builder
# ---------------------------------------------------------------------------

def build_pass_json(config: dict) -> dict:
    card = config["business_card"]
    creds = config["apple_credentials"]
    style = config.get("style", {})

    pass_data = {
        "formatVersion": 1,
        "passTypeIdentifier": creds["passTypeIdentifier"],
        "serialNumber": creds.get("serialNumber", "001"),
        "teamIdentifier": creds["teamIdentifier"],
        "organizationName": card.get("company", card["name"]),
        "description": f"{card['name']} – Business Card",
        "logoText": card.get("company", card["name"]),
        "foregroundColor": style.get("foregroundColor", "rgb(255, 255, 255)"),
        "backgroundColor": style.get("backgroundColor", "rgb(60, 65, 76)"),
        "labelColor": style.get("labelColor", "rgb(180, 180, 180)"),
        "generic": {
            "primaryFields": [
                {"key": "name", "label": "NAME", "value": card["name"]}
            ],
            "secondaryFields": [],
            "auxiliaryFields": [],
            "backFields": [],
        },
    }

    secondary = pass_data["generic"]["secondaryFields"]
    if card.get("title"):
        secondary.append({"key": "title", "label": "TITLE", "value": card["title"]})
    if card.get("company"):
        secondary.append({"key": "company", "label": "COMPANY", "value": card["company"]})

    auxiliary = pass_data["generic"]["auxiliaryFields"]
    if card.get("email"):
        auxiliary.append({"key": "email", "label": "EMAIL", "value": card["email"]})
    if card.get("phone"):
        auxiliary.append({"key": "phone", "label": "PHONE", "value": card["phone"]})

    back = pass_data["generic"]["backFields"]
    if card.get("website"):
        back.append(
            {
                "key": "website",
                "label": "WEBSITE",
                "value": card["website"],
                "attributedValue": f"<a href='{card['website']}'>{card['website']}</a>",
            }
        )
    if card.get("linkedin"):
        back.append({"key": "linkedin", "label": "LINKEDIN", "value": card["linkedin"]})

    return pass_data


def parse_rgb(rgb_string: str) -> tuple:
    """Parse an 'rgb(R, G, B)' string into a (R, G, B) integer tuple."""
    try:
        inner = rgb_string.replace("rgb(", "").replace(")", "")
        return tuple(int(c.strip()) for c in inner.split(","))
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"Invalid color format '{rgb_string}'. Expected format: rgb(R, G, B)"
        ) from exc


# ---------------------------------------------------------------------------
# Manifest + signing
# ---------------------------------------------------------------------------

def sha1_of_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def build_manifest(files: dict) -> dict:
    """files: {filename_in_pass: bytes}"""
    return {name: sha1_of_bytes(data) for name, data in files.items()}


def sign_manifest(manifest_bytes: bytes, cert: Path, key: Path, wwdr: Path) -> bytes:
    """
    Produce a DER-encoded PKCS#7 detached signature of the manifest
    using the Apple-issued Pass Type certificate.
    """
    with tempfile.TemporaryDirectory() as tmp:
        mf_path = Path(tmp) / "manifest.json"
        sig_path = Path(tmp) / "signature"
        mf_path.write_bytes(manifest_bytes)

        cmd = [
            "openssl", "smime", "-sign",
            "-signer", str(cert),
            "-inkey", str(key),
            "-certfile", str(wwdr),
            "-in", str(mf_path),
            "-out", str(sig_path),
            "-outform", "DER",
            "-binary",
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                "OpenSSL signing failed:\n" + result.stderr.decode()
            )
        return sig_path.read_bytes()


# ---------------------------------------------------------------------------
# .pkpass packager
# ---------------------------------------------------------------------------

def create_pkpass(output_path: Path, files: dict) -> None:
    """files: {filename_in_zip: bytes}"""
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    print(f"✓ Pass written to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate an Apple Wallet business card")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--output", default="businesscard.pkpass", help="Output .pkpass file")
    parser.add_argument(
        "--cert", default="certificates/certificate.pem",
        help="Path to Pass Type certificate (.pem)"
    )
    parser.add_argument(
        "--key", default="certificates/key.pem",
        help="Path to private key (.pem)"
    )
    parser.add_argument(
        "--wwdr", default="certificates/wwdr.pem",
        help="Path to Apple WWDR certificate (.pem)"
    )
    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with config_path.open() as f:
        config = json.load(f)

    # Build pass.json
    pass_json = build_pass_json(config)
    pass_bytes = json.dumps(pass_json, ensure_ascii=False, indent=2).encode()

    # Generate icon images (29×29 and 58×58, solid background colour)
    bg_str = config.get("style", {}).get("backgroundColor", "rgb(60, 65, 76)")
    bg_rgb = parse_rgb(bg_str)
    icon_bytes = create_png(29, 29, bg_rgb)
    icon2x_bytes = create_png(58, 58, bg_rgb)

    # Assemble pass files
    pass_files = {
        "pass.json": pass_bytes,
        "icon.png": icon_bytes,
        "icon@2x.png": icon2x_bytes,
    }

    # Build manifest
    manifest = build_manifest(pass_files)
    manifest_bytes = json.dumps(manifest, indent=2).encode()
    pass_files["manifest.json"] = manifest_bytes

    # Signing (optional — skipped if certificate files are absent)
    cert_path = Path(args.cert)
    key_path = Path(args.key)
    wwdr_path = Path(args.wwdr)

    if cert_path.exists() and key_path.exists() and wwdr_path.exists():
        print("Signing manifest with Apple Developer certificate …")
        try:
            signature = sign_manifest(manifest_bytes, cert_path, key_path, wwdr_path)
            pass_files["signature"] = signature
            print("✓ Manifest signed successfully.")
        except RuntimeError as e:
            print(f"Warning: signing failed — {e}", file=sys.stderr)
            print("The pass will be created without a signature (not usable on real devices).")
    else:
        print(
            "Warning: certificate files not found — creating unsigned pass.\n"
            "An unsigned pass cannot be added to a real Apple Wallet.\n"
            "See README.md for instructions on obtaining certificates."
        )

    # Package
    create_pkpass(Path(args.output), pass_files)


if __name__ == "__main__":
    main()
