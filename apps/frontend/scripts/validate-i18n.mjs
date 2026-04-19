#!/usr/bin/env node
/**
 * Ensures every locale JSON has the same key set as its English counterpart.
 * - Core: src/locales/en/*.json ↔ src/locales/de/*.json (same filenames)
 * - Plugins: src/plugins/<id>/locales/en.json ↔ de.json (optional; both required if one exists)
 */
import { readdir, readFile, stat } from "node:fs/promises";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");

function leafPaths(obj, prefix = "") {
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    throw new Error(`Expected object at "${prefix || "(root)"}"`);
  }
  const keys = [];
  for (const k of Object.keys(obj).sort()) {
    const p = prefix ? `${prefix}.${k}` : k;
    const v = obj[k];
    if (v !== null && typeof v === "object" && !Array.isArray(v)) {
      keys.push(...leafPaths(v, p));
    } else {
      keys.push(p);
    }
  }
  return keys;
}

async function readJson(path) {
  const raw = await readFile(path, "utf8");
  return JSON.parse(raw);
}

function diffKeys(a, b, labelA, labelB) {
  const setA = new Set(a);
  const setB = new Set(b);
  const onlyA = [...setA].filter((k) => !setB.has(k)).sort();
  const onlyB = [...setB].filter((k) => !setA.has(k)).sort();
  if (onlyA.length || onlyB.length) {
    console.error(`[i18n] Key mismatch: ${labelA} vs ${labelB}`);
    if (onlyA.length) console.error(`  only in ${labelA}:`, onlyA.join(", "));
    if (onlyB.length) console.error(`  only in ${labelB}:`, onlyB.join(", "));
    return false;
  }
  return true;
}

async function validatePair(enPath, dePath, labelEn, labelDe) {
  const en = await readJson(enPath);
  const de = await readJson(dePath);
  const ke = leafPaths(en);
  const kd = leafPaths(de);
  return diffKeys(ke, kd, labelEn, labelDe);
}

async function validateCoreLocales() {
  const enDir = join(ROOT, "src/locales/en");
  const deDir = join(ROOT, "src/locales/de");
  let ok = true;
  const files = (await readdir(enDir)).filter((f) => f.endsWith(".json")).sort();
  for (const name of files) {
    const enPath = join(enDir, name);
    const dePath = join(deDir, name);
    try {
      await stat(dePath);
    } catch {
      console.error(`[i18n] Missing ${dePath} (pair for ${enPath})`);
      ok = false;
      continue;
    }
    const pass = await validatePair(enPath, dePath, `en/${name}`, `de/${name}`);
    ok = ok && pass;
  }
  const deExtra = (await readdir(deDir))
    .filter((f) => f.endsWith(".json"))
    .filter((f) => !files.includes(f));
  if (deExtra.length) {
    console.error("[i18n] German locale files without English counterpart:", deExtra.join(", "));
    ok = false;
  }
  return ok;
}

async function validatePluginLocales() {
  const pluginsRoot = join(ROOT, "src/plugins");
  let ok = true;
  let st;
  try {
    st = await stat(pluginsRoot);
  } catch {
    return true;
  }
  if (!st.isDirectory()) return true;

  const entries = await readdir(pluginsRoot);
  for (const name of entries) {
    if (name.startsWith("_") || name.startsWith(".")) continue;
    const dir = join(pluginsRoot, name);
    if (!(await stat(dir)).isDirectory()) continue;
    const enPath = join(dir, "locales", "en.json");
    const dePath = join(dir, "locales", "de.json");
    let enExists = false;
    let deExists = false;
    try {
      enExists = (await stat(enPath)).isFile();
    } catch {
      enExists = false;
    }
    try {
      deExists = (await stat(dePath)).isFile();
    } catch {
      deExists = false;
    }
    if (!enExists && !deExists) continue;
    if (enExists !== deExists) {
      console.error(
        `[i18n] Plugin "${name}": provide both locales/en.json and locales/de.json (or omit both).`
      );
      ok = false;
      continue;
    }
    const pass = await validatePair(enPath, dePath, `${name}/en`, `${name}/de`);
    ok = ok && pass;
  }
  return ok;
}

async function main() {
  const a = await validateCoreLocales();
  const b = await validatePluginLocales();
  if (!a || !b) {
    process.exit(1);
  }
  console.log("[i18n] Locale key parity OK (en ↔ de).");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
