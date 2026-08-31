/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useMemo, useState } from 'react';
import { Plus, Terminal, X } from 'lucide-react';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';
import { SegmentedControl } from '../components/layout/SegmentedControl';

type Mode = 'intention' | 'guide' | 'expert';
type Sub = 'modeles' | 'groupes' | 'plugins';
type Tolerance = 'Calme' | 'Standard' | 'Vigilant';

const BLUEPRINTS = [
  { name: 'Serveur Oracle', meta: 'RHEL 9 · 7 plugins', desc: 'Partitions /u01 et /u02, listener et processus Oracle.', noise: 'Vigilant', official: true },
  { name: 'Hôte SWIFT', meta: 'Windows Server 2022 · 8 plugins', desc: 'Services Alliance et fichiers officiels. Service arrêté = majeur.', noise: 'Vigilant', official: true },
  { name: 'Serveur applicatif e-Banking', meta: 'Ubuntu 22.04 · 6 plugins', desc: 'API, nginx et volumes de journaux applicatifs.', noise: 'Standard', official: false },
  { name: 'Contrôleur de domaine', meta: 'Windows Server 2022 · 7 plugins', desc: 'Réplication, services NTDS/DNS et disque des journaux.', noise: 'Standard', official: false },
  { name: "Passerelle d'agence", meta: 'AlmaLinux 9 · 4 plugins', desc: 'Liaison agence, présence en heures ouvrées.', noise: 'Calme', official: false },
  { name: 'Poste de développement', meta: 'macOS · 4 plugins', desc: 'Poste de travail, surveillance légère sans réveil nocturne.', noise: 'Calme', official: false },
];

const PLUGIN_DEF: Array<{ id: string; enabled: boolean; priv: string; lvl: 'L0' | 'L1' }> = [
  { id: 'cpu', enabled: true, priv: 'none', lvl: 'L0' },
  { id: 'memory', enabled: true, priv: 'none', lvl: 'L0' },
  { id: 'disk', enabled: true, priv: 'none', lvl: 'L0' },
  { id: 'network', enabled: true, priv: 'none', lvl: 'L0' },
  { id: 'process', enabled: true, priv: 'none', lvl: 'L0' },
  { id: 'services', enabled: true, priv: 'read', lvl: 'L0' },
  { id: 'files', enabled: true, priv: 'read', lvl: 'L0' },
  { id: 'logs', enabled: false, priv: 'read', lvl: 'L0' },
  { id: 'service.manage', enabled: false, priv: 'admin', lvl: 'L1' },
];

const STEPS = ['Identité', 'Métier', 'Présence', 'Collecte', 'Critique', 'Tolérance', 'Revue'];
const TOL = {
  Calme: { minutes: '15 minutes', severity: 'mineure', delay: '15 min', desc: "J'accepte plus de délai, moins de bruit" },
  Standard: { minutes: '5 minutes', severity: 'majeure', delay: '5 min', desc: 'Équilibre exploitation CBC' },
  Vigilant: { minutes: '2 minutes', severity: 'critique', delay: '2 min', desc: 'SWIFT / critique métier' },
} as const;

const noiseColor = (n: string) => (n === 'Vigilant' ? '#E11D48' : n === 'Standard' ? '#D97706' : '#059669');

const PluginGrid: React.FC<{ toggles: Record<string, boolean>; onToggle: (id: string) => void }> = ({
  toggles,
  onToggle,
}) => (
  <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
    {PLUGIN_DEF.map((p) => {
      const on = toggles[p.id] ?? p.enabled;
      return (
        <div key={p.id} className="cbc-card p-[15px]">
          <div className="flex items-center justify-between gap-2">
            <span className="tnum text-[13px] font-bold">{p.id}</span>
            <button
              type="button"
              onClick={() => onToggle(p.id)}
              className={`w-[34px] h-5 rounded-[10px] relative shrink-0 ${on ? 'bg-[#D0B335]' : 'bg-slate-300'}`}
              aria-pressed={on}
            >
              <span className={`absolute top-[3px] w-3.5 h-3.5 rounded-full bg-white ${on ? 'left-[17px]' : 'left-[3px]'}`} />
            </button>
          </div>
          <div className="tnum text-[11px] text-slate-400 mt-2">{p.enabled ? 'v1.2.0 · 60 s' : 'v1.2.0 · —'}</div>
          <div className="flex items-center gap-1.5 mt-2.5">
            <span className={`px-1.5 py-0.5 rounded-md text-[10px] font-bold ${p.lvl === 'L1' ? 'bg-slate-100 text-slate-500' : 'bg-emerald-50 text-emerald-700'}`}>
              {p.lvl}
            </span>
            <span className="text-[10.5px] text-slate-400">privilège {p.priv}</span>
          </div>
          {p.lvl === 'L1' && <div className="text-[10.5px] font-semibold text-slate-400 mt-2">Lot 2</div>}
        </div>
      );
    })}
  </div>
);

export const StudioView: React.FC = () => {
  const { agents, addToast, currentRole } = useApp();
  const [mode, setMode] = useState<Mode>('intention');
  const [sub, setSub] = useState<Sub>('modeles');
  const [step, setStep] = useState(6);
  const [tol, setTol] = useState<Tolerance>('Standard');
  const [applyName, setApplyName] = useState<string | null>(null);
  const [applyScope, setApplyScope] = useState<'nouveau' | 'existant' | 'hote'>('existant');
  const [toggles, setToggles] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(PLUGIN_DEF.map((p) => [p.id, p.enabled]))
  );

  const groups = useMemo(() => {
    const byLoc = new Map<string, string[]>();
    for (const a of agents) {
      const key = a.location || 'Global';
      byLoc.set(key, [...(byLoc.get(key) || []), a.name]);
    }
    if (byLoc.size === 0) {
      return [];
    }
    return [...byLoc.entries()].map(([name, hosts], i) => ({
      name,
      hosts: hosts.slice(0, 2).join(' · '),
      blueprint: i === 0 ? 'Hôte SWIFT' : 'Serveur applicatif e-Banking',
      version: `v${10 + (i % 3)}`,
    }));
  }, [agents]);

  const togglePlugin = (id: string) => setToggles((prev) => ({ ...prev, [id]: !prev[id] }));
  const canEdit = currentRole === 'Admin';

  return (
    <div className="space-y-5">
      <PageHeader
        title="Studio Agent"
        subtitle="Configurer la supervision sans YAML."
        secondaryActions={
          <SegmentedControl
            options={[
              { id: 'intention', label: 'Intention', active: mode === 'intention', onClick: () => setMode('intention') },
              { id: 'guide', label: 'Guidé', active: mode === 'guide', onClick: () => setMode('guide') },
              { id: 'expert', label: 'Expert', active: mode === 'expert', onClick: () => setMode('expert') },
            ]}
          />
        }
      />

      {mode === 'intention' && (
        <>
          <div className="flex gap-0.5 border-b border-slate-200">
            {(
              [
                ['modeles', 'Modèles'],
                ['groupes', 'Groupes'],
                ['plugins', 'Plugins'],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setSub(id)}
                className={`px-3.5 py-2.5 border-0 bg-transparent text-[12.5px] border-b-2 ${
                  sub === id ? 'border-[#D0B335] text-slate-900 font-bold' : 'border-transparent text-slate-500 font-semibold'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {sub === 'modeles' && (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
              {BLUEPRINTS.map((b) => (
                <div
                  key={b.name}
                  className={`cbc-card p-[18px] flex flex-col min-h-[196px] ${b.official ? 'border-[#D0B335]/30' : ''}`}
                >
                  <div className="flex items-start justify-between gap-2.5">
                    <div className="text-[14.5px] font-bold tracking-tight">{b.name}</div>
                    {b.official && (
                      <span className="px-2 py-0.5 rounded-md bg-[#D0B335]/10 border border-[#D0B335]/30 text-[#A68523] text-[10px] font-bold tracking-wide shrink-0">
                        CBC
                      </span>
                    )}
                  </div>
                  <div className="tnum text-[11.5px] text-slate-400 mt-2">{b.meta}</div>
                  <div className="text-[12.5px] leading-relaxed text-slate-600 mt-2.5 flex-1">{b.desc}</div>
                  <div className="flex items-center justify-between gap-2.5 mt-3.5">
                    <span className="inline-flex items-center gap-1.5 text-[11.5px] font-semibold text-slate-600">
                      <span className="w-1.5 h-1.5 rounded-full" style={{ background: noiseColor(b.noise) }} />
                      Bruit : {b.noise}
                    </span>
                    {canEdit && (
                      <button type="button" className="cbc-btn-secondary py-1.5" onClick={() => setApplyName(b.name)}>
                        Appliquer
                      </button>
                    )}
                  </div>
                </div>
              ))}
              <button
                type="button"
                onClick={() => {
                  setMode('guide');
                  setStep(1);
                }}
                className="min-h-[196px] rounded-xl border-[1.5px] border-dashed border-slate-300 bg-transparent flex flex-col items-center justify-center gap-2.5 text-slate-500 hover:border-[#D0B335] hover:text-[#A68523] hover:bg-[#D0B335]/[0.04]"
              >
                <Plus className="w-[22px] h-[22px]" />
                <span className="text-[13px] font-bold">Personnalisé</span>
                <span className="text-[11.5px] leading-relaxed text-center max-w-[24ch]">Partir d'un modèle vierge et passer par le Guidé</span>
              </button>
            </div>
          )}

          {sub === 'groupes' && (
            <div className="cbc-card overflow-hidden max-w-[720px]">
              <div className="px-[18px] py-3.5 border-b border-slate-200">
                <h2 className="text-sm font-bold m-0">Groupes</h2>
                <p className="text-xs leading-relaxed text-[#777] mt-1.5 mb-0">
                  Un hôte hérite de son groupe, qui hérite du global. Une surcharge locale prime toujours.
                </p>
              </div>
              {groups.length === 0 ? (
                <div className="px-[18px] py-10 text-center">
                  <div className="text-[13px] font-bold">Aucun groupe pour l'instant</div>
                  <div className="text-[12px] text-[#777] mt-1.5">
                    Les groupes apparaîtront lorsque des agents réels seront enrôlés.
                  </div>
                </div>
              ) : (
                groups.map((g) => (
                <div key={g.name} className="flex items-center justify-between px-[18px] py-3.5 border-b border-slate-50 last:border-0">
                  <div>
                    <div className="text-[13px] font-bold">{g.name}</div>
                    <div className="text-[11.5px] text-[#777] mt-1">
                      {g.hosts} · modèle {g.blueprint}
                    </div>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <span className="tnum text-[11.5px] text-slate-500">{g.version}</span>
                    <button
                      type="button"
                      className="cbc-btn-secondary py-1.5"
                      onClick={() => {
                        setMode('guide');
                        setStep(6);
                      }}
                    >
                      Ouvrir
                    </button>
                  </div>
                </div>
              ))
              )}
            </div>
          )}

          {sub === 'plugins' && <PluginGrid toggles={toggles} onToggle={canEdit ? togglePlugin : () => undefined} />}
        </>
      )}

      {mode === 'guide' && (
        <div className="grid grid-cols-1 xl:grid-cols-[216px_1fr_320px] gap-5 items-start">
          <div className="cbc-card p-4">
            {STEPS.map((label, i) => {
              const num = i + 1;
              const done = num < step;
              const cur = num === step;
              return (
                <button
                  key={label}
                  type="button"
                  onClick={() => setStep(num)}
                  className={`w-full text-left flex items-center gap-2.5 px-2.5 py-2 rounded-lg border-0 mb-0.5 ${cur ? 'bg-[#D0B335]/10' : 'bg-transparent hover:bg-slate-50'}`}
                >
                  <span
                    className={`w-5 h-5 rounded-full grid place-items-center text-[10.5px] font-bold shrink-0 border-[1.5px] ${
                      done ? 'bg-emerald-600 border-emerald-600 text-white' : cur ? 'bg-[#D0B335] border-[#D0B335] text-white' : 'bg-white border-slate-300 text-slate-400'
                    }`}
                  >
                    {done ? '✓' : num}
                  </span>
                  <span className={`text-[12.5px] ${cur ? 'font-bold text-slate-900' : done ? 'font-semibold text-slate-600' : 'font-semibold text-slate-400'}`}>
                    {num}. {label}
                  </span>
                </button>
              );
            })}
          </div>

          <div>
            {step === 6 && (
              <div className="cbc-card p-6">
                <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">Étape 6 · Tolérance</div>
                <h2 className="text-[19px] font-extrabold tracking-tight mt-2.5 mb-0">À partir de quand vous réveiller ?</h2>
                <p className="text-[13px] leading-relaxed text-[#777] mt-2 mb-5">
                  La durée évite les fausses alertes sur un pic ponctuel. Choisissez un profil, ajustable ensuite règle par règle.
                </p>
                <div className="flex flex-col gap-2.5">
                  {(Object.keys(TOL) as Tolerance[]).map((name) => {
                    const on = tol === name;
                    const t = TOL[name];
                    return (
                      <button
                        key={name}
                        type="button"
                        onClick={() => setTol(name)}
                        className={`text-left cursor-pointer rounded-xl px-[19px] py-[17px] flex items-center gap-[18px] border-[1.5px] ${
                          on ? 'bg-[#D0B335]/10 border-[#D0B335]' : 'bg-white border-slate-200'
                        }`}
                      >
                        <span className={`w-5 h-5 rounded-full border-[1.5px] grid place-items-center shrink-0 ${on ? 'border-[#D0B335]' : 'border-slate-300'}`}>
                          <span className={`w-2 h-2 rounded-full ${on ? 'bg-[#D0B335]' : 'bg-transparent'}`} />
                        </span>
                        <span className="flex-1">
                          <span className="block text-[14.5px] font-bold">{name}</span>
                          <span className="block text-[12.5px] leading-relaxed text-slate-500 mt-1">{t.desc}</span>
                        </span>
                        <span className={`tnum text-[17px] font-extrabold shrink-0 ${on ? 'text-[#A68523]' : 'text-slate-400'}`}>{t.delay}</span>
                      </button>
                    );
                  })}
                </div>
                <div className="mt-5 px-[18px] py-4 rounded-xl bg-[#D0B335]/10 border border-[#D0B335]/30">
                  <div className="text-[10.5px] font-bold uppercase tracking-wider text-[#A68523] mb-2">Ce que cela veut dire</div>
                  <div className="text-[13.5px] leading-relaxed text-[#3F3007]">
                    Si le CPU dépasse <strong>90 % pendant {TOL[tol].minutes}</strong>, une alerte <strong>{TOL[tol].severity}</strong> part vers{' '}
                    <strong>Mail DSI</strong> et le scénario <strong>CPU durable</strong>.
                  </div>
                </div>
                <div className="flex justify-between gap-2.5 mt-6 pt-5 border-t border-slate-50">
                  <button type="button" className="cbc-btn-secondary" onClick={() => setStep(Math.max(1, step - 1))}>
                    Retour
                  </button>
                  <button type="button" className="cbc-btn-primary" onClick={() => setStep(7)}>
                    Continuer vers la revue
                  </button>
                </div>
              </div>
            )}

            {step === 7 && (
              <div className="cbc-card p-6">
                <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">Étape 7 · Revue</div>
                <h2 className="text-[19px] font-extrabold tracking-tight mt-2.5 mb-0">Ce qui sera publié</h2>
                <p className="text-[13px] leading-relaxed text-[#777] mt-2 mb-5">Comparaison avec la configuration active du groupe.</p>
                <div className="grid grid-cols-2 gap-0 border border-slate-200 rounded-xl overflow-hidden">
                  <div className="border-r border-slate-200">
                    <div className="tnum px-3.5 py-2.5 bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500">v12 — active</div>
                    {['cpu.duration: 0 s', 'cpu.threshold: 90 %', 'severity: majeure', 'ram.threshold: 80 %', 'channels: mail', 'playbook: —'].map((text, i) => (
                      <div key={text} className={`tnum px-3.5 py-[7px] text-xs ${i === 0 || i >= 4 ? 'text-rose-800' : 'text-slate-600'}`}>
                        {text}
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="tnum px-3.5 py-2.5 bg-slate-50 border-b border-slate-200 text-[11px] font-bold text-slate-500">v13 — proposée</div>
                    {[
                      `cpu.duration: ${TOL[tol].minutes}`,
                      'cpu.threshold: 90 %',
                      `severity: ${TOL[tol].severity}`,
                      'ram.threshold: 80 %',
                      'channels: sysadmin@cbcam.cm',
                      'playbook: CPU durable',
                    ].map((text, i) => (
                      <div key={text} className={`tnum px-3.5 py-[7px] text-xs ${i === 0 || i >= 4 ? 'text-emerald-700' : 'text-slate-600'}`}>
                        {text}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="mt-[18px] px-[18px] py-4 rounded-xl bg-emerald-50 border border-emerald-200">
                  <div className="text-[10.5px] font-bold uppercase tracking-wider text-emerald-700 mb-2">Impact estimé</div>
                  <div className="text-[13.5px] leading-relaxed text-emerald-800">
                    Cette règle aurait ouvert <strong>2 alertes hier</strong> (au lieu de 14 avec un seuil instantané).
                  </div>
                </div>
                <div className="flex justify-between gap-2.5 mt-6 pt-5 border-t border-slate-50">
                  <button type="button" className="cbc-btn-secondary" onClick={() => setStep(6)}>
                    Retour
                  </button>
                  <button
                    type="button"
                    className="cbc-btn-primary"
                    // Cet écran est une maquette d'éditeur : il ne dispose
                    // d'aucun canal de publication. Le bouton affichait
                    // « Configuration publiée » sans rien envoyer aux hôtes.
                    // La publication réelle, versionnée et réversible, se fait
                    // dans Paramètres → Groupes & config.
                    onClick={() =>
                      addToast({
                        type: 'info',
                        title: 'Publication indisponible ici',
                        message:
                          'Utiliser Paramètres → Groupes & config pour publier une version aux hôtes.',
                      })
                    }
                  >
                    Publier (indisponible)
                  </button>
                </div>
              </div>
            )}

            {step < 6 && (
              <div className="cbc-card py-14 px-8 text-center">
                <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">Étape {step}</div>
                <div className="text-base font-extrabold mt-3">
                  {STEPS[step - 1]} — déjà renseignée
                </div>
                <p className="text-[12.5px] leading-relaxed text-[#777] mt-2 mx-auto max-w-md">
                  Les étapes Identité à Critique sont préremplies. Passez à la tolérance puis à la revue.
                </p>
                <button type="button" className="cbc-btn-secondary mt-5" onClick={() => setStep(6)}>
                  Aller à l'étape 6
                </button>
              </div>
            )}
          </div>

          <div className="cbc-card p-[18px] xl:sticky xl:top-6">
            <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400">Récapitulatif</div>
            {[
              { k: 'Hôte', v: agents[0]?.hostname || 'Groupe SWIFT' },
              { k: 'Rôle métier', v: 'Serveur — passerelle SWIFT (zone sécurisée)' },
              { k: 'Présence attendue', v: '24×7' },
              { k: 'Collecte', v: 'cpu · memory · disk · services · files' },
              { k: 'Tolérance', v: `${tol} · ${TOL[tol].minutes}` },
            ].map((r) => (
              <div key={r.k} className="py-3 border-b border-slate-50">
                <div className="text-[11px] font-semibold text-slate-400">{r.k}</div>
                <div className="tnum text-[12.5px] leading-relaxed text-slate-900 mt-1">{r.v}</div>
              </div>
            ))}
            <p className="text-[11.5px] leading-relaxed text-slate-400 mt-3.5 mb-0">Publication versionnée — un push sera envoyé aux hôtes du groupe.</p>
          </div>
        </div>
      )}

      {mode === 'expert' && (
        <>
          <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-slate-50 border border-slate-200">
            <Terminal className="w-4 h-4 text-slate-600 shrink-0" />
            <span className="text-[12.5px] text-slate-600">Mode expert — manifestes de plugins et intervalles. Réservé aux administrateurs DSI.</span>
          </div>
          <PluginGrid toggles={toggles} onToggle={canEdit ? togglePlugin : () => undefined} />
        </>
      )}

      {applyName && (
        <>
          <div className="fixed inset-0 z-40 bg-slate-950/40 animate-fade-in" onClick={() => setApplyName(null)} />
          <div className="fixed inset-0 z-50 grid place-items-center p-6 pointer-events-none">
            <div className="w-full max-w-lg bg-white rounded-2xl overflow-hidden pointer-events-auto animate-modal-in">
              <div className="px-6 py-5 border-b border-slate-200 flex items-start justify-between">
                <div>
                  <h2 className="text-[17px] font-extrabold m-0">Appliquer « {applyName} »</h2>
                  <p className="text-[12.5px] text-[#777] mt-2 mb-0">Choisissez la portée. Un hôte peut toujours surcharger ensuite.</p>
                </div>
                <button type="button" onClick={() => setApplyName(null)} className="w-[30px] h-[30px] grid place-items-center rounded-lg text-slate-400 hover:bg-slate-100">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="px-6 py-5 space-y-2.5">
                {(
                  [
                    ['nouveau', 'Nouveau groupe'],
                    ['existant', 'Groupe existant'],
                    ['hote', 'Hôte seul'],
                  ] as const
                ).map(([id, label]) => {
                  const on = applyScope === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setApplyScope(id)}
                      className={`w-full text-left px-4 py-3 rounded-xl border-[1.5px] flex items-center gap-3 ${on ? 'bg-[#D0B335]/10 border-[#D0B335]' : 'border-slate-200'}`}
                    >
                      <span className={`w-4 h-4 rounded-full border-[1.5px] grid place-items-center ${on ? 'border-[#D0B335]' : 'border-slate-300'}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${on ? 'bg-[#D0B335]' : 'bg-transparent'}`} />
                      </span>
                      <span className="text-[13px] font-semibold">{label}</span>
                    </button>
                  );
                })}
                <div className="pt-2">
                  <div className="text-[10.5px] font-bold uppercase tracking-wider text-slate-400 mb-2">Aperçu des règles</div>
                  {['CPU > 90 % pendant 5 min → Majeure, mail DSI', 'RAM > 90 % pendant 5 min → Majeure, mail DSI', 'Service swift-gateway arrêté → Majeure, scénario n8n', 'Disque > 95 % → Critique, mail DSI + ticket'].map((t) => (
                    <div key={t} className="text-[12.5px] text-slate-600 py-1">{t}</div>
                  ))}
                </div>
              </div>
              <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
                <button type="button" className="cbc-btn-secondary" onClick={() => setApplyName(null)}>
                  Annuler
                </button>
                <button
                  type="button"
                  className="cbc-btn-primary"
                  onClick={() => {
                    addToast({ type: 'success', title: 'Modèle appliqué', message: `${applyName} — portée ${applyScope}.` });
                    setApplyName(null);
                  }}
                >
                  Appliquer
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
