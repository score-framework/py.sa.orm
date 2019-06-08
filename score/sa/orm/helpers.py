from .base import IdType, tbl2cls
from sqlalchemy import (
    Column, ForeignKey, Integer, UniqueConstraint)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.orderinglist import ordering_list


def create_relationship_class(cls1, cls2, member, *, classname=None,
                              sorted=False, duplicates=True, backref=None):
    """
    Creates a class linking two given models and adds appropriate relationship
    properties to the classes.

    At its minimum, this function requires two classes *cls1* and *cls2* to be
    linked—where cls1 is assumed to be the owning part of the relation—and the
    name of the member to be added to the owning class:

    >>> UserGroup = create_relationship_class(User, Group, 'groups')

    By default, this will create a class called UserGroup, which looks like the
    following:

    >>> class UserGroup(Storable):
    ...     __score_sa_orm__: {
    ...         'inheritance': None
    ...     }
    ...     index = Column(Integer, nullable=False)
    ...     user_id = Column(IdType, nullable=False, ForeignKey('_user.id'))
    ...     user = relationship(Group, foreign_keys=[user_id])
    ...     group_id = Column(IdType, nullable=False, ForeignKey('_group.id'))
    ...     group = relationship(Group, foreign_keys=[group_id])

    You can choose the name of the new class by passing it as the *classname*
    argument, which also has an effect on the table name.

    It will also add a new member 'groups' to the User class, which is of type
    :class:`sqlalchemy.orm.properties.RelationshipProperty`.

    The parameter *sorted* decides whether the relationship is stored with a
    sorting 'index' column.

    It is possible to declare that the relationship does not accept
    *duplicates*, in which case the table will also have a
    :class:`UniqueConstraint <sqlalchemy.schema.UniqueConstraint>` on
    ``[user_id, group_id]``

    Providing a *backref* member, will also add a relationship property to the
    second class with the given name.

    """
    if classname is None:
        classname = cls1.__name__ + cls2.__name__
    Base = cls1.__score_sa_orm__['base']
    if Base != cls2.__score_sa_orm__['base']:
        raise ValueError('Provided classes have different base classes')
    IdType = Base.__score_sa_orm__['id_type']
    idcol1 = cls1.__tablename__[1:] + '_id'
    idcol2 = cls2.__tablename__[1:] + '_id'
    refcol1 = cls1.__tablename__[1:]
    refcol2 = cls2.__tablename__[1:]
    members = {
        '__score_sa_orm__': {
            'inheritance': None
        },
        idcol1: Column(
            IdType,
            ForeignKey('%s.id' % cls1.__tablename__,
                       onupdate="CASCADE",
                       ondelete="CASCADE"),
            nullable=False),
        idcol2: Column(
            IdType,
            ForeignKey('%s.id' % cls2.__tablename__,
                       onupdate="CASCADE",
                       ondelete="CASCADE"),
            nullable=False),
    }
    members[refcol1] = relationship(cls1, foreign_keys=members[idcol1])
    members[refcol2] = relationship(cls2, foreign_keys=members[idcol2])
    if not duplicates:
        members['__mapper_args__'] = {
            'primary_key': [members[idcol1], members[idcol2]]
        }
    if sorted:
        members['index'] = Column(Integer, nullable=False)
    cls = type(classname, (cls1.__score_sa_orm__['base'],), members)
    if sorted:
        rel = relationship(cls2, secondary=cls.__tablename__,
                           order_by='%s.index' % classname,
                           remote_side=lambda: cls1.id)
    else:
        rel = relationship(cls2, secondary=cls.__tablename__,
                           remote_side=lambda: cls1.id)
    setattr(cls1, member, rel)
    if backref:
        rel = relationship(cls1, secondary=cls.__tablename__,
                           remote_side=lambda: cls2.id)
        setattr(cls2, backref, rel)
    return cls


def create_collection_class(owner, member, column, *,
                            sorted=True, duplicates=True):
    """
    Creates a class for holding the values of a collection in given *owner*
    class.

    The given *owner* class will be updated to have a new *member* with given
    name, which is a list containing elements as described by *column*:

    >>> create_collection_class(Group, 'permissions',
    ...                         Column(PermissionEnum.db_type(), nullable=False)

    Group objects will now have a member called 'permissions', which contain a
    sorted list of PermissionEnum values.

    See :func:`.create_relationship_class` for the description of the keyword
    arguments.
    """
    Base = cls1.__score_sa_orm__['base']
    IdType = Base.__score_sa_orm__['id_type']
    name = owner.__name__ + tbl2cls(member)
    if sorted:
        bref = backref(member + '_wrapper', order_by='%s.index' % name,
                       collection_class=ordering_list('index'))
    else:
        bref = backref(member + '_wrapper')
    members = {
        '__score_sa_orm__': {
            'inheritance': None
        },
        'owner_id': Column(IdType, ForeignKey('%s.id' % owner.__tablename__),
                           nullable=False),
        'owner': relationship(owner, backref=bref),
        'value': column,
    }
    if sorted:
        members['index'] = Column(Integer, nullable=False)
    if not duplicates:
        members['__table_args__'] = (
            UniqueConstraint(members['owner_id'], column),
        )
    cls = type(name, (owner.__score_sa_orm__['base'],), members)
    proxy = association_proxy(member + '_wrapper', 'value',
                              creator=lambda v: cls(value=v))
    setattr(owner, member, proxy)
    return cls
