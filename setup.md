Deployment Guide

This guide provides instructions for setting up a persistent server service.

1. Project Layout

Home directory:

Path: /home/<user>/<project_folder>

Entry Point: main.py

Venv Name: venv

2. Environment Initialization

# Virtual environment
python3 -m venv venv

# Install server packages inside the venv
./venv/bin/pip install gunicorn tornado


