import streamlit as st
import pandas as pd
import datetime as dt
import json, os, unicodedata, re

# ==============================
# --- Fonctions utilitaires ---
# ==============================
def to_float(x):
    if pd.isna(x): return 0.0
    s = str(x).replace("€","").replace(" ","").replace(",",".")
    try: return float(s)
    except ValueError: return 0.0

def parse_taux(x):
    if pd.isna(x): return None
    s = str(x).replace("%","").replace(" ","").replace(",",".")
    try: val = float(s)
    except ValueError: return None
    if val > 1: val = val/100
    return round(val,3)

def normalize_text(s):
    s = str(s).strip().upper()
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')

def detect_periode(xls):
    """
    Cherche une valeur de type MM/YYYY dans les 3 premières lignes
    de l'onglet 'ANALYSE FAMILLES' (celui qui contient la période).
    """
    try:
        # on lit SANS header pour voir les 3 premières lignes brutes
        df_head = pd.read_excel(xls, sheet_name="ANALYSE FAMILLES",
                                header=None, nrows=3, engine="openpyxl")
    except Exception as e:
        st.error(f"❌ Impossible de lire l'onglet 'ANALYSE FAMILLES' : {e}")
        st.stop()

    pattern = re.compile(r"^\s*(0[1-9]|1[0-2])/[0-9]{4}\s*$")
    for col in df_head.columns:
        for val in df_head[col].dropna():
            if pattern.match(str(val).strip()):
                mois_str, annee_str = str(val).strip().split("/")
                return dt.date(int(annee_str), int(mois_str), 1)
    st.warning("⚠️ Impossible de déterminer la période automatiquement (aucun MM/YYYY trouvé dans les 3 premières lignes)")
    return dt.date.today()

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

if not st.session_state["login"]:
    st.title("🔑 Veuillez entrer vos identifiants")
    u = st.text_input("Identifiant")
    p = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        if login(u, p):
            st.success(f"Bienvenue {st.session_state['name']} 👋")
            st.experimental_rerun()
        else:
            st.error("❌ Identifiants incorrects")
    st.stop()

st.sidebar.success(f"Bienvenue {st.session_state['name']} 👋")
if st.sidebar.button("Déconnexion"):
    st.session_state["login"] = False
    st.experimental_rerun()

# ==============================
# --- Paramètres utilisateurs ---
# ==============================
PARAM_FILE = f"parametres_comptes_{st.session_state['username']}.json"
def charger_parametres():
    if os.path.exists(PARAM_FILE):
        with open(PARAM_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    return {}
def sauvegarder_parametres(params):
    with open(PARAM_FILE,"w",encoding="utf-8") as f:
        json.dump(params,f,ensure_ascii=False,indent=2)

params = charger_parametres()
st.sidebar.header("⚙️ Paramètres des comptes")

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

try:
    import openpyxl
except ImportError:
    st.error("⚠️ openpyxl n'est pas installé.")
    st.stop()

uploaded_file = st.file_uploader("Choisir le fichier Excel", type=["xls","xlsx"])
if not uploaded_file:
    st.stop()

try:
    xls = pd.ExcelFile(uploaded_file, engine="openpyxl")
except Exception as e:
    st.error(f"Erreur lors de la lecture du fichier Excel : {e}")
    st.stop()

# 🔎 Détection période
periode_date = detect_periode(xls)

# lecture des feuilles réelles
try:
    df_familles = pd.read_excel(xls,"ANALYSE FAMILLES",header=2,engine="openpyxl")
    df_tva      = pd.read_excel(xls,"ANALYSE TVA",header=2,engine="openpyxl")
    df_tiroir   = pd.read_excel(xls,"Solde tiroir",header=2,engine="openpyxl")
    df_point    = pd.read_excel(xls,"Point comptable",header=6,engine="openpyxl")
except Exception as e:
    st.error(f"Erreur lors de la lecture des feuilles Excel : {e}")
    st.stop()

for df in [df_familles, df_tva, df_tiroir, df_point]:
    df.columns = [str(c).strip() for c in df.columns]

col_fam_lib = "FAMILLE" if "FAMILLE" in df_familles.columns else df_familles.columns[0]
familles_dyn = [str(f).strip() for f in df_familles[col_fam_lib] if pd.notna(f) and "TOTAL" not in str(f).upper()]

st.sidebar.subheader("Comptes Familles")
famille_to_compte_init = FAMILLES_DEFAUT.copy()
famille_to_compte_init.update(params.get("famille_to_compte", {}))
famille_to_compte = {f: st.sidebar.text_input(f"Compte pour {f}", value=famille_to_compte_init.get(f,"707000000"))
                     for f in familles_dyn}

st.sidebar.subheader("Comptes TVA")
default_tva = {0.055:"445710060",0.10:"445710080",0.20:"445710090"}
tva_to_compte = {t: st.sidebar.text_input(f"Compte TVA {int(t*100)}%", 
                                         value=params.get("tva_to_compte",{}).get(str(t),defc))
                 for t,defc in default_tva.items()}

st.sidebar.subheader("Comptes Encaissements")
default_tiroir = {"ESPECES":"530000000","CB":"582000000","CHEQUE":"581000000","VIREMENT":"584000000"}
tiroir_to_compte = {m: st.sidebar.text_input(f"Compte pour {m}", 
                            value=params.get("tiroir_to_compte",{}).get(m,defc))
                    for m,defc in default_tiroir.items()}

default_point = params.get("compte_point_comptable","467700000")
compte_point_comptable = st.sidebar.text_input("Compte Point Comptable", value=default_point)

if st.sidebar.button("💾 Sauvegarder paramètres"):
    params_new = {
        "famille_to_compte": famille_to_compte,
        "tva_to_compte": {str(k):v for k,v in tva_to_compte.items()},
        "tiroir_to_compte": tiroir_to_compte,
        "compte_point_comptable": compte_point_comptable
    }
    sauvegarder_parametres(params_new)
    st.sidebar.success("Paramètres sauvegardés ✅")

# 🗓 Utilise la période détectée par défaut
date_ecriture = st.date_input("Date d'écriture", value=periode_date)
libelle_defaut = f"CA {periode_date.strftime('%m-%Y')}"
libelle = st.text_input("Libellé d'écriture", value=libelle_defaut)
journal_code = st.text_input("Code journal", value="VE")

# ==============================
# --- Génération des écritures ---
# ==============================
ecritures = []
col_fam_caht = "CA HT" if "CA HT" in df_familles.columns else df_familles.columns[1]
for _,row in df_familles.iterrows():
    fam = str(row[col_fam_lib])
    if "TOTAL" in fam.upper(): continue
    montant = to_float(row[col_fam_caht])
    if montant<=0: continue
    compte = famille_to_compte.get(fam,"707000000")
    ecritures.append({
        "DATE": date_ecriture.strftime("%d/%m/%Y"),
        "CODE JOURNAL": journal_code,
        "NUMERO DE COMPTE": compte,
        "LIBELLE": f"{libelle} - {fam}",
        "DEBIT": 0,
        "CREDIT": montant
    })

for _,row in df_tva.iterrows():
    lib = str(row["LIBELLE TVA"]).upper()
    if "EXONERE" in lib or "TOTAL" in lib or pd.isna(row["TVA"]): continue
    montant_tva = to_float(row["TVA"])
    if montant_tva<=0: continue
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

for _,row in df_tiroir.iterrows():
    lib = normalize_text(row["Paiement"])
    if "TOTAL" in lib or lib=="": continue
    montant = to_float(row["Montant en euro"])
    if montant<=0: continue
    if "ESPECE" in lib: compte = tiroir_to_compte["ESPECES"]
    elif "CB" in lib or "CARTE" in lib: compte = tiroir_to_compte["CB"]
    elif "CHEQUE" in lib: compte = tiroir_to_compte["CHEQUE"]
    elif "VIREMENT" in lib: compte = tiroir_to_compte["VIREMENT"]
    else: compte = "411100000"
    ecritures.append({
        "DATE": date_ecriture.strftime("%d/%m/%Y"),
        "CODE JOURNAL": journal_code,
        "NUMERO DE COMPTE": compte,
        "LIBELLE": libelle,
        "DEBIT": montant,
        "CREDIT": 0
    })

for _,row in df_point.iterrows():
    lib = row["Libellé"]
    if pd.isna(lib) or str(lib).strip()=="": continue
    lib_str = str(lib).strip()
    if "TOTAL" in lib_str.upper(): continue
    montant = to_float(row["Montant en euro"])
    if montant==0: continue
    ecritures.append({
        "DATE": date_ecriture.strftime("%d/%m/%Y"),
        "CODE JOURNAL": journal_code,
        "NUMERO DE COMPTE": compte_point_comptable,
        "LIBELLE": f"{libelle} - {lib_str}",
        "DEBIT": abs(montant),
        "CREDIT": 0
    })

df_ecritures = pd.DataFrame(ecritures)
total_debit, total_credit = df_ecritures["DEBIT"].sum(), df_ecritures["CREDIT"].sum()
st.write("Total DEBIT :", total_debit)
st.write("Total CREDIT:", total_credit)
if round(total_debit,2) != round(total_credit,2):
    st.warning(f"⚠️ Les écritures ne sont pas équilibrées ! Écart : {round(total_debit - total_credit,2)} €")
else:
    st.success("✅ Les écritures sont équilibrées.")

st.subheader("👀 Aperçu des écritures générées")
st.dataframe(df_ecritures)

output_file = "ECRITURES_COMPTABLES.xlsx"
df_ecritures.to_excel(output_file, index=False)
st.download_button("📥 Télécharger le fichier généré",
                   data=open(output_file,"rb"),
                   file_name=output_file)
