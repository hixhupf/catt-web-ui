import os
import subprocess
import re
from flask import Flask, jsonify, request, render_template, send_from_directory
from werkzeug.utils import secure_filename
from urllib.parse import quote

app = Flask(__name__, template_folder='templates', static_folder='static')

# --- CONSTANTS ---
CATT_EXECUTABLE = '/opt/catt-web-ui/venv/bin/catt'
MEDIA_FOLDER = '/opt/catt-web-ui/media'
os.makedirs(MEDIA_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mkv', 'mov', 'mp3'}

# --- HELPER FUNCTIONS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def run_command(command, timeout=5):
    try:
        # The timeout value is now a parameter
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True, timeout=timeout)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        output = e.stderr.strip() if hasattr(e, 'stderr') else f"Command timed out after {timeout} seconds"
        return f"Error: {output}"


# --- HEAVILY IMPROVED: Helper to parse status output ---
def parse_catt_status(output):
    # First, check for idle state
    if "Error:" in output or "No media is currently playing" in output:
        return {"state": "IDLE", "title": None}

    # Second, determine playback state (case-insensitive)
    state = "UNKNOWN"
    upper_output = output.upper()
    if "PLAYING" in upper_output:
        state = "PLAYING"
    elif "PAUSED" in upper_output:
        state = "PAUSED"

    title = None
    # --- NEW STRATEGY: Prioritize URL over metadata title ---
    # 1. Try to find the filename from the Content ID / URL, as it's the most reliable.
    #    It looks for a URL like ".../media/My_Video_File.mp4"
    url_match = re.search(r"/media/([^?&]+)", output)
    if url_match:
        try:
            from urllib.parse import unquote
            # Get the matched group (the filename) and decode it
            title = unquote(url_match.group(1))
        except Exception as e:
            print(f"Error decoding URL match: {e}")
            title = None # Invalidate if decoding fails

    # 2. If we couldn't find a filename in the URL, fall back to the old method.
    if not title:
        title_match = re.search(r"Title:\s*(.*)", output)
        if title_match:
            # This is the less reliable metadata title
            title = title_match.group(1).strip()

    print(f"Parsed status: State='{state}', Title='{title}'")

    return {"state": state, "title": title}


# --- API ENDPOINTS ---

@app.route('/media/<path:filename>')
def serve_media(filename):
    return send_from_directory(MEDIA_FOLDER, filename)

@app.route('/api/devices')
def get_devices():
    # We give the scan command a longer, 15-second timeout.
    # The default timeout in run_command is now used for faster commands like 'status'.
    output = run_command(f'{CATT_EXECUTABLE} scan', timeout=15)
    devices = []
    for line in output.splitlines():
        if "Scanning Chromecasts..." in line or not line.strip() or "Error:" in line:
            continue
        parts = line.split(' - ', 2)
        if len(parts) >= 2:
            devices.append({'name': parts[1].strip(), 'ip': parts[0].strip()})
    return jsonify(devices)

# --- NEW: Endpoint to get status of all devices ---
@app.route('/api/all_status', methods=['POST'])
def get_all_status():
    data = request.json
    device_ips = data.get('ips', [])
    statuses = {}
    for ip in device_ips:
        status_output = run_command(f'{CATT_EXECUTABLE} -d {ip} status')
        statuses[ip] = parse_catt_status(status_output)
    return jsonify(statuses)

@app.route('/api/media')
def list_media():
    # This function is now only used for the file selection modal
    files_with_thumbs = []
    if not os.path.exists(MEDIA_FOLDER): return jsonify([])
    for filename in sorted(os.listdir(MEDIA_FOLDER)):
        if filename.endswith('.thumb.jpg'): continue
        file_path = os.path.join(MEDIA_FOLDER, filename)
        thumbnail_url = None
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', 'gif')):
            thumbnail_url = f'/media/{quote(filename)}'
        elif filename.lower().endswith(('.mp4', '.mkv', '.mov')):
            thumbnail_filename = f'{filename}.thumb.jpg'
            thumbnail_path = os.path.join(MEDIA_FOLDER, thumbnail_filename)
            thumbnail_url = f'/media/{quote(thumbnail_filename)}'
            if not os.path.exists(thumbnail_path):
                run_command(f'ffmpeg -i "{file_path}" -ss 00:00:05 -vframes 1 -q:v 3 -vf "scale=320:-1" "{thumbnail_path}" -y')
        if thumbnail_url:
            files_with_thumbs.append({'filename': filename, 'thumbnail_url': thumbnail_url})
    return jsonify(files_with_thumbs)

@app.route('/api/cast', methods=['POST'])
def cast_media():
    # (This function is mostly the same, but we return the source_file for instant UI update)
    data = request.json
    device_ip = data.get('device_ip')
    source_file = data.get('source')
    if not device_ip or not source_file:
        return jsonify({'status': 'error', 'message': 'Geräte-IP und Quelle benötigt'}), 400
    
    server_address = request.host
    media_url = f'http://{server_address}/media/{quote(source_file)}'
    command = f'{CATT_EXECUTABLE} -d {device_ip} cast "{media_url}"'
    subprocess.Popen(command, shell=True)
    
    return jsonify({'status': 'ok', 'message': 'Stream wird gestartet...', 'casting_file': source_file})

# Unchanged endpoints: upload, delete, control
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({'status': 'error', 'message': 'Keine Datei im Request'}), 400
    file = request.files['file']
    if file.filename == '': return jsonify({'status': 'error', 'message': 'Keine Datei ausgewählt'}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(MEDIA_FOLDER, filename))
        return jsonify({'status': 'ok', 'message': f'Datei {filename} hochgeladen.'})
    return jsonify({'status': 'error', 'message': 'Dateityp nicht erlaubt'}), 400

@app.route('/api/delete', methods=['POST'])
def delete_file():
    data = request.json
    filename = data.get('filename')
    if not filename: return jsonify({'status': 'error', 'message': 'Kein Dateiname angegeben'}), 400
    file_path = os.path.join(MEDIA_FOLDER, filename)
    if not os.path.abspath(file_path).startswith(os.path.abspath(MEDIA_FOLDER)):
        return jsonify({'status': 'error', 'message': 'Ungültiger Dateipfad'}), 403
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            thumbnail_path = f"{file_path}.thumb.jpg"
            if os.path.exists(thumbnail_path): os.remove(thumbnail_path)
            return jsonify({'status': 'ok', 'message': f'Datei {filename} wurde gelöscht.'})
        else:
            return jsonify({'status': 'error', 'message': 'Datei nicht gefunden'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': 'Ein interner Fehler ist aufgetreten'}), 500

@app.route('/api/control', methods=['POST'])
def control_stream():
    data = request.json
    device_ip = data.get('device_ip')
    action = data.get('action')
    if not device_ip or not action: return jsonify({'status': 'error', 'message': 'Geräte-IP und Aktion benötigt'}), 400
    command = f'{CATT_EXECUTABLE} -d {device_ip} {action}'
    run_command(command)
    return jsonify({'status': 'ok'})

# Main route
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
