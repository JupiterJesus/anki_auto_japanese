import enum

ENV_VAR_ANKI_LANGUAGE_TOOLS_BASE_URL = "ANKI_LANGUAGE_TOOLS_BASE_URL";

ENABLE_SENTRY_CRASH_REPORTING = True;

LOGGER_NAME = "anki_auto_japanese";
LOGGER_NAME_TEST = "test_anki_auto_japanese";

# PATHS
DIR_WANAKANA = "wanakana";
DIR_DICTIONARIES = "dicts";
DIR_TEMP_FOLDER = "temp";
DIR_ICONS = "icons";

FILE_JMDICT_JSON = "JmdictFurigana.json";
FILE_JMDICT_XML = "JMdict_e.xml";
FILE_JMDICT_PICKLE = "dill.pkl";
FILE_SENTENCES_PICKLE = "sentences.pickle";

ANKIWEB_ADDON_ID = "1727436922"; # FIX THIS

CONFIG_ADDON_NAME = "anki-auto-japanese";
ADDON_NAME = "Auto-Japanese";

if ANKIWEB_ADDON_ID in __file__:
    CONFIG_ADDON_NAME = ANKIWEB_ADDON_ID

# GUI
MENU_PREFIX = ADDON_NAME + ':'
TITLE_PREFIX = ADDON_NAME + ': '

GUI_BROWSER_SETTINGS_DIALOG_TITLE = "Settings";
GUI_BROWSER_BATCH_DIALOG_TITLE = "Batch Update";
GUI_BROWSER_SELECTED_BATCH_DIALOG_TITLE = "Batch Update Selected Items";

GUI_SETTINGS_DIALOG_TITLE = TITLE_PREFIX + GUI_BROWSER_SETTINGS_DIALOG_TITLE;
GUI_BATCH_DIALOG_TITLE = TITLE_PREFIX + GUI_BROWSER_BATCH_DIALOG_TITLE;

# SETTINGS

SETTING_SRC_FIELD = "kanji_field";
SETTING_FURI_DEST_FIELD = "furigana_field";
SETTING_KANA_DEST_FIELD = "kana_field";
SETTING_ROMAJI_DEST_FIELD = "romaji_field";
SETTING_TYPE_DEST_FIELD = "type_field";
SETTING_PITCH_DEST_FIELD = "pitch_field";
SETTING_MASU_DEST_FIELD = "masu_field";
SETTING_TE_DEST_FIELD = "te_field";
SETTING_PAST_DEST_FIELD = "past_field";
SETTING_NAI_DEST_FIELD = "nai_field";
SETTING_COND_DEST_FIELD = "cond_field";
SETTING_POT_DEST_FIELD = "pot_field";
SETTING_PASS_DEST_FIELD = "pass_field";
SETTING_VOL_DEST_FIELD = "vol_field";
SETTING_TAI_DEST_FIELD = "tai_field";
SETTING_IMP_DEST_FIELD = "imp_field";
SETTING_MEANING_FIELD = "definition_field";
SETTING_ALTERNATES_FIELD = "alternates_field";
SETTING_NUM_DEFS = "number_of_defs";
SETTING_NUM_SENTENCES = "number_of_sentences";
SETTING_SENTENCE_DEST_FIELD = "sentence_field";
SETTING_AUDIO_DEST_FIELD = "audio_field";

# ICONS
ICON_CLEAR = "icons8-clear-50.png";