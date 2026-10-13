import i18n from '../i18n';

// Many screens carry their copy as one "English / हिंदी" string. These helpers show only the half that matches the
// language the user picked: Hindi when it is Hindi, English for every other language.

const DEVANAGARI = /[ऀ-ॿ]/;
const LATIN = /[A-Za-z]/;
const SEPARATORS = [' / ', ' | ', ' - ', ' – '];

export function currentLanguage() {
  const lng = i18n.resolvedLanguage || i18n.language;
  if (lng) return lng;
  try {
    return localStorage.getItem('airyatra_lang') || 'en';
  } catch {
    return 'en';
  }
}

export const isHindi = () => currentLanguage().startsWith('hi');

const isHindiPart = (s) => DEVANAGARI.test(s);
const isEnglishPart = (s) => !DEVANAGARI.test(s) && LATIN.test(s);

// Returns [english, hindi] when the text holds both, otherwise null.
export function splitBilingual(text) {
  const s = text.trim();
  for (const sep of SEPARATORS) {
    if (!s.includes(sep)) continue;
    const parts = s.split(sep);
    for (let i = 1; i < parts.length; i += 1) {
      const a = parts.slice(0, i).join(sep).trim();
      const b = parts.slice(i).join(sep).trim();
      if (isHindiPart(a) && isEnglishPart(b)) return [b, a];
      if (isHindiPart(b) && isEnglishPart(a)) return [a, b];
    }
  }
  const m = s.match(/^([\s\S]*?)\s*\(([^()]*)\)\s*([\s\S]*)$/);
  if (m) {
    const outside = `${m[1]} ${m[3]}`.trim();
    const inside = m[2].trim();
    if (isHindiPart(outside) && isEnglishPart(inside)) return [inside, outside];
    if (isHindiPart(inside) && isEnglishPart(outside)) return [outside, inside];
  }
  return null;
}

// "Bank Accounts / बैंक खाते" -> "Bank Accounts" in English, "बैंक खाते" in Hindi.
export function bi(text) {
  if (typeof text !== 'string' || !DEVANAGARI.test(text)) return text;
  const pair = splitBilingual(text);
  if (!pair) return text;
  return isHindi() ? pair[1] : pair[0];
}

// For copy kept as two separate values: tr('Approved', 'स्वीकृत').
export const tr = (en, hi) => (isHindi() && hi ? hi : en);
