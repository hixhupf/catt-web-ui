# Catt Web UI - Fernseh-Dashboard

Ein einfaches, geräte-zentriertes Web-Dashboard zur Steuerung von `catt` (Cast All The Things) auf einem Server. Es ermöglicht das Hochladen und Streamen von lokalen Mediendateien auf mehrere Chromecast-Geräte im Netzwerk. Ich steuere damit Inhalte auf verschiedenen Endgeräten im Kirchengebäude.

![Screenshot des Dashboards](./assets/sample_dashboard.jpg)

## Features

*   Automatische Erkennung von Chromecast-Geräten im Netzwerk.
*   Geräte-zentriertes Dashboard zur unabhängigen Steuerung jedes Empfängers.
*   Anzeige des aktuellen Streams (inkl. Thumbnail) pro Gerät.
*   Hochladen neuer Mediendateien direkt über die Weboberfläche.
*   Löschen von Mediendateien aus der Bibliothek.

## Setup & Installation

Dieses Projekt wurde mit KI auf einem Ubuntu-Server entwickelt und verwendet **Gunicorn** als produktiven Webserver.

**1. Klonen Sie das Repository:**
```bash
git clone https://github.com/hixhupf/catt-web-ui.git
cd catt-web-ui
```

**2. Erstellen Sie eine virtuelle Umgebung:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**3. Installieren Sie die Python-Abhängigkeiten:**
```bash
pip install -r requirements.txt
```

**4. Installieren Sie die System-Abhängigkeiten:**
```bash
# catt selbst installieren (falls noch nicht geschehen)
pip install catt

# ffmpeg für die Thumbnail-Generierung installieren
sudo apt update && sudo apt install ffmpeg
```

**5. Konfigurieren Sie die Anwendung:**
Öffnen Sie `app.py` und passen Sie die folgenden Pfade an Ihre Umgebung an:
*   `CATT_EXECUTABLE`: Der absolute Pfad zu Ihrer `catt`-Installation (z.B. `/opt/catt-web-ui/venv/bin/catt`).
*   `MEDIA_FOLDER`: Der absolute Pfad zum Ordner, in dem Ihre Medien gespeichert werden sollen (z.B. `/opt/catt-web-ui/media`).

**6. Richten Sie den `systemd`-Service ein:**
Erstellen Sie eine Service-Datei, um die Anwendung mit Gunicorn im Hintergrund laufen zu lassen. Bei User und Group müssen Sie Ihren User eintragen.
```bash
sudo nano /etc/systemd/system/catt-web.service
```
Fügen Sie den folgenden Inhalt ein und passen Sie `User`, `Group` und die Pfade an:
```ini
[Unit]
Description=Gunicorn instance to serve Catt Web UI
After=network.target

[Service]
User=technik
Group=technik
WorkingDirectory=/opt/catt-web-ui
Environment="PATH=/opt/catt-web-ui/venv/bin"
# Der folgende Befehl startet die App mit Gunicorn
ExecStart=/opt/catt-web-ui/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 app:app

Restart=always

[Install]
WantedBy=multi-user.target
```

**7. Starten und aktivieren Sie den Service:**
```bash
sudo systemctl daemon-reload
sudo systemctl start catt-web.service
sudo systemctl enable catt-web.service
```
## Benutzung

Öffnen Sie einen Webbrowser und navigieren Sie zu `http://<IP_IHRES_SERVERS>:5000`.
