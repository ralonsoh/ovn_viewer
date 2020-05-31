# Copyright (c) 2020 Fistro Co.

import abc
import collections
import copy
import re

from ovsdbapp.backend.ovs_idl import rowview

from ovn_viewer import constants


class TreeType(object, metaclass=abc.ABCMeta):

    TYPE = None

    def __init__(self, treeview, ovn_nb, ovn_sb, parent_leaf=None):
        self._treeview = treeview
        self._ovn_nb = ovn_nb
        self._ovn_sb = ovn_sb
        self._parent_leaf = parent_leaf or ''
        self._own_leaf = None
        self._db = {}
        self._child_trees = {}

    @property
    def own_leaf(self):
        """Root of a subtree where a new tree will be built

        For example, all Logical Switches will be under a tree element called
        'Logical_Switch':
          tree_root
            |
            -> 'Logical_Switch'
                 |
                 -> logical_switch_1
                 -> logical_switch_2 ...
        """
        if not self._own_leaf:
            self._own_leaf = self._treeview.insert(self._parent_leaf, '0',
                                                   text=self.TYPE)
        return self._own_leaf

    @abc.abstractmethod
    def populate_subtree(self, parent_leaf=None, uuids=None):
        """Add elements to the subtree leaves

        Each element will be populated in the treeview object and will contain:
        - "text": usually the UUID plus an extra short information
        - "tags": the OVN database type (see "OVN element types" constants)
        - "values": a list of variables but just with one element, the UUID
        """

    @abc.abstractmethod
    def print_info(self):
        """Print single element information in a string variable"""

    @abc.abstractmethod
    def store_info(self):
        """Store information for each element to be used in "print_info"

        Each tree will store the information of each leaf (and subtrees), in
        case of using a static view of the OVN DB (auto-refresh disabled).
        We store a snapshot of the DB (only the needed information) when we
        populate the subtree.
        """


class LogicalSwitches(TreeType):

    TYPE = constants.LOGICAL_SWITCH

    def populate_subtree(self, parent_leaf=None, uuids=None):
        self._child_trees = {}
        for ls in self._ovn_nb.tables[self.TYPE].rows.values():
            text = str(ls.uuid)
            network_name = ls._data['external_ids'].get('neutron:network_name')
            if network_name:
                text += ' (network: %s)' % network_name
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', str(ls.uuid), text=text, tags=self.TYPE,
                values=str(ls.uuid))
            lsp_tt = LogicalSiwtchPorts(
                self._treeview, self._ovn_nb, self._ovn_sb,
                parent_leaf=child_leaf)
            lsp_tt.populate_subtree(child_leaf,
                                    [port.value for port in
                                     ls._data['ports'].values.keys()])
            self._child_trees[ls.uuid] = lsp_tt

    def print_info(self):
        pass

    def store_info(self):
        pass


class LogicalSiwtchPorts(TreeType):

    TYPE = constants.LOGICAL_SWITCH_PORT

    def populate_subtree(self, parent_leaf=None, uuids=None):
        self._child_trees = {}
        for port_uuid in uuids:
            port = self._ovn_nb.tables[self.TYPE].rows.get(port_uuid)
            text = str(port.uuid)
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', text, text=text, tags=self.TYPE,
                values=text)
            qos_tt = QoSes(self._treeview, self._ovn_nb, self._ovn_sb,
                           parent_leaf=child_leaf)
            qos_tt.populate_subtree(parent_leaf=child_leaf)
            self._child_trees[port.uuid] = qos_tt

    def print_info(self):
        pass

    def store_info(self):
        pass


class QoSes(TreeType):

    TYPE = constants.QOS
    EXTID_QOS_MAP = None
    QOS_DB = None
    REGEX_ID = re.compile(r'(inport|outport) == '
                          r'[\"\'](?P<id>[0-9a-fA-F\-]+)[\"\']')

    def populate_subtree(self, parent_leaf=None, uuids=None):
        for qos in self.extid_qos_map.get(parent_leaf, []):
            text = str(qos['uuid'])
            self._treeview.insert(
                self.own_leaf, 'end', text, text=text, tags=self.TYPE,
                values=text)

    @property
    def extid_qos_map(self):
        if self.__class__.EXTID_QOS_MAP is None:
            self.__class__.EXTID_QOS_MAP = collections.defaultdict(list)
            self.__class__.QOS_DB = {}
            for qos in self._ovn_nb.tables[self.TYPE].rows.values():
                # TODO(ralonsoh): in "external_ids", add the FIP ID or the port
                #                 ID; that will speed up the search without
                #                 using regex.
                qos_row = rowview.RowView(qos)
                match = self.REGEX_ID.search(qos_row.match)
                if match:
                    datum = copy.deepcopy(qos._data)
                    datum['uuid'] = qos.uuid
                    self.__class__.QOS_DB[qos.uuid] = copy.deepcopy(datum)
                    self.__class__.EXTID_QOS_MAP[match.group('id')].append(
                        self.__class__.QOS_DB[qos.uuid])

        return self.__class__.EXTID_QOS_MAP

    def print_info(self):
        pass

    def store_info(self):
        pass

