# Sticky Ports

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://choosealicense.com/licenses/mit/) 

Sticky Ports is an all-in-one Layer 4 honeypot framework written in Python. It emulates commonly abused Ubuntu services and logs interactions for security analysis and threat intelligence.

## Features

### Honeypot Emulators (Layer 4 Services)

* Redis
* SMTP
* Memcached
* FTP
* Telnet
* MySQL
* VNC
* RDP

### Logging & Reporting Integrations

* SQLite (local storage)
* [AbuseIPDB](https://www.abuseipdb.com/) (optional, for reputation-based reporting)

## Prerequisites

Before you begin, ensure you have:

* **Python** 3.12 or newer installed.
* **Git** (to clone the repository).
* **pip** (Python package installer).
* **systemd** (on Ubuntu/Debian for the service unit example).

## Installation

Follow these steps to get Sticky Ports up and running on your system:

1. **Clone the repository**

   ```bash
   git clone https://github.com/ImInTheICU/sticky-ports.git
   cd sticky-ports
   ```

2. **Change directory to the source**

   ```bash
   cd src
   ```

3. **Create and activate a virtual environment** (recommended)

   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   ```

4. **Install dependencies**

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Configure the honeypot**

   * Copy the sample configuration:

     ```bash
     cp config.yaml.example config.yaml
     ```
   * Open `config.yaml` in your favorite editor and adjust settings (e.g., ports, logging options, AbuseIPDB API key).

6. **Run the engine**

   ```bash
   python engine.py
   ```

7. **(Optional) Set up as a systemd service**

   To have Sticky Ports start automatically at boot and restart on failure, create a systemd unit file:

   ```ini
   [Unit]
   Description=Sticky Ports Honeypot
   After=network.target

   [Service]
   Type=simple
   User=YOUR_USER
   WorkingDirectory=/path/to/sticky-ports/src
   ExecStart=/path/to/sticky-ports/src/venv/bin/python engine.py
   Restart=on-failure
   RestartSec=10s

   [Install]
   WantedBy=multi-user.target
   ```

   * Save this as `/etc/systemd/system/sticky-ports.service`.
   * Reload systemd and enable the service:

     ```bash
     sudo systemctl daemon-reload
     sudo systemctl enable sticky-ports
     sudo systemctl start sticky-ports
     ```

## Demo

![Demo Image](https://raw.githubusercontent.com/ImInTheICU/sticky-ports/b620711a581701d48579e381beaacaab9ba6cffb/images/Screenshot%202025-07-21%20221417.png)

## License

This project is licensed under the MIT License. See the [LICENSE](https://choosealicense.com/licenses/mit/) for details.

---
