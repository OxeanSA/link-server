<h1 id="deployment-guide">Deployment Guide: Gunicorn + Tornado as a Service</h1>

<p>This guide provides instructions for setting up a Tornado application as a persistent system service using <strong>Gunicorn</strong> and a <strong>Python Virtual Environment</strong> within a home directory.</p>

<h2 id="1-project-layout">1. Project Layout</h2>
<ul>
<li><strong>Path:</strong> <code>/home/&lt;user&gt;/&lt;project_folder&gt;</code></li>
<li><strong>Entry Point:</strong> <code>app.py</code> (containing the Tornado <code>app</code> object)</li>
<li><strong>Venv Name:</strong> <code>venv</code></li>
</ul>

<h2 id="2-environment-initialization">2. Environment Initialization</h2>
<p>From your project directory, set up the virtual environment and install dependencies:</p>

<pre><code># Create the virtual environment
python3 -m venv venv

Install necessary server packages inside the venv

./venv/bin/pip install gunicorn tornado</code></pre>

<h2 id="3-gunicorn-configuration">3. Gunicorn Configuration</h2>
<p>Create <code>gunicorn_conf.py</code> in your project root:</p>

<pre><code># gunicorn_conf.py
import multiprocessing

bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "tornado"
loglevel = "info"
accesslog = "-"
errorlog = "-"</code></pre>

<h2 id="4-systemd-service-setup">4. Systemd Service Setup</h2>
<p>Create the service file at <code>/etc/systemd/system/tornado_app.service</code>:</p>

<pre><code>[Unit]
Description=Gunicorn instance to serve Tornado App
After=network.target

[Service]
User=&lt;user&gt;
Group=&lt;user&gt;
WorkingDirectory=/home/&lt;user&gt;/&lt;project_folder&gt;
Environment="PATH=/home/&lt;user&gt;/&lt;project_folder&gt;/venv/bin"
ExecStart=/home/&lt;user&gt;/&lt;project_folder&gt;/venv/bin/gunicorn -c gunicorn_conf.py app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target</code></pre>

<h2 id="5-management-commands">5. Management Commands</h2>
<table border="1">
<tr>
<th>Action</th>
<th>Command</th>
</tr>
<tr>
<td>Reload Systemd</td>
<td><code>sudo systemctl daemon-reload</code></td>
</tr>
<tr>
<td>Start Service</td>
<td><code>sudo systemctl start tornado_app</code></td>
</tr>
<tr>
<td>Check Status</td>
<td><code>sudo systemctl status tornado_app</code></td>
</tr>
<tr>
<td>View Logs</td>
<td><code>sudo journalctl -u tornado_app -f</code></td>
</tr>
</table>

<h2 id="6-permissions-fix">6. Permissions Fix</h2>
<p>If you encounter a 200/CHDIR error, run:</p>
<pre><code>chmod +x /home/&lt;your_user&gt;</code></pre>
