python -m venv venv
cd app
pip install -r requirements.txt
playwright install-deps
playwright install chromium