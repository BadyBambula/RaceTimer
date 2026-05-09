# 🏃 RaceTimer - Běžecký Timer

Webová Flask aplikace pro správu a měření běžeckých závodů. Automaticky zaznamenává časy běžců a exportuje výsledky do CSV a PDF.

## ✨ Funkce

- **Vytvoření závodu** - Zadejte název závodu
- **Registrace závodníků** - Přidávejte běžce s následujícími údaji:
  - Jméno a příjmení
  - Pohlaví (Muž/Žena)
  - Ročník (rok narození)
  - Klub (volitelné)
- **Měření času** - Interaktivní timer se zaznamenáváním časů
  - Kliknutí na běžce, který doběhl
  - Automatické zaznamenání času
- **Výsledky** - Seřazení běžců podle dosažených časů
  - Zobrazení pořadí s barevným zvýrazněním (1., 2., 3. místo)
- **Automatický export** - Po skončení závodu se výsledky automaticky uloží do souborů:
  - CSV - Tabulkový formát s oddělovačem středníkem
  - PDF - Profesionální sestava s tabulkou a informacemi
  - Soubory se ukládají do adresáře `results/` s časovým razítkem

## 🚀 Spuštění aplikace

### Požadavky

- Python 3.7+
- pip

### Instalace

1. Přejděte do adresáře projektu:

```bash
cd /Users/adambadura/Coding/RaceTimer
```

2. Aktivujte virtuální prostředí:

```bash
source .venv/bin/activate
```

3. Instalace závislostí:

```bash
pip install -r requirements.txt
```

4. Spuštění aplikace:

```bash
python3 main.py
```

5. Otevřete webový prohlížeč a přejděte na:

```
http://localhost:5001
```

## 📋 Struktura projektu

```
RaceTimer/
├── main.py              # Hlavní Flask aplikace
├── requirements.txt     # Python závislosti
├── templates/           # HTML šablony
│   ├── base.html       # Základní layout
│   ├── index.html      # Úvodní stránka
│   ├── setup.html      # Přidávání závodníků
│   ├── timer.html      # Měření času
│   └── results.html    # Zobrazení výsledků
├── static/             # CSS a JavaScript
│   ├── style.css       # Styly
│   └── script.js       # Skripty
├── results/            # Uložené výsledky (CSV a PDF)
└── .venv/              # Virtuální prostředí
```

## 🎯 Použití aplikace

### 1. Úvodní stránka

- Zadejte název závodu
- Klikněte "Pokračovat"

### 2. Registrace závodníků

- Vyplňte formulář pro každého běžce
- Klikněte "Přidat závodníka"
- Opakujte pro všechny účastníky
- Klikněte "Spustit Závod"

### 3. Měření času

- Timer se automaticky spustí
- Klikněte na tlačítko běžce, když doběhne
- Čas se automaticky zaznamenají
- Po skončení závodu klikněte "Skončit Závod"

### 4. Zobrazení výsledků

- Výsledky jsou seřazeny podle času
- Výsledky se **automaticky uloží** do CSV a PDF do adresáře `results/`
- Soubory jsou pojmenované: `{nazev_zavodu}_{YYYYMMDD_HHMMSS}.{csv|pdf}`
- Lze stáhnout kliknutím na tlačítka "Stáhnout CSV" nebo "Stáhnout PDF"
- Spuštění nového závodu kliknutím "Nový Závod"

## 📁 Exportovaný CSV soubor

Soubor obsahuje sloupce:

- **Pořadí** - Umístění v závodě
- **Jméno** - Jméno běžce
- **Příjmení** - Příjmení běžce
- **Pohlaví** - Pohlaví běžce (Muž/Žena)
- **Ročník** - Rok narození
- **Klub** - Klub, který běžec reprezentuje
- **Čas** - Dosažený čas ve formátu MM:SS.cs (minuty:sekundy.centisekundy)

## 📄 Exportovaný PDF soubor

PDF soubor obsahuje:

- **Nadpis** - Název závodu
- **Datum a čas** - Kdy byl PDF vygenerován
- **Tabulka s výsledky** - Seřazená podle času
  - Barevné zvýrazňování prvních tří míst
  - 1. místo - zlatá barva
  - 2. místo - stříbrná barva
  - 3. místo - bronzová barva
- **Přehledný formát** - Vhodný pro tisk

## 🎨 Designové prvky

- Moderní градiент pozadí (fialové tóny)
- Responzivní design pro různé velikosti obrazovek
- Přívětivé uživatelské rozhraní
- Barevné zvýrazňení výsledků (zlato, stříbro, bronz)

## ⚙️ Technologie

- **Backend**: Flask 3.0.0
- **Frontend**: HTML5, CSS3, JavaScript
- **Šablonizace**: Jinja2
- **PDF generování**: ReportLab
- **Export**: CSV a PDF formáty

## 📝 Poznámky

- Aplikace běží v debug modu pro vývoj
- Data jsou uložena v paměti aplikace
- Po restartu aplikace jsou všechna data smazána
- **Výsledky se automaticky uloží** do CSV a PDF při skončení každého závodu
- Soubory jsou uloženy v adresáři `results/` a zůstávají tam i po restartu aplikace
- Vytvořené soubory lze kdykoli stáhnout z webového rozhraní
- Pro produkci se doporučuje nasazení s WSGI serverem (Gunicorn)

## 🔧 Závislosti

- Flask==3.0.0
- Werkzeug==3.0.0
- reportlab==4.0.9

Další závislosti jsou instalovány automaticky:

- Jinja2
- MarkupSafe
- itsdangerous
- click
- blinker
- Pillow (pro PDF)
- chardet (pro PDF)

## 📄 Licence

Projekt je určen pro osobní a edukační použití.
