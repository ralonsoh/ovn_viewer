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
    def store_info(self, row, leaf):
        """Store information for each element.

        That will push into the root tree DB the datum and the treeview leaf.
        """


class RootTree(object):

    # TODO(ralonsoh): add a sync decorator to leaf operations.
    # --> https://github.com/GrahamDumpleton/wrapt/tree/develop/blog

    def __init__(self, treeview):
        self._treeview = treeview
        self._ovn_nb = None
        self._ovn_sb = None
        self._db = {}
        self._tree = {}  # Main parents: LS and PG.
        self._tree_parents = {}

    def update_ovn_connections(self, ovn_nb, ovn_sb):
        self._ovn_nb = ovn_nb
        self._ovn_sb = ovn_sb

    def populate_subtree(self):
        if not self._ovn_sb or not self._ovn_sb:
            raise RuntimeError('OVN connections should be provided')
        ls_tt = LogicalSwitches(self, self._ovn_nb, self._ovn_sb)
        ls_tt.populate_subtree()
        pg_tt = PortGroups(self, self._ovn_nb, self._ovn_sb)
        pg_tt.populate_subtree()

    def get_leaf(self, item_type, uuid):
        try:
            return self._db[uuid]
        except KeyError:
            return

    def add_leaf(self, item_type, uuid, parent_uuid, datum, leaf):
        self._db[uuid] = (datum, leaf)
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
        self._tree_parents[uuid] = None

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
        self._tree_parents[uuid] = None

    def _add_leaf_acl(self, uuid, pg_uuid):
        if uuid in self._tree[pg_uuid]:
            return
        self._tree[pg_uuid][uuid] = True  # No child leafs.
        self._tree_parents[uuid] = pg_uuid

    def delete_leaf(self, row):
        uuid = str(row.uuid)

        # Remove from _treeview
        self._treeview.delete(uuid)

        # Delete from _tree
        parent = uuid
        branches = []
        while parent:
            parent = self._tree_parents[parent]
            if parent:
                branches.append(parent)

        element_branch = self._tree
        branches.reverse()
        for branch in branches:
            element_branch = element_branch[branch]

        trimmed_branch = element_branch.pop(uuid)

        # Delete from _tree_parents and _db
        self._tree_parents.pop(uuid)
        self._db.pop(uuid)

        def remove_from_tree_parents(trimmed_branch):
            if not isinstance(trimmed_branch, dict):
                return
            for key, value in trimmed_branch.items():
                self._tree_parents.pop(key)
                self._db.pop(key)
                remove_from_tree_parents(value)

        remove_from_tree_parents(trimmed_branch)

    @property
    def treeview(self):
        return self._treeview

    def print_on_text_box(self, text_box, item_type, uuid):
        try:
            info, _ = self._db[item_type][uuid]
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
            uuid = str(ls_row.uuid)
            text = uuid
            network_name = ls._data['external_ids'].get('neutron:network_name')
            if network_name:
                text += ' (network: %s)' % network_name
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=text, tags=self.TYPE,
                values=str(ls_row.uuid))
            self.store_info(ls_row, child_leaf)
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

    def store_info(self, row, child_leaf):
        key = str(row.uuid)
        datum = {
            'name': row.name, 'other_config': row.other_config,
            'external_ids': row.external_ids}
        self._root_tree.add_leaf(self.TYPE, key, None, datum, child_leaf)
        return key


class LogicalSiwtchPorts(TreeType):

    TYPE = constants.LOGICAL_SWITCH_PORT

    def populate_subtree(self, uuids=None):
        for port_uuid in uuids:
            port = self._ovn_nb.tables[self.TYPE].rows.get(port_uuid)
            port_row = rowview.RowView(port)
            uuid = str(port_row.uuid)
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=uuid, tags=self.TYPE,
                values=uuid)
            self.store_info(port_row, child_leaf)
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

    def store_info(self, row, leaf):
        key = str(row.uuid)
        datum = {
            'device_id': row.external_ids.get('neutron:device_id'),
            'name': row.external_ids.get('neutron:port_name'),
            'addresses': row.addresses, 'id': row.name,
            'cidrs': row.external_ids.get('neutron:cidrs'),
            'ha_chassis_group': row.ha_chassis_group,
            'type': row.type}
        self._root_tree.add_leaf(self.TYPE, key, self._parent_uuid, datum,
                                 leaf)
        return key


class QoSes(TreeType):

    TYPE = constants.QOS
    REGEX_ID = re.compile(r'(inport|outport) == '
                          r'[\"\'](?P<id>[0-9a-fA-F\-]+)[\"\']')

    def populate_subtree(self, uuids=None):
        for qos_row in self.extid_qos_map(self._parent_uuid):
            text = str(qos_row.uuid)
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', text, text=text, tags=self.TYPE,
                values=text)
            self.store_info(qos_row, child_leaf)

    def extid_qos_map(self, port_uuid):
        for qos in self._ovn_nb.tables[self.TYPE].rows.values():
            # TODO(ralonsoh): in "external_ids", add the FIP ID or the port
            #                 ID; that will speed up the search without
            #                 using regex.
            qos_row = rowview.RowView(qos)
            match = self.REGEX_ID.search(qos_row.match)
            if match:
                if port_uuid == match.group('id'):
                    yield rowview.RowView(qos)

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'action: %(action)s  --  priority: %(priority)s\n'
            'bandwidth: %(bandwidth)s  --  direction: %(direction)s\n'
            'match: %(match)s' %
            {'action': datum['action'], 'priority': datum['priority'],
             'bandwidth': datum['bandwidth'], 'direction': datum['direction'],
             'match': datum['match']})

    def store_info(self, row, leaf):
        key = str(row.uuid)
        datum = {
            'uuid': key, 'action': row.action, 'match': row.match,
            'bandwidth': row.bandwidth, 'priority': row.priority,
            'direction': row.direction, 'external_ids': row.external_ids}
        self._root_tree.add_leaf(self.TYPE, key, self._parent_uuid, datum,
                                 leaf)
        return key


class PortGroups(TreeType):

    TYPE = constants.PORT_GROUP

    def populate_subtree(self, uuids=None):
        for pg in self._ovn_nb.tables[self.TYPE].rows.values():
            pg_row = rowview.RowView(pg)
            uuid = str(pg_row.uuid)
            text = uuid
            sg = pg._data['external_ids'].get('neutron:security_group_id')
            if sg:
                text += ' (Neutron SG: %s)' % sg
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=text, tags=self.TYPE,
                values=uuid)
            self.store_info(pg_row, child_leaf)
            acl_tt = ACLs(
                self._root_tree, self._ovn_nb, self._ovn_sb,
                parent_leaf=child_leaf, parent_uuid=uuid)
            acl_tt.populate_subtree(uuids=[acls.uuid for acls in pg_row.acls])

    @staticmethod
    def print_info(text_box, datum):
        text_box.set(
            'name: %(name)s\n'
            'external_ids: %(external_ids)s' %
            {'name': datum['name'], 'external_ids': datum['external_ids']})

    def store_info(self, row, leaf):
        key = str(row.uuid)
        datum = {'name': row.name,
                 'external_ids': row.external_ids}
        self._root_tree.add_leaf(self.TYPE, key, None, datum, leaf)
        return key


class ACLs(TreeType):

    TYPE = constants.ACL

    def populate_subtree(self, parent_leaf=None, uuids=None):
        for uuid in uuids:
            acl = self._ovn_nb.tables[self.TYPE].rows.get(uuid)
            acl_row = rowview.RowView(acl)
            uuid = str(acl_row.uuid)
            child_leaf = self._treeview.insert(
                self.own_leaf, 'end', uuid, text=uuid, tags=self.TYPE,
                values=uuid)
            self.store_info(acl_row, child_leaf)

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

    def store_info(self, row, leaf):
        key = str(row.uuid)
        datum = {
            'name': row.name, 'priority': row.priority,
            'direction': row.direction, 'external_ids': row.external_ids,
            'meter': row.meter, 'match': row.match, 'action': row.action,
            'severity': row.severity}
        self._root_tree.add_leaf(self.TYPE, key, self._parent_uuid, datum,
                                 leaf)
        return key
