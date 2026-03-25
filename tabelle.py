import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import unicodedata
import os
import re
import pdfplumber
import numpy as np

#Sonderzeichen Entfernen
def normalize(text):
    if not isinstance(text, str): 
        return ""
    text = text.strip().lower()
    return "".join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

def extract_robust(pdf_path, start_p, end_p):
    names = set()
    
    with pdfplumber.open(pdf_path) as pdf:
        for i in range(start_p - 1, end_p):
            page = pdf.pages[i]
            words = page.extract_words()
            
            if not words:
                print(f"Seite {i+1}: Kein Text gefunden")
                continue
            
            for w in words:
                text = w['text']
                
                # Wörter als Eigennamen suchen
                if re.match(r'^[A-ZÀÈÌÒÙÁÉÍÓÚ][a-zàèìòùáéíóú·çñ]+', text):
                    clean_name = re.sub(r'[,.:;]', '', text)
                    names.add(clean_name)
                    
                    
    return names

# katalansiche Namen aus beiden PDF's
catalan_names = extract_robust("catalan.pdf", 157, 168)
vicc_names = extract_robust("Viccionari_Llista_de_noms_propis_en_català.pdf", 1, 37)

katalanische_liste = catalan_names.union(vicc_names)
print(f"Referenzliste vergrößert: Von {len(catalan_names)} auf {len(katalanische_liste)} Namen.")

if catalan_names:
    print(f" {len(catalan_names)} Namen gefunden.")
    #print(sorted(list(catalan_names))[:20]) 
else:
    print("Fehler")


# Weibliche und männliche Datasets haben unterschiedliche Frequenzen. Festlegung von unterschiedlichen Thresholds
def get_weighted_castilian_core(configs):
    combined_set = set()
    
    for config in configs:
        path = config['path']
        threshold = config['threshold']
        
        if os.path.exists(path):
            df = pd.read_excel(path)
            counts = pd.to_numeric(
                df.iloc[:, 2].astype(str).str.replace('.', '', regex=False), 
                errors='coerce'
            ).fillna(0)
            
            core_castilian = df[counts > threshold]
            
            # Namen normalisieren (spanische Akzente) 
            names = {normalize(str(n)) for n in core_castilian.iloc[:, 1] if pd.notna(n)}
            combined_set.update(names)
        else:
            print(f"Nicht gefunden {path}")
            
    print(f" Gesamt: {len(combined_set)} Namen.")
    return combined_set


# empirische Tresholds
madrid_configs = [
    {
        'path': "C:/Machine/madrid_names.xls", 
        'threshold': 1500 #für top 200 namen
    },
    {
        'path': "C:/Machine/madrid_namesw.xls", 
        'threshold': 2500  #beinahe 1.5x mehr frauen.
    }
]

madrid_reference = get_weighted_castilian_core(madrid_configs)


katalanische_liste_norm = {normalize(n) for n in katalanische_liste}
clean_list = sorted(list(set(katalanische_liste_norm) - set(madrid_reference)))
print(len(clean_list))

#normalisierte Masterliste abspeichern
with open("katalanische_masterliste_rein.txt", "w", encoding="utf-8") as f:
    for name in clean_list:
        f.write(f"{name}\n")

print(f"Die saubere Liste enthält {len(clean_list)} Namen.")
#print(f"Datei 'katalanische_masterliste_rein.txt' erstellt.")


def fix_ine_numbers(val):
    if pd.isna(val): return 0.0
    try:
        # In String wandeln, Leerzeichen weg
        s = str(val).strip()
        # Tausender-Punkte entfernt 
        s = s.replace('.', '')
        # Dezimal-Komma durch Punkt ersetzt
        s = s.replace(',', '.')
        return float(s)
    except ValueError:
        return 0.0

# Gewichtete Prozentzahlen pro Provinz berechnen
def get_province_percentage(folder_path, provinz_base_name, year_suffix, clean_list):
    total_catalan_pop = 0
    total_province_pop = 0
    suffixes = [f"_{year_suffix}w.xls", f"_{year_suffix}.xls"]
    
    ref_norm = clean_list
    
    for suffix in suffixes:
        file_path = os.path.join(folder_path, provinz_base_name.lower() + suffix)
        
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            # Ignorieren von Total, Nombres
            df = df[~df.iloc[:, 1].astype(str).str.contains("TOTAL|Total|total|Ambos|Resto|Nombres", na=False)]
            
            freqs = df.iloc[:, 2].apply(fix_ine_numbers)
            names = df.iloc[:, 1].apply(lambda x: normalize(str(x)))
            
            total_province_pop += freqs.sum()
            is_cat_mask = names.isin(ref_norm)
            total_catalan_pop += (is_cat_mask * freqs).sum()
            
    if total_province_pop > 0:
        quote = (total_catalan_pop / total_province_pop) * 100
        
        if provinz_base_name.lower() in ["madrid", "barcelona", "girona"]:
            print(f"Check {provinz_base_name.upper()}:")
            print(f"Katalanisch: {total_catalan_pop:,.0f}")
            print(f"Gesamtpopulation:  {total_province_pop:,.0f}")
            print(f"Berechnete Quote:   {quote:.2f}%")
        return quote
    return 0.0


provinzen = [
    "araba", "albacete", "alicante", "almeria", "avila", "badajoz", "baleares", 
    "barcelona", "burgos", "caceres", "cadiz", "castellon", "ciudad", 
    "cordoba", "coruna", "cuenca", "girona", "granada", "guadalajara", 
    "guipuzcoa", "huelva", "huesca", "jaen", "leon", "lleida", "larioja", 
    "lugo", "madrid", "malaga", "murcia", "navarra", "ourense", "asturias", 
    "palencia", "laspalmas", "pontevedra", "salamanca", "tenerife", 
    "cantabria", "segovia", "sevilla", "soria", "tarragona", "teruel", 
    "toledo", "valencia", "valladolid", "zamora", "zaragoza", 
    "ceuta", "melilla"
]
# heatmap mapping
def plot_percentage_heatmap(stats_df, output_image):
    world = gpd.read_file("C:/Machine/GanzSpanien/spain_prov.json") 
    
    # Translation aufgrund anderer Bezeichnungen im geojson
    translation_dict = {
        "gerona": "girona", "lerida": "lleida", "castellon": "castello",
        "alicante": "alacant", "islas baleares": "baleares",
        "guipuzcoa": "gipuzkoa", "vizcaya": "bizkaia", "alava": "araba"
    }
    
    world['name_norm'] = world['name'].apply(normalize).replace(translation_dict)
    stats_df['name_norm'] = stats_df['Provincia'].apply(normalize)
    
    merged = world.merge(stats_df, on='name_norm', how='left').fillna(0)

    #Schwellenwerte und Farben
    levels = [0.1, 1, 3, 9, 18, 36]
    colors = ['#FFFFFF', '#FFFF00', '#FFA500', '#FF0000', '#800080']
    cmap, norm = mcolors.from_levels_and_colors(levels, colors)

    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    merged.plot(column='Quote', cmap=cmap, norm=norm, linewidth=0.5, 
                ax=ax, edgecolor='0.5', legend=True,
                legend_kwds={'label': "Anteil katalanischer Namen in %", 'orientation': "horizontal"})

    ax.set_title('Anteil katalanischer Namen (1980)', fontsize=16)
    ax.axis('off')
    plt.savefig(output_image, dpi=300)
    print(f"Prozent-Heatmap gespeichert: {output_image}")

ORDNER = "C:/Machine/GanzSpanien"
JAHR = "80"  

results = []
for p in provinzen:
    quote = get_province_percentage(ORDNER, p, JAHR, clean_list)
    results.append({'Provincia': p.capitalize(), 'Quote': quote})

df_80 = pd.DataFrame(results)


def get_province_percentage(folder_path, provinz_base_name, year_suffix, clean_list):
    total_catalan_pop = 0
    total_province_pop = 0
    suffixes = [f"_{year_suffix}w.xls", f"_{year_suffix}.xls"]
    
    ref_norm = clean_list
    
    for suffix in suffixes:
        file_path = os.path.join(folder_path, provinz_base_name.lower() + suffix)
        
        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            # Ignorieren von Total, Nombres (Metadaten, weswegen Zuweisung über .iloc)
            df = df[~df.iloc[:, 1].astype(str).str.contains("TOTAL|Total|total|Ambos|Resto|Nombres", na=False)]
            
            freqs = df.iloc[:, 2].apply(fix_ine_numbers)
            names = df.iloc[:, 1].apply(lambda x: normalize(str(x)))
            
            total_province_pop += freqs.sum()
            is_cat_mask = names.isin(ref_norm)
            total_catalan_pop += (is_cat_mask * freqs).sum()
            
    if total_province_pop > 0:
        quote = (total_catalan_pop / total_province_pop) * 100
        # --- DIAGNOSE-AUSGABE ---
        if provinz_base_name.lower() in ["madrid", "barcelona", "girona"]:
            print(f"Check {provinz_base_name.upper()}:")
            print(f"Katalanisch: {total_catalan_pop:,.0f}")
            print(f"Gesamtpopulation:  {total_province_pop:,.0f}")
            print(f"Berechnete Quote:   {quote:.2f}%")
        return quote
    return 0.0


provinzen = [
    "araba", "albacete", "alicante", "almeria", "avila", "badajoz", "baleares", 
    "barcelona", "burgos", "caceres", "cadiz", "castellon", "ciudad", 
    "cordoba", "coruna", "cuenca", "girona", "granada", "guadalajara", 
    "guipuzcoa", "huelva", "huesca", "jaen", "leon", "lleida", "larioja", 
    "lugo", "madrid", "malaga", "murcia", "navarra", "ourense", "asturias", 
    "palencia", "laspalmas", "pontevedra", "salamanca", "tenerife", 
    "cantabria", "segovia", "sevilla", "soria", "tarragona", "teruel", 
    "toledo", "valencia", "valladolid", "zamora", "zaragoza", 
    "ceuta", "melilla"
]
# heatmap mapping
def plot_percentage_heatmap(stats_df, output_image):
    world = gpd.read_file("C:/Machine/GanzSpanien/spain_prov.json") 
    
    # Translation aufgrund anderer Bezeichnungen im geojson
    translation_dict = {
        "gerona": "girona", "lerida": "lleida", "castellon": "castello",
        "alicante": "alacant", "islas baleares": "baleares",
        "guipuzcoa": "gipuzkoa", "vizcaya": "bizkaia", "alava": "araba"
    }
    
    world['name_norm'] = world['name'].apply(normalize).replace(translation_dict)
    stats_df['name_norm'] = stats_df['Provincia'].apply(normalize)
    
    merged = world.merge(stats_df, on='name_norm', how='left').fillna(0)

    #Schwellenwerte und Farben
    levels = [0.1, 1, 3, 9, 18, 36]
    colors = ['#FFFFFF', '#FFFF00', '#FFA500', '#FF0000', '#800080']
    cmap, norm = mcolors.from_levels_and_colors(levels, colors)

    fig, ax = plt.subplots(1, 1, figsize=(12, 10))
    merged.plot(column='Quote', cmap=cmap, norm=norm, linewidth=0.5, 
                ax=ax, edgecolor='0.5', legend=True,
                legend_kwds={'label': "Anteil katalanischer Namen in %", 'orientation': "horizontal"})

    ax.set_title('Anteil katalanischer Namen (1970)', fontsize=16)
    ax.axis('off')
    plt.savefig(output_image, dpi=300)
    print(f"Prozent-Heatmap gespeichert: {output_image}")

ORDNER = "C:/Machine/GanzSpanien70"
JAHR = "70" 


results = []
for p in provinzen:
    
    quote = get_province_percentage(ORDNER, p, JAHR, clean_list)
    results.append({'Provincia': p.capitalize(), 'Quote': quote})

df_70 = pd.DataFrame(results)


import pandas as pd
import matplotlib.pyplot as plt

def create_comparison_table_png1(df70, df80, output_file):
    # Zusammenfassen der Jahrezehnte, basierend auf ihrer Provinz
    comparison = pd.merge(
        df70[['Provincia', 'Quote']], 
        df80[['Provincia', 'Quote']], 
        on='Provincia', 
        suffixes=('_1970', '_1980')
    )

    # Berechnung der Veränderung
    def calc_change(row):
        q70 = row['Quote_1970']
        q80 = row['Quote_1980']
        if q70 == 0:
            return 100.0 if q80 > 0 else 0.0
        return ((q80 - q70) / q70) * 100

    comparison['Veränderung (%)'] = comparison.apply(calc_change, axis=1)

    comparison = comparison.sort_values(by='Quote_1980', ascending=False).tail(27) 
    
    display_df = comparison.copy()
    display_df['Quote_1970'] = display_df['Quote_1970'].map('{:.2f}%'.format)
    display_df['Quote_1980'] = display_df['Quote_1980'].map('{:.2f}%'.format)
    display_df['Veränderung (%)'] = display_df['Veränderung (%)'].map('{:+.1f}%'.format)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axis('off')
    
    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        cellLoc='center',
        loc='center',
        colColours=["#f2f2f2"] * 4
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)
    
    plt.title("Katalanischen Namensverteilung (1970 vs. 1980)", fontsize=14, pad=20)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Vergleichstabelle als PNG gespeichert: {output_file}")

def create_comparison_table_png(df70, df80, output_file):
    comparison = pd.merge(
        df70[['Provincia', 'Quote']], 
        df80[['Provincia', 'Quote']], 
        on='Provincia', 
        suffixes=('_1970', '_1980')
    )
    def calc_change(row):
        q70 = row['Quote_1970']
        q80 = row['Quote_1980']
        if q70 == 0:
            return 100.0 if q80 > 0 else 0.0 
        return ((q80 - q70) / q70) * 100

    comparison['Veränderung (%)'] = comparison.apply(calc_change, axis=1)
    comparison = comparison.sort_values(by='Quote_1980', ascending=False).head(27) 
    
    display_df = comparison.copy()
    display_df['Quote_1970'] = display_df['Quote_1970'].map('{:.2f}%'.format)
    display_df['Quote_1980'] = display_df['Quote_1980'].map('{:.2f}%'.format)
    display_df['Veränderung (%)'] = display_df['Veränderung (%)'].map('{:+.1f}%'.format)

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.axis('off')
    
    table = ax.table(
        cellText=display_df.values,
        colLabels=display_df.columns,
        cellLoc='center',
        loc='center',
        colColours=["#f2f2f2"] * 4
    )
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)
    
    plt.title("Katalanischen Namensverteilung (1970 vs. 1980)", fontsize=14, pad=20)
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Vergleichstabelle als PNG gespeichert: {output_file}")
    
# result
create_comparison_table_png(df_70, df_80, "Änderung_Prozent_Tabelle.png")
create_comparison_table_png1(df_70, df_80, "Änderung_Prozent_Tabelle1.png")