import csv
import io
import json
import os
from collections import defaultdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(BASE_DIR, 'results')
ACTIVE_STATE_PATH = os.path.join(RESULTS_DIR, 'current_race.json')
RACE_REGISTRY_PATH = os.path.join(RESULTS_DIR, 'race_registry.json')

if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

race_data = {
    'race_name': None,
    'race_type': 'individual',
    'start_mode': 'mass',
    'start_interval_seconds': 30,
    'status': 'preparation',
    'race_started': False,
    'race_date': None,
    'shared_start_timestamp': None,
    'runners': {},
    'runner_counter': 0,
    'race_times': {},
    'unassigned_finishes': [],
    'audit_log': [],
    'start_plan': []
}

PDF_FONT_NAME = 'ArialUnicode'
PDF_FONT_PATH = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'
if os.path.exists(PDF_FONT_PATH):
    try:
        pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, PDF_FONT_PATH))
    except Exception:
        PDF_FONT_NAME = 'Helvetica'
else:
    PDF_FONT_NAME = 'Helvetica'


def _load_json_file(file_path, default):
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, 'r', encoding='utf-8') as file_handle:
            return json.load(file_handle)
    except Exception:
        return default


def _save_json_file(file_path, payload):
    with open(file_path, 'w', encoding='utf-8') as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _now_iso():
    return datetime.now().isoformat(timespec='seconds')


def _race_year(race_date_value=None):
    race_datetime = _parse_datetime(race_date_value) or datetime.now()
    return race_datetime.year


def format_race_datetime(race_date):
    if isinstance(race_date, datetime):
        return race_date.strftime('%d.%m.%Y %H:%M:%S')
    return race_date or '-'


def sanitize_filename(filename):
    import re
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    return filename.replace(' ', '_')


def normalize_gender(value):
    if not value:
        return ''
    normalized = str(value).strip().lower()
    if normalized in {'m', 'muž', 'muz', 'male'}:
        return 'Muž'
    if normalized in {'z', 'žena', 'zena', 'female', 'f'}:
        return 'Žena'
    return str(value).strip()


def calculate_age(birth_year, race_date_value=None):
    try:
        return _race_year(race_date_value) - int(birth_year)
    except Exception:
        return None


def calculate_category(birth_year, gender, race_date_value=None):
    age = calculate_age(birth_year, race_date_value)
    normalized_gender = normalize_gender(gender)
    if age is None:
        return ''

    if age <= 7:
        return 'Under 8'
    if age <= 9:
        return 'Děti I'
    if age <= 11:
        return 'Děti II'
    if age <= 13:
        return 'Junioři I'
    if age <= 15:
        return 'Junioři II'
    if age <= 18:
        return 'Mládež'

    if normalized_gender == 'Muž':
        if age <= 39:
            return 'Muži A'
        if age <= 49:
            return 'Muži B'
        if age <= 59:
            return 'Muži C'
        if age <= 69:
            return 'Muži D'
        return 'Muži E'

    if normalized_gender == 'Žena':
        if age <= 39:
            return 'Ženy F'
        if age <= 49:
            return 'Ženy G'
        return 'Ženy H'

    return ''


def format_time(seconds):
    if seconds is None:
        return ''
    minutes = int(seconds) // 60
    seconds_part = int(seconds) % 60
    centiseconds = int(round((seconds % 1) * 100))
    if centiseconds == 100:
        minutes += 1
        centiseconds = 0
    return f'{minutes:02d}:{seconds_part:02d}.{centiseconds:02d}'


def serialize_state():
    def serialize_value(value):
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: serialize_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [serialize_value(item) for item in value]
        return value

    return serialize_value(race_data)


def persist_state():
    _save_json_file(ACTIVE_STATE_PATH, serialize_state())


def restore_state_from_disk():
    saved_state = _load_json_file(ACTIVE_STATE_PATH, None)
    if not saved_state:
        return False

    race_data.update(saved_state)
    race_data['race_date'] = _parse_datetime(race_data.get('race_date'))
    if race_data.get('shared_start_timestamp'):
        race_data['shared_start_timestamp'] = _parse_datetime(race_data['shared_start_timestamp'])

    restored_runners = {}
    for runner_id, runner in race_data.get('runners', {}).items():
        restored_runner = runner
        if restored_runner.get('start_time'):
            restored_runner['start_time'] = _parse_datetime(restored_runner['start_time'])
        if restored_runner.get('finish_timestamp'):
            restored_runner['finish_timestamp'] = _parse_datetime(restored_runner['finish_timestamp'])
        restored_runners[int(runner_id)] = restored_runner
    race_data['runners'] = restored_runners

    restored_times = {}
    for runner_id, runner_time in race_data.get('race_times', {}).items():
        restored_times[int(runner_id)] = runner_time
    race_data['race_times'] = restored_times

    race_data['unassigned_finishes'] = race_data.get('unassigned_finishes', [])
    race_data['audit_log'] = race_data.get('audit_log', [])
    race_data['start_plan'] = race_data.get('start_plan', [])
    return True


def load_race_registry():
    registry = _load_json_file(RACE_REGISTRY_PATH, [])
    return set(registry if isinstance(registry, list) else [])


def save_race_registry(registry):
    _save_json_file(RACE_REGISTRY_PATH, sorted(registry))


race_registry = load_race_registry()
restore_state_from_disk()


def append_audit_log(message, event_type='info', data=None):
    race_data['audit_log'].append({
        'timestamp': _now_iso(),
        'type': event_type,
        'message': message,
        'data': data or {}
    })
    race_data['audit_log'] = race_data['audit_log'][-200:]


def build_results_records(runners=None, race_times=None, race_date_value=None):
    runners = runners if runners is not None else race_data['runners']
    race_times = race_times if race_times is not None else race_data['race_times']
    race_date_value = race_date_value if race_date_value is not None else race_data.get('race_date')
    invalid_statuses = {'DNS', 'DNF', 'DSQ'}

    finish_rows = []
    non_finish_rows = []

    for runner_id, runner in runners.items():
        runner_time = race_times.get(runner_id)
        status = runner.get('status') or 'registered'
        is_valid = runner_time is not None and status not in invalid_statuses and not runner.get('out_of_competition', False) and status != 'out_of_competition'
        start_time_value = _parse_datetime(runner.get('start_time'))
        record = {
            'runner_id': runner_id,
            'position': None,
            'category_position': None,
            'group_position': None,
            'number': runner.get('number', ''),
            'name': f"{runner.get('name', '')} {runner.get('surname', '')}".strip(),
            'gender': normalize_gender(runner.get('gender', '')),
            'year': runner.get('year', ''),
            'age': runner.get('age') or calculate_age(runner.get('year', ''), race_date_value),
            'category': runner.get('manual_category') or runner.get('category', ''),
            'award_group': runner.get('award_group') or runner.get('category', ''),
            'team': runner.get('club', ''),
            'email': runner.get('email', ''),
            'phone': runner.get('phone', ''),
            'start_time': start_time_value.strftime('%H:%M:%S') if start_time_value else '',
            'finish_time': format_time(runner_time),
            'result_time': format_time(runner_time),
            'status': status,
            'note': runner.get('note', ''),
            'manual_time': bool(runner.get('manual_time', False)),
            'out_of_competition': bool(runner.get('out_of_competition', False)),
            'is_valid_finish': is_valid
        }

        if is_valid:
            finish_rows.append(record)
        else:
            non_finish_rows.append(record)

    finish_rows.sort(key=lambda row: race_times.get(row['runner_id'], float('inf')))

    category_counters = defaultdict(int)
    group_counters = defaultdict(int)
    for overall_position, record in enumerate(finish_rows, 1):
        record['position'] = overall_position
        category_key = record['category'] or '-'
        group_key = record['award_group'] or '-'
        category_counters[category_key] += 1
        group_counters[group_key] += 1
        record['category_position'] = category_counters[category_key]
        record['group_position'] = group_counters[group_key]

    for record in non_finish_rows:
        record['result_time'] = ''

    return finish_rows + non_finish_rows


def generate_csv_content(race_name, runners, race_times):
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow([
        'poradi_celkove', 'poradi_v_kategorii', 'poradi_ve_vyhlasovaci_skupine',
        'startovni_cislo', 'jmeno', 'prijmeni', 'pohlavi', 'rocnik', 'vek',
        'kategorie', 'vyhlasovaci_skupina', 'tym_obec', 'email', 'telefon',
        'startovni_cas', 'cilovy_cas', 'vysledny_cas', 'stav', 'poznamka',
        'rucne_upraveny_cas', 'mimo_soutez'
    ])

    for record in build_results_records(runners, race_times, race_data.get('race_date')):
        first_name, _, last_name = record['name'].partition(' ')
        writer.writerow([
            record['position'] or '',
            record['category_position'] or '',
            record['group_position'] or '',
            record['number'],
            first_name,
            last_name,
            record['gender'],
            record['year'],
            record['age'] or '',
            record['category'],
            record['award_group'],
            record['team'],
            record['email'],
            record['phone'],
            record['start_time'],
            record['finish_time'],
            record['result_time'],
            record['status'],
            record['note'],
            'ano' if record['manual_time'] else 'ne',
            'ano' if record['out_of_competition'] else 'ne'
        ])

    return output.getvalue()


def generate_pdf(race_name, runners, race_times, race_date=None):
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles = getSampleStyleSheet()

    normal_style = ParagraphStyle(
        'RaceNormal',
        parent=styles['Normal'],
        fontName=PDF_FONT_NAME,
        fontSize=10,
        leading=13,
        textColor=colors.black,
    )
    heading_style = ParagraphStyle(
        'RaceHeading',
        parent=styles['Heading2'],
        fontName=PDF_FONT_NAME,
        fontSize=14,
        leading=17,
        textColor=colors.black,
        spaceAfter=8,
    )
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        fontName=PDF_FONT_NAME,
        textColor=colors.black,
        spaceAfter=30,
        alignment=1,
    )

    elements.append(Paragraph(race_name, title_style))
    elements.append(Paragraph('Výsledky závodu', heading_style))
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(f'Datum konání: {format_race_datetime(race_date)}', normal_style))
    elements.append(Paragraph(f'Vygenerováno: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}', normal_style))
    elements.append(Spacer(1, 0.2*inch))

    finished_rows = build_results_records(runners, race_times, race_date)
    finished_count = sum(1 for record in finished_rows if record['position'])
    dns_dnf_dsq_count = sum(1 for runner in runners.values() if runner.get('status') in {'DNS', 'DNF', 'DSQ'})
    elements.append(Paragraph(f'Typ závodu: {race_data.get("race_type", "individual")}', normal_style))
    elements.append(Paragraph(f'Režim startu: {race_data.get("start_mode", "mass")}', normal_style))
    elements.append(Paragraph(f'Registrováno závodníků: {len(runners)}', normal_style))
    elements.append(Paragraph(f'Dokončivších: {finished_count}', normal_style))
    elements.append(Paragraph(f'DNS/DNF/DSQ: {dns_dnf_dsq_count}', normal_style))
    elements.append(Spacer(1, 0.2*inch))

    table_data = [[
        'Pořadí', 'Číslo', 'Jméno a Příjmení', 'Kategorie', 'Skupina', 'Stav', 'Čas'
    ]]

    for record in finished_rows:
        table_data.append([
            str(record['position'] or ''),
            str(record['number']),
            record['name'],
            record['category'],
            record['award_group'],
            record['status'],
            record['result_time'] or '-'
        ])

    table = Table(table_data, colWidths=[0.6*inch, 0.6*inch, 2*inch, 1.1*inch, 1.1*inch, 0.8*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), PDF_FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7f7f7')]),
    ]))

    if len(table_data) > 1:
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#d9d9d9')),
        ]))

    if len(table_data) > 2:
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#e3e3e3')),
        ]))

    if len(table_data) > 3:
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ededed')),
        ]))

    table.setStyle(TableStyle([
        ('FONTNAME', (0, 1), (-1, -1), PDF_FONT_NAME),
    ]))

    elements.append(table)
    doc.build(elements)
    output.seek(0)
    return output


def save_results(race_name, runners, race_times, race_date=None):
    if not race_name or not race_times:
        return None

    safe_name = sanitize_filename(race_name)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    csv_filename = f'{safe_name}_{timestamp}.csv'
    csv_path = os.path.join(RESULTS_DIR, csv_filename)
    csv_content = generate_csv_content(race_name, runners, race_times)
    with open(csv_path, 'w', encoding='utf-8-sig') as file_handle:
        file_handle.write(csv_content)

    pdf_filename = f'{safe_name}_{timestamp}.pdf'
    pdf_path = os.path.join(RESULTS_DIR, pdf_filename)
    pdf_content = generate_pdf(race_name, runners, race_times, race_date=race_date)
    with open(pdf_path, 'wb') as file_handle:
        file_handle.write(pdf_content.getvalue())

    return {
        'csv_filename': csv_filename,
        'pdf_filename': pdf_filename,
        'csv_path': csv_path,
        'pdf_path': pdf_path,
    }


def reset_race_state():
    race_data.update({
        'race_name': None,
        'race_type': 'individual',
        'start_mode': 'mass',
        'start_interval_seconds': 30,
        'status': 'preparation',
        'runners': {},
        'runner_counter': 0,
        'race_started': False,
        'race_times': {},
        'unassigned_finishes': [],
        'audit_log': [],
        'start_plan': [],
        'race_date': None,
        'shared_start_timestamp': None,
    })
    if os.path.exists(ACTIVE_STATE_PATH):
        os.remove(ACTIVE_STATE_PATH)


def start_race(data):
    race_name = (data.get('race_name') or '').strip()
    if not race_name:
        return {'success': False, 'message': 'Název závodu je povinný.'}, 400

    if race_name in race_registry and race_data.get('race_name') != race_name:
        return {'success': False, 'message': 'Závod s tímto názvem již existuje. Zadejte jiný název.'}, 409

    race_registry.add(race_name)
    save_race_registry(race_registry)

    race_data['race_name'] = race_name
    race_data['race_type'] = data.get('race_type', 'individual')
    race_data['start_mode'] = data.get('start_mode', 'mass')
    race_data['start_interval_seconds'] = int(data.get('start_interval_seconds', 30) or 30)
    race_data['status'] = 'preparation'
    race_data['race_date'] = datetime.now()
    race_data['runners'] = {}
    race_data['runner_counter'] = 0
    race_data['race_started'] = False
    race_data['race_times'] = {}
    race_data['unassigned_finishes'] = []
    race_data['audit_log'] = []
    race_data['start_plan'] = []
    race_data['shared_start_timestamp'] = None
    append_audit_log(f'Založen závod {race_name}', 'race_created')
    persist_state()
    return {'success': True}, 200
