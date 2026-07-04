#!/usr/bin/env node
// generate-og-image.mjs — renders scripts/og-card.html to img/og-card.png
// (1200x630, the standard og:image / twitter:image size) via a headless
// screenshot of an already-installed local Chrome/Edge binary.
//
// Why this approach and not pngjs (see alphahive's generate-pwa-icons.mjs
// for that pattern): the OG card needs real text layout (wrapping headline,
// gradient-clipped text, proportional fonts) that a pixel-math generator
// can't produce without also hand-rolling a bitmap font. This repo has no
// package.json / node_modules, so no SVG-rasterization library (sharp,
// resvg, puppeteer) is available either, and installing one would violate
// the "no new global installs" constraint. Headless Chrome is already
// present on this machine for other tooling — spawning it directly (not
// through the browser-extension automation layer) needs no new dependency
// and gives production-quality font rendering.
//
// Usage:  node scripts/generate-og-image.mjs
// Output: img/og-card.png
//
// If no Chrome/Edge binary is found, this script exits non-zero with the
// exact command to run by hand once a browser path is known, e.g.:
//   "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new ^
//     --disable-gpu --screenshot=img\og-card.png --window-size=1200,630 ^
//     --default-background-color=00000000 scripts\og-card.html
// (PowerShell/cmd note: use ` in PowerShell or ^ in cmd.exe for line
// continuation — the block above is written for cmd.exe.)

import { execFileSync } from 'child_process'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.join(__dirname, '..')
const SOURCE_HTML = path.join(__dirname, 'og-card.html')
const OUT_PNG = path.join(REPO_ROOT, 'img', 'og-card.png')

const CANDIDATE_BINARIES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
]

const chrome = CANDIDATE_BINARIES.find((p) => fs.existsSync(p))

if (!chrome) {
  console.error('No local Chrome/Edge binary found at the known install paths.')
  console.error('Run this by hand once you know your browser path:')
  console.error(
    `  "<chrome-path>" --headless=new --disable-gpu --screenshot=${OUT_PNG} ` +
      `--window-size=1200,630 --default-background-color=00000000 ${SOURCE_HTML}`
  )
  process.exit(1)
}

fs.mkdirSync(path.dirname(OUT_PNG), { recursive: true })

const args = [
  '--headless=new',
  '--disable-gpu',
  `--screenshot=${OUT_PNG}`,
  '--window-size=1200,630',
  '--default-background-color=00000000',
  '--force-device-scale-factor=1',
  // file:// URL avoids any relative-path ambiguity in headless mode
  'file:///' + SOURCE_HTML.replace(/\\/g, '/'),
]

execFileSync(chrome, args, { stdio: 'inherit' })

if (!fs.existsSync(OUT_PNG)) {
  console.error(`Expected output not found at ${OUT_PNG} — headless Chrome ran but produced no file.`)
  process.exit(1)
}

console.log(`wrote ${OUT_PNG} (${fs.statSync(OUT_PNG).size} bytes)`)
