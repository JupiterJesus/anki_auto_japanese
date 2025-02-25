from __future__ import annotations

import json
import os
import xml.etree.ElementTree as Et
import pickle
import requests
import base64
import hashlib
import pathlib
import urllib

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QVBoxLayout, QSpinBox, QCheckBox, QComboBox, QProgressBar

# anki imports
import aqt.qt
import aqt.editor
import aqt.gui_hooks
import aqt.sound
import aqt.utils
import anki.hooks

from anki.notes import Note
from anki.media import MediaManager

from . import sentence_examples;
from . import wanakana;
from . import constants;

# This is used to prevent excessive lookups
previous_srcTxt = None

dicts_path = os.path.join(os.path.dirname(__file__), constants.DIR_DICTIONARIES)

def load_xml_file(filepath):
    try:
        tree = Et.parse(filepath)
        root = tree.getroot()
        return root
    except FileNotFoundError:
        print(f"File {filepath} not found.")
        return None
    except Et.ParseError:
        print(f"Error parsing the file {filepath}.")
        return None

def build_dict_from_xml(root):
    output = {}
    for entry in root.iter('entry'):
        parts_of_speech_values = set()
        keb_entries = set()
        for keb_entry in entry.findall('k_ele/keb'):
            keb_entries.add(keb_entry.text)
        pos_elements = entry.findall('sense/pos')
        for pos in pos_elements:
            # Check if <!ENTITY> in tag text and replace with full string
            pos_text = pos.text
            if pos_text and "&" in pos_text and ';' in pos_text:
                entity_value = pos_text.replace('&', '').replace(';', '')
                full_string = root.docinfo.internalDTD.entities.get(entity_value)
                parts_of_speech_values.add(full_string if full_string else pos_text)
            else:
                parts_of_speech_values.add(pos_text)

        senses = {}
        for i, sense in enumerate(entry.iter('sense'), start=1):
            glosses = [gloss.text for gloss in sense.iter('gloss')]
            gloss_text = '; '.join(glosses)
            senses[i] = f"{i}: {gloss_text}"
        reb = entry.findall('r_ele/reb')[0].text.strip()
        if len(keb_entries) == 0:
          keb_entries.add(reb);  
        for ke in keb_entries:
            if ke not in output:
                output[ke] = {"parts_of_speech_values": '; '.join(parts_of_speech_values),
                              "senses": senses, "reb": reb}
    return output

# Takes a dictionary entry and a limit
# Returns an array of english definitions of length no more than limit
def get_senses(dict_item, limit=5):
    arry = []
    for number in range(1, limit+1):
        if number in dict_item["senses"]:
            sense = dict_item["senses"][number]
            if (sense):
                sense = sense.replace(";", ",")
            arry.append(sense)
    return arry

def search_def(root, keb_text, def_limit=0):
    return_val = ""
    for entry in root.iter('entry'):
        for keb in entry.iter('keb'):  # iterate over all 'keb' children of 'entry'
            if keb.text == keb_text:  # compare the text of the 'keb' element with the text you're looking for
                # Gather glosses from each sense
                for i, sense in enumerate(entry.iter('sense'), start=1):
                    glosses = [gloss.text for gloss in sense.iter('gloss')]
                    gloss_text = '; '.join(glosses)
                    return_val += f"{i}: {gloss_text}<br>"
                    def_limit = def_limit - 1
                    if def_limit == 0:
                        break
                return return_val[:-4] if return_val.endswith("<br>") else return_val
    return return_val[:-4] if return_val.endswith("<br>") else return_val

def search_reb(root, keb_text):
    # Assuming root is an ElementTree instance, and element names are as per your code base
    for entry in root.iter('entry'):
        keb = entry.find('k_ele/keb')
        if keb is not None and keb.text == keb_text:
            return entry.findall('r_ele/reb')[0].text.strip()
    return ""

def search_pos(root, keb_text):
    pos_values = set()
    for entry in root.iter('entry'):
        keb = entry.find('k_ele/keb')
        if keb is not None and keb.text == keb_text:
            pos_elements = entry.findall('sense/pos')
            for pos in pos_elements:
                # Check if <!ENTITY> in tag text and replace with full string
                pos_text = pos.text
                if pos_text and "&" in pos_text and ';' in pos_text:
                    entity_value = pos_text.replace('&', '').replace(';', '')
                    full_string = root.docinfo.internalDTD.entities.get(entity_value)
                    pos_values.add(full_string if full_string else pos_text)
                else:
                    pos_values.add(pos_text)
    return '; '.join(pos_values)

def search_furigana(data, target_text):
    for obj in data:
        if obj['text'] == target_text:
            furigana = obj['furigana']
            result = ""
            last_no_kanji = False
            for fu in furigana:
                if "rt" in fu:
                    if last_no_kanji:
                        result += " "
                    result += fu['ruby']
                    result += "[" + fu['rt'] + "]"
                else:
                    result += fu['ruby']
                    last_no_kanji = True
            return result
    return ""


def get_romaji(src_txt: str) -> str:
    
    if src_txt:
        romaji_result = wanakana.to_romaji(src_txt)
        return romaji_result
    else:
        return ""

def parts_of_speech_conversion(src_txt: str, type_str: str) -> str:
    output_str = ""
    if "noun" in type_str.lower():
        output_str += "Noun<br>"
    if "adjectival nouns" in type_str.lower():
        output_str += "な-adjective<br>"
    if "adjective (keiyoushi)" in type_str.lower():
        output_str += "い-adjective<br>"
    if type_str.startswith("transitive verb") or " transitive verb" in type_str.lower():
        output_str += "Transitive "
        if "intransitive verb" in type_str.lower():
            output_str += "and intransitive "
    if not(type_str.startswith("transitive verb") or " transitive verb" in type_str.lower()) and "intransitive verb" in type_str.lower():
        output_str += "Intransitive "
    if "ichidan" in type_str.lower():
        output_str += "ichidan verb<br>"
    if "godan" in type_str.lower():
        last_char = src_txt[-1:]
        output_str += "godan verb with '" + last_char + "' ending<br>"
    if "suru" in type_str.lower():
        output_str += "suru verb " + src_txt + "する<br>"
    return output_str.strip().removesuffix("<br>") # remove any superfluous breaks

def do_conjugation(src_txt: str, fields: list, note: Note, type_str: str) -> str:
    changed = False
    masu_form = "";
    te_form = "";
    past_form = "";
    nai_form = "";
    pot_form = "";
    pass_form = "";
    cond_form = "";
    vol_form = "";
    tai_form = "";
    imp_form = "";
    ending = src_txt[-1:];
    stem = src_txt[:-1];
    
    if "verb" in type_str.lower():
        if "来る" == src_txt:
            masu_form = "来[き]ます";
            te_form = "来[き]て";
            past_form = "来[き]た";
            nai_form = "来[こ]ない【です】 ・ 来[こ]なかった【です】";
            pot_form = "来[こ]れる";
            pass_form = "来[こ]られる";
            cond_form = "来[く]れば～ ・ 来[き]たら～";
            ｖol_form = "来[く]よう";
            tai_form = "来[き]たい【です】";
            imp_form = "来[こ]い ・ 来[き]てください ・ 来[き]なさい";
        elif "する" == src_txt:
            masu_form = "します";
            te_form = "して";
            past_form = "した";
            nai_form = "しない【です】・ しなかった【です】";
            pot_form = "できる";
            pass_form = "される";
            cond_form = "すれば～ ・ したら～";
            vol_form = "しろ";
            tai_form = "したい【です】";
            imp_form = "しろ ・ してください ・ しなさい";
        elif "ichidan" in type_str.lower():
            masu_form = stem + "ます"
            te_form = stem + "て"
            past_form = stem + "た";
            nai_form = stem + "ない【です】・ " + stem + "なかった【です】";
            pot_form = stem + "れる";
            pass_form = stem + "られる";
            cond_form = stem + "れば～ ・ " + stem + "たら～";
            vol_form = stem + "よう";
            tai_form = stem + "たい【です】";
            imp_form = stem + "ろ ・ " + stem + "てください ・ "+ stem + "なさい";
        elif "godan" in type_str.lower():
            if "す" == ending:
                masu_form = stem + "します";
                te_form = stem + "して";
                past_form = stem + "した";
                nai_form = stem + "さない【です】・ " + stem + "さなかった【です】";
                pot_form = stem + "せる";
                pass_form = stem + "される";
                cond_form = stem + "せば～ ・ " + stem + "したら～";
                vol_form = stem + "そう";
                tai_form = stem + "したい【です】";
                imp_form = stem + "せ ・ " + stem + "してください ・ "+ stem + "しなさい";
            elif "る" == ending:
                masu_form = stem + "ります";
                te_form = stem + "って";
                past_form = stem + "った";
                nai_form = stem + "らない【です】・ " + stem + "らなかった【です】";
                pot_form = stem + "れる";
                pass_form = stem + "られる";
                cond_form = stem + "れば～ ・ " + stem + "ったら～";
                vol_form = stem + "ろう";
                tai_form = stem + "りたい【です】";
                imp_form = stem + "れ ・ " + stem + "ってください ・ "+ stem + "りなさい";
            elif "む" == ending:
                masu_form = stem + "みます";
                te_form = stem + "んで";
                past_form = stem + "";
                nai_form = stem + "さない【です】・ " + stem + "さなかった【です】";
                pot_form = stem + "める";
                pass_form = stem + "まれる";
                cond_form = stem + "めば～ ・ " + stem + "んだら～";
                vol_form = stem + "もう";
                tai_form = stem + "みたい【です】";
                imp_form = stem + "め ・ " + stem + "んでください ・ "+ stem + "みなさい";
            elif "ぶ" == ending:
                masu_form = stem + "びます";
                te_form = stem + "んで";
                past_form = stem + "んだ";
                nai_form = stem + "ばない【です】・ " + stem + "ばなかった【です】";
                pot_form = stem + "ばべる";
                pass_form = stem + "ばれる";
                cond_form = stem + "べば～ ・ " + stem + "んだら～";
                vol_form = stem + "ぼう";
                tai_form = stem + "びたい【です】";
                imp_form = stem + "べ ・ " + stem + "んでください ・ "+ stem + "びなさい";
            elif "ぬ" == ending:
                masu_form = stem + "にます";
                te_form = stem + "んで";
                past_form = stem + "んだ";
                nai_form = stem + "なない【です】・ " + stem + "ななかった【です】";
                pot_form = stem + "ねる";
                pass_form = stem + "なれる";
                cond_form = stem + "ねば～ ・ " + stem + "んだら～";
                vol_form = stem + "のう";
                tai_form = stem + "にたい【です】";
                imp_form = stem + "ね ・ " + stem + "んでください ・ "+ stem + "になさい";
            elif "つ" == ending:
                masu_form = stem + "ちます"
                te_form = stem + "って";
                past_form = stem + "った";
                nai_form = stem + "たない【です】・ " + stem + "たなかった【です】";
                pot_form = stem + "てる";
                pass_form = stem + "たれる";
                cond_form = stem + "てば～ ・ " + stem + "ったら～";
                vol_form = stem + "とう";
                tai_form = stem + "ちたい【です】";
                imp_form = stem + "て ・ " + stem + "ってください ・ "+ stem + "ちなさい";
            elif "く" == ending:
                masu_form = stem + "きます";
                if stem == "行":
                    te_form = stem + "って"
                    past_form = stem + "った";
                    imp_form = stem + "け ・ " + stem + "ってください ・ "+ stem + "きなさい";
                    cond_form = stem + "けば～ ・ " + stem + "ったら～";
                else:
                    te_form = stem + "いて"
                    past_form = stem + "いた";
                    imp_form = stem + "け ・ " + stem + "いてください ・ "+ stem + "きなさい";
                    cond_form = stem + "けば～ ・ " + stem + "いたら～";
                nai_form = stem + "かない【です】・ " + stem + "かなかった【です】";
                pot_form = stem + "ける";
                pass_form = stem + "かれる";
                vol_form = stem + "こう";
                tai_form = stem + "きたい【です】";
            elif "ぐ" == ending:
                masu_form = stem + "ぎます";
                te_form = stem + "いで";
                past_form = stem + "いだ";
                nai_form = stem + "がない【です】・ " + stem + "がなかった【です】";
                pot_form = stem + "げる";
                pass_form = stem + "がれる";
                cond_form = stem + "げば～ ・ " + stem + "いだら～";
                vol_form = stem + "ごう";
                tai_form = stem + "ぎたい【です】";
                imp_form = stem + "げ ・ " + stem + "いでください ・ "+ stem + "ぎなさい";
            elif "う" == ending:
                masu_form = stem + "います";
                te_form = stem + "って";
                past_form = stem + "った";
                nai_form = stem + "わない【です】・ " + stem + "わなかった【です】";
                pot_form = stem + "える";
                pass_form = stem + "われる";
                cond_form = stem + "えば～ ・ " + stem + "ったら～";
                vol_form = stem + "おう";
                tai_form = stem + "いたい【です】";
                imp_form = stem + "え ・ " + stem + "ってください ・ "+ stem + "いなさい";
        elif "suru" in type_str.lower():
            stem = src_txt.removesuffix("する") # just in case the dictionary def has suru in it already
            masu_form = stem + "します";
            te_form = stem + "して";
            past_form = stem + "した";
            nai_form = stem + "しない【です】・ " + stem + "しなかった【です】";
            pot_form = stem + "できる";
            pass_form = stem + "される";
            cond_form = stem + "すれば～ ・ " + stem + "したら～";
            vol_form = stem + "しろ";
            tai_form = stem + "したい【です】";
            imp_form = stem + "しろ ・ " + stem + "してください ・ "+ stem + "しなさい";
    elif "adjective (keiyoushi)" in type_str.lower():
        if "いい" == src_txt:
            stem = よ;
        te_form = stem + "くて";
        past_form = stem + "かった";
        nai_form = stem + "くない【です】・" + stem + "くなかった【です】";
        
    if masu_form and replace_field(fields, note, constants.SETTING_MASU_DEST_FIELD, masu_form):
        changed = True
    if te_form and replace_field(fields, note, constants.SETTING_TE_DEST_FIELD, te_form):
        changed = True
    if past_form and replace_field(fields, note, constants.SETTING_PAST_DEST_FIELD, past_form):
        changed = True
    if nai_form and replace_field(fields, note, constants.SETTING_NAI_DEST_FIELD, nai_form):
        changed = True
    if pot_form and replace_field(fields, note, constants.SETTING_POT_DEST_FIELD, pot_form):
        changed = True
    if pass_form and replace_field(fields, note, constants.SETTING_PASS_DEST_FIELD, pass_form):
        changed = True
    if cond_form and replace_field(fields, note, constants.SETTING_COND_DEST_FIELD, cond_form):
        changed = True
    if vol_form and replace_field(fields, note, constants.SETTING_VOL_DEST_FIELD, vol_form):
        changed = True
    if tai_form and replace_field(fields, note, constants.SETTING_TAI_DEST_FIELD, tai_form):
        changed = True
    if imp_form and replace_field(fields, note, constants.SETTING_IMP_DEST_FIELD, imp_form):
        changed = True
    return changed
  
def do_meanings(src_txt: str, fields: list, note: Note, def_num: int, jmdict_info) -> str:
    changed = False;
    senses = get_senses(jmdict_info, def_num)
    
    # Grab the meanings, then put them all in the meaning field or 
    # split between meaning and alternates fields, if defined
    if config.get(constants.SETTING_MEANING_FIELD) in fields:
        if config.get(constants.SETTING_ALTERNATES_FIELD) in fields:
            # If we're doing separate meaning and alternates fields,
            # Put the first definition into the meaning field by itself, with the 1: stripped
            if (senses):
                primary = senses.pop(0).removeprefix("1: ")
                if insert_if_empty(fields, note, constants.SETTING_MEANING_FIELD, primary):
                    changed = True;
                if senses:
                    alternates = "<br>".join(senses);
                    if insert_if_empty(fields, note, constants.SETTING_ALTERNATES_FIELD, alternates):
                        changed = True;
        else: # otherwise, we just put all meanings into a list in the meaning field
            if senses:
                defs = "<br>".join(senses);
                if insert_if_empty(fields, note, constants.SETTING_MEANING_FIELD, defs):
                    changed = True;
            
    return changed
 
def do_pitch(src_txt: str, fields: list, note: Note, jmdict_info) -> str: 
    changed = False;
    
    # TODO Load pitch accent for word
    # TODO Draw pitch accent svg for word
    return changed;
 
def do_audio(word: str, kana: str, fields: list, note: Note, jmdict_info) -> str: 

    changed = False;
    dest_field = config[constants.SETTING_AUDIO_DEST_FIELD]
    if dest_field in fields:
        if note[dest_field] != "":
            return changed;
            
    if config.get(constants.SETTING_AUDIO_DEST_FIELD) in fields:
      # Download audio
      # If audio downloaded, append it
      filename = "jpod-" + word + "-" + kana + ".mp3";
      #print("Word: " + word);
      #print("Kana: " + kana);
      #print("Filename: " + filename);

      temp_dir = os.path.join(pathlib.Path(__file__).parent.absolute(), constants.DIR_TEMP_FOLDER);
      dl_path = os.path.join(temp_dir, filename);
      #print("DL Path: " + dl_path);
      
      
      jpod_url = get_jpod_audio_url(urllib.parse.quote(word) if word else "", urllib.parse.quote(kana) if kana else "")
      #print("JPOD Url: " + jpod_url);
      if jpod_url:
          jpod_audio = get_jpod_audio(jpod_url);
          if jpod_audio:
            with open(dl_path, "wb") as f:
                f.write(jpod_audio.read());
                jpod_audio.close();
          
            audio_filename = note.col.media.add_file(dl_path);
            #print("Media: " + audio_filename);
            changed = insert_if_empty(fields, note, constants.SETTING_AUDIO_DEST_FIELD, "[sound:" + audio_filename + "]");
        
    return changed
    
def on_focus_lost(changed: bool, note: Note, current_field_index: int) -> bool:
    # Get the field names
    fields = aqt.mw.col.models.field_names(note.note_type());
    
    # Get the modified field
    modified_field = fields[current_field_index];
    
    # Check if it's the same as config, if so proceed
    if modified_field == config[constants.SETTING_SRC_FIELD]:
        # Strip for good measure
        src_txt = aqt.mw.col.media.strip(note[modified_field]);
        if src_txt != "" and (previous_srcTxt is None or src_txt != previous_srcTxt):
            changed = update_note(note, src_txt);
                   
    return changed;
    
def update_note(note: Note, src_txt):
    changed = False;
    fields = aqt.mw.col.models.field_names(note.note_type());
    
    # Added the field checks for people who don't have all fields for whatever reason
    if config.get(constants.SETTING_FURI_DEST_FIELD) in fields:
        if insert_if_empty(fields, note, constants.SETTING_FURI_DEST_FIELD, search_furigana(jmdict_furi_data, src_txt)):
            changed = True;
    
    kana_txt = get_field(fields, note, constants.SETTING_KANA_DEST_FIELD);
    def_num = config[constants.SETTING_NUM_DEFS]
    
    jmdict_info = dict_data.get(src_txt, None);
    if jmdict_info is not None:
        
        if do_meanings(src_txt, fields, note, def_num, jmdict_info):
            changed = True;
         
        if config.get(constants.SETTING_KANA_DEST_FIELD) in fields:
            if insert_if_empty(fields, note, constants.SETTING_KANA_DEST_FIELD, jmdict_info.get("reb", "")):
                changed = True;
            kana_txt = get_field(fields, note, constants.SETTING_KANA_DEST_FIELD);
                
        if config.get(constants.SETTING_TYPE_DEST_FIELD) in fields:
            if insert_if_empty(fields, note, constants.SETTING_TYPE_DEST_FIELD, parts_of_speech_conversion(src_txt, jmdict_info.get("parts_of_speech_values", ""))):
                changed = True;
                
        if config.get(constants.SETTING_SENTENCE_DEST_FIELD) in fields:
            sentence_num = config[constants.SETTING_NUM_SENTENCES];
            if insert_if_empty(fields, note, constants.SETTING_SENTENCE_DEST_FIELD, jsl.find_example_sentences_by_word_formatted(src_txt, sentence_num)):
                changed = True;
            
        if do_conjugation(src_txt, fields, note, jmdict_info.get("parts_of_speech_values", "")):
            changed = True;
    
            
    if config.get(constants.SETTING_AUDIO_DEST_FIELD) in fields:
        if do_audio(src_txt, kana_txt, fields, note, jmdict_info):
            changed = True;
            
    if config.get(constants.SETTING_ROMAJI_DEST_FIELD) in fields:
        if insert_if_empty(fields, note, constants.SETTING_ROMAJI_DEST_FIELD, get_romaji(kana_txt)):
            changed = True;
    
    return changed;
            
def insert_if_empty(fields: list, note: Note, dest_config: str, new_text: str):
    if new_text == "":
        return False;
    dest_field = config[dest_config];
    if dest_field in fields:
        if note[dest_field] == "":
            note[dest_field] = new_text;
        return True;

def append_field(fields: list, note: Note, dest_config: str, new_text: str):
    if new_text == "":
        return False;
    dest_field = config[dest_config];
    if dest_field in fields:
        note[dest_field] = note[dest_field] + new_text;
        return True;

def replace_field(fields: list, note: Note, dest_config: str, new_text: str):
    if new_text == "":
        return False;
    dest_field = config[dest_config];
    if dest_field in fields:
        if new_text == note[dest_field]:
            return False;
        note[dest_field] = new_text;
        return True;
    return False;

def get_field(fields: list, note: Note, dest_config: str):
    dest_field = config[dest_config];
    if dest_field in fields:
        return note[dest_field];
    return "";

def get_jpod_audio(url):
    try:
        #requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        req = urllib.request.Request(url);
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0');
        #req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8')
        #req.add_header('Accept-Language', 'en-US,en;q=0.5')

        r = urllib.request.urlopen(req);

        #r = requests.get(url, verify=False, timeout=5)
        return r
    except Exception as inst:
        print("EXCEPTION doing request!");
        print(inst);
        return None;

def validate_jpod_audio_url(url):
    jpod_audio = get_jpod_audio(url);
    if jpod_audio:
        size = jpod_audio.headers.get('content-length');
        return size != "52288"; # invalid audio;
    else:
        return False;

def audioIsPlaceholder(data):
    m = hashlib.md5();
    m.update(data);
    return m.hexdigest() == '7e2c2f954ef6051373ba916f000168dc';

def get_jpod_audio_url(kanji, kana):
    if (kanji == ""):
      url = 'https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kana={}'.format(kana);
    else:
      url = 'https://assets.languagepod101.com/dictionary/japanese/audiomp3.php?kanji={}&kana={}'.format(kanji, kana);
    print("url: " + url);
    return url if (validate_jpod_audio_url(url)) else '';

def get_jpod_audio_base64(kanji, kana):
    jpod_url = get_jpod_audio_url(kanji, kana);
    if jpod_url:
        jpod_audio = get_jpod_audio(jpod_url);
        if jpod_audio:
            return 'data:audio/mp3;base64,' + str(base64.b64encode(jpod_audio.content));
        else:
            return '';
    return '';
    
def settings_dialog():
    dialog = QDialog(aqt.mw)
    dialog.setWindowTitle("Furigana Addon")

    # Input Field
    box_query = QHBoxLayout()
    label_query = QLabel("Input field:")
    text_query = QLineEdit("")
    text_query.setMinimumWidth(200)
    box_query.addWidget(label_query)
    box_query.addWidget(text_query)

    # All the output stuff
    box_furigana = QHBoxLayout()
    label_furigana = QLabel("Furigana field:")
    text_furigana = QLineEdit("")
    text_furigana.setMinimumWidth(200)
    box_furigana.addWidget(label_furigana)
    box_furigana.addWidget(text_furigana)

    box_def = QHBoxLayout()
    label_def = QLabel("Definition field:")
    text_def = QLineEdit("")
    text_def.setMinimumWidth(200)
    box_def.addWidget(label_def)
    box_def.addWidget(text_def)

    box_alt = QHBoxLayout()
    label_alt = QLabel("Alternate/additional definitions field:")
    text_alt = QLineEdit("")
    text_alt.setMinimumWidth(200)
    box_alt.addWidget(label_alt)
    box_alt.addWidget(text_alt)

    box_kana = QHBoxLayout()
    label_kana = QLabel("Kana field:")
    text_kana = QLineEdit("")
    text_kana.setMinimumWidth(200)
    box_kana.addWidget(label_kana)
    box_kana.addWidget(text_kana)

    box_romaji = QHBoxLayout()
    label_romaji = QLabel("Romaji field:")
    text_romaji = QLineEdit("")
    text_romaji.setMinimumWidth(200)
    box_romaji.addWidget(label_romaji)
    box_romaji.addWidget(text_romaji)

    box_pitch = QHBoxLayout()
    label_pitch = QLabel("Pitch Accent field:")
    text_pitch = QLineEdit("")
    text_pitch.setMinimumWidth(200)
    box_pitch.addWidget(label_pitch)
    box_pitch.addWidget(text_pitch)

    box_audio = QHBoxLayout()
    label_audio = QLabel("Audio field:")
    text_audio = QLineEdit("")
    text_audio.setMinimumWidth(200)
    box_audio.addWidget(label_audio)
    box_audio.addWidget(text_audio)

    box_type = QHBoxLayout()
    label_type = QLabel("Type field:")
    text_type = QLineEdit("")
    text_type.setMinimumWidth(200)
    box_type.addWidget(label_type)
    box_type.addWidget(text_type)

    box_def_nums = QHBoxLayout()
    label_def_nums = QLabel("Number of Defs:")
    text_def_nums = QSpinBox()
    text_def_nums.setMinimumWidth(200)
    box_def_nums.addWidget(label_def_nums)
    box_def_nums.addWidget(text_def_nums)

    box_sentence = QHBoxLayout()
    label_sentence = QLabel("Example Sentence field:")
    text_sentence = QLineEdit("")
    text_sentence.setMinimumWidth(200)
    box_sentence.addWidget(label_sentence)
    box_sentence.addWidget(text_sentence)

    box_sentc_nums = QHBoxLayout()
    label_sentc_nums = QLabel("Number of Sentences:")
    text_sentc_nums = QSpinBox()
    text_sentc_nums.setMinimumWidth(200)
    box_sentc_nums.addWidget(label_sentc_nums)
    box_sentc_nums.addWidget(text_sentc_nums)

    box_te = QHBoxLayout()
    label_te = QLabel("-te form field:")
    text_te = QLineEdit("")
    text_te.setMinimumWidth(200)
    box_te.addWidget(label_te)
    box_te.addWidget(text_te)

    box_masu = QHBoxLayout()
    label_masu = QLabel("-masu form field:")
    text_masu = QLineEdit("")
    text_masu.setMinimumWidth(200)
    box_masu.addWidget(label_masu)
    box_masu.addWidget(text_masu)

    box_past = QHBoxLayout()
    label_past = QLabel("plain past form field:")
    text_past = QLineEdit("")
    text_past.setMinimumWidth(200)
    box_past.addWidget(label_past)
    box_past.addWidget(text_past)
    
    box_nai = QHBoxLayout();
    label_nai = QLabel("negative/nai form field:");
    text_nai = QLineEdit("");
    text_nai.setMinimumWidth(200);
    box_nai.addWidget(label_nai);
    box_nai.addWidget(text_nai);
    
    box_pass = QHBoxLayout();
    label_pass = QLabel("Passive form field:");
    text_pass = QLineEdit("");
    text_pass.setMinimumWidth(200);
    box_pass.addWidget(label_pass);
    box_pass.addWidget(text_pass);
    
    box_pot = QHBoxLayout();
    label_pot = QLabel("Potential form field:");
    text_pot = QLineEdit("");
    text_pot.setMinimumWidth(200);
    box_pot.addWidget(label_pot);
    box_pot.addWidget(text_pot);
    
    box_cond = QHBoxLayout();
    label_cond = QLabel("Conditional/ba form field:");
    text_cond = QLineEdit("");
    text_cond.setMinimumWidth(200);
    box_cond.addWidget(label_cond);
    box_cond.addWidget(text_cond);
    
    box_vol = QHBoxLayout();
    label_vol = QLabel("volitional form field:");
    text_vol = QLineEdit("");
    text_vol.setMinimumWidth(200);
    box_vol.addWidget(label_vol);
    box_vol.addWidget(text_vol);
    
    box_tai = QHBoxLayout();
    label_tai = QLabel("wanting/-tai form field:");
    text_tai = QLineEdit("");
    text_tai.setMinimumWidth(200);
    box_tai.addWidget(label_tai);
    box_tai.addWidget(text_tai);
    
    box_imp = QHBoxLayout();
    label_imp = QLabel("imperative forms field:");
    text_imp = QLineEdit("");
    text_imp.setMinimumWidth(200);
    box_imp.addWidget(label_imp);
    box_imp.addWidget(text_imp);
    
    ok = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok);
    cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel);

    def init_configui():
        text_query.setText(config.get(constants.SETTING_SRC_FIELD, "not_set"));
        text_furigana.setText(config.get(constants.SETTING_FURI_DEST_FIELD, "not_set"));
        text_def.setText(config.get(constants.SETTING_MEANING_FIELD, "not_set"));
        text_def.setText(config.get(constants.SETTING_AUDIO_DEST_FIELD, "not_set"));
        text_alt.setText(config.get(constants.SETTING_ALTERNATES_FIELD, "not_set"));
        text_kana.setText(config.get(constants.SETTING_KANA_DEST_FIELD, "not_set"));
        text_romaji.setText(config.get(constants.SETTING_ROMAJI_DEST_FIELD, "not_set"));
        text_pitch.setText(config.get(constants.SETTING_PITCH_DEST_FIELD, "not_set"));
        text_type.setText(config.get(constants.SETTING_TYPE_DEST_FIELD, "WordType"));
        text_def_nums.setValue(config.get(constants.SETTING_NUM_DEFS, 5));
        text_sentence.setText(config.get(constants.SETTING_SENTENCE_DEST_FIELD, "Examples"));
        text_sentc_nums.setValue(config.get(constants.SETTING_NUM_SENTENCES, 3));
        text_masu.setText(config.get(constants.SETTING_MASU_DEST_FIELD, "not_set"));
        text_te.setText(config.get(constants.SETTING_TE_DEST_FIELD, "not_set"));
        text_past.setText(config.get(constants.SETTING_PAST_DEST_FIELD, "not_set"));
        text_nai.setText(config.get(constants.SETTING_NAI_DEST_FIELD, "not_set"));
        text_pot.setText(config.get(constants.SETTING_POT_DEST_FIELD, "not_set"));
        text_pass.setText(config.get(constants.SETTING_PASS_DEST_FIELD, "not_set"));
        text_cond.setText(config.get(constants.SETTING_COND_DEST_FIELD, "not_set"));
        text_vol.setText(config.get(constants.SETTING_VOL_DEST_FIELD, "not_set"));
        text_tai.setText(config.get(constants.SETTING_TAI_DEST_FIELD, "not_set"));
        text_imp.setText(config.get(constants.SETTING_IMP_DEST_FIELD, "not_set"));

    def save_config():
        config[constants.SETTING_SRC_FIELD] = text_query.text();
        config[constants.SETTING_FURI_DEST_FIELD] = text_furigana.text();
        config[constants.SETTING_MEANING_FIELD] = text_def.text();
        config[constants.SETTING_ALTERNATES_FIELD] = text_alt.text();
        config[constants.SETTING_KANA_DEST_FIELD] = text_kana.text();
        config[constants.SETTING_AUDIO_DEST_FIELD] = text_audio.text();
        config[constants.SETTING_ROMAJI_DEST_FIELD] = text_romaji.text();
        config[constants.SETTING_PITCH_DEST_FIELD] = text_pitch.text();
        config[constants.SETTING_TYPE_DEST_FIELD] = text_type.text();
        config[constants.SETTING_NUM_DEFS] = text_def_nums.value();
        config[constants.SETTING_SENTENCE_DEST_FIELD] = text_sentence.text();
        config[constants.SETTING_NUM_SENTENCES] = text_sentc_nums.value();
        config[constants.SETTING_MASU_DEST_FIELD] = text_masu.text();
        config[constants.SETTING_TE_DEST_FIELD] = text_te.text();
        config[constants.SETTING_PAST_DEST_FIELD] = text_past.text();
        config[constants.SETTING_NAI_DEST_FIELD] = text_nai.text();
        config[constants.SETTING_POT_DEST_FIELD] = text_pot.text();
        config[constants.SETTING_PASS_DEST_FIELD] = text_pass.text();
        config[constants.SETTING_COND_DEST_FIELD] = text_cond.text();
        config[constants.SETTING_VOL_DEST_FIELD] = text_vol.text();
        config[constants.SETTING_TAI_DEST_FIELD] = text_tai.text();
        config[constants.SETTING_IMP_DEST_FIELD] = text_imp.text();
        
        aqt.mw.addonManager.writeConfig(__name__, config);
        
        dialog.close();

    def layout_everything():
        layout = QVBoxLayout();
        dialog.setLayout(layout);

        layout.addLayout(box_query);
        layout.addLayout(box_furigana);
        layout.addLayout(box_kana);
        layout.addLayout(box_romaji);
        layout.addLayout(box_pitch);
        layout.addLayout(box_audio);
        layout.addLayout(box_def);
        layout.addLayout(box_alt);
        layout.addLayout(box_type);
        layout.addLayout(box_def_nums);
        layout.addLayout(box_sentence);
        layout.addLayout(box_sentc_nums);
        
        layout.addLayout(box_masu);
        layout.addLayout(box_te);
        layout.addLayout(box_past);
        layout.addLayout(box_nai);
        layout.addLayout(box_pot);
        layout.addLayout(box_cond);
        layout.addLayout(box_vol);
        layout.addLayout(box_tai);
        layout.addLayout(box_imp);

        layout.addWidget(ok);
        layout.addWidget(cancel);

    init_configui();
    ok.clicked.connect(save_config);
    cancel.clicked.connect(dialog.close);

    layout_everything();

    dialog.exec();
    
def batch_update_dialog():
    dialog = QDialog(aqt.mw);
    dialog.setWindowTitle(constants.GUI_BROWSER_BATCH_DIALOG_TITLE);
    
    # Dropdown box (combo box) for available note types
    dropdown_layout = QHBoxLayout();
    label_note_type = QLabel("Select Note Type:");
    note_type_dropdown = QComboBox();
    
    # Fetch available note types from the collection and populate the dropdown
    note_types = aqt.mw.col.models.all_names();
    if note_types:
        note_type_dropdown.addItems(note_types);
        
    dropdown_layout.addWidget(label_note_type);
    dropdown_layout.addWidget(note_type_dropdown);
    
    # Progress bar at the bottom of the layout
    progress_bar = QProgressBar();
    progress_bar.setRange(0, 0);  # Default initial range
    progress_bar.setValue(0);
    progress_bar.setTextVisible(True);
    progress_bar.setFormat("%v/%m notes updated");
    
    # OK and Cancel buttons
    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Close);
    
    def on_ok_clicked():
        selected_note_type = note_type_dropdown.currentText();
        if selected_note_type:
            print(f"Selected Note Type: {selected_note_type}");
            model = aqt.mw.col.models.by_name(selected_note_type);
            if model:
                note_ids = aqt.mw.col.db.list(
                    "SELECT id FROM notes WHERE mid = ?", model["id"]
                );
                for idx, note_id in enumerate(note_ids):
                    note = aqt.mw.col.getNote(note_id);
                    src_field = config.get(constants.SETTING_SRC_FIELD, "");
                    if src_field in note and note[src_field]:
                        if update_note(note, note[src_field]):
                            note.flush();
                    progress_bar.setValue(idx + 1);
        dialog.close();
        
    def on_cancel_clicked():
        dialog.close();
        
    # Event handler for when the combobox selection changes
    def on_note_type_changed(index):
        if index >= 0:
            selected_note_type = note_type_dropdown.itemText(index);
            
            # Get the ID of the selected note type
            model = aqt.mw.col.models.by_name(selected_note_type);
            if model:
                # Fetch total number of notes of the selected type
                note_count = aqt.mw.col.db.scalar(
                    "SELECT COUNT() FROM notes WHERE mid = ?", model["id"]
                );
                print(f"Total Notes for {selected_note_type}: {note_count}");
                
                # Update progress bar maximum to the count
                progress_bar.setRange(0, note_count);
                progress_bar.setValue(0);  # Reset progress bar value
    # Connect signals to slots
    note_type_dropdown.currentIndexChanged.connect(on_note_type_changed);
    button_box.accepted.connect(on_ok_clicked);
    button_box.rejected.connect(on_cancel_clicked);
    layout = QVBoxLayout(dialog);
    layout.addLayout(dropdown_layout);
    layout.addWidget(progress_bar);
    layout.addWidget(button_box);
    dialog.setLayout(layout);
    dialog.exec();
    
def init_menu():
  
    def browerMenusInit(browser: aqt.browser.Browser):
      
        # Make a new browser menu item for this addon
        menu = aqt.qt.QMenu(constants.ADDON_NAME, browser.form.menubar)
        browser.form.menubar.addMenu(menu)

        action_browser_settings = QAction(constants.GUI_BROWSER_SETTINGS_DIALOG_TITLE, browser);
        aqt.qconnect(action_browser_settings.triggered, settings_dialog);
        menu.addAction(action_browser_settings);
        
        batch_browser_update = QAction(constants.GUI_BROWSER_BATCH_DIALOG_TITLE, browser);
        aqt.qconnect(batch_browser_update.triggered, batch_update_dialog);
        menu.addAction(batch_browser_update);
        
        def selected_batch_update_dialog():
            dialog = QDialog(aqt.mw);
            dialog.setWindowTitle(constants.GUI_BROWSER_SELECTED_BATCH_DIALOG_TITLE);
           
            notes = browser.selectedNotes();
                
            # Progress bar at the bottom of the layout
            progress_bar = QProgressBar();
            progress_bar.setRange(0, len(notes));  # Default initial range
            progress_bar.setValue(0);
            progress_bar.setTextVisible(True);
            progress_bar.setFormat("%v/%m notes updated");
            
            # OK and Cancel buttons
            button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Close);
            
            def on_ok_clicked():
              
                for idx, note_id in enumerate(notes):
                    note = aqt.mw.col.getNote(note_id);
                    src_field = config.get(constants.SETTING_SRC_FIELD, "");
                    if src_field in note and note[src_field]:
                        if update_note(note, note[src_field]):
                            note.flush();
                    progress_bar.setValue(idx + 1);
                dialog.close();
            
            def on_cancel_clicked():
                dialog.close();
                
            # Connect signals to slots
            button_box.accepted.connect(on_ok_clicked);
            button_box.rejected.connect(on_cancel_clicked);
            layout = QVBoxLayout(dialog);
            layout.addWidget(progress_bar);
            layout.addWidget(button_box);
            dialog.setLayout(layout);
            dialog.exec();
            
        selected_batch_browser_update = QAction(constants.GUI_BROWSER_SELECTED_BATCH_DIALOG_TITLE, browser);
        aqt.qconnect(selected_batch_browser_update.triggered, selected_batch_update_dialog);
        menu.addAction(selected_batch_browser_update);
        
    action_settings = QAction(constants.GUI_SETTINGS_DIALOG_TITLE, aqt.mw);
    aqt.qconnect(action_settings.triggered, settings_dialog);
    aqt.mw.form.menuTools.addAction(action_settings);
    
    action_batch_update = QAction(constants.GUI_BATCH_DIALOG_TITLE, aqt.mw);
    aqt.qconnect(action_batch_update.triggered, batch_update_dialog);
    aqt.mw.form.menuTools.addAction(action_batch_update);
    
    # browser menus
    aqt.gui_hooks.browser_menus_did_init.append(browerMenusInit)
    
    # GUI Hooks
    aqt.gui_hooks.editor_did_unfocus_field.append(on_focus_lost);
    aqt.gui_hooks.editor_did_init_buttons.append(editor_button_setup);
    
def get_field_names_array():
    array = [
             config.get(constants.SETTING_SRC_FIELD), 
             config.get(constants.SETTING_FURI_DEST_FIELD), 
             config.get(constants.SETTING_KANA_DEST_FIELD), 
             config.get(constants.SETTING_ROMAJI_DEST_FIELD), 
             config.get(constants.SETTING_PITCH_DEST_FIELD),
             config.get(constants.SETTING_TYPE_DEST_FIELD),
             config.get(constants.SETTING_MEANING_FIELD),
             config.get(constants.SETTING_ALTERNATES_FIELD),
             config.get(constants.SETTING_SENTENCE_DEST_FIELD),
             config.get(constants.SETTING_AUDIO_DEST_FIELD),
             config.get(constants.SETTING_MASU_DEST_FIELD),
             config.get(constants.SETTING_TE_DEST_FIELD),
             config.get(constants.SETTING_PAST_DEST_FIELD),
             config.get(constants.SETTING_NAI_DEST_FIELD),
             config.get(constants.SETTING_POT_DEST_FIELD),
             config.get(constants.SETTING_PASS_DEST_FIELD),
             config.get(constants.SETTING_COND_DEST_FIELD),
             config.get(constants.SETTING_VOL_DEST_FIELD),
             config.get(constants.SETTING_TAI_DEST_FIELD),
             config.get(constants.SETTING_IMP_DEST_FIELD)
            ];
    return array;

def clear_fields(editor):
    fields = aqt.mw.col.models.field_names(editor.note.note_type());
    dest_fields = get_field_names_array();
    for field in fields:
        if field in dest_fields:
            editor.note[field] = "";
    editor.loadNote();

def editor_button_setup(buttons, editor):
    icons_path = os.path.join(os.path.dirname(__file__), constants.DIR_ICONS);
    clear_icon = constants.ICON_CLEAR;
    clear_icon_path = os.path.join(icons_path, clear_icon);
    btn = editor.addButton(clear_icon_path,
                           'clear_fields',
                           clear_fields,
                           tip='Clear fields');
    buttons.append(btn);



# Dictionary Furigana Dictionary
with open(os.path.join(dicts_path, constants.FILE_JMDICT_JSON), 'r', encoding='utf-8-sig') as f:
    jmdict_furi_data = json.load(f);

# JMDict Data Load
data_file = os.path.join(dicts_path, constants.FILE_JMDICT_PICKLE) # DIctionary LLoad?
# Check to see if we already have a file
if os.path.isfile(data_file):
    # Open the pickle file and load the data
    with open(data_file, 'rb') as file:
        dict_data = pickle.load(file);
else:
    # No pickle file found, so we build the array and save for next time. This takes a few seconds.
    jmdict_data = load_xml_file(os.path.join(dicts_path, constants.FILE_JMDICT_XML));
    if jmdict_data is not None:
        print(f"Successfully loaded XML file. Root tag is '{jmdict_data.tag}'.");
    else:
        print("Failed to load XML file.");
    dict_data = build_dict_from_xml(jmdict_data);
    jmdict_data = None;
    with open(data_file, "wb") as file:
        pickle.dump(dict_data, file);

# Begin Section for example sentences
if os.path.isfile(os.path.join(dicts_path, constants.FILE_SENTENCES_PICKLE)):
    jsl = sentence_examples.JapaneseSentenceLib();
    jsl.load_pickle_file(os.path.join(dicts_path, constants.FILE_SENTENCES_PICKLE));
else:
    jsl = sentence_examples.JapaneseSentenceLib();

    # Won't include these in the release... However... can be downloaded from the following.
    # https://tatoeba.org/en/downloads
    jsl.load_sentences_from_file(os.path.join(dicts_path, 'translated_sentences.tsv'));
    jsl.load_sentence_rating_data(os.path.join(dicts_path, 'users_sentences.csv'));
    jsl.save_pickle_file(os.path.join(dicts_path, constants.FILE_SENTENCES_PICKLE));
    
# TODO Load nhk pronunciation dictionary
# Create config variable
config = aqt.mw.addonManager.getConfig(__name__);

# Add the options to the menu
init_menu();
