# Copyright © 2015-2018 STRG.AT GmbH, Vienna, Austria
# Copyright © 2019 Necdet Can Ateşman, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in
# the file named COPYING.LESSER.txt.
#
# The SCORE Framework and all its parts are distributed without any WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. For more details see the GNU Lesser General Public
# License.
#
# If you have not received a copy of the GNU Lesser General Public License see
# http://www.gnu.org/licenses/.
#
# The License-Agreement realised between you as Licensee and STRG.AT GmbH as
# Licenser including the issue of its valid conclusion and its pre- and
# post-contractual effects is governed by the laws of Austria. Any disputes
# concerning this License-Agreement including the issue of its valid conclusion
# and its pre- and post-contractual effects are exclusively decided by the
# competent court, in whose district STRG.AT GmbH has its registered seat, at
# the discretion of STRG.AT GmbH also the competent court, in whose district
# the Licensee has his registered seat, an establishment or assets.

from sqlalchemy.sql.expression import Executable, ClauseElement
from sqlalchemy.ext.compiler import compiles
import textwrap


class DropInheritanceTrigger(Executable, ClauseElement):

    def __init__(self, table):
        self.table = table


@compiles(DropInheritanceTrigger, 'sqlite')
def visit_drop_inheritance_trigger_sqlite(element, compiler, **kw):
    return "DROP TRIGGER IF EXISTS autodel{table}".format(
        table=element.table.name)


@compiles(DropInheritanceTrigger, 'postgresql')
def visit_drop_inheritance_trigger_postgresql(element, compiler, **kw):
    return "DROP TRIGGER IF EXISTS autodel{table} ON {table}".format(
        table=element.table.name)


class CreateInheritanceTrigger(Executable, ClauseElement):

    def __init__(self, table, parent):
        self.table = table
        self.parent = parent


@compiles(CreateInheritanceTrigger, 'sqlite')
def visit_create_inheritance_trigger_sqlite(element, compiler, **kw):
    return textwrap.dedent("""
        CREATE TRIGGER autodel{table} AFTER DELETE ON {table}
        FOR EACH ROW BEGIN
            DELETE FROM {parent} WHERE id = OLD.id;
        END
    """).strip().format(parent=element.parent.name, table=element.table.name)


@compiles(CreateInheritanceTrigger, 'postgresql')
def visit_create_inheritance_trigger_postgresql(element, compiler, **kw):
    return textwrap.dedent("""
        CREATE OR REPLACE FUNCTION autodel{parent}() RETURNS TRIGGER AS $_$
            BEGIN
                DELETE FROM {parent} WHERE id = OLD.id;
                RETURN OLD;
            END $_$ LANGUAGE 'plpgsql';
        CREATE TRIGGER autodel{table} AFTER DELETE ON {table}
        FOR EACH ROW EXECUTE PROCEDURE autodel{parent}();
    """).strip().format(parent=element.parent.name, table=element.table.name)
