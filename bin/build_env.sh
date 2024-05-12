pip install -U pip wheel pip-tools
pip-compile --no-header -q -o requirements/main_3.12.txt pyproject.toml
pip-compile --no-header -q --extra dev -o requirements/dev_3.12.txt pyproject.toml
pip install -r requirements/dev_3.12.txt
