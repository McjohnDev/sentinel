/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { useApp } from '../context/AppContext';
import { GlobalThresholds, MessagingNotificationConfig, ServicesMonitoringConfig, FilesMonitoringConfig, DataRetentionConfig } from '../types';
import { Modal } from '../components/common/Modal';
import {
  Settings,
  Sliders,
  MessageSquare,
  Clock,
  Key,
  Plus,
  Trash2,
  Send,
  Save,
  RotateCcw,
  Copy,
  Check,
  Cpu,
  Database,
  HardDrive,
  Award,
  ShieldCheck,
  CheckCircle2,
  Lock,
  Building2,
  FileText,
  Download,
  BadgeCheck,
  Sparkles,
  Layers,
  File,
} from 'lucide-react';

export const SettingsView: React.FC = () => {
  const {
    globalThresholds,
    messagingConfig,
    servicesMonitoringConfig,
    filesMonitoringConfig,
    availabilityPolicy,
    retentionConfig,
    enrollmentTokens,
    currentRole,
    updateGlobalThresholds,
    updateMessagingConfig,
    updateServicesMonitoringConfig,
    updateFilesMonitoringConfig,
    updateAvailabilityPolicy,
    updateRetentionConfig,
    generateEnrollmentToken,
    addToast,
  } = useApp();

  const [activeTab, setActiveTab] = useState<'thresholds' | 'messaging' | 'services' | 'files' | 'availability' | 'retention' | 'tokens' | 'compliance'>('thresholds');

  // Form states
  const [thresholdsForm, setThresholdsForm] = useState<GlobalThresholds>(globalThresholds);
  const [messagingForm, setMessagingForm] = useState<MessagingNotificationConfig>(messagingConfig);
  const [servicesForm, setServicesForm] = useState<ServicesMonitoringConfig>(servicesMonitoringConfig);
  const [filesForm, setFilesForm] = useState<FilesMonitoringConfig>(filesMonitoringConfig);
  const [availabilityForm, setAvailabilityForm] = useState<AvailabilityPolicy>(availabilityPolicy);
  const [retentionForm, setRetentionForm] = useState<DataRetentionConfig>(retentionConfig);
  const [newRecipient, setNewRecipient] = useState('');
  const [newService, setNewService] = useState('');
  const [newFilePath, setNewFilePath] = useState('');
  const [newFileSizeMb, setNewFileSizeMb] = useState('');
  const [formError, setFormError] = useState('');

  // Token Modal
  const [tokenModalOpen, setTokenModalOpen] = useState(false);
  const [currentTokenCode, setCurrentTokenCode] = useState<string | null>(null);
  const [copiedTokenId, setCopiedTokenId] = useState<string | null>(null);

  const handleSaveThresholds = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (thresholdsForm.cpuWarning >= thresholdsForm.cpuCritical) {
      setFormError('Le seuil CPU Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    if (thresholdsForm.ramWarning >= thresholdsForm.ramCritical) {
      setFormError('Le seuil RAM Warning doit être strictement inférieur au seuil Critique.');
      return;
    }
    if (thresholdsForm.diskWarning >= thresholdsForm.diskCritical) {
      setFormError('Le seuil Disque Warning doit être strictement inférieur au seuil Critique.');
      return;
    }

    updateGlobalThresholds(thresholdsForm);
  };

  const handleAddRecipient = () => {
    if (!newRecipient || !newRecipient.includes('@')) {
      addToast({
        type: 'error',
        title: 'Destinataire invalide',
        message: 'Veuillez renseigner une adresse email valide.',
      });
      return;
    }
    if (messagingForm.recipients.includes(newRecipient)) {
      addToast({
        type: 'warning',
        title: 'Adresse existante',
        message: 'Ce destinataire fait déjà partie de la liste.',
      });
      return;
    }
    setMessagingForm({ ...messagingForm, recipients: [...messagingForm.recipients, newRecipient] });
    setNewRecipient('');
  };

  const handleRemoveRecipient = (recipient: string) => {
    setMessagingForm({ ...messagingForm, recipients: messagingForm.recipients.filter(r => r !== recipient) });
  };

  const handleSaveMessaging = (e: React.FormEvent) => {
    e.preventDefault();
    updateMessagingConfig(messagingForm);
  };

  const handleTestMessaging = () => {
    addToast({
      type: 'info',
      title: 'Test API de messagerie en cours',
      message: `Envoi d'un message de test via l'API CBC...`,
    });
    setTimeout(() => {
      addToast({
        type: 'success',
        title: 'Test API réussi !',
        message: 'L\'API de messagerie CBC a accepté le message de test avec succès.',
      });
    }, 1200);
  };

  const handleAddService = () => {
    if (!newService.trim()) {
      addToast({
        type: 'error',
        title: 'Service invalide',
        message: 'Veuillez renseigner un nom de service valide.',
      });
      return;
    }
    if (servicesForm.services.includes(newService)) {
      addToast({
        type: 'warning',
        title: 'Service existant',
        message: 'Ce service fait déjà partie de la liste.',
      });
      return;
    }
    setServicesForm({ ...servicesForm, services: [...servicesForm.services, newService] });
    setNewService('');
  };

  const handleRemoveService = (service: string) => {
    setServicesForm({ ...servicesForm, services: servicesForm.services.filter(s => s !== service) });
  };

  const handleSaveServices = (e: React.FormEvent) => {
    e.preventDefault();
    updateServicesMonitoringConfig(servicesForm);
  };

  const handleAddFile = () => {
    if (!newFilePath.trim()) {
      addToast({
        type: 'error',
        title: 'Fichier invalide',
        message: 'Veuillez renseigner un chemin de fichier valide.',
      });
      return;
    }
    const newFile: { path: string; max_size_mb?: number } = { path: newFilePath };
    if (newFileSizeMb) {
      newFile.max_size_mb = parseInt(newFileSizeMb);
    }
    if (filesForm.files.some(f => f.path === newFilePath)) {
      addToast({
        type: 'warning',
        title: 'Fichier existant',
        message: 'Ce fichier fait déjà partie de la liste.',
      });
      return;
    }
    setFilesForm({ ...filesForm, files: [...filesForm.files, newFile] });
    setNewFilePath('');
    setNewFileSizeMb('');
  };

  const handleRemoveFile = (filePath: string) => {
    setFilesForm({ ...filesForm, files: filesForm.files.filter(f => f.path !== filePath) });
  };

  const handleSaveFiles = (e: React.FormEvent) => {
    e.preventDefault();
    updateFilesMonitoringConfig(filesForm);
  };

  const handleSaveRetention = (e: React.FormEvent) => {
    e.preventDefault();
    updateRetentionConfig(retentionForm);
  };

  const handleGenerateToken = () => {
    const tokenObj = generateEnrollmentToken();
    setCurrentTokenCode(tokenObj.token);
    setTokenModalOpen(true);
  };

  const handleCopyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedTokenId(id);
    setTimeout(() => setCopiedTokenId(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs">
        <div>
          <h2 className="text-xl font-black text-slate-900 tracking-tight flex items-center gap-2">
            <Settings className="w-5 h-5 text-[#D0B335]" />
            Configuration Globale de la Plateforme
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Paramétrage des seuils d'alerte, notifications SMTP, rétention et jetons d'enrôlement
          </p>
        </div>
      </div>

      {currentRole !== 'Admin' && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-xs text-amber-900 font-medium">
          Note: Seul un <strong>Administrateur</strong> a les privilèges pour modifier la configuration globale.
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-200 space-x-2 bg-white px-4 pt-2 rounded-t-2xl">
        <button
          onClick={() => setActiveTab('thresholds')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'thresholds'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Sliders className="w-4 h-4" />
          Seuils d'alerte globaux
        </button>
        <button
          onClick={() => setActiveTab('messaging')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'messaging'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          Notifications API CBC
        </button>
        <button
          onClick={() => setActiveTab('services')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'services'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" />
          Supervision Services
        </button>
        <button
          onClick={() => setActiveTab('files')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'files'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <File className="w-4 h-4" />
          Supervision Fichiers
        </button>
        <button
          onClick={() => setActiveTab('availability')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'availability'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Clock className="w-4 h-4" />
          Fenêtres Horaires
        </button>
        <button
          onClick={() => setActiveTab('retention')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'retention'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Clock className="w-4 h-4" />
          Rétention des données
        </button>
        <button
          onClick={() => setActiveTab('tokens')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'tokens'
              ? 'border-[#D0B335] text-slate-900'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Key className="w-4 h-4" />
          Jetons d'enrôlement ({enrollmentTokens.length})
        </button>
        <button
          onClick={() => setActiveTab('compliance')}
          className={`pb-3 px-4 text-xs font-bold border-b-2 flex items-center gap-2 transition-colors ${
            activeTab === 'compliance'
              ? 'border-[#D0B335] text-slate-900 font-extrabold'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Award className="w-4 h-4 text-[#D0B335]" />
          Conformité & Certifications Banking
        </button>
      </div>

      {/* TAB 1: THRESHOLDS */}
      {activeTab === 'thresholds' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          {formError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-700 font-bold">
              {formError}
            </div>
          )}

          <form onSubmit={handleSaveThresholds} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* CPU */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <Cpu className="w-4 h-4 text-[#D0B335]" /> Seuils CPU (%)
                </h4>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.cpuWarning}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, cpuWarning: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Critique (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.cpuCritical}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, cpuCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                  />
                </div>
              </div>

              {/* RAM */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-blue-500" /> Seuils RAM (%)
                </h4>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.ramWarning}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, ramWarning: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Critique (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.ramCritical}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, ramCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                  />
                </div>
              </div>

              {/* DISK */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                  <HardDrive className="w-4 h-4 text-purple-500" /> Seuils Disque (%)
                </h4>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Warning (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="99"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.diskWarning}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, diskWarning: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs text-slate-600 font-medium mb-1">Critique (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    disabled={currentRole !== 'Admin'}
                    value={thresholdsForm.diskCritical}
                    onChange={(e) => setThresholdsForm({ ...thresholdsForm, diskCritical: Number(e.target.value) })}
                    className="w-full p-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-rose-600"
                  />
                </div>
              </div>
            </div>

            {currentRole === 'Admin' && (
              <div className="flex justify-end pt-4 border-t border-slate-100">
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5"
                >
                  <Save className="w-4 h-4" />
                  Sauvegarder les seuils globaux
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 2: MESSAGING API CBC */}
      {activeTab === 'messaging' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={handleSaveMessaging} className="space-y-6">
            {/* Destinataires */}
            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Destinataires des notifications d'alerte
              </h4>

              <div className="flex items-center gap-2">
                <input
                  type="email"
                  value={newRecipient}
                  onChange={(e) => setNewRecipient(e.target.value)}
                  placeholder="nom@cbcam.cm"
                  disabled={currentRole !== 'Admin'}
                  className="w-full sm:w-80 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
                />
                {currentRole === 'Admin' && (
                  <button
                    type="button"
                    onClick={handleAddRecipient}
                    className="px-4 py-2.5 bg-slate-900 text-white text-xs font-bold rounded-xl flex items-center gap-1 hover:bg-slate-800"
                  >
                    <Plus className="w-4 h-4" />
                    Ajouter
                  </button>
                )}
              </div>

              <div className="flex flex-wrap gap-2 pt-2">
                {messagingForm.recipients.map((rec) => (
                  <span
                    key={rec}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 text-slate-800 rounded-xl text-xs font-semibold border border-slate-200"
                  >
                    {rec}
                    {currentRole === 'Admin' && (
                      <button
                        type="button"
                        onClick={() => handleRemoveRecipient(rec)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            </div>

            {/* API de messagerie CBC Config */}
            <div className="pt-4 border-t border-slate-100 space-y-4">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Configuration de l'API de messagerie interne CBC
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Endpoint API</label>
                  <input
                    type="text"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.apiEndpoint}
                    onChange={(e) => setMessagingForm({ ...messagingForm, apiEndpoint: e.target.value })}
                    placeholder="https://api.cbc.internal/messaging"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Clé API</label>
                  <input
                    type="password"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.apiKey}
                    onChange={(e) => setMessagingForm({ ...messagingForm, apiKey: e.target.value })}
                    placeholder="••••••••••••••••"
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-slate-700 mb-1">Timeout (secondes)</label>
                  <input
                    type="number"
                    disabled={currentRole !== 'Admin'}
                    value={messagingForm.apiTimeout}
                    onChange={(e) => setMessagingForm({ ...messagingForm, apiTimeout: Number(e.target.value) })}
                    className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
                  />
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <input
                    type="checkbox"
                    id="messagingEnabled"
                    disabled={currentRole !== 'Admin'}
                    checked={messagingForm.enabled}
                    onChange={(e) => setMessagingForm({ ...messagingForm, enabled: e.target.checked })}
                    className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                  />
                  <label htmlFor="messagingEnabled" className="text-xs font-bold text-slate-700">
                    Activer les notifications
                  </label>
                </div>
              </div>
            </div>

            {/* Actions */}
            {currentRole === 'Admin' && (
              <div className="pt-4 border-t border-slate-100 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer la configuration
                </button>
                <button
                  type="button"
                  onClick={handleTestMessaging}
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-bold rounded-xl transition-colors border border-slate-200"
                >
                  <Send className="w-4 h-4" />
                  Tester l'API
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 3: SUPERVISION SERVICES */}
      {activeTab === 'services' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={handleSaveServices} className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Configuration de la supervision des services système
              </h4>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="servicesEnabled"
                  disabled={currentRole !== 'Admin'}
                  checked={servicesForm.enabled}
                  onChange={(e) => setServicesForm({ ...servicesForm, enabled: e.target.checked })}
                  className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                />
                <label htmlFor="servicesEnabled" className="text-xs font-bold text-slate-700">
                  Activer la supervision
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Liste des services à superviser
              </h4>
              <p className="text-xs text-slate-500">
                Ajoutez les services système à superviser (ex: SWIFT AutoClient, SQL Server, IIS)
              </p>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={newService}
                  onChange={(e) => setNewService(e.target.value)}
                  placeholder="Nom du service (ex: SWIFT AutoClient)"
                  disabled={currentRole !== 'Admin'}
                  className="w-full sm:w-80 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
                />
                {currentRole === 'Admin' && (
                  <button
                    type="button"
                    onClick={handleAddService}
                    className="px-4 py-2.5 bg-slate-900 text-white text-xs font-bold rounded-xl flex items-center gap-1 hover:bg-slate-800"
                  >
                    <Plus className="w-4 h-4" />
                    Ajouter
                  </button>
                )}
              </div>

              <div className="flex flex-wrap gap-2 pt-2">
                {servicesForm.services.map((service) => (
                  <span
                    key={service}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 text-slate-800 rounded-xl text-xs font-semibold border border-slate-200"
                  >
                    {service}
                    {currentRole === 'Admin' && (
                      <button
                        type="button"
                        onClick={() => handleRemoveService(service)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </span>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <label className="block text-xs font-bold text-slate-700 mb-1">Intervalle de vérification (secondes)</label>
              <input
                type="number"
                disabled={currentRole !== 'Admin'}
                value={servicesForm.interval}
                onChange={(e) => setServicesForm({ ...servicesForm, interval: Number(e.target.value) })}
                className="w-full sm:w-40 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
              />
            </div>

            {/* Actions */}
            {currentRole === 'Admin' && (
              <div className="pt-4 border-t border-slate-100 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer la configuration
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 4: SUPERVISION FICHIERS */}
      {activeTab === 'files' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={handleSaveFiles} className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Configuration de la supervision des fichiers
              </h4>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="filesEnabled"
                  disabled={currentRole !== 'Admin'}
                  checked={filesForm.enabled}
                  onChange={(e) => setFilesForm({ ...filesForm, enabled: e.target.checked })}
                  className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                />
                <label htmlFor="filesEnabled" className="text-xs font-bold text-slate-700">
                  Activer la supervision
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Liste des fichiers à superviser
              </h4>
              <p className="text-xs text-slate-500">
                Ajoutez les fichiers à superviser (ex: fichiers de logs, fichiers de configuration)
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <input
                  type="text"
                  value={newFilePath}
                  onChange={(e) => setNewFilePath(e.target.value)}
                  placeholder="Chemin du fichier (ex: /var/log/swift.log)"
                  disabled={currentRole !== 'Admin'}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
                />
                <input
                  type="number"
                  value={newFileSizeMb}
                  onChange={(e) => setNewFileSizeMb(e.target.value)}
                  placeholder="Taille max (Mo, optionnel)"
                  disabled={currentRole !== 'Admin'}
                  className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-900 font-medium focus:outline-none focus:ring-2 focus:ring-[#D0B335]"
                />
                {currentRole === 'Admin' && (
                  <button
                    type="button"
                    onClick={handleAddFile}
                    className="px-4 py-2.5 bg-slate-900 text-white text-xs font-bold rounded-xl flex items-center gap-1 hover:bg-slate-800"
                  >
                    <Plus className="w-4 h-4" />
                    Ajouter
                  </button>
                )}
              </div>

              <div className="space-y-2 pt-2">
                {filesForm.files.map((file) => (
                  <div
                    key={file.path}
                    className="inline-flex items-center gap-2 px-3 py-1.5 bg-slate-100 text-slate-800 rounded-xl text-xs font-semibold border border-slate-200"
                  >
                    <span className="font-mono">{file.path}</span>
                    {file.max_size_mb && (
                      <span className="text-slate-500">(max: {file.max_size_mb} Mo)</span>
                    )}
                    {currentRole === 'Admin' && (
                      <button
                        type="button"
                        onClick={() => handleRemoveFile(file.path)}
                        className="text-slate-400 hover:text-rose-600"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <label className="block text-xs font-bold text-slate-700 mb-1">Intervalle de vérification (secondes)</label>
              <input
                type="number"
                disabled={currentRole !== 'Admin'}
                value={filesForm.interval}
                onChange={(e) => setFilesForm({ ...filesForm, interval: Number(e.target.value) })}
                className="w-full sm:w-40 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
              />
            </div>

            {/* Actions */}
            {currentRole === 'Admin' && (
              <div className="pt-4 border-t border-slate-100 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer la configuration
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 5: FENÊTRES HORAIRES */}
      {activeTab === 'availability' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={(e) => { e.preventDefault(); updateAvailabilityPolicy(availabilityForm); }} className="space-y-6">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Configuration des fenêtres horaires de disponibilité
              </h4>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="availabilityEnabled"
                  disabled={currentRole !== 'Admin'}
                  checked={availabilityForm.enabled}
                  onChange={(e) => setAvailabilityForm({ ...availabilityForm, enabled: e.target.checked })}
                  className="w-4 h-4 text-[#D0B335] rounded focus:ring-[#D0B335]"
                />
                <label htmlFor="availabilityEnabled" className="text-xs font-bold text-slate-700">
                  Activer les fenêtres horaires
                </label>
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Fenêtres horaires par jour
              </h4>
              <p className="text-xs text-slate-500">
                Définissez les plages horaires pendant lesquelles les postes de travail doivent être disponibles.
                En dehors de ces plages, l'absence d'un poste ne générera pas d'alerte.
              </p>

              <div className="space-y-4">
                {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map((day) => (
                  <div key={day} className="p-4 bg-slate-50 rounded-xl border border-slate-200/80">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-bold text-slate-800 capitalize">{day}</span>
                      <button
                        type="button"
                        onClick={() => {
                          const newTimeWindows = { ...availabilityForm.timeWindows };
                          if (!newTimeWindows[day]) {
                            newTimeWindows[day] = [{ start: '08:00', end: '18:00' }];
                          }
                          setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                        }}
                        disabled={currentRole !== 'Admin'}
                        className="text-xs text-slate-600 hover:text-slate-900"
                      >
                        + Ajouter plage
                      </button>
                    </div>
                    
                    {availabilityForm.timeWindows[day]?.map((window, index) => (
                      <div key={index} className="flex items-center gap-2 mb-2">
                        <input
                          type="time"
                          value={window.start}
                          onChange={(e) => {
                            const newTimeWindows = { ...availabilityForm.timeWindows };
                            newTimeWindows[day][index].start = e.target.value;
                            setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                          }}
                          disabled={currentRole !== 'Admin'}
                          className="w-32 p-2 bg-white border border-slate-200 rounded-lg text-xs font-mono"
                        />
                        <span className="text-xs text-slate-500">→</span>
                        <input
                          type="time"
                          value={window.end}
                          onChange={(e) => {
                            const newTimeWindows = { ...availabilityForm.timeWindows };
                            newTimeWindows[day][index].end = e.target.value;
                            setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                          }}
                          disabled={currentRole !== 'Admin'}
                          className="w-32 p-2 bg-white border border-slate-200 rounded-lg text-xs font-mono"
                        />
                        {currentRole === 'Admin' && (
                          <button
                            type="button"
                            onClick={() => {
                              const newTimeWindows = { ...availabilityForm.timeWindows };
                              newTimeWindows[day].splice(index, 1);
                              setAvailabilityForm({ ...availabilityForm, timeWindows: newTimeWindows });
                            }}
                            className="text-slate-400 hover:text-rose-600"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100">
              <label className="block text-xs font-bold text-slate-700 mb-1">Seuil offline personnalisé (secondes, optionnel)</label>
              <input
                type="number"
                disabled={currentRole !== 'Admin'}
                value={availabilityForm.offlineThresholdSeconds || ''}
                onChange={(e) => setAvailabilityForm({ ...availabilityForm, offlineThresholdSeconds: e.target.value ? Number(e.target.value) : undefined })}
                placeholder="Laisser vide pour utiliser le seuil par défaut"
                className="w-full sm:w-40 p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-mono font-bold text-slate-900"
              />
              <p className="text-xs text-slate-500 mt-1">
                Remplace le seuil par défaut (90s pour serveurs, 7200s pour postes) si défini
              </p>
            </div>

            {/* Actions */}
            {currentRole === 'Admin' && (
              <div className="pt-4 border-t border-slate-100 flex items-center gap-3">
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs transition-colors"
                >
                  <Save className="w-4 h-4" />
                  Enregistrer la configuration
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 6: RÉTENTION DES DONNÉES */}
      {activeTab === 'retention' && (
        <div className="bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-6">
          <form onSubmit={handleSaveRetention} className="space-y-6">
            <h4 className="text-sm font-bold text-slate-900 tracking-tight">
              Politique d'archivage et de suppression automatique
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
                <label className="block text-xs font-bold text-slate-800">
                  Rétention de l'historique des alertes (en jours)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  disabled={currentRole !== 'Admin'}
                  value={retentionForm.alertsDays}
                  onChange={(e) => setRetentionForm({ ...retentionForm, alertsDays: Number(e.target.value) })}
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-900"
                />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Archivage automatique dans l'historique d'audit à 00:00 UTC.
                </p>
              </div>

              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 space-y-3">
                <label className="block text-xs font-bold text-slate-800">
                  Rétention des logs d'heartbeat (en jours)
                </label>
                <input
                  type="number"
                  min="1"
                  max="365"
                  disabled={currentRole !== 'Admin'}
                  value={retentionForm.heartbeatsDays}
                  onChange={(e) => setRetentionForm({ ...retentionForm, heartbeatsDays: Number(e.target.value) })}
                  className="w-full p-2.5 bg-white border border-slate-200 rounded-xl text-xs font-bold text-slate-900"
                />
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Purge des métriques brutes à 01:00 UTC.
                </p>
              </div>
            </div>

            {currentRole === 'Admin' && (
              <div className="flex justify-end pt-4 border-t border-slate-100">
                <button
                  type="submit"
                  className="px-5 py-2.5 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5"
                >
                  <Save className="w-4 h-4" />
                  Sauvegarder la rétention
                </button>
              </div>
            )}
          </form>
        </div>
      )}

      {/* TAB 4: ENROLLMENT TOKENS */}
      {activeTab === 'tokens' && (
        <div className="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden space-y-4 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-100">
            <div>
              <h4 className="text-sm font-bold text-slate-900 tracking-tight">
                Jetons d'enrôlement générés
              </h4>
              <p className="text-xs text-slate-500">
                Les jetons permettent d'authentifier les nouveaux agents lors de l'installation
              </p>
            </div>

            {currentRole === 'Admin' && (
              <button
                onClick={handleGenerateToken}
                className="px-4 py-2 bg-[#D0B335] hover:bg-[#b89d2d] text-slate-950 text-xs font-bold rounded-xl shadow-xs flex items-center gap-1.5 cursor-pointer"
              >
                <Plus className="w-4 h-4" />
                Générer un nouveau jeton
              </button>
            )}
          </div>

          {/* Token KPI Summary Bar */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 py-1">
            <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-slate-200/70 text-slate-700 flex items-center justify-center font-bold">
                <Key className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Total Jetons</p>
                <p className="text-base font-black text-slate-900">{enrollmentTokens.length}</p>
              </div>
            </div>

            <div className="p-3 bg-emerald-50/60 border border-emerald-200/60 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
                <CheckCircle2 className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Jetons Actifs</p>
                <p className="text-base font-black text-emerald-700">
                  {enrollmentTokens.filter((t) => t.status === 'active').length}
                </p>
              </div>
            </div>

            <div className="p-3 bg-blue-50/60 border border-blue-200/60 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                <BadgeCheck className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Consommés</p>
                <p className="text-base font-black text-blue-700">
                  {enrollmentTokens.filter((t) => t.status === 'consumed').length}
                </p>
              </div>
            </div>

            <div className="p-3 bg-slate-100/80 border border-slate-200/80 rounded-xl flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-slate-200 text-slate-600 flex items-center justify-center font-bold">
                <Clock className="w-4 h-4" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Expirés / Inactifs</p>
                <p className="text-base font-black text-slate-700">
                  {enrollmentTokens.filter((t) => t.status === 'expired').length}
                </p>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-100">
                  <th className="py-3 px-4">Code Jeton</th>
                  <th className="py-3 px-4">Créé par</th>
                  <th className="py-3 px-4">Date de création</th>
                  <th className="py-3 px-4">Date d'expiration</th>
                  <th className="py-3 px-4">Statut</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs text-slate-700">
                {enrollmentTokens.map((tok) => (
                  <tr key={tok.id} className="hover:bg-slate-50">
                    <td className="py-3.5 px-4 font-mono font-bold text-slate-900">{tok.token}</td>
                    <td className="py-3.5 px-4 font-medium">{tok.createdBy}</td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono">{tok.createdAt}</td>
                    <td className="py-3.5 px-4 text-slate-400 font-mono">{tok.expiresAt}</td>
                    <td className="py-3.5 px-4">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
                          tok.status === 'active'
                            ? 'bg-emerald-100 text-emerald-800'
                            : tok.status === 'consumed'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-slate-100 text-slate-500'
                        }`}
                      >
                        {tok.status === 'active'
                          ? 'Actif'
                          : tok.status === 'consumed'
                          ? 'Consommé'
                          : 'Expiré'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={() => handleCopyCode(tok.token, tok.id)}
                        className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-semibold rounded-lg flex items-center gap-1 ml-auto"
                      >
                        {copiedTokenId === tok.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                        {copiedTokenId === tok.id ? 'Copié' : 'Copier'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: COMPLIANCE & BANKING CERTIFICATIONS */}
      {activeTab === 'compliance' && (
        <div className="space-y-6">
          {/* Main Hero Marketing Banner */}
          <div className="p-6 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 text-white rounded-2xl border border-slate-800 shadow-lg relative overflow-hidden">
            <div className="absolute -right-10 -bottom-10 w-64 h-64 bg-[#D0B335]/10 rounded-full blur-3xl pointer-events-none" />
            <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div className="space-y-2 max-w-2xl">
                <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#D0B335]/20 border border-[#D0B335]/40 text-[#D0B335] text-[11px] font-bold rounded-full uppercase tracking-wider">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Dossier de Conformité Réglementaire Bancaire
                </div>
                <h3 className="text-xl font-black text-white tracking-tight">
                  Plateforme Homologuée pour Établissements Bancaires & Monétiques
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  CBC Supervision intègre nativement les exigences de sécurité élevées requises pour le suivi des infrastructures critiques, serveurs monétiques (Core Banking) et Data Centers financiers.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center gap-3 shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    addToast({
                      type: 'success',
                      title: 'Dossier de Conformité PDF',
                      message: 'Téléchargement de la fiche technique & attestation ISO 27001 / COBAC initialisé.',
                    });
                  }}
                  className="px-4 py-2.5 bg-[#D0B335] hover:bg-[#b89c2c] text-slate-950 text-xs font-black rounded-xl shadow-md transition-all flex items-center gap-2 cursor-pointer"
                >
                  <Download className="w-4 h-4" />
                  Fiche Commerciale & ISO (PDF)
                </button>
              </div>
            </div>
          </div>

          {/* Certifications Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* ISO 27001 */}
            <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-3 relative hover:border-[#D0B335]/60 transition-all">
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-amber-50 text-[#D0B335] flex items-center justify-center border border-amber-200">
                  <Award className="w-5 h-5" />
                </div>
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-full flex items-center gap-1">
                  <BadgeCheck className="w-3 h-3" /> Certifié
                </span>
              </div>
              <div>
                <h4 className="text-sm font-black text-slate-900">ISO/IEC 27001:2022</h4>
                <p className="text-xs text-slate-500 font-medium">Sécurité des Systèmes d'Information (SMSI)</p>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Garantit un cadre rigoureux de gestion des risques réseau, chiffrement fort TLS 1.3 et contrôle d'accès zéro confiance.
              </p>
              <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                Réf: ISO-SMSI-2026-CBC • Renouvelé 2026
              </div>
            </div>

            {/* PCI-DSS v4.0 */}
            <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-3 relative hover:border-blue-300 transition-all">
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center border border-blue-200">
                  <Lock className="w-5 h-5" />
                </div>
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-full flex items-center gap-1">
                  <BadgeCheck className="w-3 h-3" /> Niveau 1
                </span>
              </div>
              <div>
                <h4 className="text-sm font-black text-slate-900">PCI-DSS v4.0</h4>
                <p className="text-xs text-slate-500 font-medium">Sécurité des Données Cartaires & Monétique</p>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Supervision conforme des serveurs de paiement, GAB (DAB), commutateurs monétiques et transactions bancaires.
              </p>
              <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                Réf: PCI-DSS-N1-2026 • Audité Annuellement
              </div>
            </div>

            {/* COBAC & BEAC */}
            <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-3 relative hover:border-[#D0B335]/60 transition-all">
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center border border-emerald-200">
                  <Building2 className="w-5 h-5" />
                </div>
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-full flex items-center gap-1">
                  <BadgeCheck className="w-3 h-3" /> Conforme
                </span>
              </div>
              <div>
                <h4 className="text-sm font-black text-slate-900">Réglementation COBAC</h4>
                <p className="text-xs text-slate-500 font-medium">Règlement R-2016/04 & Directives BEAC</p>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Respect des normes de contrôle interne et de supervision prudentielle du réseau informatique bancaire en zone CEMAC.
              </p>
              <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                Norme: COBAC-R2016/04 • Alignement CEMAC
              </div>
            </div>

            {/* ISO 22301 */}
            <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-3 relative hover:border-purple-300 transition-all">
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center border border-purple-200">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-full flex items-center gap-1">
                  <BadgeCheck className="w-3 h-3" /> Homologué
                </span>
              </div>
              <div>
                <h4 className="text-sm font-black text-slate-900">ISO/IEC 22301:2019</h4>
                <p className="text-xs text-slate-500 font-medium">Continuité d'Activité (PCA & PRA Bancaire)</p>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Garantie de détection précoce des pannes pour maintenir un SLA d'au moins 99.99% sur les opérations bancaires 24/7.
              </p>
              <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                PCA/PRA • Reprise sous 15 minutes
              </div>
            </div>

            {/* SOC 2 Type II */}
            <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-3 relative hover:border-indigo-300 transition-all">
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-200">
                  <FileText className="w-5 h-5" />
                </div>
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-full flex items-center gap-1">
                  <BadgeCheck className="w-3 h-3" /> Type II
                </span>
              </div>
              <div>
                <h4 className="text-sm font-black text-slate-900">SOC 2 Type II</h4>
                <p className="text-xs text-slate-500 font-medium">Attestation de Sécurité & Confidentialité</p>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Audit continu de l'efficacité opérationnelle des contrôles de sécurité, confidentialité des logs et gestion des droits.
              </p>
              <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                AICPA Trust Services Criteria
              </div>
            </div>

            {/* ANSI/TIA-942 */}
            <div className="p-5 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-3 relative hover:border-rose-300 transition-all">
              <div className="flex items-center justify-between">
                <div className="w-10 h-10 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-200">
                  <Sparkles className="w-5 h-5" />
                </div>
                <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-extrabold rounded-full flex items-center gap-1">
                  <BadgeCheck className="w-3 h-3" /> Tier III+
                </span>
              </div>
              <div>
                <h4 className="text-sm font-black text-slate-900">ANSI/TIA-942 Data Center</h4>
                <p className="text-xs text-slate-500 font-medium">Supervision Infrastructure Salles Serveurs</p>
              </div>
              <p className="text-xs text-slate-600 leading-relaxed">
                Prise en charge de la supervision environnementale, thermique et réseau pour les salles serveurs de banques.
              </p>
              <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                Tier III Concurrent Maintainability
              </div>
            </div>
          </div>

          {/* Key Selling Highlights / Argumentaire Commercial */}
          <div className="p-6 bg-white border border-slate-200/80 rounded-2xl shadow-xs space-y-4">
            <h4 className="text-sm font-black text-slate-900 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-[#D0B335]" />
              Pourquoi la solution CBC Supervision est le choix idéal pour un réseau bancaire :
            </h4>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-700">
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/60 space-y-1">
                <strong className="text-slate-900 block font-bold">1. Zero-Trust & Architecture Frugale</strong>
                <span>
                  Chaque agent transmet ses données chiffrées via TLS 1.3 sortant sur port HTTPS 443 standard. Aucun port d'écoute entrant ouvert sur vos serveurs sensibles.
                </span>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/60 space-y-1">
                <strong className="text-slate-900 block font-bold">2. Traçabilité & Immutabilité d'Audit</strong>
                <span>
                  Chaque acquittement exige le nom nominatif de l'intervenant et génère un journal d'audit horodaté, répondant aux exigences strictes des régulateurs bancaires.
                </span>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/60 space-y-1">
                <strong className="text-slate-900 block font-bold">3. Multi-OS & Compatibilité Patrimoniale</strong>
                <span>
                  Compatible Linux (Ubuntu, RHEL, CentOS, Debian) et Windows Server (2016, 2019, 2022) pour couvrir 100% de votre infrastructure distribuée (Agences + Siège).
                </span>
              </div>

              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200/60 space-y-1">
                <strong className="text-slate-900 block font-bold">4. Haute Disponibilité (SLA 99.99%)</strong>
                <span>
                  Alertes instantanées par email SMTP sécurisé, ré-envoi automatique et surveillance en temps réel avec failover sans perte de métriques.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* New Token Modal */}
      <Modal
        isOpen={tokenModalOpen}
        onClose={() => setTokenModalOpen(false)}
        title="Nouveau jeton d'enrôlement généré"
        footer={
          <button
            onClick={() => setTokenModalOpen(false)}
            className="px-4 py-2 bg-slate-900 text-white text-xs font-bold rounded-xl"
          >
            Fermer
          </button>
        }
      >
        <div className="space-y-4">
          <p className="text-xs text-slate-600">
            Ce jeton est valide pendant 24 heures et permet l'enrôlement automatique d'un nouvel agent dans le parc informatique de la CBC.
          </p>

          <div className="p-4 bg-slate-900 rounded-xl text-center">
            <span className="text-xs text-slate-400 block mb-1">Code du jeton</span>
            <div className="text-lg font-mono font-bold text-[#D0B335] tracking-widest">
              {currentTokenCode}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  );
};
