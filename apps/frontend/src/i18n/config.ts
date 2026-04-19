import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import deCommon from "../locales/de/common.json";
import enCommon from "../locales/en/common.json";

const SUPPORTED = ["en", "de"] as const;

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { common: enCommon },
      de: { common: deCommon },
    },
    fallbackLng: "en",
    supportedLngs: [...SUPPORTED],
    defaultNS: "common",
    ns: ["common"],
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      caches: ["localStorage"],
      lookupLocalStorage: "agent-ui.lang",
    },
  });

export { SUPPORTED };
export default i18n;
