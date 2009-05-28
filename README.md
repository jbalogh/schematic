The worst schema versioning system, ever?

Usage: schematic.py path/to/schema_files

schematic talks to your database over stdin on the command line.  Thus,
it supports all DBMSs that have a command line interface and doesn't
care what programming language you worship.  Win!

Schematic expects 1 argument which is the directory full of schema and
DDL files you wish to migrate.

Configuration is done in `settings.py`, which should look something like:

    # How to connect to the database
    db = 'mysql --silent -p blam -D pow'
    # The table where version info is stored.
    table = 'schema_version'

It's python so you can do whatever crazy things you want, and it's a
separate file so you can keep local settings out of version control.
schematic will try to look for settings.py on the PYTHON_PATH and then
in the migrations directory.

Migrations are just sql in files whose names start with a number, like
`001-adding-awesome.sql`.  They're matched against `'^\d+'` so you can
put zeros in front to keep ordering in `ls` happy, and whatever you want
after the migration number, such as text describing the migration.

schematic creates a table (named in settings.py) with one column, that
holds one row, which describes the current version of the database.  Any
migration file with a number greater than the current version will be
applied to the database and the version tracker will be upgraded.  The
migration and version bump are performed in a transaction.

The version-tracking table will initially be set to 0, so the 0th
migration could be a script that creates all your tables (for
reference).  Migration numbers are not required to increase linearly.

schematic doesn't pretend to be intelligent. Running migrations manually
without upgrading the version tracking will throw things off.

Tested on sqlite any mysql.

NOTE: any superfluous output, like column headers, will cause an error.
On mysql, this is fixed by using the `--silent` parameter.

Things that might be nice: downgrades, running python files.
