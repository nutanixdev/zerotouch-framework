## Dev Mode Setup

### For macOS:

- Install Xcode
- Install homebrew: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- Install git and openssl: `brew install git openssl`
- Add path to flags: `export LDFLAGS="-L$(brew --prefix openssl)/lib"`
  and `export CFLAGS="-I$(brew --prefix openssl)/include"`
- Install Python >= 3.10 (you can use pyenv to manage multiple Python versions): `brew install pyenv`
  and `pyenv install 3.10.6`
- Clone this repo
- Install required python modules: `make dev`
- Getting into virtualenv: `source venv/bin/activate`
- Getting out of virtualenv: `deactivate`

### For Centos:

- Install Python >= 3.10 (you can use pyenv to manage multiple Python versions)
- Clone this repo
- Install any dependencies using: `make centos`
- Ensure Python version inside the repository is >= 3.10 `python -V`
- Create python virtual environment: `python -m venv venv`
- Install required python modules:`make dev`
- Getting into virtualenv: `source venv/bin/activate`
- Getting out of virtualenv: `deactivate`

### For Debian/Ubuntu:

- Install Python >= 3.10 (you can use pyenv to manage multiple Python versions)
- Clone this repo
- Install any dependencies using: `make ubuntu`
- Ensure Python version inside the repository is >= 3.10 `python -V`
- Create python virtual environment: `python -m venv venv`
- Install required python modules:`make dev`
- Getting into virtualenv: `source venv/bin/activate`
- Getting out of virtualenv: `deactivate`

### For dark-site:

- We need to download the required Python packages from a VM with the same Linux distribution as dark-site VM, having
  internet access (PyPI repository).
- Copy the "requirements/prod.txt" to the VM with internet access.
- Execute this command in the VM with internet access: `pip wheel -r requirements/prod.txt -w ./site-packages --no-deps`
- Compress and copy this site-packages.tar to the dark-site VM
- In dark-site VM:
    - Ensure all the dependant libraries are installed, check MAKEFILE for more information.
    - Install Python >= 3.10
    - Clone this repo
    - Ensure Python version inside the repository is >= 3.10 `python -V`
    - Create python virtual environment: `python -m venv venv`
    - Extract site-packages folder, that was copied over
    - Perform installation using the following
      command: `pip install --no-index --find-links=site-packages/ -r requirements/prod.txt`

### Test the installation

Ensure you're inside the virtualenv

```sh
python main.py --help 
```

```
usage: main.py [-h] [--workflow WORKFLOW] [--script SCRIPT] [--schema SCHEMA] -f FILE [--debug]
Description

options:
  -h, --help            show this help message and exit
  --workflow WORKFLOW   workflow to run
  --script SCRIPT       script/s to run
  --schema SCHEMA       schema for the script
  -f FILE, --file FILE  input file/s
  --debug
```