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
