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

from .base import create_base, cls2tbl, tbl2cls, IdType
from ._init import init, ConfiguredSaOrmModule, DEFAULTS
from ._session import QueryIdsMixin
from .dataloader import load_data
from .helpers import create_collection_class, create_relationship_class

__version__ = '0.4.0'

__all__ = (
    'create_base', 'init', 'ConfiguredSaOrmModule', 'DEFAULTS', 'cls2tbl',
    'tbl2cls', 'IdType', 'QueryIdsMixin', 'load_data',
    'create_collection_class', 'create_relationship_class')
