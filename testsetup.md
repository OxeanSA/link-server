<h1 id="test-server-manual-run">Test Server: Manual Execution Guide</h1>

<p>Use this guide to verify your Gunicorn and Tornado setup manually in a terminal session. This bypasses <code>systemd</code> to help you see errors in real-time.</p>

<h2 id="1-environment-check">1. Environment Activation</h2>
<p>Ensure you are in your project directory and your virtual environment is active:</p>

<pre><code>cd ~/&lt;project_folder&gt;
source venv/bin/activate</code></pre>

<h2 id="2-manual-execution-test">2. Manual Execution Test</h2>
<p>Run Gunicorn directly using your configuration file. This will stream logs directly to your terminal window:</p>

<pre><code># Command to run Gunicorn manually
gunicorn -c gunicorn_conf.py app:app</code></pre>

<h2 id="3-validation-checklist">3. Validation Checklist</h2>
<ul>
<li><strong>Port Check:</strong> Open a second terminal and run <code>curl http://localhost:8000</code> to see if the server responds.</li>
<li><strong>Log Monitoring:</strong> Watch the terminal for <code>[INFO]</code> or <code>[ERROR]</code> messages.</li>
<li><strong>Configuration Verification:</strong> If you change <code>gunicorn_conf.py</code>, stop the process (Ctrl+C) and restart it to see changes.</li>
</ul>

<h2 id="4-useful-debug-flags">4. Useful Debug Flags</h2>
<p>If the server fails to start, try running it with extra debug output:</p>

<pre><code># Force debug logging and a single worker for easier tracing
gunicorn --worker-class tornado --log-level debug --workers 1 app:app</code></pre>

<h2 id="5-stopping-the-server">5. Stopping the Server</h2>
<p>To stop the manual test server, press <strong>Ctrl + C</strong> in the terminal window where Gunicorn is running.</p>