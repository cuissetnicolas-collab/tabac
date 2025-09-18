import streamlit as st
import pandas as pd
import datetime as dt
import json, os
import unicodedata
import re

# ==============================
# --- Fonctions utilitaires ---
# ==============================
def to_float(x):
    if pd.isna(x): return 0.0
    s = str(x).replace("€","").replace(" ","").replace(",",".")
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_taux(x):
    if pd.isna(x): return None
    s = str(x).replace("%","").replace(" ","").replace(",",".")
    try:
        val = float(s)
    except ValueError:
        return None
    if val > 1: val = val/100
    return round(val,3)

def normalize_text(s):
    """Supprime accents, met en majuscules et strip"""
    s = str(s).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')

# ==============================
# --- Authentification ---
# ==============================
USERS = {
    "aurore": {"password": "12345", "name": "Aurore Demoulin"},
    "nicolas": {"password": "12345", "name": "Nicolas Cuisset"},
    "manana": {"password": "46789", "name": "Manana"},
    "louis": {"password": "195827", "name": "Louis le plus grand collaborateur du monde"}
}

def login(username, password):
    if username in USERS and password == USERS[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = USERS[username]["name"]
        return True
    return False

if "login" not in st.session_state:
    st.session_state["login"] = False

# ------------------------------
# Bloc login
# ------------------------------
if not st.session_state["login"]:
    st.title("🔑 Veuillez entrer vos identifiants")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        if login(username_input, password_input):
            st.success(f"Bienvenue {st.session_state['name']} 👋")
            st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.stop()
        else:
            st.error("❌ Identifiants incorrects")
    st.stop()

st.sidebar.success(f"Bienvenue {st.session_state['name']} 👋")
if st.sidebar.button("Déconnexion"):
    st.session_state["login"] = False
    st.experimental_rerun() if hasattr(st, "experimental_rerun") else st.stop()

# ==============================
# --- Gestion paramètres utilisateurs ---
# ==============================
PARAM_FILE = f"parametres_comptes_{st.session_state['username']}.json"

def charger_parametres():
    if os.path.exists(PARAM_FILE):
        with open(PARAM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def sauvegarder_parametres(params):
    with open(PARAM_FILE, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

params = charger_parametres()
st.sidebar.header("⚙️ Paramètres des comptes")

# ==============================
# --- Comptes familles par défaut ---
# ==============================
FAMILLES_DEFAUT = {
    "Accessoires fumeurs": "707100000",
    "Articles Divers Logista 20%": "707100000",
    "Bar 10%": "707010000",
    "Bar 20%": "707000000",
    "Boissons A Emporter": "707020000",
    "Boissons à emporter": "707022000",
    "Brasserie 10%": "707600000",
    "Brasserie A Emporter": "707021000",
    "Briquets": "707100000",
    "Chewing Gum": "707200000",
    "Chocolat 5,5%": "707210000",
    "Cigarettes Electroniques": "707100000",
    "Confiserie 20%": "707210000",
    "Confiserie 5,5%": "707210000",
    "Jeux instantanés": "467700000",
    "Loto": "467700000",
    "MONETIQUE 0 %": "467900000",
    "Paiement de Proximite": "467900000",
    "Papier tubes et filtres": "707400000",
    "Publication": "467600000",
    "Tabac": "467100000",
    "TELEPHONIE 20.00 %": "707300000",
    "Timbres poste": "467200000",
    "Transport": "467400000"
}

# ==============================
# --- Upload fichier Excel ---
# ==============================
try:
    import openpyxl
except ImportError:
    st.error("⚠️ openpyxl n'est pas installé. Vérifie ton requirements.txt et rebuild l'app.")
    st.stop()

uploaded_file = st.file_uploader("Choisir le fichier Excel", type=["xls","xlsx"])
if not uploaded_file:
    st.stop()

try:
    xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
except Exception as e:
    st.error(f"Erreur lors de la lecture du fichier Excel : {e}")
    st.stop()

# --- Lecture des feuilles ---
try:
    df_familles = pd.read_excel(xls, sheet_name="ANALYSE FAMILLES", header=2, engine="openpyxl")
    df_tva      = pd.read_excel(xls, sheet_name="ANALYSE TVA", header=2, engine="openpyxl")
    df_tiroir   = pd.read_excel(xls, sheet_name="Solde tiroir", header=2, engine="openpyxl")
    df_point    = pd.read_excel(xls, sheet_name="Point comptable", header=6, engine="openpyxl")
except Exception as e:
    st.error(f"Erreur lors de la lecture des feuilles Excel : {e}")
    st.stop()

for df in [df_familles, df_tva, df_tiroir, df_point]:
    df.columns = [str(c).strip() for c in df.columns]

# ==============================
# --- Détection de la période ---
# ==============================
def detect_periode(df):
    for r in range(min(3, len(df))):
        for c in df.columns:
            cell = str(df.iloc[r][c]).strip()
            match = re.search(r"(\d{2}/\d{4})", cell)
            if match:
                return match.group(1)
    return None

periode_str = detect_periode(df_familles)
if periode_str:
    mois, annee = periode_str.split("/")
    libelle_defaut = f"CA {mois}-{annee}"
    date_ecriture = dt.date(int(annee), int(mois), 1)
else:
    st.warning("Impossible de déterminer la période automatiquement. Utilisation de la date d'aujourd'hui.")
    date_ecriture = dt.date.today()
    libelle_defaut = f"CA {date_ecriture.strftime('%m-%Y')}"

# ==============================
# --- Paramètres comptes dynamiques ---
# ==============================
col_fam_lib = "FAMILLE" if "FAMILLE" in df_familles.columns else df_familles.columns[0]
familles_dyn = [str(f).strip() for f in df_familles[col_fam_lib] if pd.notna(f) and "TOTAL" not in str(f).upper()]

# Comptes familles
st.sidebar.subheader("Comptes Familles")
famille_to_compte_init = FAMILLES_DEFAUT.copy()
famille_to_compte_init.update(params.get("famille_to_compte", {}))

famille_to_compte = {}
for fam in familles_dyn:
    default = famille_to_compte_init.get(fam, "707000000")
    famille_to_compte[fam] = st.sidebar.text_input(f"Compte pour {fam}", value=default)

# Comptes TVA
st.sidebar.subheader("Comptes TVA")
default_tva = {0.055: "445710060", 0.10: "445710080", 0.20: "445710090"}
tva_to_compte = {}
for taux, def_cpt in default_tva.items():
    default = params.get("tva_to_compte", {}).get(str(taux), def_cpt)
    tva_to_compte[taux] = st.sidebar.text_input(f"Compte TVA {int(taux*100)}%", value=default)

# Comptes encaissements
st.sidebar.subheader("Comptes Encaissements")
default_tiroir = {"ESPECES": "530000000", "CB": "582000000", "CHEQUE": "581000000", "VIREMENT": "584000000"}
tiroir_to_compte = {}
for mode, def_cpt in default_tiroir.items():
    default = params.get("tiroir_to_compte", {}).get(mode, def_cpt)
    tiroir_to_compte[mode] = st.sidebar.text_input(f"Compte pour {mode}", value=default)

# Compte point comptable
default_point = params.get("compte_point_comptable", "467700000")
compte_point_comptable = st.sidebar.text_input("Compte Point Comptable", value=default_point)

# Sauvegarde paramètres
if st.sidebar.button("💾 Sauvegarder paramètres"):
    params_new = {
        "famille_to_compte": famille_to_compte,
        "tva_to_compte": {str(k): v for k, v in tva_to_compte.items()},
        "tiroir_to_compte": tiroir_to_compte,
        "compte_point_comptable": compte_point_comptable
    }
    sauvegarder_parametres(params_new)
    st.sidebar.success("Paramètres sauvegardés ✅")

# ==============================
# --- Paramètres écriture ---
# ==============================
# Libellé automatique modifiable
libelle = st.text_input("Libellé d'écriture", value=libelle_defaut)

# Code journal
journal_code = st.text_input("Code journal", value="VE")

# ==============================
# --- Génération des écritures ---
# ==============================
ecritures = []

# 1️⃣ CA HT par famille
col_fam_caht = "CA HT" if "CA HT" in df_familles.columns else df_familles.columns[1]
for _, row in df_familles.iterrows():
    fam = str(row[col_fam_lib])
    if "TOTAL" in fam.upper(): continue
    montant = to_float(row[col_fam_caht])
    if montant <= 0: continue
    compte = famille_to_compte.get(fam, "707000000")
    ecritures.append({
        "DATE": date_ecriture.strftime("%d/%m/%Y"),
        "CODE JOURNAL": journal_code,
        "NUMERO DE COMPTE": compte,
        "LIBELLE": f"{libelle} - {fam}",
        "DEBIT": 0,
        "CREDIT": montant
    })

# 2️⃣ TVA collectée
for _, row in df_tva.iterrows():
    lib = str(row["LIBELLE TVA"]).upper()
    if "EXONERE" in lib or "TOTAL" in lib or pd.isna(row["TVA"]): continue
    montant_tva = to_float(row["TVA"])
    if montant_tva <= 0: continue
    taux = parse_taux(row["Taux"])
    compte = tva_to_compte.get(taux)
    if compte:
        ecritures.append({
            "DATE": date_ecriture.strftime("%d/%m/%Y"),
            "CODE JOURNAL": journal_code,
            "NUMERO DE COMPTE": compte,
            "LIBELLE": f"TVA {int(taux*100)}%",
            "DEBIT": 0,
            "CREDIT": montant_tva
        })

# 3️⃣ Encaissements tiroir
for _, row in df_tiroir.iterrows():
    lib = normalize_text(row["Paiement"])
    if "TOTAL" in lib or lib == "": continue
    montant = to_float(row["Montant en euro"])
    if montant <= 0: continue

    if "ESPECE" in lib:
        compte = tiroir_to_compte["ESPECES"]
    elif "CB" in lib or "CARTE" in lib:
        compte = tiroir_to_compte["CB"]
    elif "CHEQUE" in lib:
        compte = tiroir_to_compte["CHEQUE"]
    elif "VIREMENT" in lib:
        compte = tiroir_to_compte["VIREMENT"]
    else:
        compte = "411100000"

    ecritures.append({
        "DATE": date_ecriture.strftime("%d/%m/%Y"),
        "CODE JOURNAL": journal_code,
        "NUMERO DE COMPTE": compte,
        "LIBELLE": libelle,
        "DEBIT": montant,
        "CREDIT": 0
    })

# 4️⃣ Sorties point comptable
for _, row in df_point.iterrows():
    lib = row["Libellé"]
    if pd.isna(lib) or str(lib).strip() == "": continue
    lib_str = str(lib).strip()
    if "TOTAL" in lib_str.upper(): continue
    montant = to_float(row["Montant en euro"])
    if montant == 0: continue
    ecritures.append({
        "DATE": date_ecriture.strftime("%d/%m/%Y"),
        "CODE JOURNAL": journal_code,
        "NUMERO DE COMPTE": compte_point_comptable,
        "LIBELLE": f"{libelle} - {lib_str}",
        "DEBIT": abs(montant),
        "CREDIT": 0
    })

# ==============================
# Vérification équilibre
# ==============================
df_ecritures = pd.DataFrame(ecritures)
total_debit  = df_ecritures["DEBIT"].sum()
total_credit = df_ecritures["CREDIT"].sum()
st.write("Total DEBIT :", total_debit)
st.write("Total CREDIT:", total_credit)
if round(total_debit,2) != round(total_credit,2):
    st.warning("⚠️ Les écritures ne sont pas équilibrées ! Écart : "
               f"{round(total_debit - total_credit,2)} €")
else:
    st.success("✅ Les écritures sont équilibrées.")

st.subheader("👀 Aperçu des écritures générées")
st.dataframe(df_ecritures)

# Export Excel
output_file = "ECRITURES_COMPTABLES.xlsx"
df_ecritures.to_excel(output_file, index=False)
st.download_button("📥 Télécharger le fichier généré",
                   data=open(output_file,"rb"),
                   file_name=output_file)
