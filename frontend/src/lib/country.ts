// Country helpers for ISO 3166-1 alpha-2 codes such as "MY".

let displayNames: Intl.DisplayNames | null = null;

/** "MY" -> "Malaysia". Falls back to the code when the browser can't name it. */
export function countryName(code?: string | null): string {
  if (!code) return "";
  const cc = code.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(cc)) return code;
  try {
    displayNames ??= new Intl.DisplayNames(["en"], { type: "region" });
    return displayNames.of(cc) || cc;
  } catch {
    return cc;
  }
}

/** "MY" -> 🇲🇾 (regional indicator symbols). Empty for anything else. */
export function countryFlag(code?: string | null): string {
  if (!code) return "";
  const cc = code.trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(cc)) return "";
  return String.fromCodePoint(...Array.from(cc).map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}
