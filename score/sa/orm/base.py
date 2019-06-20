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

import re
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative.api import DeclarativeMeta


IdType = sa.BigInteger()
IdType = IdType.with_variant(sa.Integer, 'sqlite')


# taken from stackoverflow:
# http://stackoverflow.com/a/1176023/44562
_first_cap_re = re.compile('(.)([A-Z][a-z]+)')
_all_cap_re = re.compile('([a-z0-9])([A-Z])')


def cls2tbl(cls):
    """
    Converts a class (or a class name) to a table name. The class name is
    expected to be in *CamelCase*. The return value will be
    *seperated_by_underscores* and prefixed with an underscore. Omitting
    the underscore will yield the name of the class's :ref:`view <sa_orm_view>`.
    """
    if isinstance(cls, type):
        cls = cls.__name__
    s1 = _first_cap_re.sub(r'\1_\2', cls)
    return '_' + _all_cap_re.sub(r'\1_\2', s1).lower()


def tbl2cls(tbl):
    """
    Inverse of :func:`.cls2tbl`. Returns the name of a class.
    """
    if tbl[0] == '_':
        tbl = tbl[1:]
    parts = tbl.split('_')
    return ''.join(map(lambda s: s.capitalize(), parts))


def clsname(cls):
    return '%s.%s' % (cls.__module__, cls.__name__)


class ConfigurationError(Exception):
    pass


class BaseMeta(DeclarativeMeta):
    """
    Metaclass for the created :class:`.Base` class.
    """

    def __init__(cls, classname, bases, attrs):
        """
        Normalizes configuration values of new database classes.
        """
        if hasattr(cls, '__score_sa_orm__'):
            BaseMeta.set_config(cls, classname, bases, attrs)
            BaseMeta.set_tablename(cls, classname, bases, attrs)
            BaseMeta.configure_inheritance(cls, classname, bases, attrs)
            BaseMeta.set_id(cls, classname, bases, attrs)
        DeclarativeMeta.__init__(cls, classname, bases, attrs)

    def set_config(cls, classname, bases, attrs):
        """
        Sets the class' __score_sa_orm__ value with the computed configuration.
        This dict will contain the following values at the end of this
        function:

        - base: the :term:`base class` of this class.
        - parent: the parent class in the inheritance hierarchy towards
            Base.
        - inheritance: the inheritance type
        - type_name: name of this type in the database, as stored in the
            type_column.
        - type_column: name of the column containing the type_name
        """
        if '__score_sa_orm__' not in attrs:
            cls.__score_sa_orm__ = attrs['__score_sa_orm__'] = {}
        BaseMeta.set_base_config(cls, classname, bases, attrs)
        BaseMeta.set_parent_config(cls, classname, bases, attrs)
        BaseMeta.set_inheritance_config(cls, classname, bases, attrs)
        BaseMeta.set_type_name_config(cls, classname, bases, attrs)
        BaseMeta.set_type_column_config(cls, classname, bases, attrs)

    def set_base_config(cls, classname, bases, attrs):
        base_classes = dict()
        for base in bases:
            if hasattr(base, '__score_sa_orm__'):
                base_classes[base.__score_sa_orm__['base']] = base
        if len(base_classes) > 1:
            raise ConfigurationError(
                'Multiple base class parents for class %s:\n- %s' % (
                    clsname(cls),
                    '\n- '.join(base_classes.values())))
        cls.__score_sa_orm__['base'] = next(iter(base_classes))

    def set_parent_config(cls, classname, bases, attrs):
        cfg = cls.__score_sa_orm__
        cfg['parent'] = None
        for base in bases:
            if base != cfg['base'] and issubclass(base, cfg['base']):
                if cfg['parent'] is not None:
                    raise ConfigurationError(
                        'Diamond inheritance from Base class in %s' %
                        clsname(cls))
                cfg['parent'] = base

    def set_inheritance_config(cls, classname, bases, attrs):
        cfg = cls.__score_sa_orm__
        parent = cfg['parent']
        if parent is not None:
            # this is a sub-class of another class that should
            # already have the 'polymorphic_on' configuration.
            inheritance = parent.__score_sa_orm__['inheritance']
            if inheritance is None:
                raise ConfigurationError(
                    'Parent table of %s does not support inheritance' %
                    clsname(cls))
            if 'inheritance' not in cfg:
                cfg['inheritance'] = inheritance
            elif cfg['inheritance'] != inheritance:
                raise ConfigurationError(
                    'Cannot change inheritance type of %s in subclass %s' %
                    (parent.__name__, clsname(cls)))
        elif 'inheritance' not in cfg:
            cfg['inheritance'] = 'joined-table'
        else:
            if cfg['inheritance'] not in ('single-table', 'joined-table', None):
                raise ConfigurationError(
                    'Invalid inheritance configuration "%s" in class %s' %
                    cfg['inheritance'], clsname(cls))

    def set_type_name_config(cls, classname, bases, attrs):
        cfg = cls.__score_sa_orm__
        if 'type_name' not in cfg:
            if 'polymorphic_identity' in attrs.get('__mapper_args__', {}):
                type_name = attrs['__mapper_args__']['polymorphic_identity']
                cfg['type_name'] = type_name
            else:
                cfg['type_name'] = cls2tbl(classname)[1:]
        elif 'polymorphic_identity' in attrs.get('__mapper_args__', {}):
            raise ConfigurationError(
                'Both sqlalchemy and score.sa.orm configured with a '
                'polymorphic identity,\n'
                'please remove one of the two configurations in %s:\n'
                ' - __mapper_args__[polymorphic_identity]\n'
                ' - __score_sa_orm__[type_name]' % (clsname(cls),))

    def set_type_column_config(cls, classname, bases, attrs):
        cfg = cls.__score_sa_orm__
        if 'type_column' not in cfg:
            if 'polymorphic_on' in attrs.get('__mapper_args__', {}):
                cfg['type_column'] = attrs['__mapper_args__']['polymorphic_on']
            else:
                cfg['type_column'] = '_type'
        if 'polymorphic_on' in attrs.get('__mapper_args__', {}):
            raise ConfigurationError(
                'Both sqlalchemy and score.sa.orm configured with a type '
                'column,\n'
                'please remove one of the two configurations in %s:\n'
                ' - __mapper_args__[polymorphic_on]\n'
                ' - __score_sa_orm__[type_column]' % (clsname(cls),))

    def set_tablename(cls, classname, bases, attrs):
        """
        Sets the ``__tablename__`` member for sqlalchemy.
        """
        if cls.__score_sa_orm__['inheritance'] == 'single-table' and \
                cls.__score_sa_orm__['parent'] is not None:
            # this is a sub-class of another class that should
            # already have a __tablename__ attribute.
            return
        cls.__tablename__ = attrs['__tablename__'] = cls2tbl(classname)

    def configure_inheritance(cls, classname, bases, attrs):
        """
        Sets all necessary members to make the desired inheritance
        configuration work. Will set any/all of the following attributes,
        depending on the *inheritance* configuration:

        - cls.__mapper_args__['polymorphic_identity']
        - cls.__mapper_args__['polymorphic_on']
        - cls._type (or equivalent)
        """
        cfg = cls.__score_sa_orm__
        if cfg['inheritance'] is None:
            return
        if '__mapper_args__' not in attrs:
            cls.__mapper_args__ = attrs['__mapper_args__'] = {}
        if 'polymorphic_identity' not in cls.__mapper_args__:
            cls.__mapper_args__['polymorphic_identity'] = cfg['type_name']
        if cfg['parent'] is not None:
            # this is a sub-class of another class that should
            # already have the 'polymorphic_on' configuration.
            return
        type_column = cfg['type_column']
        cls.__mapper_args__['polymorphic_on'] = type_column
        if type_column not in attrs:
            attrs[type_column] = sa.Column(sa.String(100), nullable=False)
            setattr(cls, type_column, attrs[type_column])

    def set_id(cls, classname, bases, attrs):
        """
        Generates the ``id`` column. The column will contain a foreign key
        constraint to parent class' table, if it is not a direct descendant
        of the :ref:`base class <sa_orm_base_class>`.
        """
        if cls.__score_sa_orm__['inheritance'] == 'single-table' and \
                cls.__score_sa_orm__['parent'] is not None:
            return
        try:
            cls.__mapper_args__['primary_key']
            # primary key already configured via mapper, nothing to do here
            return
        except (AttributeError, KeyError):
            pass
        if 'id' in attrs:
            # do not override explicitly defined id column
            return
        Base = cls.__score_sa_orm__['base']
        args = [Base.__score_sa_orm__['id_type']]
        kwargs = {
            'primary_key': True,
            'nullable': False,
            'unique': True,
        }
        for base in bases:
            if base != Base and issubclass(base, Base):
                args.append(sa.ForeignKey('%s.id' % base.__tablename__,
                                          ondelete='CASCADE',
                                          onupdate='CASCADE'))
                break
        cls.id = attrs['id'] = sa.Column(*args, **kwargs)


def create_base(*, id_type=IdType):
    """
    Returns a :ref:`base class <sa_orm_base_class>` for database access objects.

    It is possible to define the type of auto-generated ID columns by passing an
    sqlalchemy column type as *id_type*.
    """
    Base = declarative_base(metaclass=BaseMeta)
    Base.__score_sa_orm__ = {
        'id_type': id_type,
        'base': Base,
    }
    return Base
