# Copyright (c) 2020 Fistro Co.

from ovsdbapp.backend.ovs_idl import idlutils
from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp import event as ovs_event
from ovsdbapp.schema.ovn_northbound import impl_idl as nb_impl_idl

from ovn_viewer import constants


class OvnIdl(connection.OvsdbIdl):

    def __init__(self, connection_string, schema_name, notification_backend):
        helper = idlutils.get_schema_helper(connection_string, schema_name)
        helper.register_all()
        self._notification_backend = notification_backend
        super(OvnIdl, self).__init__(connection_string, helper)

    def notify(self, event, row, updates=None):
        if row._table.name not in constants.NOTIFY_ELEMENT_TYPES:
            return
        if event == ovs_event.RowEvent.ROW_CREATE:
            pass  # TODO(ralonsoh): to implement
        if event == ovs_event.RowEvent.ROW_UPDATE:
            pass  # TODO(ralonsoh): to implement
        if event == ovs_event.RowEvent.ROW_DELETE:
            self._notification_backend.delete_leaf(row)


def get_ovn_conn(viewer):
    _nb_idl = OvnIdl(constants.OVN_NB_CONNECTION, 'OVN_Northbound', viewer)
    _nb_conn = connection.Connection(
        _nb_idl, timeout=constants.OVSDB_CONNECTION_TIMEOUT)
    ovn_nb = nb_impl_idl.OvnNbApiIdlImpl(_nb_conn, start=True)
    _sb_idl = OvnIdl(constants.OVN_SB_CONNECTION, 'OVN_Southbound', viewer)
    _sb_conn = connection.Connection(
        _sb_idl, timeout=constants.OVSDB_CONNECTION_TIMEOUT)
    ovn_sb = nb_impl_idl.OvnNbApiIdlImpl(_sb_conn, start=True)
    return ovn_nb, ovn_sb
