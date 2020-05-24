#!/usr/bin/python

###############################################################################
# Install:
# apt install python3-tk
##




###############################################################################
import abc
from ovs import ovsuuid
from ovsdbapp.backend.ovs_idl import idlutils
from ovsdbapp.backend.ovs_idl import connection
from ovsdbapp.schema.ovn_northbound import impl_idl as nb_impl_idl
import tkinter
from tkinter import ttk


# OVN parameters
OVN_NB_CONNECTION = 'tcp:127.0.0.1:6641'
OVN_SB_CONNECTION = 'tcp:127.0.0.1:6642'
OVSDB_CONNECTION_TIMEOUT = 30

# OVN element types
LOGICAL_SWITCH = 'Logical_Switch'
LOGICAL_SWITCH_PORT = 'Logical_Switch_Port'
QOS = 'QaS'
ACL = 'ACL'
DHCP_OPTIONS = 'DHCP_Options'
GATEWAY_CHASSIS = 'Gateway_Chassis'


class OvnIdl(connection.OvsdbIdl):

    def __init__(self, connection_string, schema_name):
        helper = idlutils.get_schema_helper(connection_string, schema_name)
        helper.register_all()
        super(OvnIdl, self).__init__(connection_string, helper)

    def notify(self, event, row, updates=None):
        # NOTE(ralonsoh): do something when a register is update (refresh the
        # tree view)
        pass


class TreeType(object, metaclass=abc.ABCMeta):

    TYPE = None

    def __init__(self, treeview):
        self._treeview = treeview

    @abc.abstractmethod
    def populate_tree(self, parent_leaf=None, uuids=None):
        """Add elements to the tree leaves

        Each element will be populated in the treeview object and will contain:
        - "text": usually the UUID plus an extra short information
        - "tags": the OVN database type (see "OVN element types" constants)
        - "values": a list of variables but just with one element, the UUID
        """

    @abc.abstractmethod
    def print_info(self):
        """Print single element information in a string variable"""


class LogicalSiwtchPort(TreeType):

    TYPE = LOGICAL_SWITCH_PORT

    def populate_tree(self, parent_leaf=None, uuids=None):
        port_leaf = self._treeview.insert(parent_leaf, 'end', text=self.TYPE)
        for port_uuid in uuids:
            port = ovn_nb.tables[self.TYPE].rows.get(port_uuid)
            text = str(port.uuid)
            treeview.insert(port_leaf, 'end', str(port.uuid),
                            text=text, tags=self.TYPE, values=str(port.uuid))

        #ovn_nb.tables[self.TYPE].rows

    def print_info(self):
        pass

class LogicalSwitch(TreeType):

    TYPE = LOGICAL_SWITCH

    def populate_tree(self, parent_leaf=None, uuids=None):
        ls_leaf = self._treeview.insert('', '0', text=self.TYPE)
        for ls in ovn_nb.tables[self.TYPE].rows.values():
            text = str(ls.uuid)
            network_name = ls._data['external_ids'].get('neutron:network_name')
            if network_name:
                text += ' (network: %s)' % network_name
            leaf = treeview.insert(ls_leaf, 'end', str(ls.uuid),
                                   text=text, tags=self.TYPE,
                                   values=str(ls.uuid))
            lsp_tt = LogicalSiwtchPort(self._treeview)
            lsp_tt.populate_tree(leaf, [port.value for port in
                                        ls._data['ports'].values.keys()])

    def print_info(self):
        pass




_nb_idl = OvnIdl(OVN_NB_CONNECTION, 'OVN_Northbound')
_nb_conn = connection.Connection(_nb_idl, timeout=OVSDB_CONNECTION_TIMEOUT)
ovn_nb = nb_impl_idl.OvnNbApiIdlImpl(_nb_conn, start=True)
_sb_idl = OvnIdl(OVN_SB_CONNECTION, 'OVN_Southbound')
_sb_conn = connection.Connection(_sb_idl, timeout=OVSDB_CONNECTION_TIMEOUT)
ovn_sb = nb_impl_idl.OvnNbApiIdlImpl(_sb_conn, start=True)

# Creating app window
master_window = tkinter.Tk()
master_window.update()
master_window.minsize(800, 600)  # Full SVGA resolution, welcome to the future
master_window.title("GUI Application of Python")

# Master frame (the tree viewer and the StringVar box will container here)
master_frame = tkinter.Frame(master_window)
master_frame.grid(row=1, column=0, columnspan=5, padx=0, pady=0,
                   sticky=tkinter.E+tkinter.W+tkinter.N+tkinter.S)
master_frame.rowconfigure(0, weight=1)
master_frame.columnconfigure(0, weight=1)
master_frame.pack(expand=True, fill='both')


###############################################################################
#Creating treeview window
treeview = ttk.Treeview(master_frame)
# # Calling pack method on the treeview
treeview.pack(expand=True, fill='both')

###############################################################################
# Create text box
text_box = tkinter.StringVar()
label = tkinter.Label(master_frame, textvariable=text_box, height=6,
                      justify=tkinter.LEFT)
label.pack(side='left')
text_box.set('(no item selected)')

def print_on_text_box(text_box, datum, type):
    if type == LOGICAL_SWITCH:
        text_box.set('name: %(name)s\n'
                     'other_config: %(other_config)s\n'
                     'external_ids: %(external_ids)s' %
                     {'name': datum['name'],
                      'other_config': datum['other_config'],
                      'external_ids': datum['external_ids'],
                      })

    elif type == LOGICAL_SWITCH_PORT:
        text_box.set(
            'id: %(id)s  --  name: %(name)s\n'
            'device_id: %(device_id)s\n' 
            'addresses: %(addresses)s  -- cidrs: %(cidrs)s\n'
            'ha_chassis_group: %(ha_chassis_group)s\n'
            'type: %(type)s\n' %
            {'id': datum['name'],
             'device_id': datum['external_ids'].get('neutron:device_id'),
             'name': datum['external_ids'].get('neutron:port_name'),
             'addresses': datum['addresses'],
             'cidrs': datum['external_ids'].get('neutron:cidrs'),
             'ha_chassis_group': datum['ha_chassis_group'],
             'type': datum['type'],
             })


# LOGICAL_WITCH
ls_tt = LogicalSwitch(treeview)
ls_tt.populate_tree()


###treeview.focus(a)

###############################################################################
def on_select(event):
    selected = event.widget.selection()
    tree_item = treeview.item(selected)
    if not tree_item['tags']:
        return
    uuid = ovsuuid.from_string(tree_item['values'][0])
    ovs_item_type = tree_item['tags'][0]
    ovs_item = ovn_nb.tables[ovs_item_type].rows.get(uuid)
    print_on_text_box(text_box, ovs_item._data, ovs_item_type)

treeview.bind('<<TreeviewSelect>>', on_select)



# Calling main()
master_window.mainloop()
