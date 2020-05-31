# Copyright (c) 2020 Fistro Co.

from ovsdbapp.backend.ovs_idl import idlutils
from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp.schema.ovn_northbound import impl_idl as nb_impl_idl

from ovn_viewer import constants


class OvnIdl(connection.OvsdbIdl):

    def __init__(self, connection_string, schema_name):
        helper = idlutils.get_schema_helper(connection_string, schema_name)
        helper.register_all()
        super(OvnIdl, self).__init__(connection_string, helper)

    def notify(self, event, row, updates=None):
        # TODO(ralonsoh): do something when a register is update (refresh the
        #                 tree view)
        pass


def get_ovn_conn():
    _nb_idl = OvnIdl(constants.OVN_NB_CONNECTION, 'OVN_Northbound')
    _nb_conn = connection.Connection(
        _nb_idl, timeout=constants.OVSDB_CONNECTION_TIMEOUT)
    ovn_nb = nb_impl_idl.OvnNbApiIdlImpl(_nb_conn, start=True)
    _sb_idl = OvnIdl(constants.OVN_SB_CONNECTION, 'OVN_Southbound')
    _sb_conn = connection.Connection(
        _sb_idl, timeout=constants.OVSDB_CONNECTION_TIMEOUT)
    ovn_sb = nb_impl_idl.OvnNbApiIdlImpl(_sb_conn, start=True)
    return ovn_nb, ovn_sb
