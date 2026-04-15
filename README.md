# business-card

Lightweight digital business card generator for **Apple Wallet** (`.pkpass`).

Edit your details in `config.json`, run the script, and share the generated
`.pkpass` file — recipients can add it straight to their iPhone Wallet.

---

## Quick start

### 1. Fill in your details

Edit `config.json`:

```json
{
  "business_card": {
    "name": "Your Name",
    "title": "Job Title",
    "company": "Company Name",
    "email": "you@example.com",
    "phone": "+1 234 567 8900",
    "website": "https://example.com",
    "linkedin": "linkedin.com/in/yourprofile"
  },
  "apple_credentials": {
    "passTypeIdentifier": "pass.com.example.businesscard",
    "teamIdentifier": "XXXXXXXXXX",
    "serialNumber": "001"
  },
  "style": {
    "backgroundColor": "rgb(60, 65, 76)",
    "foregroundColor": "rgb(255, 255, 255)",
    "labelColor": "rgb(180, 180, 180)"
  }
}
```

### 2. Obtain Apple Developer certificates

To install a pass on a **real device** you need three `.pem` files in the
`certificates/` directory:

| File | How to get it |
|------|---------------|
| `certificates/certificate.pem` | Export your **Pass Type ID** certificate from Keychain Access → convert with OpenSSL |
| `certificates/key.pem` | Private key used when generating the CSR for the Pass Type ID |
| `certificates/wwdr.pem` | [Apple WWDR G4 certificate](https://www.apple.com/certificateauthority/) |

**Steps:**

1. Sign in to [developer.apple.com](https://developer.apple.com) → *Certificates, Identifiers & Profiles*.
2. Create a **Pass Type ID** (e.g. `pass.com.yourname.businesscard`).
3. Generate a certificate for that Pass Type ID and download it (`Certificates.p12`).
4. Convert to PEM:
   ```sh
   openssl pkcs12 -in Certificates.p12 -clcerts -nokeys -out certificates/certificate.pem
   openssl pkcs12 -in Certificates.p12 -nocerts -nodes  -out certificates/key.pem
   ```
5. Download the Apple WWDR certificate and convert it:
   ```sh
   openssl x509 -inform DER -in AppleWWDRCAG4.cer -out certificates/wwdr.pem
   ```

> **Note:** certificate files are excluded from git via `.gitignore` — never
> commit your private key.

### 3. Generate the pass

```sh
python generate_pass.py
```

Options:

```
--config  PATH   Path to config file          (default: config.json)
--output  PATH   Output .pkpass file          (default: businesscard.pkpass)
--cert    PATH   Pass Type certificate (.pem) (default: certificates/certificate.pem)
--key     PATH   Private key (.pem)           (default: certificates/key.pem)
--wwdr    PATH   Apple WWDR certificate (.pem)(default: certificates/wwdr.pem)
```

### 4. Share the pass

- **AirDrop** the `.pkpass` file directly to someone's iPhone.
- **Email / iMessage** it as an attachment.
- **Host it** on a web server with MIME type `application/vnd.apple.pkpass` and share the link.

Tapping the file on iOS opens a *"Add to Wallet"* sheet instantly.

---

## Pass layout (Generic pass)

```
┌─────────────────────────────────┐
│  Company Name          [logo]   │
├─────────────────────────────────┤
│  NAME                           │
│  Your Name                      │
├──────────────┬──────────────────┤
│  TITLE       │  COMPANY         │
│  Job Title   │  Company Name    │
├──────────────┴──────────────────┤
│  EMAIL              PHONE       │
│  you@example.com   +1 234…      │
├─────────────────────────────────┤
│  ← flip for back side           │
│  WEBSITE / LINKEDIN             │
└─────────────────────────────────┘
```

---

## Requirements

- Python 3.6+
- OpenSSL (pre-installed on macOS / most Linux distributions)
- Apple Developer account (99 USD/year) for signing

