#!/bin/bash

set -e  # Si ocurre un error, se detiene el script inmediatamente

# Instalar los navegadores necesarios para Playwright
playwright install --with-deps

# Ejecutar el script principal
python main.py
