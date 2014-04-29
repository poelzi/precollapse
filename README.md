precollapse
===========

collecting the information you want and holding it up to date.


Installing
----------

precollapse requires python 3.3 and a bunch of modules you will find in `requirements.txt`.
The simples and a clean way is to use virtualenv.

Install virtualenv and python3.3.

> git clone https://github.com/poelzi/precollapse
> cd precollapse
> ./bootstrap.sh

This may require some development packages to be installed.

[INSERT LIST HERE] :-)


Getting Started
---------------

create your database:
> ./bin/precollapse-local db-sync

run precollapse:

> ./bin/precollapse-local

This will give you a shell to work with.
You can also run the commands directly:

> ./bin/precollapse-local help

Will show you  all commands currently available, depending on plugins loaded.

FIXME: describe daemon
