from flask import Blueprint, jsonify, render_template, request, send_file
import io
import os
from datetime import datetime

from race_service import (
    RESULTS_DIR,
    append_audit_log,
    build_results_records,
    calculate_age,
    calculate_category,
    format_race_datetime,
    generate_csv_content,
    _parse_datetime,
    normalize_gender,
    persist_state,
    race_data,
    reset_race_state,
    save_results,
    start_race,
)

race_bp = Blueprint('race_bp', __name__)

########################################
#
# === API ===
#

@race_bp.route('/api/start-race', methods=['POST'])
def api_start_race():
    payload = request.get_json() or {}
    body, status_code = start_race(payload)
    return jsonify(body), status_code

@race_bp.route('/api/import-runners', methods=['POST'])
def import_runners():
    data = request.get_json() or {}
    csv_text = data.get('csv_text', '')
    if not csv_text.strip():
        return jsonify({'success': False, 'message': 'CSV je prázdné.'}), 400

    import csv
    reader = csv.DictReader(io.StringIO(csv_text))
    preview_rows = []
    errors = []
    next_auto_number = 1

    for row_index, row in enumerate(reader, 1):
        raw_number = row.get('startovni_cislo') or row.get('bib') or row.get('číslo') or row.get('cislo') or ''
        number = str(raw_number).strip()
        if not number:
            while str(next_auto_number) in {str(runner.get('number', '')) for runner in race_data['runners'].values()}:
                next_auto_number += 1
            number = str(next_auto_number)
            next_auto_number += 1

        gender = normalize_gender(row.get('pohlavi') or row.get('gender') or '')
        if gender not in {'Muž', 'Žena'}:
            errors.append(f'Řádek {row_index}: neplatné pohlaví')

        year_value = row.get('rocnik') or row.get('birthYear') or row.get('year') or ''
        if not str(year_value).strip().isdigit():
            errors.append(f'Řádek {row_index}: neplatný ročník')

        preview_rows.append({
            'number': number,
            'name': row.get('jmeno') or row.get('firstName') or '',
            'surname': row.get('prijmeni') or row.get('lastName') or '',
            'gender': gender,
            'year': str(year_value).strip(),
            'club': row.get('tym') or row.get('club') or row.get('obec') or '',
            'email': row.get('email') or '',
            'phone': row.get('telefon') or '',
            'note': row.get('poznamka') or '',
            'manual_category': row.get('kategorie') or '',
            'out_of_competition': str(row.get('mimo_soutez') or '').strip().lower() in {'1', 'true', 'ano', 'yes'},
        })

    return jsonify({'success': True, 'preview': preview_rows, 'errors': errors})

@race_bp.route('/api/start-timer', methods=['POST'])
def start_timer():
    race_data['race_started'] = True
    race_data['status'] = 'running'
    from datetime import timedelta
    race_data['shared_start_timestamp'] = datetime.now()

    if race_data.get('start_mode') == 'interval':
        sorted_runners = sorted(
            race_data['runners'].items(),
            key=lambda item: (
                int(item[1].get('start_order') or 10**9),
                str(item[1].get('number', '')),
            )
        )
        plan = []
        for position, (runner_id, runner) in enumerate(sorted_runners, 1):
            start_time = race_data['shared_start_timestamp'] + timedelta(seconds=(position - 1) * race_data['start_interval_seconds'])
            runner['start_time'] = start_time.isoformat()
            runner['start_offset_seconds'] = (position - 1) * race_data['start_interval_seconds']
            runner['start_order'] = position
            plan.append({
                'position': position,
                'runner_id': runner_id,
                'number': runner.get('number', ''),
                'name': f"{runner.get('name', '')} {runner.get('surname', '')}".strip(),
                'category': runner.get('category', ''),
                'start_time': start_time.strftime('%H:%M:%S'),
            })
        race_data['start_plan'] = plan
    else:
        for runner in race_data['runners'].values():
            runner['start_time'] = race_data['shared_start_timestamp'].isoformat()
            runner['start_offset_seconds'] = 0

    append_audit_log('Start závodu', 'race_started')
    persist_state()
    return jsonify({'success': True, 'start_time': race_data['shared_start_timestamp'].isoformat()})


@race_bp.route('/api/finish-runner/<int:runner_id>/<float:time_seconds>', methods=['POST'])
def finish_runner(runner_id, time_seconds):
    runner = race_data['runners'].get(runner_id)
    if runner is None:
        return jsonify({'success': False, 'message': 'Závodník nenalezen'}), 404

    from datetime import datetime as _datetime
    finish_timestamp = _datetime.now()
    race_data['race_times'][runner_id] = time_seconds
    runner['finish_timestamp'] = finish_timestamp.isoformat()
    runner['result_time_ms'] = int(time_seconds * 1000)
    start_timestamp = _parse_datetime(runner.get('start_time')) or race_data.get('shared_start_timestamp')
    if start_timestamp:
        elapsed_seconds = (finish_timestamp - start_timestamp).total_seconds()
        race_data['race_times'][runner_id] = elapsed_seconds
        runner['result_time_ms'] = int(elapsed_seconds * 1000)
    runner['status'] = 'finished' if not runner.get('out_of_competition') else 'out_of_competition'
    append_audit_log(f'Doběh #{runner.get("number", "")} {runner.get("name", "")} {runner.get("surname", "")}', 'finish_recorded', {'runner_id': runner_id, 'time': time_seconds})
    persist_state()
    return jsonify({'success': True})


@race_bp.route('/api/unfinish-runner/<int:runner_id>', methods=['POST'])
def unfinish_runner(runner_id):
    runner = race_data['runners'].get(runner_id)
    if runner is None:
        return jsonify({'success': False, 'message': 'Závodník nenalezen'}), 404

    if runner_id in race_data['race_times']:
        del race_data['race_times'][runner_id]
    runner['finish_timestamp'] = None
    runner['result_time_ms'] = None
    runner['status'] = 'registered'
    append_audit_log(f'Zrušen doběh #{runner.get("number", "")} {runner.get("name", "")} {runner.get("surname", "")}', 'finish_cancelled', {'runner_id': runner_id})
    persist_state()
    return jsonify({'success': True})


@race_bp.route('/api/update-runner/<int:runner_id>', methods=['POST'])
def update_runner(runner_id):
    runner = race_data['runners'].get(runner_id)
    if not runner:
        return jsonify({'success': False, 'message': 'Závodník nenalezen'}), 404

    data = request.get_json() or {}
    for field in ['name', 'surname', 'gender', 'year', 'club', 'email', 'phone', 'note', 'manual_category', 'status', 'start_order']:
        if field in data:
            runner[field] = data[field]

    runner['gender'] = normalize_gender(runner.get('gender', ''))
    runner['age'] = calculate_age(runner.get('year', ''), race_data.get('race_date'))
    runner['category'] = calculate_category(runner.get('year', ''), runner.get('gender', ''), race_data.get('race_date'))
    runner['award_group'] = runner.get('manual_category') or runner.get('category', '')
    runner['out_of_competition'] = bool(data.get('out_of_competition', runner.get('out_of_competition', False)))
    append_audit_log(f'Upraven závodník #{runner.get("number", "")}', 'runner_updated', {'runner_id': runner_id})
    persist_state()
    return jsonify({'success': True, 'runner': runner})


@race_bp.route('/api/update-finish/<int:runner_id>', methods=['POST'])
def update_finish(runner_id):
    runner = race_data['runners'].get(runner_id)
    if not runner:
        return jsonify({'success': False, 'message': 'Závodník nenalezen'}), 404

    data = request.get_json() or {}
    seconds_value = float(data.get('time_seconds', 0))
    race_data['race_times'][runner_id] = seconds_value
    runner['manual_time'] = True
    runner['status'] = data.get('status', runner.get('status', 'finished'))
    append_audit_log(f'Ruční oprava času #{runner.get("number", "")}', 'time_corrected', {'runner_id': runner_id, 'time_seconds': seconds_value})
    persist_state()
    return jsonify({'success': True})


@race_bp.route('/api/import-runners/confirm', methods=['POST'])
def confirm_import_runners():
    data = request.get_json() or {}
    rows = data.get('rows', [])
    imported_count = 0
    for row in rows:
        runner_id = race_data['runner_counter']
        race_data['runner_counter'] += 1
        runner = {
            'id': runner_id,
            'number': row.get('number', ''),
            'name': row.get('name', ''),
            'surname': row.get('surname', ''),
            'gender': normalize_gender(row.get('gender', '')),
            'year': row.get('year', ''),
            'club': row.get('club', ''),
            'email': row.get('email', ''),
            'phone': row.get('phone', ''),
            'note': row.get('note', ''),
            'manual_category': row.get('manual_category', ''),
            'category': calculate_category(row.get('year', ''), row.get('gender', ''), race_data.get('race_date')),
            'award_group': row.get('manual_category', '') or calculate_category(row.get('year', ''), row.get('gender', ''), race_data.get('race_date')),
            'out_of_competition': bool(row.get('out_of_competition', False)),
            'status': 'registered',
            'manual_time': False,
            'start_order': row.get('start_order'),
        }
        race_data['runners'][runner_id] = runner
        imported_count += 1

    append_audit_log(f'Importováno {imported_count} závodníků z CSV', 'import')
    persist_state()
    return jsonify({'success': True, 'imported_count': imported_count})


@race_bp.route('/api/add-runner', methods=['POST'])
def add_runner():
    data = request.get_json() or {}
    runner_id = race_data['runner_counter']
    race_data['runner_counter'] += 1

    manual_category = data.get('manual_category', '')
    category = calculate_category(data.get('year', ''), data.get('gender', ''), race_data.get('race_date'))

    race_data['runners'][runner_id] = {
        'id': runner_id,
        'number': data.get('number', ''),
        'name': data.get('name', ''),
        'surname': data.get('surname', ''),
        'gender': normalize_gender(data.get('gender', '')),
        'year': data.get('year', ''),
        'age': calculate_age(data.get('year', ''), race_data.get('race_date')),
        'club': data.get('club', ''),
        'email': data.get('email', ''),
        'phone': data.get('phone', ''),
        'manual_category': manual_category,
        'category': category,
        'award_group': manual_category or category,
        'status': 'registered',
        'manual_time': False,
        'start_order': data.get('start_order', ''),
        'start_time': None,
        'finish_timestamp': None,
    }

    append_audit_log(f'Přidán závodník #{data.get("number", "")} {data.get("name", "")} {data.get("surname", "")}', 'runner_added', {'runner_id': runner_id})
    persist_state()
    return jsonify({'success': True, 'runner_id': runner_id, 'runners': race_data['runners']})


@race_bp.route('/api/get-runners', methods=['GET'])
def get_runners():
    return jsonify({'runners': race_data['runners']})


@race_bp.route('/api/get-state', methods=['GET'])
def get_state():
    return jsonify({
        'race_name': race_data['race_name'],
        'race_date': format_race_datetime(race_data['race_date']),
        'race_type': race_data['race_type'],
        'start_mode': race_data['start_mode'],
        'start_interval_seconds': race_data['start_interval_seconds'],
        'status': race_data['status'],
        'draft_available': bool(race_data['race_name']),
        'audit_log': race_data['audit_log'][-20:],
        'unassigned_finishes': race_data['unassigned_finishes'],
    })


@race_bp.route('/api/delete-runner/<int:runner_id>', methods=['DELETE'])
def delete_runner(runner_id):
    if runner_id in race_data['runners']:
        del race_data['runners'][runner_id]
        race_data['race_times'].pop(runner_id, None)
        append_audit_log(f'Smazán závodník #{runner_id}', 'runner_deleted', {'runner_id': runner_id})
        persist_state()
    return jsonify({'success': True, 'runners': race_data['runners']})


@race_bp.route('/')
def index():
    draft_available = bool(race_data.get('race_name'))
    return render_template('index.html', draft_available=draft_available, draft_name=race_data.get('race_name'))


@race_bp.route('/setup')
def setup():
    return render_template(
        'setup.html',
        race_name=race_data['race_name'],
        race_date=format_race_datetime(race_data['race_date']),
        race_type=race_data['race_type'],
        start_mode=race_data['start_mode'],
        start_interval_seconds=race_data['start_interval_seconds'],
        runners=race_data['runners'],
        start_plan=race_data['start_plan'],
    )

#######################################
#
# === Timer ===
#

@race_bp.route('/timer')
def timer():
    return render_template(
        'timer.html',
        race_name=race_data['race_name'],
        race_date=format_race_datetime(race_data['race_date']),
        start_mode=race_data['start_mode'],
        runners=race_data['runners'],
        audit_log=race_data['audit_log'][-20:],
        unassigned_finishes=race_data['unassigned_finishes'],
    )
    

#######################################
#
# === Results ===
#

@race_bp.route('/results')
def results():
    results_data = build_results_records()
    saved_files = save_results(
        race_data['race_name'],
        race_data['runners'],
        race_data['race_times'],
        race_date=race_data['race_date'],
    )
    return render_template(
        'results.html',
        race_name=race_data['race_name'],
        race_date=format_race_datetime(race_data['race_date']),
        results=results_data,
        saved_files=saved_files,
        race_type=race_data['race_type'],
        start_mode=race_data['start_mode'],
        registered_count=len(race_data['runners']),
        finished_count=sum(1 for record in results_data if record['position']),
        invalid_count=sum(1 for record in results_data if record['status'] in {'DNS', 'DNF', 'DSQ'}),
        audit_log=race_data['audit_log'][-20:],
        unassigned_finishes=race_data['unassigned_finishes'],
    )


@race_bp.route('/api/export-csv', methods=['GET'])
def export_csv():
    csv_content = generate_csv_content(race_data['race_name'], race_data['runners'], race_data['race_times'])
    return send_file(
        io.BytesIO(csv_content.encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"{race_data['race_name'].replace(' ', '_') if race_data['race_name'] else 'vysledky'}.csv",
    )


@race_bp.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(RESULTS_DIR, filename)
    if os.path.abspath(filepath).startswith(os.path.abspath(RESULTS_DIR)):
        return send_file(filepath, as_attachment=True)
    return 'Soubor nenalezen', 404


@race_bp.route('/api/reset-race', methods=['POST'])
def reset_race():
    reset_race_state()
    return jsonify({'success': True})
