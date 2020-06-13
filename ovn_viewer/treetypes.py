# Copyright (c) 2020 Fistro Co.

import abc
import collections
import re

from ovsdbapp.backend.ovs_idl import rowview

from ovn_viewer import constants


class TreeType(object, metaclass=abc.ABCMeta):

    TYPE = None

    def __init__(self, root_tree, ovn_nb, ovn_sb, parent_leaf=None,
                 parent_uuid=None):
        self._root_tree = root_tree
        self._treeview = root_tree.treeview
        self._ovn_nb = ovn_nb
        self._ovn_sb = ovn_sb
        self._parent_leaf = parent_leaf or ''
        self._parent_uuid = parent_uuid
        self._own_leaf = None

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
    def populate_subtree(self, uuids=None):
        """Add elements to the subtree leaves

        Each element will be populated in the treeview object and will contain:
        - "text": usually the UUID plus an extra short information
        - "tags": the OVN database type (see "OVN element types" constants)
        - "values": a list of variables but just with one element, the UUID
        """

    @staticmethod
    @abc.abstractmethod
    def print_info(text_box, datum):
        """Print single element information in a string variable"""

    @abc.abstractmethod
    def store_info(self, row):
        """Store information for each element to be used in "print_info"

        Each tree will store the information of each leaf (and subtrees), in
        case of using a static view of the OVN DB (auto-refresh disabled).
        We store a snapshot of the DB (only the needed information) when we
        populate the subtree.
        """


class RootTree(object):

    def __init__(self, treeview, ovn_nb, ovn_sb):
        self._treeview = treeview
        self._ovn_nb = ovn_nb
        self._ovn_sb = ovn_sb
        self._db = {
            constants.LOGICAL_SWITCH: {},
            constants.LOGICAL_SWITCH_PORT: {},
            constants.PORT_GROUP: {},
            constants.QOS: {},
            constants.ACL: {},
        }
        self._tree = {}  # Main parents: LS and PG.
        self._tree_parents = {}

    def populate_subtree(self):
        ls_tt = LogicalSwitches(self, self._ovn_nb, self._ovn_sb)
        ls_tt.populate_subtree()
        pg_tt = PortGroups(self, self._ovn_nb, self._ovn_sb)
        pg_tt.populate_subtree()

    def get_leaf(self, item_type, uuid):
        try:
            return self._db[item_type][uuid]
        except KeyError:
            return

    def add_leaf(self, item_type, uuid, parent_uuid, datum):
        self._db[item_type][uuid] = datum
        if item_type == constants.LOGICAL_SWITCH:
            self._add_leaf_ls(uuid)
        elif item_type == constants.LOGICAL_SWITCH_PORT:
            self._add_leaf_lsp(uuid, parent_uuid)
        elif item_type == constants.QOS:
            self._add_leaf_qos(uuid, parent_uuid)
        elif item_type == constants.PORT_GROUP:
            self._add_leaf_pg(uuid)
        elif item_type == constants.ACL:
            self._add_leaf_acl(uuid, parent_uuid)

    def _add_leaf_ls(self, uuid):
        if uuid in self._tree:
            return
        self._tree[uuid] = {}

    def _add_leaf_lsp(self, uuid, ls_uuid):
        if uuid in self._tree[ls_uuid]:
            return
        self._tree[ls_uuid][uuid] = {}
        self._tree_parents[uuid] = ls_uuid

    def _add_leaf_qos(self, uuid, lsp_uuid):
        ls_uuid = self._tree_parents[lsp_uuid]
        if uuid in self._tree[ls_uuid][lsp_uuid]:
            return

        self._tree[ls_uuid][lsp_uuid][uuid] = True  # No child leafs.
        self._tree_parents[uuid] = lsp_uuid

    def _add_leaf_pg(self, uuid):
        if uuid in self._tree:
            return
        self._tree[uuid] = {}

    def _add_leaf_acl(self, uuid, pg_uuid):
        if uuid in self._tree[pg_uuid]:
            return
        self._tree[pg_uuid][uuid] = True  # No child leafs.
        self._tree_parents[uuid] = pg_uuid

    @property
    def treeview(self):
        return self._treeview

    def print_on_text_box(self, text_box, item_type, uuid):
        try:
            info = self._db[item_type][uuid]
        except KeyError:
            return

        for klass in (k for k in TreeType.__subclasses__() if
                      k.TYPE == item_type):
            klass.print_info(text_box, info)


class LogicalSwitches(TreeType):

    TYPE = constants.LOGICAL_SWITCH

    def populate_subtree(self, uuids=None):
        for ls in self._ovn_nb.tables[self.TYPE].rows.values():
            ls_row = rowview.RowView(ls)
            uuid = self.store_info(ls_row)
            text = uuid
            network_name = ls._data['external_ids'].get('neutron:network_name')
            if network_name:
                text += ' (network: %s)' % network_name
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=text, tags=self.TYPE,
                values=str(ls_row.uuid))
            lsp_tt = LogicalSiwtchPorts(self._root_tree, self._ovn_nb,
                                        self._ovn_sb, parent_leaf=child_leaf,
                                        parent_uuid=uuid)
            lsp_tt.populate_subtree(uuids=[port.uuid for port in ls_row.ports])

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'name: %(name)s\n'
            'other_config: %(other_config)s\n'
            'external_ids: %(external_ids)s' %
            {'name': datum['name'], 'other_config': datum['other_config'],
             'external_ids': datum['external_ids']})

    def store_info(self, row):
        key = str(row.uuid)
        datum = {
            'name': row.name, 'other_config': row.other_config,
            'external_ids': row.external_ids}
        self._root_tree.add_leaf(self.TYPE, key, None, datum)
        return key


class LogicalSiwtchPorts(TreeType):

    TYPE = constants.LOGICAL_SWITCH_PORT

    def populate_subtree(self, uuids=None):
        for port_uuid in uuids:
            port = self._ovn_nb.tables[self.TYPE].rows.get(port_uuid)
            port_row = rowview.RowView(port)
            uuid = self.store_info(port_row)
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=uuid, tags=self.TYPE,
                values=uuid)
            qos_tt = QoSes(self._root_tree, self._ovn_nb, self._ovn_sb,
                           parent_leaf=child_leaf, parent_uuid=uuid)
            qos_tt.populate_subtree()

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'id: %(id)s  --  name: %(name)s\n'
            'device_id: %(device_id)s  -- type: %(type)s\n'
            'addresses: %(addresses)s  -- cidrs: %(cidrs)s\n'
            'ha_chassis_group: %(ha_chassis_group)s' %
            {'id': datum['name'], 'device_id': datum['device_id'],
             'name': datum['name'], 'addresses': datum['addresses'],
             'cidrs': datum['cidrs'], 'type': datum['type'],
             'ha_chassis_group': datum['ha_chassis_group']})

    def store_info(self, row):
        key = str(row.uuid)
        datum = {
            'device_id': row.external_ids.get('neutron:device_id'),
            'name': row.external_ids.get('neutron:port_name'),
            'addresses': row.addresses, 'id': row.name,
            'cidrs': row.external_ids.get('neutron:cidrs'),
            'ha_chassis_group': row.ha_chassis_group,
            'type': row.type}
        self._root_tree.add_leaf(self.TYPE, key, self._parent_uuid, datum)
        return key


class QoSes(TreeType):

    TYPE = constants.QOS
    EXTID_QOS_MAP = None  # External ID (port) <-> QoS ID map
    REGEX_ID = re.compile(r'(inport|outport) == '
                          r'[\"\'](?P<id>[0-9a-fA-F\-]+)[\"\']')

    def populate_subtree(self, uuids=None):
        for qos in self.extid_qos_map.get(self._parent_leaf, []):
            text = str(qos['uuid'])
            self._treeview.insert(
                self.own_leaf, 'end', text, text=text, tags=self.TYPE,
                values=text)

    @property
    def extid_qos_map(self):
        if self.__class__.EXTID_QOS_MAP is None:
            self.__class__.EXTID_QOS_MAP = collections.defaultdict(list)
            for qos in self._ovn_nb.tables[self.TYPE].rows.values():
                # TODO(ralonsoh): in "external_ids", add the FIP ID or the port
                #                 ID; that will speed up the search without
                #                 using regex.
                qos_row = rowview.RowView(qos)
                match = self.REGEX_ID.search(qos_row.match)
                if match:
                    qos_row = rowview.RowView(qos)
                    key = self.store_info(qos_row)
                    self.__class__.EXTID_QOS_MAP[match.group('id')].append(
                        self._root_tree.get_leaf(self.TYPE, key))

        return self.__class__.EXTID_QOS_MAP

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'action: %(action)s  --  priority: %(priority)s\n'
            'bandwidth: %(bandwidth)s  --  direction: %(direction)s\n'
            'match: %(match)s' %
            {'action': datum['action'], 'priority': datum['priority'],
             'bandwidth': datum['bandwidth'], 'direction': datum['direction'],
             'match': datum['match']})

    def store_info(self, row):
        key = str(row.uuid)
        datum = {
            'uuid': key, 'action': row.action, 'match': row.match,
            'bandwidth': row.bandwidth, 'priority': row.priority,
            'direction': row.direction, 'external_ids': row.external_ids}
        self._root_tree.add_leaf(self.TYPE, key, self._parent_uuid, datum)
        return key


class PortGroups(TreeType):

    TYPE = constants.PORT_GROUP

    def populate_subtree(self, uuids=None):
        self._child_trees = {}
        for pg in self._ovn_nb.tables[self.TYPE].rows.values():
            pg_row = rowview.RowView(pg)
            uuid = self.store_info(pg_row)
            text = uuid
            sg = pg._data['external_ids'].get('neutron:security_group_id')
            if sg:
                text += ' (Neutron SG: %s)' % sg
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=text, tags=self.TYPE,
                values=uuid)
            acl_tt = ACLs(
                self._root_tree, self._ovn_nb, self._ovn_sb,
                parent_leaf=child_leaf, parent_uuid=uuid)
            acl_tt.populate_subtree(uuids=[acls.uuid for acls in pg_row.acls])

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'name: %(name)s\n'
            'external_ids: %(external_ids)s' %
            {'name': datum['name'], 'external_ids': datum['external_ids']})\

    def store_info(self, row):
        key = str(row.uuid)
        datum = {'name': row.name,
                 'external_ids': row.external_ids}
        self._root_tree.add_leaf(self.TYPE, key, None, datum)
        return key


class ACLs(TreeType):

    TYPE = constants.ACL

    def populate_subtree(self, parent_leaf=None, uuids=None):
        for uuid in uuids:
            acl = self._ovn_nb.tables[self.TYPE].rows.get(uuid)
            acl_row = rowview.RowView(acl)
            key = self.store_info(acl_row)
            self._treeview.insert(
                self.own_leaf, 'end', key, text=key, tags=self.TYPE,
                values=key)

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'action: %(action)s  --  priority: %(priority)s\n'
            'meter: %(meter)s  --  direction: %(direction)s\n'
            'match: %(match)s\n'
            'severity: %(severity)s' %
            {'action': datum['action'], 'priority': datum['priority'],
             'meter': datum['meter'], 'direction': datum['direction'],
             'match': datum['match'], 'severity': datum['severity']})

    def store_info(self, row):
        key = str(row.uuid)
        datum = {
            'name': row.name, 'priority': row.priority,
            'direction': row.direction, 'external_ids': row.external_ids,
            'meter': row.meter, 'match': row.match, 'action': row.action,
            'severity': row.severity}
        self._root_tree.add_leaf(self.TYPE, key, self._parent_uuid, datum)
        return key
