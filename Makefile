dev:
	# Setup our python based virtualenv
	# This step assumes python3 is installed on your dev machine as python
	[ -f venv/bin/python ] || (python -m venv venv)
		. venv/bin/activate
		venv/bin/pip install --upgrade pip setuptools
		venv/bin/pip install pip-tools
		venv/bin/pip-compile --output-file=requirements/dev.txt requirements/dev.in
		venv/bin/pip install --no-cache -r requirements/dev.txt

test: dev
	# In progress
	pytest

dist: dev
	venv/bin/python setup.py build

centos:
	rpm -q epel-release || sudo yum -y install epel-release
	sudo yum -y install gcc git openssl-devel sqlite-devel ncurses-devel

ubuntu:
	sudo apt-get update
	sudo apt-get -y install build-essential
	sudo apt-get -y install gcc git libssl-dev sqlite3 libncurses-dev