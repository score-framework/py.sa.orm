# Copyright © 2015-2018 STRG.AT GmbH, Vienna, Austria
#
# This file is part of the The SCORE Framework.
#
# The SCORE Framework and all its parts are free software: you can redistribute
# them and/or modify them under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation which is in the
# file named COPYING.LESSER.txt.
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
# the discretion of STRG.AT GmbH also the competent court, in whose district the
# Licensee has his registered seat, an establishment or assets.

from datetime import datetime
import io
from score.init import parse_dotted_path
from score.sa.db import Enum, EnumType
import sqlalchemy as sa
from sqlalchemy.ext.associationproxy import AssociationProxy
import urllib.request


class DataLoaderException(Exception):
    pass


def load_data(thing, objects=None):
    """
    Loads data from given *thing*, i.e. a file, a file-like object or a URL. If
    the source contains references to other objects loaded in an earlier call,
    you can pass them as *objects*. Usual usage:

    .. code-block:: python

        objects = load_data('base.yaml')
        if generate_dummy_data:
            objects = load_data('dummy.yaml', objects)
    """
    if isinstance(thing, io.IOBase):
        return load_yaml(thing, objects)
    if not isinstance(thing, str):
        raise DataLoaderException('Could not determine loader to use')
    if ':' in thing:
        return load_url(thing, objects)
    return load_yaml(thing, objects)


def load_url(url, objects=None):
    """
    Loads objects from a yaml resources under given *url*. See :func:`load_data`
    for the description of the *objects* parameter.
    """
    return load_yaml(urllib.request.urlopen(url))


def load_yaml(file, objects=None):
    """
    Loads objects from a yaml *file*. See :func:`load_data` for the description
    of the *objects* parameter.
    """
    import yaml
    try:
        from yaml import CLoader as Loader
    except ImportError:
        from yaml import Loader
    if not isinstance(file, io.IOBase):
        file = open(file)
    return _postprocess(yaml.load(file, Loader=Loader), objects)


def _postprocess(data, objects=None):
    relationships = {}
    proxies = {}
    columns = {}
    if not objects:
        objects = {}
        classes = {}
    else:
        classes = dict((cls, parse_dotted_path(cls))
                       for cls in objects)
    for classname in data:
        classes[classname] = parse_dotted_path(classname)
        cls = classes[classname]
        relationships[classname] = {}
        proxies[classname] = {}
        for relationship in sa.inspect(cls).relationships:
            relationships[classname][relationship.key] = relationship
        columns[classname] = {}
        for column in sa.inspect(cls).columns:
            columns[classname][column.description] = column
        if classname not in objects:
            objects[classname] = {}
        objects[classname].update(dict((id, cls()) for id in data[classname]))
        for member in dir(cls):
            if member.startswith('__'):
                continue
            value = getattr(cls, member)
            if isinstance(value, AssociationProxy):
                proxies[classname][member] = value
    for classname in data:
        cls = classes[classname]
        for id in data[classname]:
            obj = objects[classname][id]
            if not data[classname][id]:
                continue
            for member in data[classname][id]:
                value = data[classname][id][member]
                if member in relationships[classname]:
                    relcls = relationships[classname][member].argument
                    if isinstance(relcls, sa.orm.Mapper):
                        relcls = relcls.class_
                    else:
                        relcls = relcls()
                    if not isinstance(relcls, type):
                        relcls = relcls.__class__
                    value = _replace_object(classes, objects, relcls, value)
                elif member in proxies[classname]:
                    proxy = proxies[classname][member]
                    col = proxy.attr[1].property.columns[0]
                    if isinstance(col.type, type(cls)):
                        value = _replace_object(classes, objects, relcls, value)
                    else:
                        value = map(lambda v: _convert_value(v, col), value)
                elif member in columns[classname]:
                    value = _convert_value(value, columns[classname][member])
                setattr(obj, member, value)
    return objects


def _replace_object(classes, objects, cls, value):
    if isinstance(value, list):
        def converter(item):
            return _replace_object(classes, objects, cls, item)
        return list(map(converter, value))
    key = '%s.%s' % (cls.__module__, cls.__name__)
    if key in objects:
        return objects[key][value]
    for classname in objects:
        othercls = classes[classname]
        if not issubclass(othercls, cls):
            continue
        if value in objects[classname]:
            return objects[classname][value]
    raise DataLoaderException('Could not find referenced object "%s"' % value)


def _convert_value(value, column):
    if isinstance(column.type, sa.DateTime) and not isinstance(value, datetime):
        return datetime(value)
    if isinstance(column.type, EnumType) and not isinstance(value, Enum):
        return column.type.enum(value.strip())
    return value
