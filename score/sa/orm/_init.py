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

from score.init import (
    ConfiguredModule, ConfigurationError, parse_dotted_path, parse_bool)
from ._session import sessionmaker, QueryIdsMixin
from .base import BaseMeta
from .triggers import CreateInheritanceTrigger, DropInheritanceTrigger
from .views import (
    generate_drop_inheritance_view_statement,
    generate_create_inheritance_view_statement,
)
import weakref
import sqlalchemy as sa


defaults = {
    'ctx.member': 'orm',
    'zope_transactions': False,
}


def init(confdict, db, ctx=None):
    """
    Initializes this module acoording to :ref:`our module initialization
    guidelines <module_initialization>` with the following configuration keys:

    :confkey:`base`
        The dotted python path to the :ref:`base class <sa_orm_base_class>` to
        configure, as interpreted by :func:`score.init.parse_dotted_path`.

    :confkey:`ctx.member` :confdefault:`db`
        The name of the :term:`context member`, that should be registered with
        the configured :mod:`score.ctx` module (if there is one). The default
        value allows you to always access a valid session within a
        :class:`score.ctx.Context` like this:

        >>> ctx.orm.query(User).first()

    :confkey:`zope_transactions` :confdefault:`False`
        Whether the :attr:`Session` should include the `zope transaction
        extension`_ outside of :class:`score.ctx.Context` objects. Note that
        sessions created as :term:`context members <context member>` always
        include this extension, since the :mod:`score.ctx` module makes use of
        zope transactions.

        .. _zope transaction extension:
            https://pypi.python.org/pypi/zope.sqlalchemy

    """
    conf = defaults.copy()
    conf.update(confdict)
    if not conf['base']:
        raise ConfigurationError('score.sa.orm', 'No base class configured')
    Base = parse_dotted_path(conf['base'])
    if not issubclass(type(Base), BaseMeta):
        raise ConfigurationError(
            'score.sa.orm',
            'Configured base class not created via create_base()')
    if Base.metadata.bind:
        raise ConfigurationError(
            'score.sa.orm', 'Base class already bound to another engine')
    Base.metadata.bind = db.engine
    ctx_member = None
    if conf['ctx.member'] and conf['ctx.member'] != 'None':
        ctx_member = conf['ctx.member']
    if ctx and ctx_member and db.ctx_transaction:
        raise ConfigurationError(
            'score.sa.orm',
            'score.sa.db is configured to manage transactions in Context '
            'objects. This feature conflicts with the zope transaction '
            'extension used by this module (score.sa.orm). Until there is a '
            'proper solution to this issue, you must either disable Context '
            'transactions in score.sa.db (by setting ctx.transaction to '
            '`False`) or disable ctx support for this module by setting '
            'ctx.member to `None`.')
    if db.engine.dialect.name == 'sqlite':
        @sa.event.listens_for(db.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    zope_transactions = parse_bool(conf['zope_transactions'])
    return ConfiguredSaOrmModule(db, ctx, Base, ctx_member, zope_transactions)


class ConfiguredSaOrmModule(ConfiguredModule):
    """
    This module's :class:`configuration class
    <score.init.ConfiguredModule>`.
    """

    def __init__(self, db, ctx, Base, ctx_member, zope_transactions):
        super().__init__('score.sa.orm')
        self.db = db
        self.Base = Base
        self.ctx_member = ctx_member
        self.zope_transactions = zope_transactions
        self.Session = None
        self.session_mixins = {QueryIdsMixin}
        self.__ctx_sessions = weakref.WeakKeyDictionary()
        if ctx and ctx_member:
            ctx.register(ctx_member, self.get_session)

    def add_session_mixin(self, mixin):
        """
        Adds a mixin class to the Session obejct.

        You can use this function to add arbitrary features to your database
        sessions:

        .. code-block:: python

            class RestaurantSketch:

                def __init__(self, *args, **kwargs):
                    # this function will receive the same arguments as the
                    # base Session class (sqlalchemy.orm.session.Session)
                    pass

                def dirty_fork(self):
                    try:
                        raise Exception('The waiter has commited suicide!')
                    except Exception as e:
                        raise BadPunchLineException() from e

        After registering this mixin through this function, you can access its
        functions in every session instance:

        .. code-block:: python

            try:
                # prepare for a bad punch line
                ctx.orm.dirty_fork()
            except BadPunchLineException:
                pass  # out

        This function must be called before this object is finalized.
        """
        assert not self._finalized
        self.session_mixins.add(mixin)

    def _finalize(self):
        kwargs = {
            'bind': self.db.engine,
        }
        if self.zope_transactions:
            from zope.sqlalchemy import ZopeTransactionExtension
            kwargs['extension'] = ZopeTransactionExtension()
        self.Session = sessionmaker(self, **kwargs)

    def get_session(self, ctx):
        """
        Provides a session instance, which is bound to the life-cycle of given
        context object. Will always return the same session object for the same
        input value.
        """
        try:
            return self.__ctx_sessions[ctx]
        except KeyError:
            from zope.sqlalchemy import ZopeTransactionExtension
            zope_tx = ZopeTransactionExtension(
                transaction_manager=ctx.tx_manager)
            if self.db.ctx_member:
                connection = self.db.get_connection(ctx)
            else:
                connection = self.db.engine
            session = self.Session(extension=zope_tx, bind=connection)
            self.__ctx_sessions[ctx] = session
            return session

    def create(self):
        """
        Generates all necessary tables, views, triggers, sequences, etc.
        """
        # create all tables
        self.Base.metadata.create_all()
        session = self.Session(extension=[])
        # generate inheritance views and triggers: we do this starting with the
        # base class and working our way down the inheritance hierarchy
        classes = [cls for cls in self.Base.__subclasses__()
                   if cls.__score_sa_orm__['parent'] is None]
        while classes:
            for cls in classes:
                self._create_inheritance_trigger(session, cls)
                self._create_inheritance_view(session, cls)
            classes = [sub for cls in classes for sub in cls.__subclasses__()]
        session.commit()

    def _create_inheritance_trigger(self, session, class_):
        """
        Creates the inheritance trigger for given *class_*. This trigger will
        delete entries from parent tables, whenever a row in the given table is
        deleted.

        Example: assuming the given class ``Administrator`` is a sub-class of
        ``User``, this will create an sqlite trigger like the following:

            CREATE TRIGGER autodel_administrator
              AFTER DELETE ON _administrator
            FOR EACH ROW BEGIN
              DELETE FROM _user WHERE id = OLD.id;
            END
        """
        parent_tables = []
        parent = class_.__score_sa_orm__['parent']
        while parent:
            parent_tables.append(parent.__table__)
            parent = parent.__score_sa_orm__['parent']
        session.execute(DropInheritanceTrigger(class_.__table__))
        if parent_tables:
            session.execute(CreateInheritanceTrigger(
                class_.__table__, parent_tables[0]))

    def _create_inheritance_view(self, session, class_):
        """
        Creates the inheritance view for given *class_*. The view combines all
        fields in the given class, as well as those in parent classes.

        Example: assuming the following table structure:

          CREATE TABLE _file (
            id INTEGER NOT NULL,
            name VARCHAR(100)
          );

          CREATE TABLE _image (
            id INTEGER NOT NULL,
            format VARCHAR(10),
            FOREIGN KEY(id) REFERENCES _file (id)
          );

        The inheritance view for the ``Image`` class would look like the
        following:

          CREATE VIEW image AS
          SELECT f.id, f.name, i.format
          FROM _file f INNER JOIN _image i ON f.id = i.id
        """
        dropview = generate_drop_inheritance_view_statement(class_)
        session.execute(dropview)
        if class_.__score_sa_orm__['inheritance'] is not None:
            createview = generate_create_inheritance_view_statement(class_)
            session.execute(createview)
