/// <reference types="vite/client" />

/**
 * Variables d'environnement exposées au client par Vite.
 *
 * Sans ce fichier, `import.meta.env` n'était pas typé et `tsc --noEmit`
 * échouait sur axios.config.ts — l'une des raisons pour lesquelles aucune
 * vérification de types ne pouvait être branchée en intégration continue.
 */
interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
