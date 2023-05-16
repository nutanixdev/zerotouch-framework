dev:
	# Setup our python based virtualenv
	# This step assumes python3 is installed on your dev machine as python
	[ -f venv/bin/python ] || (python -m venv venv && \
		venv/bin/pip install --upgrade pip setuptools)
		cd framework && \
	    ../venv/bin/pip install --no-cache -r requirements/dev.txt

test: dev
	# In progress
	pytest
