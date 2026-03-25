import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import unicodedata
import os
import re
import pdfplumber
import numpy as np

# Sonderzeichen entfernen
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
                print(f"Kein Text gefunden")
                continue
            
           
            
            for w in words:
                text = w['text']
                
                # Suche nach Eigennamen
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
    print(f"{len(catalan_names)} Namen gefunden.")
    #print(sorted(list(catalan_names))[:20]) 
else:
    print("Fehler")



def get_weighted_castilian_core(configs):
    # Weibliche und männliche Datasets haben unterschiedliche Frequenzen. Festlegung von unterschiedlichen Thresholds

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
            
            # Namen normalisieren (ohne spansiche Akzente)
            names = {normalize(str(n)) for n in core_castilian.iloc[:, 1] if pd.notna(n)}
            combined_set.update(names)
        else:
            print(f"Datei nicht gefunden: {path}")
            
    print(f"{len(combined_set)} Namen.")
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

# Textdatei speichern
with open("katalanische_masterliste_rein.txt", "w", encoding="utf-8") as f:
    for name in clean_list:
        f.write(f"{name}\n")

print(f"Die Liste enthält {len(clean_list)} Namen.")
#print(f"Datei 'katalanische_masterliste_rein.txt' wurde erstellt.")


def fix_ine_numbers(val):
    if pd.isna(val): return 0.0
    try:
        s = str(val).strip()
        s = s.replace('.', '')
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
# mapping heatmap
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
    print(f"✅ Prozent-Heatmap gespeichert: {output_image}")

ORDNER = "C:/Machine/GanzSpanien"
JAHR = "80"  
results = []
for p in provinzen:
    quote = get_province_percentage(ORDNER, p, JAHR, clean_list)
    results.append({'Provincia': p.capitalize(), 'Quote': quote})

df_percent_stats = pd.DataFrame(results)
plot_percentage_heatmap(df_percent_stats, "Katalan_Boom_Prozent_1980_compl.png")
print("Beispiele für Namen in der cleanlist:")
print(clean_list[:50])
df_sorted = df_percent_stats.sort_values(by='Quote', ascending=False)

print("\n" + "="*40)
print("ANTEIL KATALANISCHER NAMEN (1980)")
print(df_sorted.to_string(index=False, formatters={'Quote': '{:,.2f}%'.format}))

#print("="*40)


# Ob alle Dateien nach Dateinamen gefunden wurden
def check_files(folder_path, province_list, year_suffix):
    files_in_folder = [f.lower() for f in os.listdir(folder_path)]
    missing = []

    print(f"Suche Dateien für Jahr {year_suffix}...\n")
    for p in province_list:
        file_m = f"{p.lower()}_{year_suffix}.xls"
        file_w = f"{p.lower()}_{year_suffix}w.xls"
        
        found_m = file_m in files_in_folder
        found_w = file_w in files_in_folder
        
        if not found_m or not found_w:
            missing.append((p, file_m if not found_m else "", file_w if not found_w else ""))

    if not missing:
        print("Alle Dateien gefunden")
    else:
        print("Dateien fehlen oder sind falsch benannt:")
        for p, m, w in missing:
            print(f"- {p:12}: {m} {w}")
check_files("C:/Machine/GanzSpanien", provinzen, "80")
