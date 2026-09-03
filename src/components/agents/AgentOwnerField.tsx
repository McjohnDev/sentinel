/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useEffect, useRef, useState } from 'react';
import { Check, Pencil, Users, X } from 'lucide-react';
import { Agent, User } from '../../types';
import { AdminGroup, adminGroupsService, agentsService } from '../../services/api/agents.service';
import { usersService } from '../../services/api/users.service';

/**
 * Attribution d'un hôte à un responsable nommé ou à une équipe (point 3).
 *
 * Les deux voies coexistent délibérément, parce que le serveur les traite en
 * union : un hôte est administré par son responsable nommé *ou* par un membre
 * de son équipe (voir `user_administers_agent`). Proposer un choix exclusif
 * dans l'interface décrirait donc faussement qui a réellement la main.
 *
 * Un hôte sans attribution n'appartient pas « à tout le monde » : il ne reste
 * accessible qu'aux administrateurs globaux. C'est dit à l'écran, sans quoi
 * l'oubli d'attribution passe pour un état neutre alors qu'il concentre la
 * charge sur les seuls administrateurs.
 */

interface Props {
  agent: Agent;
  canEdit: boolean;
  onSaved?: () => void | Promise<void>;
}

const UNASSIGNED = '';

export const AgentOwnerField: React.FC<Props> = ({ agent, canEdit, onSaved }) => {
  const [editing, setEditing] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [groups, setGroups] = useState<AdminGroup[]>([]);
  const [owner, setOwner] = useState<string>(agent.ownerUserId || UNASSIGNED);
  const [group, setGroup] = useState<string>(agent.adminGroupId || UNASSIGNED);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setOwner(agent.ownerUserId || UNASSIGNED);
    setGroup(agent.adminGroupId || UNASSIGNED);
  }, [agent.ownerUserId, agent.adminGroupId]);

  useEffect(() => {
    if (!editing || users.length || groups.length) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([usersService.getUsers(), adminGroupsService.list()])
      .then(([u, g]) => {
        if (cancelled) return;
        setUsers(u);
        setGroups(g);
      })
      .catch(() => {
        if (!cancelled) setError('Liste des responsables indisponible.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [editing, users.length, groups.length]);

  // Fermer au clic extérieur : un panneau d'attribution laissé ouvert
  // au-dessus de la fiche masque l'état qu'il vient de modifier.
  useEffect(() => {
    if (!editing) return;
    const onClick = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) cancel();
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  });

  const cancel = () => {
    setOwner(agent.ownerUserId || UNASSIGNED);
    setGroup(agent.adminGroupId || UNASSIGNED);
    setError(null);
    setEditing(false);
  };

  const save = async () => {
    const nextOwner = owner || null;
    const nextGroup = group || null;
    if (nextOwner === (agent.ownerUserId || null) && nextGroup === (agent.adminGroupId || null)) {
      cancel();
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await agentsService.patchAgent(agent.id, {
        owner_user_id: nextOwner,
        admin_group_id: nextGroup,
      });
      setEditing(false);
      await onSaved?.();
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      if (detail && typeof detail === 'object' && 'fields' in detail) {
        const d = detail as { message?: string; fields?: string[] };
        setError(d.message || `Champ refusé : ${(d.fields || []).join(', ')}`);
      } else {
        setError(typeof detail === 'string' ? detail : 'Attribution impossible.');
      }
    } finally {
      setSaving(false);
    }
  };

  const summary = () => {
    const parts: string[] = [];
    if (agent.ownerUsername) parts.push(agent.ownerUsername);
    if (agent.adminGroupName) parts.push(`équipe ${agent.adminGroupName}`);
    if (!parts.length) {
      return (
        <span
          className="text-amber-700"
          title="Seuls les administrateurs globaux peuvent intervenir sur cet hôte."
        >
          Non attribué
        </span>
      );
    }
    return <span className="text-[12.5px] text-[var(--color-tx2)]">{parts.join(' · ')}</span>;
  };

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5 group">
        {summary()}
        {canEdit && (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="opacity-0 group-hover:opacity-100 focus:opacity-100 text-[var(--color-tx3)] hover:text-[var(--color-tx2)] transition-opacity"
            title="Attribuer cet hôte"
            aria-label="Attribuer cet hôte"
          >
            <Pencil className="w-3.5 h-3.5" />
          </button>
        )}
      </span>
    );
  }

  return (
    <div ref={panelRef} className="relative inline-block">
      <div className="absolute z-30 top-0 left-0 w-[330px] cbc-card p-4 shadow-lg">
        <div className="flex items-center gap-2 pb-2.5 mb-3 border-b border-[var(--color-ln2)]">
          <Users className="w-4 h-4 text-[#A68523]" />
          <span className="text-[13px] font-bold">Responsabilité de l'hôte</span>
        </div>

        {loading ? (
          <p className="text-[12.5px] text-[var(--color-tx2)] m-0">Chargement…</p>
        ) : (
          <>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-tx3)] mb-1.5">
              Responsable nommé
            </label>
            <select
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              disabled={saving}
              className="cbc-input py-1.5 text-[13px] w-full"
            >
              <option value={UNASSIGNED}>Aucun</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} — {u.role}
                </option>
              ))}
            </select>

            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[var(--color-tx3)] mt-3.5 mb-1.5">
              Équipe d'administration
            </label>
            <select
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              disabled={saving}
              className="cbc-input py-1.5 text-[13px] w-full"
            >
              <option value={UNASSIGNED}>Aucune</option>
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>

            <p className="text-[11.5px] leading-relaxed text-[var(--color-tx2)] mt-3 mb-0">
              {owner || group
                ? "Le responsable et les membres de l'équipe pourront administrer cet hôte."
                : "Sans attribution, seuls les administrateurs globaux pourront intervenir sur cet hôte."}
            </p>

            {error && <p className="text-[11.5px] text-rose-600 mt-2 mb-0">{error}</p>}

            <div className="flex items-center gap-2 mt-4">
              <button
                type="button"
                onClick={() => void save()}
                disabled={saving}
                className="cbc-btn-primary py-1.5 px-3 text-[12.5px] inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                <Check className="w-3.5 h-3.5" />
                {saving ? 'Enregistrement…' : 'Attribuer'}
              </button>
              <button
                type="button"
                onClick={cancel}
                disabled={saving}
                className="cbc-btn-secondary py-1.5 px-3 text-[12.5px] inline-flex items-center gap-1.5 disabled:opacity-50"
              >
                <X className="w-3.5 h-3.5" />
                Annuler
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
