# Copyright © 2015-2018 STRG.AT GmbH, Vienna, Austria
# Copyright © 2019-2023 Necdet Can Ateşman, Vienna, Austria
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

from sqlalchemy import __version__ as sqlalchemy_version
from sqlalchemy.sql.expression import Executable, ClauseElement, select
from sqlalchemy.ext.compiler import compiles


# We need to use an older select() API when working with SqlAlchemy 1.3
# or lower. We could use an external library to parse SqlAlchemy's version
# string properly, but we don't want to add an unnecessary dependency for a
# rather trivial operation like this.
sqlalchemy_version_parts = sqlalchemy_version.split('.', maxsplit=2)
sqlalchemy_major_version = int(sqlalchemy_version_parts[0])
sqlalchemy_minor_version = int(sqlalchemy_version_parts[1])
_USE_OLD_STYLE_SELECT = (
    sqlalchemy_major_version < 1
    or (sqlalchemy_major_version == 1 and sqlalchemy_minor_version < 4))


class DropView(Executable, ClauseElement):

    inherit_cache = True

    def __init__(self, name):
        self.name = name


@compiles(DropView, 'sqlite')
@compiles(DropView, 'postgresql')
def visit_drop_view(element, compiler, **kw):
    return 'DROP VIEW IF EXISTS "%s"' % element.name


class CreateView(Executable, ClauseElement):

    inherit_cache = True

    def __init__(self, name, select):
        self.name = name
        self.select = select


@compiles(CreateView, 'sqlite')
@compiles(CreateView, 'postgresql')
def visit_create_view(element, compiler, **kw):
    return 'CREATE VIEW "%s" AS %s' % (
         element.name,
         compiler.process(element.select, literal_binds=True)
     )


def generate_create_inheritance_view_statement(class_):
    viewname = class_.__tablename__[1:]
    tables = class_.__table__
    cols = {}

    def add_cols(table):
        for col in table.c:
            if col.name not in cols:
                cols[col.name] = col

    add_cols(class_.__table__)
    if class_.__score_sa_orm__['inheritance'] is not None:
        parent = class_.__score_sa_orm__['parent']
        while parent:
            table = parent.__table__
            tables = tables.join(
                table, onclause=table.c.id == class_.__table__.c.id)
            add_cols(table)
            parent = parent.__score_sa_orm__['parent']
    if class_.__score_sa_orm__['inheritance'] != 'single-table':
        if _USE_OLD_STYLE_SELECT:
            viewselect = select(cols.values(), from_obj=tables)
        else:
            viewselect = select(*cols.values())\
                .select_from(tables)
    else:
        typecol = getattr(
            class_, class_.__score_sa_orm__['type_column'])
        typenames = []

        def add_typenames(cls):
            typenames.append(cls.__score_sa_orm__['type_name'])
            for subclass in cls.__subclasses__():
                add_typenames(subclass)

        add_typenames(class_)
        if _USE_OLD_STYLE_SELECT:
            viewselect = select(cols.values(),
                                from_obj=class_.__table__,
                                whereclause=typecol.in_(typenames))
        else:
            viewselect = select(*cols.values())\
                .select_from(class_.__table__)\
                .where(typecol.in_(typenames))
    return CreateView(viewname, viewselect)


def generate_drop_inheritance_view_statement(class_):
    viewname = class_.__tablename__[1:]
    return DropView(viewname)
