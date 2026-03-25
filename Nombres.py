import pdfplumber
import re
import pandas as pd
import unicodedata
import numpy as np
import os
import geopandas as gpd
import matplotlib.pyplot as plt


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
                print(f"Kein Text")
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

            names = {normalize(str(n)) for n in core_castilian.iloc[:, 1] if pd.notna(n)}
            combined_set.update(names)
        else:
            print(f"Datei nicht gefunden: {path}")
            
    print(f"Gewichteter Kern: {len(combined_set)} Namen.")
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

with open("katalanische_masterliste_rein.txt", "w", encoding="utf-8") as f:
    for name in clean_list:
        f.write(f"{name}\n")

print(f"Die Liste enthält {len(clean_list)} Namen.")
#print(f"Datei 'katalanische_masterliste_rein.txt' erstellt.")


def fix_ine_numbers(val):
    if pd.isna(val): 
        return 0.0
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).replace(',', '.')
        return float(s)
    except ValueError:
        return 0.0
    

def label_and_weight_data(input_path, output_path, reference_names):
   
    
    
    df = pd.read_excel(input_path, thousands='.', decimal=',')
    ref_norm = {normalize(n) for n in reference_names}

    # Datenverarbeitung durch iloc, Spalten, da Metatext die Auswertung stört
    names_col = df.iloc[:, 1]
    freq_col = df.iloc[:, 2].apply(fix_ine_numbers)

    # Labelling (0 oder 1)
    df['is_catalan'] = names_col.apply(lambda x: 1 if normalize(str(x)) in ref_norm else 0)
    df['katalanische_haeufigkeit'] = df['is_catalan'] * freq_col


    df.to_excel(output_path, index=False)

    total_population = freq_col.sum()
    catalan_population = df['katalanische_haeufigkeit'].sum()
    
    if total_population > 0:
        quote = (catalan_population / total_population) * 100
    else:
        quote = 0

    print("-" * 30)
    print(f"Analyse abgeschlossen!")
    print(f"Anzahl verschiedener katalanischer Namen: {int(df['is_catalan'].sum())}")
    print(f"Gesamtanzahl von Personen im Datensatz: {int(total_population):,}")
    print(f"Davon katalanische Namen (gewichtet): {int(catalan_population):,}")
    print(f"Quote: {quote:.2f}%")
    print("-" * 30)


#label_and_weight_data("C:/Machine/GanzSpanien/madrid_80.xls", "Analyse_Barcelona6.xlsx", clean_list)

def get_yearly_stats(folder_path, year_suffix, reference_names):
    file_m = os.path.join(folder_path, f"l{year_suffix}.xls")
    file_w = os.path.join(folder_path, f"l{year_suffix}w.xls")
    
    ref_norm = {normalize(n) for n in reference_names}
    stats = {'cat_m': 0, 'cat_w': 0, 'others': 0}

    for gender, path in [('m', file_m), ('w', file_w)]:
        if os.path.exists(path):
            df = pd.read_excel(path)
            freqs = df.iloc[:, 2].apply(fix_ine_numbers)
            
            is_cat = df.iloc[:, 1].apply(lambda x: 1 if normalize(str(x)) in ref_norm else 0)
            
            cat_count = (is_cat * freqs).sum()
            total_count = freqs.sum()
            
            if gender == 'm':
                stats['cat_m'] = cat_count
            else:
                stats['cat_w'] = cat_count
                
            stats['others'] += (total_count - cat_count)
            
    return stats



def plot_absolute_with_percent_labels(base_path, jahre, labels, reference_list):
    cat_m_abs = []
    cat_w_abs = []
    others_abs = []
    
    cat_m_pct = []
    cat_w_pct = []
    others_pct = []

    
    for j in jahre:
        
        res = get_yearly_stats(base_path, j, reference_list)
        
        m, w, o = res['cat_m'], res['cat_w'], res['others']
        total = m + w + o

        cat_m_abs.append(m)
        cat_w_abs.append(w)
        others_abs.append(o)
        
        # Prozentuale Werte berechnen
        if total > 0:
            cat_m_pct.append((m / total) * 100)
            cat_w_pct.append((w / total) * 100)
            others_pct.append((o / total) * 100)
        else:
            cat_m_pct.append(0); cat_w_pct.append(0); others_pct.append(0)

  
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(12, 8))

    # Balken mit Prozenten
    bar_others = ax.bar(x, others_abs, label='Kastilisch / Andere', color='#D3D3D3', edgecolor='white')
    bar_w = ax.bar(x, cat_w_abs, bottom=others_abs, label='Weiblich (Katalanisch)', color='#FF7F7F', edgecolor='white')
    
    # Oben zuersrt Männlich (startet mit Others + Weiblich)
    bottom_m = np.array(others_abs) + np.array(cat_w_abs)
    bar_m = ax.bar(x, cat_m_abs, bottom=bottom_m, label='Männlich (Katalanisch)', color='#4A90E2', edgecolor='white')


    def add_labels(rects, percentages, bottoms=None):
        for i, (rect, pct) in enumerate(zip(rects, percentages)):
            height = rect.get_height()
            if pct < 2: continue
            
            base = 0 if bottoms is None else bottoms[i]
            y_pos = base + (height / 2)
            
            ax.text(rect.get_x() + rect.get_width()/2., y_pos,
                    f'{pct:.1f}%', ha='center', va='center', 
                    color='black', fontweight='bold', fontsize=9)

    add_labels(bar_others, others_pct)
    add_labels(bar_w, cat_w_pct, others_abs)
    add_labels(bar_m, cat_m_pct, bottom_m)

    ax.set_ylabel('Anzahl der Personen (gesamt)')
    ax.set_title('Katalanische Namensrückentwicklung der Provinz Lleida')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
    
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, p: format(int(x), ',')))

    plt.tight_layout()
    plt.savefig("Lleida_Prozent.png", dpi=300)
    #print("Diagramm 'Lleida_Prozent.png' erstellt.")


plot_absolute_with_percent_labels("C:/Machine/Lleida", 
                                 ["30", "40", "50", "60", "70", "80", "90"], 
                                 ["1930", "1940", "1950", "1960", "1970", "1980", "1990"], 
                                 clean_list)




