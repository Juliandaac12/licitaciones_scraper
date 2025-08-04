#!/bin/bash

# Actualiza e instala Chrome y ChromeDriver en entorno Linux
apt-get update
apt-get install -y chromium chromium-driver

# Ejecutar tu scraper con Selenium
python main.py
