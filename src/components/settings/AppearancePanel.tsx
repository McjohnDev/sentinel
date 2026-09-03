/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Check, Moon, Paintbrush, RotateCcw, Sun } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import {
  ACCENT_SWATCHES,
  APPEARANCE_PRESETS,
  HoverStrength,
  SURFACE_SWATCHES,
  SurfaceChoice,
} from '../../theme/appearance';

/**
 * Personnalisation de la coquille — barre latérale, bandeau, contenu, accent.
 *
 * Un réglage par thème, pas un réglage global : ce qui est choisi en clair
 * ne s'applique pas en sombre, et réciproquement — un dégradé pensé pour le
 * jour peut jurer une fois la nuit tombée. Le panneau édite toujours le
 * thème **actif** ; la bascule en haut à droite de l'écran en change.
 */

const HOVER_OPTIONS: Array<{ id: HoverStrength; label: string; sub: string }> = [
  { id: 'doux', label: 'Doux', sub: 'à peine perceptible' },
  { id: 'normal', label: 'Normal', sub: 'le réglage d’origine' },
  { id: 'marque', label: 'Marqué', sub: 'net, pour un thème sombre ou saturé' },
];

const Swatch: React.FC<{
  hex: string;
  active: boolean;
  onClick: () => void;
  title: string;
}> = ({ hex, active, onClick, title }) => (
  <button
    type="button"
    title={title}
    onClick={onClick}
    className="w-8 h-8 rounded-full shrink-0 grid place-items-center transition-transform"
    style={{
      background: hex,
      border: active ? '2px solid var(--color-acc)' : '1px solid var(--color-ln)',
      transform: active ? 'scale(1.08)' : 'none',
    }}
  >
    {active && (
      <Check
        className="w-3.5 h-3.5"
        style={{ color: hex.toUpperCase() > '#AAAAAA' ? '#101218' : '#FFFFFF' }}
      />
    )}
  </button>
);

const SurfaceEditor: React.FC<{
  label: string;
  hint: string;
  value: SurfaceChoice;
  onChange: (next: SurfaceChoice) => void;
  allowGradient?: boolean;
}> = ({ label, hint, value, onChange, allowGradient = true }) => (
  <div className="cbc-card p-4">
    <div className="flex items-center justify-between gap-3 mb-1">
      <span className="text-[13px] font-bold" style={{ color: 'var(--color-tx)' }}>
        {label}
      </span>
      <div className="flex rounded-lg border overflow-hidden" style={{ borderColor: 'var(--color-ln)' }}>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: 'theme' })}
          className="px-2.5 py-1 text-[11px] font-semibold"
          style={{
            background: value.mode === 'theme' ? 'var(--color-acc-t)' : 'transparent',
            color: value.mode === 'theme' ? 'var(--color-acc)' : 'var(--color-tx2)',
          }}
        >
          Suit le thème
        </button>
        <button
          type="button"
          onClick={() => onChange({ ...value, mode: 'custom' })}
          className="px-2.5 py-1 text-[11px] font-semibold border-l"
          style={{
            borderColor: 'var(--color-ln)',
            background: value.mode === 'custom' ? 'var(--color-acc-t)' : 'transparent',
            color: value.mode === 'custom' ? 'var(--color-acc)' : 'var(--color-tx2)',
          }}
        >
          Personnalisée
        </button>
      </div>
    </div>
    <p className="text-[11.5px] mt-0 mb-3" style={{ color: 'var(--color-tx3)' }}>
      {hint}
    </p>

    {value.mode === 'custom' && (
      <>
        <div className="flex flex-wrap items-center gap-2.5">
          {SURFACE_SWATCHES.map((s) => (
            <Swatch
              key={s.hex}
              hex={s.hex}
              title={s.label}
              active={value.color.toLowerCase() === s.hex.toLowerCase()}
              onClick={() => onChange({ ...value, color: s.hex })}
            />
          ))}
          <input
            type="color"
            value={/^#[0-9a-fA-F]{6}$/.test(value.color) ? value.color : '#0B1220'}
            onChange={(e) => onChange({ ...value, color: e.target.value })}
            title="Couleur personnalisée"
            className="w-8 h-8 rounded-full border-0 p-0 cursor-pointer shrink-0"
          />
        </div>
        {allowGradient && (
          <label className="flex items-center gap-2 mt-3 text-[12px] cursor-pointer" style={{ color: 'var(--color-tx2)' }}>
            <input
              type="checkbox"
              checked={value.gradient}
              onChange={(e) => onChange({ ...value, gradient: e.target.checked })}
              className="w-3.5 h-3.5"
              style={{ accentColor: 'var(--color-acc)' }}
            />
            Dégradé (assombri automatiquement vers le bas)
          </label>
        )}
      </>
    )}
  </div>
);

export const AppearancePanel: React.FC = () => {
  const { theme, toggleTheme, appearance, setAppearance, resetAppearance, applyAppearancePreset } = useApp();
  const [customAccent, setCustomAccent] = useState(appearance.accent);

  return (
    <div className="space-y-5">
      <div className="cbc-card p-6">
        <div className="flex items-start gap-4">
          <div
            className="w-10 h-10 rounded-xl grid place-items-center shrink-0"
            style={{ background: 'var(--color-acc-t)', color: 'var(--color-acc)' }}
          >
            <Paintbrush className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h3 className="text-[15px] font-extrabold tracking-tight m-0" style={{ color: 'var(--color-tx)' }}>
                Apparence
              </h3>
              <span
                className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold"
                style={{ background: 'var(--color-ln2)', color: 'var(--color-tx2)' }}
              >
                {theme === 'dark' ? <Moon className="w-3 h-3" /> : <Sun className="w-3 h-3" />}
                Vous éditez le thème {theme === 'dark' ? 'sombre' : 'clair'}
              </span>
            </div>
            <p className="text-[12.5px] mt-2 leading-relaxed max-w-3xl mb-0" style={{ color: 'var(--color-tx2)' }}>
              Chaque réglage est propre au thème actif — ce qui est choisi ici
              ne s’applique pas à l’autre. Basculez avec le bouton{' '}
              {theme === 'dark' ? <Sun className="w-3.5 h-3.5 inline -mt-0.5" /> : <Moon className="w-3.5 h-3.5 inline -mt-0.5" />}{' '}
              en haut à droite pour régler l’autre thème.
            </p>

            <div className="flex items-center gap-2 mt-4">
              <button
                type="button"
                onClick={toggleTheme}
                className="cbc-btn-secondary py-1.5 px-3 text-[12px]"
              >
                Éditer le thème {theme === 'dark' ? 'clair' : 'sombre'}
              </button>
              <button
                type="button"
                onClick={resetAppearance}
                className="cbc-btn-secondary py-1.5 px-3 text-[12px] inline-flex items-center gap-1.5"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Réinitialiser ce thème
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="cbc-card p-5">
        <h4 className="text-[13px] font-bold mb-1" style={{ color: 'var(--color-tx)' }}>
          Thèmes proposés
        </h4>
        <p className="text-[11.5px] mb-3" style={{ color: 'var(--color-tx3)' }}>
          Chaque thème règle en un geste l’accent, la barre, le bandeau et le
          contenu — pour le clair et le sombre à la fois. Modifiable ensuite
          en détail ci-dessous.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {APPEARANCE_PRESETS.map((preset) => {
            const cfg = theme === 'dark' ? preset.dark : preset.light;
            const sidebarBg =
              cfg.sidebar.mode === 'custom' ? cfg.sidebar.color : theme === 'dark' ? '#12151C' : '#FFFFFF';
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => applyAppearancePreset(preset)}
                className="rounded-xl border overflow-hidden text-left cbc-hover"
                style={{ borderColor: 'var(--color-ln)' }}
              >
                <div className="h-14 flex" style={{ background: cfg.accent }}>
                  <div className="w-1/3 h-full" style={{ background: sidebarBg }} />
                </div>
                <div className="p-2.5">
                  <div className="text-[12px] font-bold" style={{ color: 'var(--color-tx)' }}>
                    {preset.label}
                  </div>
                  <div className="text-[10.5px] mt-0.5 leading-snug" style={{ color: 'var(--color-tx3)' }}>
                    {preset.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div className="cbc-card p-4">
        <span className="text-[13px] font-bold block mb-1" style={{ color: 'var(--color-tx)' }}>
          Accent
        </span>
        <p className="text-[11.5px] mt-0 mb-3" style={{ color: 'var(--color-tx3)' }}>
          Boutons pleins, liens, entrée active du menu, anneau de focus.
        </p>
        <div className="flex flex-wrap items-center gap-2.5">
          {ACCENT_SWATCHES.map((s) => (
            <Swatch
              key={s.hex}
              hex={s.hex}
              title={s.label}
              active={appearance.accent.toLowerCase() === s.hex.toLowerCase()}
              onClick={() => setAppearance({ accent: s.hex })}
            />
          ))}
          <input
            type="color"
            value={/^#[0-9a-fA-F]{6}$/.test(customAccent) ? customAccent : '#A68523'}
            onChange={(e) => {
              setCustomAccent(e.target.value);
              setAppearance({ accent: e.target.value });
            }}
            title="Couleur personnalisée"
            className="w-8 h-8 rounded-full border-0 p-0 cursor-pointer shrink-0"
          />
        </div>
      </div>

      <SurfaceEditor
        label="Barre latérale"
        hint="Le badge CBC et les icônes s’adaptent automatiquement à la couleur choisie."
        value={appearance.sidebar}
        onChange={(sidebar) => setAppearance({ sidebar })}
      />
      <SurfaceEditor
        label="Bandeau"
        hint="La barre du haut — indépendante de la barre latérale."
        value={appearance.navbar}
        onChange={(navbar) => setAppearance({ navbar })}
      />
      <SurfaceEditor
        label="Contenu"
        hint="Un lavis léger sur le fond des écrans — jamais une recoloration complète : le texte de l’application suppose un fond neutre."
        value={{ mode: appearance.content.mode, color: appearance.content.color, gradient: false }}
        onChange={(next) => setAppearance({ content: { mode: next.mode, color: next.color } })}
        allowGradient={false}
      />

      <div className="cbc-card p-4">
        <span className="text-[13px] font-bold block mb-1" style={{ color: 'var(--color-tx)' }}>
          Intensité du survol
        </span>
        <p className="text-[11.5px] mt-0 mb-3" style={{ color: 'var(--color-tx3)' }}>
          À quel point une ligne ou un bouton se distingue au passage de la souris.
        </p>
        <div className="grid grid-cols-3 gap-2">
          {HOVER_OPTIONS.map((opt) => (
            <button
              key={opt.id}
              type="button"
              onClick={() => setAppearance({ hover: opt.id })}
              className="rounded-lg border p-2.5 text-left"
              style={{
                borderColor: appearance.hover === opt.id ? 'var(--color-acc-b)' : 'var(--color-ln)',
                background: appearance.hover === opt.id ? 'var(--color-acc-t)' : 'transparent',
              }}
            >
              <div
                className="text-[12px] font-semibold"
                style={{ color: appearance.hover === opt.id ? 'var(--color-acc)' : 'var(--color-tx)' }}
              >
                {opt.label}
              </div>
              <div className="text-[10.5px] mt-0.5" style={{ color: 'var(--color-tx3)' }}>
                {opt.sub}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
