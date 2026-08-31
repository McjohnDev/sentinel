/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef, useState } from 'react';
import { Check, Lock, Pencil, X } from 'lucide-react';
import { Agent } from '../../types';
import { AgentPatch, agentsService } from '../../services/api/agents.service';

/**
 * Édition en place d'un champ *attribué* d'un hôte (point 2).
 *
 * Le composant ne décide pas seul de ce qui est modifiable : il s'appuie sur
 * `editable_fields`, servi par le serveur avec la fiche. C'est la même liste
 * que celle qui gouverne le refus côté API — l'interface ne peut donc pas
 * proposer une modification que le serveur refusera, ni verrouiller un champ
 * que le serveur accepte.
 */

interface Props {
  agent: Agent;
  field: keyof AgentPatch;
  value: string;
  placeholder?: string;
  className?: string;
  onSaved?: () => void | Promise<void>;
}

export const EditableAgentField: React.FC<Props> = ({
  agent,
  field,
  value,
  placeholder,
  className = '',
  onSaved,
}) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Une liste vide signifie « le serveur ne s'est pas prononcé » (fiche d'une
  // version antérieure) : on autorise alors l'édition plutôt que de tout
  // verrouiller, le serveur restant l'autorité qui tranche.
  const editable = !agent.editableFields?.length || agent.editableFields.includes(field);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const cancel = () => {
    setDraft(value);
    setError(null);
    setEditing(false);
  };

  const save = async () => {
    const next = draft.trim();
    if (next === (value || '').trim()) {
      cancel();
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await agentsService.patchAgent(agent.id, { [field]: next } as AgentPatch);
      setEditing(false);
      await onSaved?.();
    } catch (err) {
      // Le serveur nomme les champs qu'il refuse : on relaie son message
      // plutôt qu'un « échec » générique qui laisserait deviner la cause.
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (detail && typeof detail === 'object' && 'fields' in detail) {
        const d = detail as { message?: string; fields?: string[] };
        setError(d.message || `Champ non modifiable : ${(d.fields || []).join(', ')}`);
      } else {
        setError(typeof detail === 'string' ? detail : 'Enregistrement impossible.');
      }
    } finally {
      setSaving(false);
    }
  };

  if (!editable) {
    return (
      <span className={`inline-flex items-center gap-1.5 ${className}`}>
        {value || placeholder}
        <Lock className="w-3 h-3 text-slate-400" aria-label="Constaté par l'agent — non modifiable" />
      </span>
    );
  }

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5 group">
        <span className={className}>
          {value || <span className="text-slate-400 italic">{placeholder}</span>}
        </span>
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 text-slate-400 hover:text-slate-700 transition-opacity"
          title="Modifier"
          aria-label={`Modifier ${field}`}
        >
          <Pencil className="w-3.5 h-3.5" />
        </button>
      </span>
    );
  }

  return (
    <span className="inline-flex flex-col gap-1">
      <span className="inline-flex items-center gap-1">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void save();
            if (e.key === 'Escape') cancel();
          }}
          disabled={saving}
          placeholder={placeholder}
          className="cbc-input py-1 px-2 text-[13px] min-w-[180px]"
        />
        <button
          type="button"
          onClick={() => void save()}
          disabled={saving}
          className="p-1 rounded text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
          title="Enregistrer"
        >
          <Check className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={cancel}
          disabled={saving}
          className="p-1 rounded text-slate-500 hover:bg-slate-100 disabled:opacity-50"
          title="Annuler"
        >
          <X className="w-4 h-4" />
        </button>
      </span>
      {error && <span className="text-[11.5px] text-rose-600">{error}</span>}
    </span>
  );
};
