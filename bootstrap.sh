#!/bin/bash
set -e
which virtualenv >/dev/null || echo "install virtualenv"

if [ `which python3.4` ]; then
    ver=python3.4
else
    ver=python3.3
fi
echo "use python version $ver"
virtualenv -p $ver env
. env/bin/activate
pip install --upgrade -r requirements.txt
#cd env
#if [ ! -e rainfall ]; then
#  git clone https://github.com/mind1master/rainfall.git
#  cd rainfall
#  python setup.py install
#fi

echo "-------------------------------------------------------"
echo "to active your environment run:"
echo "# source env/bin/activate"
echo "# bin/precollapse [...]"
echo "-------------------------------------------------------"
