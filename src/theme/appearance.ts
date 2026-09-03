/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

/**
 * Personnalisation visuelle de la coquille — barre latérale, en-tête,
 * contenu — indépendamment du choix clair/sombre.
 *
 * Le clair/sombre reste un jeu de jetons figé (`src/index.css`) : c'est la
 * lisibilité de référence, jamais cassée. Ce module ajoute une **surcharge**
 * par-dessus, propre à chaque thème (le choix fait en clair ne s'applique
 * pas en sombre, et réciproquement) : une barre marine convient aux deux,
 * un dégradé pensé pour le clair peut jurer une fois la nuit tombée.
 *
 * Une surface personnalisée calcule elle-même son texte lisible plutôt que
 * de laisser l'exploitant choisir une combinaison illisible : `isDark`
 * décide entre texte clair et texte sombre par luminance relative, pas par
 * une case à cocher de plus.
 */

export interface SurfaceChoice {
  mode: 'theme' | 'custom';
  color: string;
  gradient: boolean;
}

export type HoverStrength = 'doux' | 'normal' | 'marque';

export interface AppearanceConfig {
  accent: string;
  sidebar: SurfaceChoice;
  navbar: SurfaceChoice;
  /** Teinte légère du fond de contenu — jamais une recoloration complète :
   *  le texte courant de toute l'application suppose un fond clair (thème
   *  clair) ou sombre (thème sombre), une surface qui inverserait ce
   *  contraste casserait la lisibilité loin de ce panneau. */
  content: { mode: 'theme' | 'custom'; color: string };
  hover: HoverStrength;
}

export const HOVER_ALPHA: Record<HoverStrength, number> = {
  doux: 0.045,
  normal: 0.075,
  marque: 0.13,
};

function clampByte(n: number): number {
  return Math.max(0, Math.min(255, Math.round(n)));
}

function parseHex(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(hex.trim());
  if (!m) return null;
  const v = m[1];
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
}

function toHex([r, g, b]: [number, number, number]): string {
  return '#' + [r, g, b].map((c) => clampByte(c).toString(16).padStart(2, '0')).join('');
}

/** Luminance relative (WCAG), pour choisir un texte clair ou sombre. */
export function relLuminance(hex: string): number {
  const rgb = parseHex(hex);
  if (!rgb) return 1;
  const lin = (v: number) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const [r, g, b] = rgb;
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

export function isDarkColor(hex: string): boolean {
  return relLuminance(hex) < 0.4;
}

/** Mélange vers le noir (ratio 0–1), pour un second point de dégradé
 *  toujours plus sombre que la couleur choisie — quelle qu'elle soit. */
export function darken(hex: string, ratio: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  return toHex([rgb[0] * (1 - ratio), rgb[1] * (1 - ratio), rgb[2] * (1 - ratio)]);
}

/** Mélange vers le blanc (ratio 0–1) — variante « bouton plein » de l'accent. */
export function lighten(hex: string, ratio: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  return toHex([
    rgb[0] + (255 - rgb[0]) * ratio,
    rgb[1] + (255 - rgb[1]) * ratio,
    rgb[2] + (255 - rgb[2]) * ratio,
  ]);
}

export function withAlpha(hex: string, alpha: number): string {
  const rgb = parseHex(hex);
  if (!rgb) return hex;
  return `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha})`;
}

export interface ResolvedSurface {
  background: string;
  fg: string;
  fg2: string;
  fg3: string;
  hover: string;
  ln: string;
  accT: string;
}

/**
 * Traduit un choix de surface en valeurs CSS effectives.
 *
 * `themeBg` porte la variable de repli (`var(--color-panel)`) : une surface
 * qui « suit le thème » ne fige rien, elle continue de basculer avec le
 * clair/sombre global.
 */
export function resolveSurface(
  choice: SurfaceChoice,
  themeBgVar: string,
  accent: string,
  hover: HoverStrength
): ResolvedSurface {
  if (choice.mode !== 'custom' || !choice.color) {
    return {
      background: themeBgVar,
      fg: 'var(--color-tx)',
      fg2: 'var(--color-tx2)',
      fg3: 'var(--color-tx3)',
      hover: 'var(--color-ln2)',
      ln: 'var(--color-ln)',
      accT: 'var(--color-acc-t)',
    };
  }
  const dark = isDarkColor(choice.color);
  const fg = dark ? '#F4F6FA' : '#101218';
  const fg2 = dark ? withAlpha('#FFFFFF', 0.7) : withAlpha('#101218', 0.62);
  const fg3 = dark ? withAlpha('#FFFFFF', 0.44) : withAlpha('#101218', 0.4);
  const hoverAlpha = HOVER_ALPHA[hover] * (dark ? 2.2 : 1);
  return {
    background: choice.gradient
      ? `linear-gradient(165deg, ${choice.color}, ${darken(choice.color, 0.24)})`
      : choice.color,
    fg,
    fg2,
    fg3,
    hover: dark ? withAlpha('#FFFFFF', hoverAlpha) : withAlpha('#101218', hoverAlpha),
    ln: dark ? withAlpha('#FFFFFF', 0.12) : withAlpha('#101218', 0.1),
    accT: withAlpha(accent, dark ? 0.22 : 0.12),
  };
}

export function defaultAppearance(theme: 'light' | 'dark'): AppearanceConfig {
  return {
    accent: theme === 'dark' ? '#D8B458' : '#A68523',
    sidebar: { mode: 'theme', color: '#0B1220', gradient: false },
    navbar: { mode: 'theme', color: '#0B1220', gradient: false },
    content: { mode: 'theme', color: theme === 'dark' ? '#141A24' : '#EEF1F6' },
    hover: 'normal',
  };
}

export const SURFACE_SWATCHES: Array<{ label: string; hex: string }> = [
  { label: 'Marine', hex: '#0B1220' },
  { label: 'Ardoise', hex: '#1E2530' },
  { label: 'Anthracite', hex: '#15171C' },
  { label: 'Or profond', hex: '#5A4413' },
  { label: 'Bleu nuit', hex: '#1B2A55' },
  { label: 'Émeraude', hex: '#0F3D2E' },
  { label: 'Bordeaux', hex: '#54182A' },
  { label: 'Violet', hex: '#331B54' },
  { label: 'Ivoire', hex: '#F6F3EA' },
  { label: 'Brume', hex: '#EEF1F6' },
];

export const ACCENT_SWATCHES: Array<{ label: string; hex: string }> = [
  { label: 'Or CBC', hex: '#A68523' },
  { label: 'Bleu', hex: '#2E6BD6' },
  { label: 'Émeraude', hex: '#0E8F62' },
  { label: 'Violet', hex: '#7C3AED' },
  { label: 'Rose', hex: '#DB2777' },
  { label: 'Ambre', hex: '#B45309' },
];

export interface AppearancePreset {
  id: string;
  label: string;
  description: string;
  light: AppearanceConfig;
  dark: AppearanceConfig;
}

/**
 * Un préréglage fixe les DEUX thèmes en un geste : choisir « Aurore » ne
 * doit pas laisser le mode sombre sur un dégradé pensé pour le jour.
 */
export const APPEARANCE_PRESETS: AppearancePreset[] = [
  {
    id: 'cbc',
    label: 'Or CBC',
    description: 'Le réglage d’origine — barre et bandeau suivent le thème.',
    light: defaultAppearance('light'),
    dark: defaultAppearance('dark'),
  },
  {
    id: 'marine',
    label: 'Marine',
    description: 'Barre latérale et bandeau en marine profond, accent or.',
    light: {
      accent: '#A68523',
      sidebar: { mode: 'custom', color: '#0B1220', gradient: true },
      navbar: { mode: 'custom', color: '#0B1220', gradient: false },
      content: { mode: 'theme', color: '#EEF1F6' },
      hover: 'normal',
    },
    dark: {
      accent: '#D8B458',
      sidebar: { mode: 'custom', color: '#060A12', gradient: true },
      navbar: { mode: 'custom', color: '#060A12', gradient: false },
      content: { mode: 'theme', color: '#141A24' },
      hover: 'normal',
    },
  },
  {
    id: 'ardoise',
    label: 'Ardoise',
    description: 'Gris sourd, accent bleu — sobre, sans doré.',
    light: {
      accent: '#2E6BD6',
      sidebar: { mode: 'custom', color: '#1E2530', gradient: false },
      navbar: { mode: 'theme', color: '#0B1220', gradient: false },
      content: { mode: 'theme', color: '#EEF1F6' },
      hover: 'doux',
    },
    dark: {
      accent: '#6CA8FF',
      sidebar: { mode: 'custom', color: '#12161D', gradient: false },
      navbar: { mode: 'theme', color: '#0B1220', gradient: false },
      content: { mode: 'theme', color: '#141A24' },
      hover: 'doux',
    },
  },
  {
    id: 'aurore',
    label: 'Aurore',
    description: 'Dégradé violet vers rose — le plus marqué des quatre.',
    light: {
      accent: '#7C3AED',
      sidebar: { mode: 'custom', color: '#3B1E5E', gradient: true },
      navbar: { mode: 'custom', color: '#3B1E5E', gradient: true },
      content: { mode: 'theme', color: '#F5F0FB' },
      hover: 'marque',
    },
    dark: {
      accent: '#C77DFF',
      sidebar: { mode: 'custom', color: '#241236', gradient: true },
      navbar: { mode: 'custom', color: '#241236', gradient: true },
      content: { mode: 'theme', color: '#18101F' },
      hover: 'marque',
    },
  },
];
