/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { PageHeader } from '../components/layout/PageHeader';
import { LdapImportModal } from '../components/settings/LdapImportModal';
import { Badge } from '../components/common/Badge';
import { Modal } from '../components/common/Modal';
import { User, Role } from '../types';
import {
  Users,
  Building2,
  UserPlus,
  Pencil,
  Trash2,
  Search,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Lock,
  Eye,
  UserCheck,
} from 'lucide-react';

export const UsersView: React.FC = () => {
  const { users, currentRole, createUser, updateUser, deleteUser, refreshData } = useApp();

  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');

  // Modal states
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [ldapOpen, setLdapOpen] = useState(false);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const [targetUser, setTargetUser] = useState<User | null>(null);

  // Form inputs
  const [nameInput, setNameInput] = useState('');
  const [emailInput, setEmailInput] = useState('');
  const [roleInput, setRoleInput] = useState<Role>('Operator');
  const [passwordInput, setPasswordInput] = useState('');
  const [confirmPasswordInput, setConfirmPasswordInput] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const totalUsersCount = users.length;
  const adminUsersCount = users.filter((u) => u.role === 'Admin').length;
  const operatorUsersCount = users.filter((u) => u.role === 'Operator').length;
  const readOnlyUsersCount = users.filter((u) => u.role === 'ReadOnly').length;
  const securityUsersCount = users.filter((u) => u.role === 'Security').length;

  const filteredUsers = users.filter((u) => {
    const matchesSearch =
      u.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = roleFilter === 'all' || u.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  const handleOpenCreateModal = () => {
    setNameInput('');
    setEmailInput('');
    setRoleInput('Operator');
    setPasswordInput('');
    setConfirmPasswordInput('');
    setErrorMsg('');
    setCreateModalOpen(true);
  };

  const handleOpenEditModal = (u: User) => {
    setTargetUser(u);
    setNameInput(u.name);
    setEmailInput(u.email);
    setRoleInput(u.role);
    setErrorMsg('');
    setEditModalOpen(true);
  };

  const handleOpenDeleteModal = (u: User) => {
    setTargetUser(u);
    setDeleteModalOpen(true);
  };

  const handleConfirmCreate = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (nameInput.length < 2) {
      setErrorMsg('Le nom doit contenir au moins 2 caractères.');
      return;
    }
    if (!emailInput || !emailInput.includes('@')) {
      setErrorMsg('Veuillez renseigner une adresse email valide.');
      return;
    }
    if (passwordInput.length < 8) {
      setErrorMsg('Le mot de passe doit contenir au moins 8 caractères.');
      return;
    }
    if (!/[A-Z]/.test(passwordInput) || !/[0-9]/.test(passwordInput)) {
      setErrorMsg('Le mot de passe doit inclure au moins une majuscule et un chiffre.');
      return;
    }
    if (passwordInput !== confirmPasswordInput) {
      setErrorMsg('Les mots de passe ne correspondent pas.');
      return;
    }

    // Le mot de passe était validé ci-dessus puis absent de l'appel : le
    // serveur l'exige, la création échouait donc systématiquement.
    void createUser({
      name: nameInput,
      email: emailInput,
      role: roleInput,
      password: passwordInput,
    });
    setCreateModalOpen(false);
  };

  const handleConfirmEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (targetUser) {
      void updateUser(targetUser.id, {
        name: nameInput,
        email: emailInput,
        role: roleInput,
      });
      setEditModalOpen(false);
    }
  };

  const handleConfirmDelete = () => {
    if (targetUser) {
      void deleteUser(targetUser.id);
      setDeleteModalOpen(false);
    }
  };

  return (
    <div className="space-y-5">
      <LdapImportModal
        open={ldapOpen}
        onClose={() => setLdapOpen(false)}
        onImported={() => refreshData()}
      />
      <PageHeader
        title="Utilisateurs"
        subtitle="Comptes et rôles d'accès à la plateforme CBC Supervision."
        primaryAction={
          currentRole === 'Admin' ? (
            <div className="flex items-center gap-2">
              {/* L'import d'annuaire précède la création locale : sur un parc
                  bancaire, la plupart des comptes existent déjà côté annuaire,
                  et en recréer un localement ferait détenir un mot de passe
                  que la plateforme n'a pas à connaître. */}
              <button
                type="button"
                onClick={() => setLdapOpen(true)}
                className="cbc-btn-secondary"
                title="Créer un compte à partir de l'annuaire, sans mot de passe local"
              >
                <Building2 className="w-4 h-4" />
                Importer depuis l’annuaire
              </button>
              <button type="button" onClick={handleOpenCreateModal} className="cbc-btn-primary">
                <UserPlus className="w-4 h-4" />
                Compte local
              </button>
            </div>
          ) : undefined
        }
      />

      {/* Contextual KPI Stats Bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="cbc-card p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[var(--color-ln2)] text-[var(--color-tx2)] flex items-center justify-center font-bold">
            <Users className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[var(--color-tx2)] uppercase tracking-wide">Total Utilisateurs</p>
            <p className="text-lg font-black text-[var(--color-tx)]">{totalUsersCount}</p>
          </div>
        </div>

        <div className="cbc-card p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-amber-50 text-[#D0B335] flex items-center justify-center font-bold border border-amber-200/60">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[var(--color-tx2)] uppercase tracking-wide">Administrateurs</p>
            <p className="text-lg font-black text-[var(--color-tx)]">{adminUsersCount}</p>
          </div>
        </div>

        <div className="cbc-card p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
            <UserCheck className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[var(--color-tx2)] uppercase tracking-wide">Opérateurs</p>
            <p className="text-lg font-black text-blue-600">{operatorUsersCount}</p>
          </div>
        </div>

        <div className="cbc-card p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-violet-50 text-violet-600 flex items-center justify-center font-bold">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[var(--color-tx2)] uppercase tracking-wide">Sécurité</p>
            <p className="text-lg font-black text-violet-700">{securityUsersCount}</p>
          </div>
        </div>
        <div className="cbc-card p-3.5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[var(--color-ln2)] text-[var(--color-tx2)] flex items-center justify-center font-bold">
            <Eye className="w-4 h-4" />
          </div>
          <div>
            <p className="text-[11px] font-semibold text-[var(--color-tx2)] uppercase tracking-wide">Lecture Seule</p>
            <p className="text-lg font-black text-[var(--color-tx2)]">{readOnlyUsersCount}</p>
          </div>
        </div>
      </div>

      {currentRole !== 'Admin' && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900">
          Seul un <strong>Administrateur</strong> a l'autorisation de créer, modifier ou supprimer des comptes.
        </div>
      )}

      {/* Filter & Search Bar */}
      <div className="cbc-card p-4 flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-[var(--color-tx3)] absolute left-3.5 top-3" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Rechercher par nom ou email..."
            className="w-full pl-10 pr-4 py-2 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
          />
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <span className="text-xs text-[var(--color-tx2)] font-medium">Filtrer par rôle :</span>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-2 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs font-bold text-[var(--color-tx)] focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
          >
            <option value="all">Tous les rôles</option>
            <option value="Admin">Administrateurs</option>
            <option value="Operator">Opérateurs</option>
            <option value="Security">Sécurité</option>
            <option value="ReadOnly">Lecture seule</option>
          </select>
        </div>
      </div>

      {/* Users Table */}
      <div className="cbc-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[var(--color-ln2)] text-[11px] font-bold text-[var(--color-tx2)] uppercase tracking-wider border-b border-[var(--color-ln2)]">
                <th className="py-3 px-4">Nom complet</th>
                <th className="py-3 px-4">Email professionnel</th>
                <th className="py-3 px-4">Rôle & Permissions</th>
                <th className="py-3 px-4">Date de création</th>
                <th className="py-3 px-4">Statut</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-ln2)] text-xs text-[var(--color-tx2)]">
              {filteredUsers.map((u) => (
                <tr key={u.id} className="hover:bg-[var(--color-ln2)]">
                  <td className="py-3.5 px-4 font-bold text-[var(--color-tx)]">{u.name}</td>
                  <td className="py-3.5 px-4 font-mono text-[var(--color-tx2)]">{u.email}</td>
                  <td className="py-3.5 px-4">
                    <Badge type="role" value={u.role} size="sm" />
                  </td>
                  <td className="py-3.5 px-4 text-[var(--color-tx3)] font-mono">{u.createdAt}</td>
                  <td className="py-3.5 px-4">
                    <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full font-bold text-[11px]">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Actif
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-right">
                    {currentRole === 'Admin' && (
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => handleOpenEditModal(u)}
                          className="p-1.5 text-[var(--color-tx2)] hover:text-amber-600 hover:bg-amber-50 rounded-lg transition-colors"
                          title="Modifier l'utilisateur"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleOpenDeleteModal(u)}
                          className="p-1.5 text-[var(--color-tx3)] hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                          title="Supprimer l'utilisateur"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Permissions Matrix Table */}
      <div className="bg-[var(--color-panel)] p-6 rounded-2xl border border-[var(--color-ln)]/80 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-[var(--color-tx)] tracking-tight flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#D0B335]" />
          Matrice des Permissions par Rôle (RBAC)
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[var(--color-ln2)] text-[11px] font-bold text-[var(--color-tx2)] uppercase border-b border-[var(--color-ln)]">
                <th className="py-3 px-4">Action / Fonctionnalité</th>
                <th className="py-3 px-4 text-center">Administrateur</th>
                <th className="py-3 px-4 text-center">Opérateur</th>
                <th className="py-3 px-4 text-center">Lecture seule</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-ln2)]">
              <tr>
                <td className="py-3 px-4 font-medium text-[var(--color-tx)]">Consultation du Dashboard & Métriques</td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium text-[var(--color-tx)]">Acquittement des alertes (Info & Warning)</td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium text-[var(--color-tx)]">Acquittement des alertes Critiques & Lot</td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium text-[var(--color-tx)]">Exportation CSV des données</td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium text-[var(--color-tx)]">Configuration des seuils d'alerte</td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-medium text-[var(--color-tx)]">Gestion des utilisateurs & Révocation des agents</td>
                <td className="py-3 px-4 text-center"><CheckCircle2 className="w-4 h-4 text-emerald-600 mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
                <td className="py-3 px-4 text-center"><XCircle className="w-4 h-4 text-[var(--color-tx3)] mx-auto" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="Créer un nouvel utilisateur"
      >
        <form onSubmit={handleConfirmCreate} className="space-y-4">
          {errorMsg && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-bold">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Nom complet</label>
            <input
              type="text"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              placeholder="Ex: Alain Kengne"
              className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Adresse Email</label>
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="nom@cbcam.cm"
              className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Rôle & Permissions</label>
            <select
              value={roleInput}
              onChange={(e) => setRoleInput(e.target.value as Role)}
              className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs font-bold text-[var(--color-tx)] focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
            >
              <option value="Admin">Administrateur (Tous droits)</option>
              <option value="Operator">Opérateur (Supervision & Ack)</option>
              <option value="Security">Sécurité (Audit & conformité)</option>
              <option value="ReadOnly">Lecture seule (Consultation)</option>
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
            <div>
              <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Mot de passe</label>
              <input
                type="password"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                placeholder="Min 8 chars, 1 maj, 1 chiffre"
                className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Confirmer mot de passe</label>
              <input
                type="password"
                value={confirmPasswordInput}
                onChange={(e) => setConfirmPasswordInput(e.target.value)}
                placeholder="Répéter le mot de passe"
                className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] focus:outline-none"
                required
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4 border-t border-[var(--color-ln2)]">
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              className="px-4 py-2 bg-[var(--color-ln2)] text-[var(--color-tx2)] text-xs font-semibold rounded-xl"
            >
              Annuler
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-[#D0B335] text-slate-950 text-xs font-bold rounded-xl shadow-xs hover:bg-[#b89d2d]"
            >
              Créer le compte
            </button>
          </div>
        </form>
      </Modal>

      {/* Edit User Modal */}
      <Modal
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        title="Modifier le compte utilisateur"
      >
        <form onSubmit={handleConfirmEdit} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Nom complet</label>
            <input
              type="text"
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] font-medium"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Email</label>
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs text-[var(--color-tx)] font-medium"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-[var(--color-tx2)] mb-1">Rôle</label>
            <select
              value={roleInput}
              onChange={(e) => setRoleInput(e.target.value as Role)}
              className="w-full p-2.5 bg-[var(--color-ln2)] border border-[var(--color-ln)] rounded-xl text-xs font-bold text-[var(--color-tx)]"
            >
              <option value="Admin">Administrateur</option>
              <option value="Operator">Opérateur</option>
              <option value="Security">Sécurité</option>
              <option value="ReadOnly">Lecture seule</option>
            </select>
          </div>

          <p className="text-[11px] text-[var(--color-tx2)] italic">
            Note: Le mot de passe ne peut être modifié que par l'utilisateur lui-même dans son profil.
          </p>

          <div className="flex justify-end gap-2 pt-4 border-t border-[var(--color-ln2)]">
            <button
              type="button"
              onClick={() => setEditModalOpen(false)}
              className="px-4 py-2 bg-[var(--color-ln2)] text-[var(--color-tx2)] text-xs font-semibold rounded-xl"
            >
              Annuler
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl shadow-xs"
            >
              Enregistrer
            </button>
          </div>
        </form>
      </Modal>

      {/* Delete User Modal */}
      <Modal
        isOpen={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        title="Supprimer l'utilisateur ?"
        footer={
          <>
            <button
              onClick={() => setDeleteModalOpen(false)}
              className="px-4 py-2 bg-[var(--color-ln2)] text-[var(--color-tx2)] text-xs font-semibold rounded-xl"
            >
              Annuler
            </button>
            <button
              onClick={handleConfirmDelete}
              className="px-4 py-2 bg-rose-600 text-white text-xs font-bold rounded-xl shadow-xs"
            >
              Confirmer la suppression
            </button>
          </>
        }
      >
        <p className="text-xs text-[var(--color-tx2)] leading-relaxed">
          Êtes-vous certain de vouloir supprimer le compte de{' '}
          <strong>{targetUser?.name}</strong> ({targetUser?.email}) ? Cette action est irréversible et sera enregistrée dans les journaux d'audit de la banque.
        </p>
      </Modal>
    </div>
  );
};
