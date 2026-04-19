import i18n from "./config";

/**
 * UI plugins (or lazily loaded features) keep their own JSON next to the plugin:
 *   src/plugins/<pluginId>/locales/en.json
 *   src/plugins/<pluginId>/locales/de.json
 * At runtime, load those files (e.g. via dynamic import) and call this once per plugin.
 * Use namespace `plugin:<pluginId>` with useTranslation(`plugin:${pluginId}`).
 */
export function registerPluginLocales(
  pluginId: string,
  bundles: { en: Record<string, unknown>; de: Record<string, unknown> }
): void {
  const ns = pluginNamespace(pluginId);
  i18n.addResourceBundle("en", ns, bundles.en, true, true);
  i18n.addResourceBundle("de", ns, bundles.de, true, true);
}

export function pluginNamespace(pluginId: string): string {
  return `plugin:${pluginId}`;
}
