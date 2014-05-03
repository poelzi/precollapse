#!/bin/bash
set -e
which virtualenv >/dev/null || echo "install virtualenv"


virtualenv -p python3.3 env
. env/bin/activate
pip install --upgrade -r requirements.txt
cd env
if [ ! -e rainfall ]; then
  git clone https://github.com/mind1master/rainfall.git
  cd rainfall
  python setup.py install
fi

echo "-------------------------------------------------------"
echo "to active your environment run:"
echo "# source env/bin/activate"
echo "# bin/precollapse [...]"
echo "-------------------------------------------------------"
