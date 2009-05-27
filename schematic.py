#!/usr/bin/env python
"""
The worst schema versioning system, ever?

Usage: schematic.py path/to/schema_files

schematic talks to your database over stdin on the command line.  Thus,
it supports all DBMSs that have a command line interface and doesn't
care what programming language you worship.  Win!

Schematic expects 1 argument which is the directory full of schema and
DDL files you wish to mirgrate.

Configuration is done in `settings.py`, which should look something like:

    # How to connect to the database
    db = 'mysql --silent -p blam -D pow'
    # The table where version info is stored.
    table = 'schema_version'

It's python so you can do whatever crazy things you want, and it's a
separate file so you can keep local settings out of version control.

Migrations are just sql in files whose names start with a number, like
`001-adding-awesome.sql`.  They're matched against `'^\d+'` so you can
put zeros in front to keep ordering in `ls` happy, and whatever you want
after the migration number, such as text describing the migration.
Make sure settings.py is in your PYTHONPATH.

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

"""

import getopt
import os
import re
import sys
from subprocess import Popen, PIPE

try:
    import settings
except ImportError, e:
    print "You must create a settings.py and put it in your PYTHONPATH"
    raise e


SETTINGS = 'settings'
VARIABLES = ['db', 'table']

CREATE  = 'CREATE TABLE %s (version INTEGER NOT NULL);'
COUNT   = 'SELECT COUNT(version) FROM %s;'
SELECT  = 'SELECT version FROM %s;'
INSERT  = 'INSERT INTO %s (version) VALUES (%s);'
UPDATE  = 'UPDATE %s SET version = %s;'
UPGRADE = 'BEGIN;\n%s\n%s\nCOMMIT;'


class SchematicError(Exception):
    """Base class for custom errors."""


def exception(f):
    """Decorator to turn a function into an subclass of SchematicError."""
    def __init__(self, *args, **kwargs):
        msg = f(self, *args, **kwargs)
        super(self.__class__, self).__init__(msg)
    return type(f.__name__, (SchematicError,), {'__init__': __init__})

@exception
def MissingSettings(self, path):
    return "Couldn't import settings file at %s" % path


@exception
def SettingsError(self, k):
    return "Couldn't find value for '%s' in %s.py" % (k, SETTINGS)


@exception
def DbError(self, cmd, stdout, stderr, returncode):
        msg = '\n'.join(["Had trouble running this: %s", "stdout: %s",
                         "stderr: %s", "returncode: %s"])
        return msg % (cmd, stdout, stderr, returncode)


def get_args(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "h", ["help"])        
        for opt, args in opts:
            if opt in ('-h', '--help'):
                usage(argv[0])
                sys.exit(0)
        if len(args) == 1:
            path = os.path.realpath(args[0])
            if (os.path.exists(path) and os.path.isdir(path)):
                return path
            else:
                signalError(argv[0], "Error: %s is not valid directory." % path)
        else:
            signalError(argv[0], "Error: Wrong number of arguments.")
    except getopt.GetoptError, Error:
        signalError(argv[0])


def usage(name):
    print """Usage: %s [OPTIONS]...  path/to/schema_files
    OPTIONS
    help    Dishplay this help and exit""" % name

    
def signalError(program_name, message=None):
    if message != None:
        print "%s\n" % message
    usage(program_name)
    sys.exit(2)


def ensure_settings():
    conf = {}
    for k in VARIABLES:
        try:
            getattr(settings, k)
        except AttributeError:
            raise SettingsError(k)

    return conf


def say(db, command):
    """Try talking to the database, bail if there's anything on stderr
    or a bad returncode."""
    p = Popen(db, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = p.communicate(command)

    if stderr or p.returncode != 0:
        raise DbError(command, stdout, stderr, p.returncode)
    else:
        return stdout


def table_check(db, table):
    try:
        # Try a count to see if the table is there.
        count = int(say(db, COUNT % table))
    except DbError:
        # Try to create the table.
        say(db, CREATE % table)
        count = 0

    # Start tracking at version 0.
    if count == 0:
        say(db, INSERT % (table, 0))


def find_upgrades(schema_dir):
    fullpath = lambda p: os.path.join(schema_dir, p)
    files = [p for p in map(fullpath, os.listdir(schema_dir)) if os.path.isfile(p)]
    
    upgrades = {}
    for f in files:
        print os.path.basename(f)
        m = re.match('^(\d+)', os.path.basename(f))
        if m:
            upgrades[int(m.group(0))] = f
    return upgrades


def run_upgrades(db, table, schema_dir):
    current = get_version(db, table)
    all_upgrades = sorted(find_upgrades(schema_dir).items())
    upgrades = [(version, path) for version, path in all_upgrades
                if version > current]
    for version, path in upgrades:
        upgrade(db, table, version, path)


def upgrade(db, table, version, path):
    sql = open(path).read()
    update = UPDATE % (table, version)
    print 'Running migration %s:\n' % version, sql
    say(db, UPGRADE % (sql, update))


def get_version(db, table):
    return int(say(db, SELECT % table))


def main(argv):
    schema_dir = get_args(argv)
    
    ensure_settings()
    db = settings.db
    table = settings.table
    
    table_check(db, table)
    run_upgrades(db, table, schema_dir)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except SchematicError, e:
        print 'Error:', e
