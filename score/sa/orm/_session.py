# Copyright © 2015-2017 STRG.AT GmbH, Vienna, Austria
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

import sqlalchemy.orm.session


class IdsNotFound(Exception):
    """
    Thrown by :meth:`.SessionMixin.by_ids` if any of the given ids was not
    found.
    """
    pass


class QueryIdsMixin:
    """
    A mixin for sqlalchemy :class:`session <sqlalchemy.orm.session.Session>`
    classes that adds some convenience features.
    """

    def __init__(self, *args, **kwargs):
        pass

    def by_ids(self, type, ids, *, ignore_missing=True):
        """
        Yields objects of *type* with given *ids*. The function will return the
        objects in the order of their id in the *ids* parameter. The following
        code will print the User with id #4 first, followed by
        the users #2 and #5::

          for user in session.by_ids(User, [4,2,5]):
            print(user)

        If *ignore_missing* evaluates to `False`, the function will raise an
        :class:`IdsNotFound` exception if any of the ids were not present in the
        database.

        The main use case of this function is retrieval of objects, that were
        found through queries on external resources, such as full text indexing
        services like elasticsearch_.

        .. _elasticsearch: https://www.elastic.co/products/elasticsearch
        """
        if not ignore_missing:
            rows = self.query(type.id).filter(type.id.in_(ids)).all()
            if len(rows) != len(ids):
                existing_ids = list(row[0] for row in rows)
                missing_ids = list(id for id in ids if id not in existing_ids)
                raise IdsNotFound(missing_ids)
        chunk_size = 20
        while len(ids) > 0:
            chunk = ids[0:chunk_size]
            ids = ids[chunk_size:]
            result = dict(self.query(type.id, type).
                          filter(type.id.in_(chunk)))
            for id in chunk:
                try:
                    yield result[id]
                except KeyError:
                    pass


def sessionmaker(conf, *args, **kwargs):
    """
    Wrapper around sqlalchemy's :func:`sessionmaker
    <sqlalchemy.orm.sessionmaker>` that adds our :class:`.SessionMixin` to the
    session base class. All arguments — except the :class:`.DbConfiguration`
    *conf* — are passed to the wrapped ``sessionmaker`` function.
    """
    try:
        base = kwargs['class_']
    except KeyError:
        base = sqlalchemy.orm.session.Session
    bases = (base,) + tuple(conf.session_mixins)

    def __init__(self, *args, **kwargs):
        self.conf = conf
        for base in bases:
            base.__init__(self, *args, **kwargs)

    ConfiguredSession = type('ConfiguredSession', bases, {
        '__init__': __init__
    })
    kwargs['class_'] = ConfiguredSession
    return sqlalchemy.orm.sessionmaker(*args, **kwargs)
